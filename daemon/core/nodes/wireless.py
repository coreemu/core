"""
Defines a wireless node that allows programmatic link connectivity and
configuration between pairs of nodes.
"""
import copy
import logging
import math
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config import ConfigBool, ConfigFloat, ConfigInt, Configuration
from core.emulator.data import LinkData, LinkOptions
from core.emulator.enumerations import LinkTypes, MessageFlags
from core.errors import CoreError
from core.executables import NFTABLES
from core.nodes.base import CoreNetworkBase, NodeOptions
from core.nodes.interface import CoreInterface

if TYPE_CHECKING:
    from core.emulator.session import Session
    from core.emulator.distributed import DistributedServer

logger = logging.getLogger(__name__)
CONFIG_ENABLED: bool = True
CONFIG_RANGE: float = 400.0
CONFIG_LOSS_RANGE: float = 300.0
CONFIG_LOSS_FACTOR: float = 1.0
CONFIG_LOSS: float = 0.0
CONFIG_DELAY: int = 5000
CONFIG_BANDWIDTH: int = 54_000_000
CONFIG_JITTER: int = 0
KEY_ENABLED: str = "movement"
KEY_RANGE: str = "max-range"
KEY_BANDWIDTH: str = "bandwidth"
KEY_DELAY: str = "delay"
KEY_JITTER: str = "jitter"
KEY_LOSS_RANGE: str = "loss-range"
KEY_LOSS_FACTOR: str = "loss-factor"
KEY_LOSS: str = "loss"


def calc_distance(
    point1: tuple[float, float, float], point2: tuple[float, float, float]
) -> float:
    a = point1[0] - point2[0]
    b = point1[1] - point2[1]
    c = 0
    if point1[2] is not None and point2[2] is not None:
        c = point1[2] - point2[2]
    return math.hypot(math.hypot(a, b), c)


def get_key(node1_id: int, node2_id: int) -> tuple[int, int]:
    return (node1_id, node2_id) if node1_id < node2_id else (node2_id, node1_id)


@dataclass
class WirelessLink:
    bridge1: str
    bridge2: str
    iface: CoreInterface
    linked: bool
    label: str = None


