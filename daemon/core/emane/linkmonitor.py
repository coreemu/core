import logging
import sched
import threading
import time
from typing import TYPE_CHECKING, Dict, List, Tuple

import emane.shell as emanesh
import netaddr
from lxml import etree

from core.emulator.data import LinkData
from core.emulator.enumerations import LinkTypes, MessageFlags
from core.nodes.network import CtrlNet

if TYPE_CHECKING:
    from core.emane.emanemanager import EmaneManager

DEFAULT_PORT = 47_000
MAC_COMPONENT_INDEX = 1
EMANE_RFPIPE = "rfpipemaclayer"
EMANE_80211 = "ieee80211abgmaclayer"
EMANE_TDMA = "tdmaeventschedulerradiomodel"
SINR_TABLE = "NeighborStatusTable"
NEM_SELF = 65535


class LossTable:
    def __init__(self, losses: Dict[float, float]) -> None:
        self.losses = losses
        self.sinrs = sorted(self.losses.keys())
        self.loss_lookup = {}
        for index, value in enumerate(self.sinrs):
            self.loss_lookup[index] = self.losses[value]
        self.mac_id = None

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
        self.from_nem = from_nem
        self.to_nem = to_nem
        self.sinr = sinr
        self.last_seen = None
        self.touch()

    def update(self, sinr: float) -> None:
        self.sinr = sinr
        self.touch()

    def touch(self) -> None:
        self.last_seen = time.monotonic()

    def is_dead(self, timeout: int) -> bool:
        return (time.monotonic() - self.last_seen) >= timeout

    def __repr__(self) -> str:
        return f"EmaneLink({self.from_nem}, {self.to_nem}, {self.sinr})"


class EmaneClient:
    def __init__(self, address: str) -> None:
        self.address = address
        self.client = emanesh.ControlPortClient(self.address, DEFAULT_PORT)
        self.nems = {}
        self.setup()

    def setup(self) -> None:
        manifest = self.client.getManifest()
        for nem_id, components in manifest.items():
            # get mac config
            mac_id, _, emane_model = components[MAC_COMPONENT_INDEX]
            mac_config = self.client.getConfiguration(mac_id)
            logging.debug(
                "address(%s) nem(%s) emane(%s)", self.address, nem_id, emane_model
            )

            # create loss table based on current configuration
            if emane_model == EMANE_80211:
                loss_table = self.handle_80211(mac_config)
            elif emane_model == EMANE_RFPIPE:
                loss_table = self.handle_rfpipe(mac_config)
            else:
                logging.warning("unknown emane link model: %s", emane_model)
                continue
            loss_table.mac_id = mac_id
            self.nems[nem_id] = loss_table

    def check_links(
        self, links: Dict[Tuple[int, int], EmaneLink], loss_threshold: int
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

    def handle_tdma(self, config: Dict[str, Tuple]):
        pcr = config["pcrcurveuri"][0][0]
        logging.debug("tdma pcr: %s", pcr)

    def handle_80211(self, config: Dict[str, Tuple]) -> LossTable:
        unicastrate = config["unicastrate"][0][0]
        pcr = config["pcrcurveuri"][0][0]
        logging.debug("80211 pcr: %s", pcr)
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

    def handle_rfpipe(self, config: Dict[str, Tuple]) -> LossTable:
        pcr = config["pcrcurveuri"][0][0]
        logging.debug("rfpipe pcr: %s", pcr)
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
        self.emane_manager = emane_manager
        self.clients = []
        self.links = {}
        self.complete_links = set()
        self.loss_threshold = None
        self.link_interval = None
        self.link_timeout = None
        self.scheduler = None
        self.running = False

    def start(self) -> None:
        self.loss_threshold = int(self.emane_manager.get_config("loss_threshold"))
        self.link_interval = int(self.emane_manager.get_config("link_interval"))
        self.link_timeout = int(self.emane_manager.get_config("link_timeout"))
        self.initialize()
        self.scheduler = sched.scheduler()
        self.scheduler.enter(0, 0, self.check_links)
        self.running = True
        thread = threading.Thread(target=self.scheduler.run, daemon=True)
        thread.start()

    def initialize(self) -> None:
        addresses = self.get_addresses()
        for address in addresses:
            client = EmaneClient(address)
            self.clients.append(client)

    def get_addresses(self) -> List[str]:
        addresses = []
        nodes = self.emane_manager.getnodes()
        for node in nodes:
            logging.info("link monitor node: %s", node.name)
            for netif in node.netifs():
                if isinstance(netif.net, CtrlNet):
                    ip4 = None
                    for x in netif.addrlist:
                        address, prefix = x.split("/")
                        if netaddr.valid_ipv4(address):
                            ip4 = address
                    if ip4:
                        addresses.append(ip4)
                    break
        return addresses

    def check_links(self) -> None:
        # check for new links
        previous_links = set(self.links.keys())
        for client in self.clients:
            try:
                client.check_links(self.links, self.loss_threshold)
            except emanesh.ControlPortException:
                if self.running:
                    logging.exception("link monitor error")

        # find new links
        current_links = set(self.links.keys())
        new_links = current_links - previous_links

        # find dead links
        dead_links = []
        for link_id, link in self.links.items():
            if link.is_dead(self.link_timeout):
                dead_links.append(link_id)

        # announce dead links
        for link_id in dead_links:
            del self.links[link_id]
            complete_id = self.get_complete_id(link_id)
            if complete_id in self.complete_links:
                self.complete_links.remove(complete_id)
                self.send_link(MessageFlags.DELETE, complete_id)

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

    def get_complete_id(self, link_id: Tuple[int, int]) -> Tuple[int, int]:
        value_one, value_two = link_id
        if value_one < value_two:
            return value_one, value_two
        else:
            return value_two, value_one

    def is_complete_link(self, link_id: Tuple[int, int]) -> bool:
        reverse_id = link_id[1], link_id[0]
        return link_id in self.links and reverse_id in self.links

    def send_link(self, message_type: MessageFlags, link_id: Tuple[int, int]) -> None:
        nem_one, nem_two = link_id
        emane_one, netif = self.emane_manager.nemlookup(nem_one)
        if not emane_one or not netif:
            logging.error("invalid nem: %s", nem_one)
            return
        node_one = netif.node
        emane_two, netif = self.emane_manager.nemlookup(nem_two)
        if not emane_two or not netif:
            logging.error("invalid nem: %s", nem_two)
            return
        node_two = netif.node
        logging.debug(
            "%s emane link from %s(%s) to %s(%s)",
            message_type.name,
            node_one.name,
            nem_one,
            node_two.name,
            nem_two,
        )
        self.send_message(message_type, node_one.id, node_two.id, emane_one.id)

    def send_message(self, message_type, node_one, node_two, emane_id) -> None:
        link_data = LinkData(
            message_type=message_type,
            node1_id=node_one,
            node2_id=node_two,
            network_id=emane_id,
            link_type=LinkTypes.WIRELESS,
        )
        self.emane_manager.session.broadcast_link(link_data)

    def stop(self) -> None:
        self.running = False
        for client in self.clients:
            client.stop()
        self.clients.clear()
        self.links.clear()
        self.complete_links.clear()
