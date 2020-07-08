import os
import socket
from typing import TYPE_CHECKING, List, Tuple

import netaddr
from lxml import etree

from core import utils
from core.emane.nodes import EmaneNet
from core.executables import IP
from core.nodes.base import CoreNodeBase, NodeBase

if TYPE_CHECKING:
    from core.emulator.session import Session


def add_type(parent_element: etree.Element, name: str) -> None:
    type_element = etree.SubElement(parent_element, "type")
    type_element.text = name


def add_address(
    parent_element: etree.Element,
    address_type: str,
    address: str,
    iface_name: str = None,
) -> None:
    address_element = etree.SubElement(parent_element, "address", type=address_type)
    address_element.text = address
    if iface_name is not None:
        address_element.set("iface", iface_name)


def add_mapping(parent_element: etree.Element, maptype: str, mapref: str) -> None:
    etree.SubElement(parent_element, "mapping", type=maptype, ref=mapref)


def add_emane_iface(
    host_element: etree.Element,
    nem_id: int,
    platform_name: str = "p1",
    transport_name: str = "t1",
) -> etree.Element:
    host_id = host_element.get("id")

    # platform data
    platform_id = f"{host_id}/{platform_name}"
    platform_element = etree.SubElement(
        host_element, "emanePlatform", id=platform_id, name=platform_name
    )

    # transport data
    transport_id = f"{host_id}/{transport_name}"
    etree.SubElement(
        platform_element, "transport", id=transport_id, name=transport_name
    )

    # nem data
    nem_name = f"nem{nem_id}"
    nem_element_id = f"{host_id}/{nem_name}"
    nem_element = etree.SubElement(
        platform_element, "nem", id=nem_element_id, name=nem_name
    )
    nem_id_element = etree.SubElement(nem_element, "parameter", name="nemid")
    nem_id_element.text = str(nem_id)

    return platform_element


def get_address_type(address: str) -> str:
    addr, _slash, _prefixlen = address.partition("/")
    if netaddr.valid_ipv4(addr):
        address_type = "IPv4"
    elif netaddr.valid_ipv6(addr):
        address_type = "IPv6"
    else:
        raise NotImplementedError
    return address_type


def get_ipv4_addresses(hostname: str) -> List[Tuple[str, str]]:
    if hostname == "localhost":
        addresses = []
        args = f"{IP} -o -f inet address show"
        output = utils.cmd(args)
        for line in output.split(os.linesep):
            split = line.split()
            if not split:
                continue
            iface_name = split[1]
            address = split[3]
            if not address.startswith("127."):
                addresses.append((iface_name, address))
        return addresses
    else:
        # TODO: handle other hosts
        raise NotImplementedError


class CoreXmlDeployment:
    def __init__(self, session: "Session", scenario: etree.Element) -> None:
        self.session: "Session" = session
        self.scenario: etree.Element = scenario
        self.root: etree.SubElement = etree.SubElement(
            scenario, "container", id="TestBed", name="TestBed"
        )
        self.add_deployment()

    def find_device(self, name: str) -> etree.Element:
        device = self.scenario.find(f"devices/device[@name='{name}']")
        return device

    def find_iface(self, device: NodeBase, name: str) -> etree.Element:
        iface = self.scenario.find(
            f"devices/device[@name='{device.name}']/interfaces/interface[@name='{name}']"
        )
        return iface

    def add_deployment(self) -> None:
        physical_host = self.add_physical_host(socket.gethostname())

        for node_id in self.session.nodes:
            node = self.session.nodes[node_id]
            if isinstance(node, CoreNodeBase):
                self.add_virtual_host(physical_host, node)

    def add_physical_host(self, name: str) -> etree.Element:
        # add host
        root_id = self.root.get("id")
        host_id = f"{root_id}/{name}"
        host_element = etree.SubElement(self.root, "testHost", id=host_id, name=name)

        # add type element
        add_type(host_element, "physical")

        # add ipv4 addresses
        for iface_name, address in get_ipv4_addresses("localhost"):
            add_address(host_element, "IPv4", address, iface_name)

        return host_element

    def add_virtual_host(self, physical_host: etree.Element, node: NodeBase) -> None:
        if not isinstance(node, CoreNodeBase):
            raise TypeError(f"invalid node type: {node}")

        # create virtual host element
        phys_id = physical_host.get("id")
        host_id = f"{phys_id}/{node.name}"
        host_element = etree.SubElement(
            physical_host, "testHost", id=host_id, name=node.name
        )

        # add host type
        add_type(host_element, "virtual")

        for iface in node.get_ifaces():
            emane_element = None
            if isinstance(iface.net, EmaneNet):
                nem_id = self.session.emane.get_nem_id(iface)
                emane_element = add_emane_iface(host_element, nem_id)

            parent_element = host_element
            if emane_element is not None:
                parent_element = emane_element

            for ip in iface.ips():
                address = str(ip.ip)
                address_type = get_address_type(address)
                add_address(parent_element, address_type, address, iface.name)
