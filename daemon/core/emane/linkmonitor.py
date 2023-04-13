import logging
import sched
import threading
import time
from typing import TYPE_CHECKING, Optional

from lxml import etree

from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData
from core.emulator.enumerations import LinkTypes, MessageFlags
from core.nodes.network import CtrlNet

logger = logging.getLogger(__name__)

try:
    from emane import shell
except ImportError:
    try:
        from emanesh import shell
    except ImportError:
        shell = None
        logger.debug("compatible emane python bindings not installed")

if TYPE_CHECKING:
    from core.emane.emanemanager import EmaneManager

MAC_COMPONENT_INDEX: int = 1
EMANE_RFPIPE: str = "rfpipemaclayer"
EMANE_80211: str = "ieee80211abgmaclayer"
EMANE_TDMA: str = "tdmaeventschedulerradiomodel"
SINR_TABLE: str = "NeighborStatusTable"
NEM_SELF: int = 65535


class LossTable:
    def __init__(self, losses: dict[float, float]) -> None:
        self.losses: dict[float, float] = losses
        self.sinrs: list[float] = sorted(self.losses.keys())
        self.loss_lookup: dict[int, float] = {}
        for index, value in enumerate(self.sinrs):
            self.loss_lookup[index] = self.losses[value]
        self.mac_id: Optional[str] = None

    def get_loss(self, sinr: float) -> float:
        index = self._get_index(sinr)
        loss = 100.0 - self.loss_lookup[index]
        return loss

    def _get_index(self, current_sinr: float) -> int:
        for index, sinr in enumerate(self.sinrs):
            if current_sinr <= sinr:
                return index
        return len(self.sinrs) - 1


class EmaneLink:
    def __init__(self, from_nem: int, to_nem: int, sinr: float) -> None:
        self.from_nem: int = from_nem
        self.to_nem: int = to_nem
        self.sinr: float = sinr
        self.last_seen: Optional[float] = None
        self.updated: bool = False
        self.touch()

    def update(self, sinr: float) -> None:
        self.updated = self.sinr != sinr
        self.sinr = sinr
        self.touch()

    def touch(self) -> None:
        self.last_seen = time.monotonic()

    def is_dead(self, timeout: int) -> bool:
        return (time.monotonic() - self.last_seen) >= timeout

    def __repr__(self) -> str:
        return f"EmaneLink({self.from_nem}, {self.to_nem}, {self.sinr})"


class EmaneClient:
    def __init__(self, address: str, port: int) -> None:
        self.address: str = address
        self.client: shell.ControlPortClient = shell.ControlPortClient(
            self.address, port
        )
        self.nems: dict[int, LossTable] = {}
        self.setup()

    def setup(self) -> None:
        manifest = self.client.getManifest()
        for nem_id, components in manifest.items():
            # get mac config
            mac_id, _, emane_model = components[MAC_COMPONENT_INDEX]
            mac_config = self.client.getConfiguration(mac_id)
            logger.debug(
                "address(%s) nem(%s) emane(%s)", self.address, nem_id, emane_model
            )

            # create loss table based on current configuration
            if emane_model == EMANE_80211:
                loss_table = self.handle_80211(mac_config)
            elif emane_model == EMANE_RFPIPE:
                loss_table = self.handle_rfpipe(mac_config)
            else:
                logger.warning("unknown emane link model: %s", emane_model)
                continue
            logger.info("monitoring links nem(%s) model(%s)", nem_id, emane_model)
            loss_table.mac_id = mac_id
            self.nems[nem_id] = loss_table

    def check_links(
        self, links: dict[tuple[int, int], EmaneLink], loss_threshold: int
    ) -> None:
        for from_nem, loss_table in self.nems.items():
            tables = self.client.getStatisticTable(loss_table.mac_id, (SINR_TABLE,))
            table = tables[SINR_TABLE][1:][0]
            for row in table:
                row = row
                to_nem = row[0][0]
                sinr = row[5][0]
                age = row[-1][0]

                # exclude invalid links
                is_self = to_nem == NEM_SELF
                has_valid_age = 0 <= age <= 1
                if is_self or not has_valid_age:
                    continue

                # check if valid link loss
                link_key = (from_nem, to_nem)
                loss = loss_table.get_loss(sinr)
                if loss < loss_threshold:
                    link = links.get(link_key)
                    if link:
                        link.update(sinr)
                    else:
                        link = EmaneLink(from_nem, to_nem, sinr)
                        links[link_key] = link

    def handle_tdma(self, config: dict[str, tuple]):
        pcr = config["pcrcurveuri"][0][0]
        logger.debug("tdma pcr: %s", pcr)

    def handle_80211(self, config: dict[str, tuple]) -> LossTable:
        unicastrate = config["unicastrate"][0][0]
        pcr = config["pcrcurveuri"][0][0]
        logger.debug("80211 pcr: %s", pcr)
        tree = etree.parse(pcr)
        root = tree.getroot()
        table = root.find("table")
        losses = {}
        for rate in table.iter("datarate"):
            index = int(rate.get("index"))
            if index == unicastrate:
                for row in rate.iter("row"):
                    sinr = float(row.get("sinr"))
                    por = float(row.get("por"))
                    losses[sinr] = por
        return LossTable(losses)

    def handle_rfpipe(self, config: dict[str, tuple]) -> LossTable:
        pcr = config["pcrcurveuri"][0][0]
        logger.debug("rfpipe pcr: %s", pcr)
        tree = etree.parse(pcr)
        root = tree.getroot()
        table = root.find("table")
        losses = {}
        for row in table.iter("row"):
            sinr = float(row.get("sinr"))
            por = float(row.get("por"))
            losses[sinr] = por
        return LossTable(losses)

    def stop(self) -> None:
        self.client.stop()


