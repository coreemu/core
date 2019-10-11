import os
import socket

from lxml import etree

from core import utils
from core.constants import IP_BIN
from core.emane.nodes import EmaneNet
from core.nodes import ipaddress
from core.nodes.base import CoreNodeBase


def add_type(parent_element, name):
    type_element = etree.SubElement(parent_element, "type")
    type_element.text = name


def add_address(parent_element, address_type, address, interface_name=None):
    address_element = etree.SubElement(parent_element, "address", type=address_type)
    address_element.text = address
    if interface_name is not None:
        address_element.set("iface", interface_name)


def add_mapping(parent_element, maptype, mapref):
    etree.SubElement(parent_element, "mapping", type=maptype, ref=mapref)


def add_emane_interface(host_element, netif, platform_name="p1", transport_name="t1"):
    nem_id = netif.net.nemidmap[netif]
    host_id = host_element.get("id")

    # platform data
    platform_id = "%s/%s" % (host_id, platform_name)
    platform_element = etree.SubElement(
        host_element, "emanePlatform", id=platform_id, name=platform_name
    )

    # transport data
    transport_id = "%s/%s" % (host_id, transport_name)
    etree.SubElement(
        platform_element, "transport", id=transport_id, name=transport_name
    )

    # nem data
    nem_name = "nem%s" % nem_id
    nem_element_id = "%s/%s" % (host_id, nem_name)
    nem_element = etree.SubElement(
        platform_element, "nem", id=nem_element_id, name=nem_name
    )
    nem_id_element = etree.SubElement(nem_element, "parameter", name="nemid")
    nem_id_element.text = str(nem_id)

    return platform_element


def get_address_type(address):
    addr, _slash, _prefixlen = address.partition("/")
    if ipaddress.is_ipv4_address(addr):
        address_type = "IPv4"
    elif ipaddress.is_ipv6_address(addr):
        address_type = "IPv6"
    else:
        raise NotImplementedError
    return address_type


def get_ipv4_addresses(hostname):
    if hostname == "localhost":
        addresses = []
        args = "%s -o -f inet address show" % IP_BIN
        output = utils.check_cmd(args)
        for line in output.split(os.linesep):
            split = line.split()
            if not split:
                continue
            interface_name = split[1]
            address = split[3]
            if not address.startswith("127."):
                addresses.append((interface_name, address))
        return addresses
    else:
        # TODO: handle other hosts
        raise NotImplementedError


class CoreXmlDeployment(object):
    def __init__(self, session, scenario):
        self.session = session
        self.scenario = scenario
        self.root = etree.SubElement(
            scenario, "container", id="TestBed", name="TestBed"
        )
        self.add_deployment()

    def find_device(self, name):
        device = self.scenario.find("devices/device[@name='%s']" % name)
        return device

    def find_interface(self, device, name):
        interface = self.scenario.find(
            "devices/device[@name='%s']/interfaces/interface[@name='%s']"
            % (device.name, name)
        )
        return interface

    def add_deployment(self):
        physical_host = self.add_physical_host(socket.gethostname())

        # TODO: handle other servers
        #   servers = self.session.broker.getservernames()
        #   servers.remove("localhost")

        for node_id in self.session.nodes:
            node = self.session.nodes[node_id]
            if isinstance(node, CoreNodeBase):
                self.add_virtual_host(physical_host, node)

    def add_physical_host(self, name):
        # add host
        host_id = "%s/%s" % (self.root.get("id"), name)
        host_element = etree.SubElement(self.root, "testHost", id=host_id, name=name)

        # add type element
        add_type(host_element, "physical")

        # add ipv4 addresses
        for interface_name, address in get_ipv4_addresses("localhost"):
            add_address(host_element, "IPv4", address, interface_name)

        return host_element

    def add_virtual_host(self, physical_host, node):
        if not isinstance(node, CoreNodeBase):
            raise TypeError("invalid node type: %s" % node)

        # create virtual host element
        host_id = "%s/%s" % (physical_host.get("id"), node.name)
        host_element = etree.SubElement(
            physical_host, "testHost", id=host_id, name=node.name
        )

        # add host type
        add_type(host_element, "virtual")

        for netif in node.netifs():
            emane_element = None
            if isinstance(netif.net, EmaneNet):
                emane_element = add_emane_interface(host_element, netif)

            parent_element = host_element
            if emane_element is not None:
                parent_element = emane_element

            for address in netif.addrlist:
                address_type = get_address_type(address)
                add_address(parent_element, address_type, address, netif.name)
