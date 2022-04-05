"""
Defines a wireless node that allows programmatic link connectivity and
configuration between pairs of nodes.
"""

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Tuple

from core.emulator.data import LinkData, LinkOptions
from core.emulator.enumerations import LinkTypes, MessageFlags
from core.errors import CoreError
from core.executables import NFTABLES
from core.nodes.base import CoreNetworkBase
from core.nodes.interface import CoreInterface

if TYPE_CHECKING:
    from core.emulator.session import Session
    from core.emulator.distributed import DistributedServer

logger = logging.getLogger(__name__)


def calc_distance(
    point1: Tuple[float, float, float], point2: Tuple[float, float, float]
) -> float:
    a = point1[0] - point2[0]
    b = point1[1] - point2[1]
    c = 0
    if point1[2] is not None and point2[2] is not None:
        c = point1[2] - point2[2]
    return math.hypot(math.hypot(a, b), c)


def get_key(node1_id: int, node2_id: int) -> Tuple[int, int]:
    return (node1_id, node2_id) if node1_id < node2_id else (node2_id, node1_id)


@dataclass
class WirelessLink:
    bridge1: str
    bridge2: str
    iface: CoreInterface
    linked: bool
    label: str = None


class WirelessNode(CoreNetworkBase):
    def __init__(
        self,
        session: "Session",
        _id: int,
        name: str,
        server: "DistributedServer" = None,
    ):
        super().__init__(session, _id, name, server)
        self.bridges: Dict[int, Tuple[CoreInterface, str]] = {}
        self.links: Dict[Tuple[int, int], WirelessLink] = {}

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
            # assign position callback
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
                session_id = self.session.short_session_id()
                name1 = f"we{self.id}.{node1.id}.{node2.id}.{session_id}"
                name2 = f"we{self.id}.{node2.id}.{node1.id}.{session_id}"
                link_iface = CoreInterface(0, name1, name2, self.session.use_ovs())
                link_iface.startup()
                link = WirelessLink(bridge1, bridge2, link_iface, True)
                self.links[key] = link
                # assign ifaces to respective bridges
                self.net_client.set_iface_master(bridge1, link_iface.name)
                self.net_client.set_iface_master(bridge2, link_iface.localname)
                # track bridge routes
                node1_routes = routes.setdefault(node1.id, set())
                node1_routes.add(name1)
                node2_routes = routes.setdefault(node2.id, set())
                node2_routes.add(name2)
                # send link
                self.send_link(node1.id, node2.id, MessageFlags.ADD)
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
        point1 = iface1.node.position.get()
        point2 = iface2.node.position.get()
        distance = calc_distance(point1, point2) - 250
        distance = max(distance, 0.0)
        loss = min((distance / 500) * 100.0, 100.0)
        node1_id = iface1.node.id
        node2_id = iface2.node.id
        options = LinkOptions(loss=loss, delay=0)
        self.link_config(node1_id, node2_id, options, options)

    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        raise CoreError(f"{type(self)} does not support adopt interface")