class WirelessNode(CoreNetworkBase):
    options: list[Configuration] = [
        ConfigBool(
            id=KEY_ENABLED, default="1" if CONFIG_ENABLED else "0", label="Enabled?"
        ),
        ConfigFloat(
            id=KEY_RANGE, default=str(CONFIG_RANGE), label="Max Range (pixels)"
        ),
        ConfigInt(
            id=KEY_BANDWIDTH, default=str(CONFIG_BANDWIDTH), label="Bandwidth (bps)"
        ),
        ConfigInt(id=KEY_DELAY, default=str(CONFIG_DELAY), label="Delay (usec)"),
        ConfigInt(id=KEY_JITTER, default=str(CONFIG_JITTER), label="Jitter (usec)"),
        ConfigFloat(
            id=KEY_LOSS_RANGE,
            default=str(CONFIG_LOSS_RANGE),
            label="Loss Start Range (pixels)",
        ),
        ConfigFloat(
            id=KEY_LOSS_FACTOR, default=str(CONFIG_LOSS_FACTOR), label="Loss Factor"
        ),
        ConfigFloat(id=KEY_LOSS, default=str(CONFIG_LOSS), label="Loss Initial"),
    ]
    devices: set[str] = set()

    @classmethod
    def add_device(cls) -> str:
        while True:
            name = f"we{secrets.token_hex(6)}"
            if name not in cls.devices:
                cls.devices.add(name)
                break
        return name

    @classmethod
    def delete_device(cls, name: str) -> None:
        cls.devices.discard(name)

    def __init__(
        self,
        session: "Session",
        _id: int,
        name: str,
        server: "DistributedServer" = None,
        options: NodeOptions = None,
    ):
        super().__init__(session, _id, name, server, options)
        self.bridges: dict[int, tuple[CoreInterface, str]] = {}
        self.links: dict[tuple[int, int], WirelessLink] = {}
        self.position_enabled: bool = CONFIG_ENABLED
        self.bandwidth: int = CONFIG_BANDWIDTH
        self.delay: int = CONFIG_DELAY
        self.jitter: int = CONFIG_JITTER
        self.max_range: float = CONFIG_RANGE
        self.loss_initial: float = CONFIG_LOSS
        self.loss_range: float = CONFIG_LOSS_RANGE
        self.loss_factor: float = CONFIG_LOSS_FACTOR

    def startup(self) -> None:
        if self.up:
            return
        self.up = True

    def shutdown(self) -> None:
        while self.bridges:
            _, (_, bridge_name) = self.bridges.popitem()
            self.net_client.delete_bridge(bridge_name)
            self.host_cmd(f"{NFTABLES} delete table bridge {bridge_name}")
        while self.links:
            _, link = self.links.popitem()
            link.iface.shutdown()
        self.up = False

    def attach(self, iface: CoreInterface) -> None:
        super().attach(iface)
        logging.info("attaching node(%s) iface(%s)", iface.node.name, iface.name)
        if self.up:
            # create node unique bridge
            bridge_name = f"wb{iface.node.id}.{self.id}.{self.session.id}"
            self.net_client.create_bridge(bridge_name)
            # setup initial bridge rules
            self.host_cmd(f'{NFTABLES} "add table bridge {bridge_name}"')
            self.host_cmd(
                f"{NFTABLES} "
                f"'add chain bridge {bridge_name} forward {{type filter hook "
                f"forward priority -1; policy drop;}}'"
            )
            self.host_cmd(
                f"{NFTABLES} "
                f"'add rule bridge {bridge_name} forward "
                f"ibriport != {bridge_name} accept'"
            )
            # associate node iface with bridge
            iface.net_client.set_iface_master(bridge_name, iface.localname)
            # assign position callback, when enabled
            if self.position_enabled:
                iface.poshook = self.position_callback
            # save created bridge
            self.bridges[iface.node.id] = (iface, bridge_name)

    def post_startup(self) -> None:
        routes = {}
        for node_id, (iface, bridge_name) in self.bridges.items():
            for onode_id, (oiface, obridge_name) in self.bridges.items():
                if node_id == onode_id:
                    continue
                if node_id < onode_id:
                    node1, node2 = iface.node, oiface.node
                    bridge1, bridge2 = bridge_name, obridge_name
                else:
                    node1, node2 = oiface.node, iface.node
                    bridge1, bridge2 = obridge_name, bridge_name
                key = (node1.id, node2.id)
                if key in self.links:
                    continue
                # create node to node link
                name1 = self.add_device()
                name2 = self.add_device()
                link_iface = CoreInterface(0, name1, name2, self.session.use_ovs())
                link_iface.startup()
                link = WirelessLink(bridge1, bridge2, link_iface, False)
                self.links[key] = link
                # track bridge routes
                node1_routes = routes.setdefault(node1.id, set())
                node1_routes.add(name1)
                node2_routes = routes.setdefault(node2.id, set())
                node2_routes.add(name2)
                if self.position_enabled:
                    link.linked = True
                    # assign ifaces to respective bridges
                    self.net_client.set_iface_master(bridge1, link_iface.name)
                    self.net_client.set_iface_master(bridge2, link_iface.localname)
                    # calculate link data
                    self.calc_link(iface, oiface)
        for node_id, ifaces in routes.items():
            iface, bridge_name = self.bridges[node_id]
            ifaces = ",".join(ifaces)
            # out routes
            self.host_cmd(
                f"{NFTABLES} "
                f'"add rule bridge {bridge_name} forward '
                f"iif {iface.localname} oif {{{ifaces}}} "
                f'accept"'
            )
            # in routes
            self.host_cmd(
                f"{NFTABLES} "
                f'"add rule bridge {bridge_name} forward '
                f"iif {{{ifaces}}} oif {iface.localname} "
                f'accept"'
            )

    def link_control(self, node1_id: int, node2_id: int, linked: bool) -> None:
        key = get_key(node1_id, node2_id)
        link = self.links.get(key)
        if not link:
            raise CoreError(f"invalid node links node1({node1_id}) node2({node2_id})")
        bridge1, bridge2 = link.bridge1, link.bridge2
        iface = link.iface
        if not link.linked and linked:
            link.linked = True
            self.net_client.set_iface_master(bridge1, iface.name)
            self.net_client.set_iface_master(bridge2, iface.localname)
            self.send_link(key[0], key[1], MessageFlags.ADD, link.label)
        elif link.linked and not linked:
            link.linked = False
            self.net_client.delete_iface(bridge1, iface.name)
            self.net_client.delete_iface(bridge2, iface.localname)
            self.send_link(key[0], key[1], MessageFlags.DELETE, link.label)

    def link_config(
        self, node1_id: int, node2_id: int, options1: LinkOptions, options2: LinkOptions
    ) -> None:
        key = get_key(node1_id, node2_id)
        link = self.links.get(key)
        if not link:
            raise CoreError(f"invalid node links node1({node1_id}) node2({node2_id})")
        iface = link.iface
        has_netem = iface.has_netem
        iface.options.update(options1)
        iface.set_config()
        name, localname = iface.name, iface.localname
        iface.name, iface.localname = localname, name
        iface.options.update(options2)
        iface.has_netem = has_netem
        iface.set_config()
        iface.name, iface.localname = name, localname
        if options1 == options2:
            link.label = f"{options1.loss:.2f}%/{options1.delay}us"
        else:
            link.label = (
                f"({options1.loss:.2f}%/{options1.delay}us) "
                f"({options2.loss:.2f}%/{options2.delay}us)"
            )
        self.send_link(key[0], key[1], MessageFlags.NONE, link.label)

    def send_link(
        self,
        node1_id: int,
        node2_id: int,
        message_type: MessageFlags,
        label: str = None,
    ) -> None:
        """
        Broadcasts out a wireless link/unlink message.

        :param node1_id: first node in link
        :param node2_id: second node in link
        :param message_type: type of link message to send
        :param label: label to display for link
        :return: nothing
        """
        color = self.session.get_link_color(self.id)
        link_data = LinkData(
            message_type=message_type,
            type=LinkTypes.WIRELESS,
            node1_id=node1_id,
            node2_id=node2_id,
            network_id=self.id,
            color=color,
            label=label,
        )
        self.session.broadcast_link(link_data)

    def position_callback(self, iface: CoreInterface) -> None:
        for oiface, bridge_name in self.bridges.values():
            if iface == oiface:
                continue
            self.calc_link(iface, oiface)

    def calc_link(self, iface1: CoreInterface, iface2: CoreInterface) -> None:
        key = get_key(iface1.node.id, iface2.node.id)
        link = self.links.get(key)
        point1 = iface1.node.position.get()
        point2 = iface2.node.position.get()
        distance = calc_distance(point1, point2)
        if distance >= self.max_range:
            if link.linked:
                self.link_control(iface1.node.id, iface2.node.id, False)
        else:
            if not link.linked:
                self.link_control(iface1.node.id, iface2.node.id, True)
            loss_distance = max(distance - self.loss_range, 0.0)
            max_distance = max(self.max_range - self.loss_range, 0.0)
            loss = min((loss_distance / max_distance) * 100.0 * self.loss_factor, 100.0)
            loss = max(self.loss_initial, loss)
            options = LinkOptions(
                loss=loss,
                delay=self.delay,
                bandwidth=self.bandwidth,
                jitter=self.jitter,
            )
            self.link_config(iface1.node.id, iface2.node.id, options, options)

    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        raise CoreError(f"{type(self)} does not support adopt interface")

    def get_config(self) -> dict[str, Configuration]:
        config = {x.id: x for x in copy.copy(self.options)}
        config[KEY_ENABLED].default = "1" if self.position_enabled else "0"
        config[KEY_RANGE].default = str(self.max_range)
        config[KEY_LOSS_RANGE].default = str(self.loss_range)
        config[KEY_LOSS_FACTOR].default = str(self.loss_factor)
        config[KEY_LOSS].default = str(self.loss_initial)
        config[KEY_BANDWIDTH].default = str(self.bandwidth)
        config[KEY_DELAY].default = str(self.delay)
        config[KEY_JITTER].default = str(self.jitter)
        return config

    def set_config(self, config: dict[str, str]) -> None:
        logger.info("wireless config: %s", config)
        self.position_enabled = config[KEY_ENABLED] == "1"
        self.max_range = float(config[KEY_RANGE])
        self.loss_range = float(config[KEY_LOSS_RANGE])
        self.loss_factor = float(config[KEY_LOSS_FACTOR])
        self.loss_initial = float(config[KEY_LOSS])
        self.bandwidth = int(config[KEY_BANDWIDTH])
        self.delay = int(config[KEY_DELAY])
        self.jitter = int(config[KEY_JITTER])
