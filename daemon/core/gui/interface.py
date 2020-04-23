import logging
import random
from typing import TYPE_CHECKING, Set, Union

import netaddr
from netaddr import EUI, IPNetwork

from core.gui import appconfig
from core.gui.nodeutils import NodeUtils

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.api.grpc import core_pb2
    from core.gui.graph.node import CanvasNode


def random_mac():
    return ("{:02x}" * 6).format(*[random.randrange(256) for _ in range(6)])


class Subnets:
    def __init__(self, ip4: IPNetwork, ip6: IPNetwork) -> None:
        self.ip4 = ip4
        self.ip6 = ip6

    def __eq__(self, other: "Subnets") -> bool:
        return (self.ip4, self.ip6) == (other.ip4, other.ip6)

    def __hash__(self) -> int:
        return hash((self.ip4, self.ip6))

    def next(self) -> "Subnets":
        return Subnets(self.ip4.next(), self.ip6.next())


class InterfaceManager:
    def __init__(self, app: "Application") -> None:
        self.app = app
        ip_config = self.app.guiconfig.get("ips", {})
        ip4 = ip_config.get("ip4", appconfig.DEFAULT_IP4)
        ip6 = ip_config.get("ip6", appconfig.DEFAULT_IP6)
        self.ip4_mask = 24
        self.ip6_mask = 64
        self.ip4_subnets = IPNetwork(f"{ip4}/{self.ip4_mask}")
        self.ip6_subnets = IPNetwork(f"{ip6}/{self.ip6_mask}")
        mac = self.app.guiconfig.get("mac", appconfig.DEFAULT_MAC)
        self.mac = EUI(mac)
        self.current_mac = None
        self.current_subnets = None

    def update_ips(self, ip4: str, ip6: str) -> None:
        self.reset()
        self.ip4_subnets = IPNetwork(f"{ip4}/{self.ip4_mask}")
        self.ip6_subnets = IPNetwork(f"{ip6}/{self.ip6_mask}")

    def reset_mac(self) -> None:
        self.current_mac = self.mac
        self.current_mac.dialect = netaddr.mac_unix_expanded

    def next_mac(self) -> str:
        mac = str(self.current_mac)
        value = self.current_mac.value + 1
        self.current_mac = EUI(value)
        self.current_mac.dialect = netaddr.mac_unix_expanded
        return mac

    def next_subnets(self) -> Subnets:
        # define currently used subnets
        used_subnets = set()
        for edge in self.app.core.links.values():
            link = edge.link
            subnets = None
            if link.HasField("interface_one"):
                subnets = self.get_subnets(link.interface_one)
            if link.HasField("interface_two"):
                subnets = self.get_subnets(link.interface_two)
            if subnets:
                used_subnets.add(subnets)

        # find next available subnets
        subnets = Subnets(self.ip4_subnets, self.ip6_subnets)
        while subnets in used_subnets:
            subnets = subnets.next()
        return subnets

    def reset(self):
        self.current_subnets = None

    def get_ips(self, node_id: int) -> [str, str]:
        ip4 = self.current_subnets.ip4[node_id]
        ip6 = self.current_subnets.ip6[node_id]
        return str(ip4), str(ip6)

    @classmethod
    def get_subnets(cls, interface: "core_pb2.Interface") -> Subnets:
        ip4_subnet = IPNetwork(f"{interface.ip4}/{interface.ip4mask}").cidr
        ip6_subnet = IPNetwork(f"{interface.ip6}/{interface.ip6mask}").cidr
        return Subnets(ip4_subnet, ip6_subnet)

    def determine_subnets(
        self, canvas_src_node: "CanvasNode", canvas_dst_node: "CanvasNode"
    ):
        src_node = canvas_src_node.core_node
        dst_node = canvas_dst_node.core_node
        is_src_container = NodeUtils.is_container_node(src_node.type)
        is_dst_container = NodeUtils.is_container_node(dst_node.type)
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
            logging.info("ignoring subnet change for link between network nodes")

    def find_subnets(
        self, canvas_node: "CanvasNode", visited: Set[int] = None
    ) -> Union[IPNetwork, None]:
        logging.info("finding subnet for node: %s", canvas_node.core_node.name)
        canvas = self.app.canvas
        subnets = None
        if not visited:
            visited = set()
        visited.add(canvas_node.core_node.id)
        for edge in canvas_node.edges:
            src_node = canvas.nodes[edge.src]
            dst_node = canvas.nodes[edge.dst]
            interface = edge.src_interface
            check_node = src_node
            if src_node == canvas_node:
                interface = edge.dst_interface
                check_node = dst_node
            if check_node.core_node.id in visited:
                continue
            visited.add(check_node.core_node.id)
            if interface:
                subnets = self.get_subnets(interface)
            else:
                subnets = self.find_subnets(check_node, visited)
            if subnets:
                logging.info("found subnets: %s", subnets)
                break
        return subnets
