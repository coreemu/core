import logging
import random

from netaddr import IPNetwork

from core.gui.nodeutils import NodeUtils


def random_mac():
    return ("{:02x}" * 6).format(*[random.randrange(256) for _ in range(6)])


class InterfaceManager:
    def __init__(self, app, address="10.0.0.0", mask=24):
        self.app = app
        self.mask = mask
        self.base_prefix = max(self.mask - 8, 0)
        self.subnets = IPNetwork(f"{address}/{self.base_prefix}")
        self.current_subnet = None

    def next_subnet(self):
        # define currently used subnets
        used_subnets = set()
        for edge in self.app.core.links.values():
            link = edge.link
            if link.HasField("interface_one"):
                subnet = self.get_subnet(link.interface_one)
                used_subnets.add(subnet)
            if link.HasField("interface_two"):
                subnet = self.get_subnet(link.interface_two)
                used_subnets.add(subnet)

        # find next available subnet
        for i in self.subnets.subnet(self.mask):
            if i not in used_subnets:
                return i

    def reset(self):
        self.current_subnet = None

    def get_ips(self, node_id):
        ip4 = self.current_subnet[node_id]
        ip6 = ip4.ipv6()
        prefix = self.current_subnet.prefixlen
        return str(ip4), str(ip6), prefix

    @classmethod
    def get_subnet(cls, interface):
        return IPNetwork(f"{interface.ip4}/{interface.ip4mask}").cidr

    def determine_subnet(self, canvas_src_node, canvas_dst_node):
        src_node = canvas_src_node.core_node
        dst_node = canvas_dst_node.core_node
        is_src_container = NodeUtils.is_container_node(src_node.type)
        is_dst_container = NodeUtils.is_container_node(dst_node.type)
        if is_src_container and is_dst_container:
            self.current_subnet = self.next_subnet()
        elif is_src_container and not is_dst_container:
            subnet = self.find_subnet(canvas_dst_node, visited={src_node.id})
            if subnet:
                self.current_subnet = subnet
            else:
                self.current_subnet = self.next_subnet()
        elif not is_src_container and is_dst_container:
            subnet = self.find_subnet(canvas_src_node, visited={dst_node.id})
            if subnet:
                self.current_subnet = subnet
            else:
                self.current_subnet = self.next_subnet()
        else:
            logging.info("ignoring subnet change for link between network nodes")

    def find_subnet(self, canvas_node, visited=None):
        logging.info("finding subnet for node: %s", canvas_node.core_node.name)
        canvas = self.app.canvas
        cidr = None
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
                cidr = self.get_subnet(interface)
            else:
                cidr = self.find_subnet(check_node, visited)
            if cidr:
                logging.info("found subnet: %s", cidr)
                break
        return cidr
