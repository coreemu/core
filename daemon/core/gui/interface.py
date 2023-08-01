import logging
from typing import TYPE_CHECKING, Any, Optional

import netaddr
from netaddr import EUI, IPNetwork

from core.api.grpc.wrappers import Interface, Link, LinkType, Node
from core.gui import nodeutils as nutils
from core.gui.graph.edges import CanvasEdge
from core.gui.graph.node import CanvasNode

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application

IP4_MASK: int = 24
IP6_MASK: int = 64
WIRELESS_IP4_MASK: int = 32
WIRELESS_IP6_MASK: int = 128


def get_index(iface: Interface) -> Optional[int]:
    if not iface.ip4:
        return None
    net = netaddr.IPNetwork(f"{iface.ip4}/{iface.ip4_mask}")
    ip_value = net.value
    cidr_value = net.cidr.value
    return ip_value - cidr_value


class Subnets:
    def __init__(self, ip4: IPNetwork, ip6: IPNetwork) -> None:
        self.ip4 = ip4
        self.ip6 = ip6
        self.used_indexes = set()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Subnets):
            return False
        return self.key() == other.key()

    def __hash__(self) -> int:
        return hash(self.key())

    def key(self) -> tuple[IPNetwork, IPNetwork]:
        return self.ip4, self.ip6

    def next(self) -> "Subnets":
        return Subnets(self.ip4.next(), self.ip6.next())


