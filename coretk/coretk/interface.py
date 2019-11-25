import logging
import random

from netaddr import IPNetwork

from coretk.nodeutils import NodeUtils


def random_mac():
    return ("{:02x}" * 6).format(*[random.randrange(256) for _ in range(6)])


class InterfaceManager:
    def __init__(self, app, cidr="10.0.0.0/24"):
        self.app = app
        self.default = cidr
        self.cidr = IPNetwork(cidr)
        self.deleted = []
        self.current = None

    def reset(self):
        self.cidr = IPNetwork(self.default)
        self.deleted.clear()
        self.current = None

    def get_ips(self, node_id):
        ip4 = self.current[node_id]
        ip6 = ip4.ipv6()
        return str(ip4), str(ip6), self.current.prefixlen

    def next_subnet(self):
        if self.deleted:
            return self.deleted.pop(0)
        else:
            if self.current:
                self.cidr = self.cidr.next()
            return self.cidr

    def deleted_cidr(self, cidr):
        logging.info("deleted cidr: %s", cidr)
        if cidr not in self.deleted:
            self.deleted.append(cidr)
            self.deleted.sort()

    @classmethod
    def get_cidr(cls, interface):
        return IPNetwork(f"{interface.ip4}/{interface.ip4mask}").cidr

    def determine_subnet(self, canvas_src_node, canvas_dst_node):
        src_node = canvas_src_node.core_node
        dst_node = canvas_dst_node.core_node
        is_src_container = NodeUtils.is_container_node(src_node.type)
        is_dst_container = NodeUtils.is_container_node(dst_node.type)
        if is_src_container and is_dst_container:
            self.current = self.next_subnet()
        elif is_src_container and not is_dst_container:
            cidr = self.find_subnet(canvas_dst_node, visited={src_node.id})
            if cidr:
                self.current = cidr
            else:
                self.current = self.next_subnet()
        elif not is_src_container and is_dst_container:
            cidr = self.find_subnet(canvas_src_node, visited={dst_node.id})
            if cidr:
                self.current = cidr
            else:
                self.current = self.next_subnet()
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
                cidr = self.get_cidr(interface)
            else:
                cidr = self.find_subnet(check_node, visited)
            if cidr:
                logging.info("found subnet: %s", cidr)
                break
        return cidr