class EmaneLinkMonitor:
    def __init__(self, emane_manager: "EmaneManager") -> None:
        self.emane_manager: "EmaneManager" = emane_manager
        self.clients: list[EmaneClient] = []
        self.links: dict[tuple[int, int], EmaneLink] = {}
        self.complete_links: set[tuple[int, int]] = set()
        self.loss_threshold: Optional[int] = None
        self.link_interval: Optional[int] = None
        self.link_timeout: Optional[int] = None
        self.scheduler: Optional[sched.scheduler] = None
        self.running: bool = False

    def start(self) -> None:
        options = self.emane_manager.session.options
        self.loss_threshold = options.get_int("loss_threshold")
        self.link_interval = options.get_int("link_interval")
        self.link_timeout = options.get_int("link_timeout")
        self.initialize()
        if not self.clients:
            logger.info("no valid emane models to monitor links")
            return
        self.scheduler = sched.scheduler()
        self.scheduler.enter(0, 0, self.check_links)
        self.running = True
        thread = threading.Thread(target=self.scheduler.run, daemon=True)
        thread.start()

    def initialize(self) -> None:
        addresses = self.get_addresses()
        for address, port in addresses:
            client = EmaneClient(address, port)
            if client.nems:
                self.clients.append(client)

    def get_addresses(self) -> list[tuple[str, int]]:
        addresses = []
        nodes = self.emane_manager.getnodes()
        for node in nodes:
            control = None
            ports = []
            for iface in node.get_ifaces():
                if isinstance(iface.net, CtrlNet):
                    ip4 = iface.get_ip4()
                    if ip4:
                        control = str(ip4.ip)
                if isinstance(iface.net, EmaneNet):
                    port = self.emane_manager.get_nem_port(iface)
                    ports.append(port)
            if control:
                for port in ports:
                    addresses.append((control, port))
        return addresses

    def check_links(self) -> None:
        # check for new links
        previous_links = set(self.links.keys())
        for client in self.clients:
            try:
                client.check_links(self.links, self.loss_threshold)
            except shell.ControlPortException:
                if self.running:
                    logger.exception("link monitor error")

        # find new links
        current_links = set(self.links.keys())
        new_links = current_links - previous_links

        # find updated and dead links
        dead_links = []
        for link_id, link in self.links.items():
            complete_id = self.get_complete_id(link_id)
            if link.is_dead(self.link_timeout):
                dead_links.append(link_id)
            elif link.updated and complete_id in self.complete_links:
                link.updated = False
                self.send_link(MessageFlags.NONE, complete_id)

        # announce dead links
        for link_id in dead_links:
            complete_id = self.get_complete_id(link_id)
            if complete_id in self.complete_links:
                self.complete_links.remove(complete_id)
                self.send_link(MessageFlags.DELETE, complete_id)
            del self.links[link_id]

        # announce new links
        for link_id in new_links:
            complete_id = self.get_complete_id(link_id)
            if complete_id in self.complete_links:
                continue
            if self.is_complete_link(link_id):
                self.complete_links.add(complete_id)
                self.send_link(MessageFlags.ADD, complete_id)

        if self.running:
            self.scheduler.enter(self.link_interval, 0, self.check_links)

    def get_complete_id(self, link_id: tuple[int, int]) -> tuple[int, int]:
        value1, value2 = link_id
        if value1 < value2:
            return value1, value2
        else:
            return value2, value1

    def is_complete_link(self, link_id: tuple[int, int]) -> bool:
        reverse_id = link_id[1], link_id[0]
        return link_id in self.links and reverse_id in self.links

    def get_link_label(self, link_id: tuple[int, int]) -> str:
        source_id = tuple(sorted(link_id))
        source_link = self.links[source_id]
        dest_id = link_id[::-1]
        dest_link = self.links[dest_id]
        return f"{source_link.sinr:.1f} / {dest_link.sinr:.1f}"

    def send_link(self, message_type: MessageFlags, link_id: tuple[int, int]) -> None:
        nem1, nem2 = link_id
        link = self.emane_manager.get_nem_link(nem1, nem2, message_type)
        if link:
            label = self.get_link_label(link_id)
            link.label = label
            self.emane_manager.session.broadcast_link(link)

    def send_message(
        self,
        message_type: MessageFlags,
        label: str,
        node1: int,
        node2: int,
        emane_id: int,
    ) -> None:
        color = self.emane_manager.session.get_link_color(emane_id)
        link_data = LinkData(
            message_type=message_type,
            type=LinkTypes.WIRELESS,
            label=label,
            node1_id=node1,
            node2_id=node2,
            network_id=emane_id,
            color=color,
        )
        self.emane_manager.session.broadcast_link(link_data)

    def stop(self) -> None:
        self.running = False
        for client in self.clients:
            client.stop()
        self.clients.clear()
        self.links.clear()
        self.complete_links.clear()