class InterfaceManager:
    def __init__(self, app: "Application") -> None:
        self.app: "Application" = app
        ip4 = self.app.guiconfig.ips.ip4
        ip6 = self.app.guiconfig.ips.ip6
        self.ip4_subnets: IPNetwork = IPNetwork(f"{ip4}/{IP4_MASK}")
        self.ip6_subnets: IPNetwork = IPNetwork(f"{ip6}/{IP6_MASK}")
        mac = self.app.guiconfig.mac
        self.mac: EUI = EUI(mac, dialect=netaddr.mac_unix_expanded)
        self.current_mac: Optional[EUI] = None
        self.current_subnets: Optional[Subnets] = None
        self.used_subnets: dict[tuple[IPNetwork, IPNetwork], Subnets] = {}
        self.used_macs: set[str] = set()

    def update_ips(self, ip4: str, ip6: str) -> None:
        self.reset()
        self.ip4_subnets = IPNetwork(f"{ip4}/{IP4_MASK}")
        self.ip6_subnets = IPNetwork(f"{ip6}/{IP6_MASK}")

    def next_mac(self) -> str:
        while str(self.current_mac) in self.used_macs:
            value = self.current_mac.value + 1
            self.current_mac = EUI(value, dialect=netaddr.mac_unix_expanded)
        mac = str(self.current_mac)
        value = self.current_mac.value + 1
        self.current_mac = EUI(value, dialect=netaddr.mac_unix_expanded)
        return mac

    def next_subnets(self) -> Subnets:
        subnets = self.current_subnets
        if subnets is None:
            subnets = Subnets(self.ip4_subnets, self.ip6_subnets)
        while subnets.key() in self.used_subnets:
            subnets = subnets.next()
        self.used_subnets[subnets.key()] = subnets
        return subnets

    def reset(self) -> None:
        self.current_subnets = None
        self.used_subnets.clear()

    def removed(self, links: list[Link]) -> None:
        # get remaining subnets
        remaining_subnets = set()
        for edge in self.app.core.links.values():
            link = edge.link
            if link.iface1:
                subnets = self.get_subnets(link.iface1)
                remaining_subnets.add(subnets)
            if link.iface2:
                subnets = self.get_subnets(link.iface2)
                remaining_subnets.add(subnets)

        # remove all subnets from used subnets when no longer present
        # or remove used indexes from subnet
        ifaces = []
        for link in links:
            if link.iface1:
                ifaces.append(link.iface1)
            if link.iface2:
                ifaces.append(link.iface2)
        for iface in ifaces:
            subnets = self.get_subnets(iface)
            if subnets not in remaining_subnets:
                self.used_subnets.pop(subnets.key(), None)
            else:
                index = get_index(iface)
                if index is not None:
                    subnets.used_indexes.discard(index)
        self.current_subnets = None

    def set_macs(self, links: list[Link]) -> None:
        self.current_mac = self.mac
        self.used_macs.clear()
        for link in links:
            if link.iface1:
                self.used_macs.add(link.iface1.mac)
            if link.iface2:
                self.used_macs.add(link.iface2.mac)

    def joined(self, links: list[Link]) -> None:
        ifaces = []
        for link in links:
            if link.iface1:
                ifaces.append(link.iface1)
            if link.iface2:
                ifaces.append(link.iface2)

        # add to used subnets and mark used indexes
        for iface in ifaces:
            subnets = self.get_subnets(iface)
            index = get_index(iface)
            if index is None:
                continue
            subnets.used_indexes.add(index)
            if subnets.key() not in self.used_subnets:
                self.used_subnets[subnets.key()] = subnets

    def next_index(self, node: Node) -> int:
        if nutils.is_router(node):
            index = 1
        else:
            index = 20
        while True:
            if index not in self.current_subnets.used_indexes:
                self.current_subnets.used_indexes.add(index)
                break
            index += 1
        return index

    def get_ips(self, node: Node) -> [Optional[str], Optional[str]]:
        enable_ip4 = self.app.guiconfig.ips.enable_ip4
        enable_ip6 = self.app.guiconfig.ips.enable_ip6
        ip4, ip6 = None, None
        if not enable_ip4 and not enable_ip6:
            return ip4, ip6
        index = self.next_index(node)
        if enable_ip4:
            ip4 = str(self.current_subnets.ip4[index])
        if enable_ip6:
            ip6 = str(self.current_subnets.ip6[index])
        return ip4, ip6

    def get_subnets(self, iface: Interface) -> Subnets:
        ip4_subnet = self.ip4_subnets
        if iface.ip4:
            ip4_subnet = IPNetwork(f"{iface.ip4}/{IP4_MASK}").cidr
        ip6_subnet = self.ip6_subnets
        if iface.ip6:
            ip6_subnet = IPNetwork(f"{iface.ip6}/{IP6_MASK}").cidr
        subnets = Subnets(ip4_subnet, ip6_subnet)
        return self.used_subnets.get(subnets.key(), subnets)

    def determine_subnets(
        self, canvas_src_node: CanvasNode, canvas_dst_node: CanvasNode
    ) -> None:
        src_node = canvas_src_node.core_node
        dst_node = canvas_dst_node.core_node
        is_src_container = nutils.is_container(src_node)
        is_dst_container = nutils.is_container(dst_node)
        if is_src_container and is_dst_container:
            self.current_subnets = self.next_subnets()
        elif is_src_container and not is_dst_container:
            subnets = self.find_subnets(canvas_dst_node, visited={src_node.id})
            if subnets:
                self.current_subnets = subnets
            else:
                self.current_subnets = self.next_subnets()
        elif not is_src_container and is_dst_container:
            subnets = self.find_subnets(canvas_src_node, visited={dst_node.id})
            if subnets:
                self.current_subnets = subnets
            else:
                self.current_subnets = self.next_subnets()
        else:
            logger.info("ignoring subnet change for link between network nodes")

    def find_subnets(
        self, canvas_node: CanvasNode, visited: set[int] = None
    ) -> Optional[IPNetwork]:
        logger.info("finding subnet for node: %s", canvas_node.core_node.name)
        subnets = None
        if not visited:
            visited = set()
        visited.add(canvas_node.core_node.id)
        for edge in canvas_node.edges:
            iface = edge.link.iface1
            check_node = edge.src
            if edge.src == canvas_node:
                iface = edge.link.iface2
                check_node = edge.dst
            if check_node.core_node.id in visited:
                continue
            visited.add(check_node.core_node.id)
            if iface:
                subnets = self.get_subnets(iface)
            else:
                subnets = self.find_subnets(check_node, visited)
            if subnets:
                logger.info("found subnets: %s", subnets)
                break
        return subnets

    def create_link(self, edge: CanvasEdge) -> Link:
        """
        Create core link for a given edge based on src/dst nodes.
        """
        src_node = edge.src.core_node
        dst_node = edge.dst.core_node
        self.determine_subnets(edge.src, edge.dst)
        src_iface = None
        if nutils.is_iface_node(src_node):
            src_iface = self.create_iface(edge.src, edge.linked_wireless)
        dst_iface = None
        if nutils.is_iface_node(dst_node):
            dst_iface = self.create_iface(edge.dst, edge.linked_wireless)
        link = Link(
            type=LinkType.WIRED,
            node1_id=src_node.id,
            node2_id=dst_node.id,
            iface1=src_iface,
            iface2=dst_iface,
        )
        logger.info("added link between %s and %s", src_node.name, dst_node.name)
        return link

    def create_iface(self, canvas_node: CanvasNode, wireless_link: bool) -> Interface:
        node = canvas_node.core_node
        if nutils.is_bridge(node):
            iface_id = canvas_node.next_iface_id()
            iface = Interface(id=iface_id)
        else:
            ip4, ip6 = self.get_ips(node)
            if wireless_link:
                ip4_mask = WIRELESS_IP4_MASK
                ip6_mask = WIRELESS_IP6_MASK
            else:
                ip4_mask = IP4_MASK
                ip6_mask = IP6_MASK
            iface_id = canvas_node.next_iface_id()
            name = f"eth{iface_id}"
            iface = Interface(
                id=iface_id,
                name=name,
                ip4=ip4,
                ip4_mask=ip4_mask,
                ip6=ip6,
                ip6_mask=ip6_mask,
            )
        logger.info("create node(%s) interface(%s)", node.name, iface)
        return iface
