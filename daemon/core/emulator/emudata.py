from typing import List, Optional

import netaddr

from core import utils
from core.api.grpc.core_pb2 import LinkOptions
from core.emane.nodes import EmaneNet
from core.emulator.enumerations import LinkTypes
from core.nodes.base import CoreNetworkBase, CoreNode
from core.nodes.interface import CoreInterface
from core.nodes.physical import PhysicalNode


class IdGen:
    def __init__(self, _id: int = 0) -> None:
        self.id = _id

    def next(self) -> int:
        self.id += 1
        return self.id


def link_config(
    network: CoreNetworkBase,
    interface: CoreInterface,
    link_options: LinkOptions,
    devname: str = None,
    interface_two: CoreInterface = None,
) -> None:
    """
    Convenience method for configuring a link,

    :param network: network to configure link for
    :param interface: interface to configure
    :param link_options: data to configure link with
    :param devname: device name, default is None
    :param interface_two: other interface associated, default is None
    :return: nothing
    """
    config = {
        "netif": interface,
        "bw": link_options.bandwidth,
        "delay": link_options.delay,
        "loss": link_options.per,
        "duplicate": link_options.dup,
        "jitter": link_options.jitter,
        "netif2": interface_two,
    }

    # hacky check here, because physical and emane nodes do not conform to the same
    # linkconfig interface
    if not isinstance(network, (EmaneNet, PhysicalNode)):
        config["devname"] = devname

    network.linkconfig(**config)


class NodeOptions:
    """
    Options for creating and updating nodes within core.
    """

    def __init__(self, name: str = None, model: str = "PC", image: str = None) -> None:
        """
        Create a NodeOptions object.

        :param name: name of node, defaults to node class name postfix with its id
        :param model: defines services for default and physical nodes, defaults to
            "router"
        :param image: image to use for docker nodes
        """
        self.name = name
        self.model = model
        self.canvas = None
        self.icon = None
        self.opaque = None
        self.services = None
        self.config_services = []
        self.x = None
        self.y = None
        self.lat = None
        self.lon = None
        self.alt = None
        self.emulation_id = None
        self.server = None
        self.image = image
        self.emane = None

    def set_position(self, x: float, y: float) -> None:
        """
        Convenience method for setting position.

        :param x: x position
        :param y: y position
        :return: nothing
        """
        self.x = x
        self.y = y

    def set_location(self, lat: float, lon: float, alt: float) -> None:
        """
        Convenience method for setting location.

        :param lat: latitude
        :param lon: longitude
        :param alt: altitude
        :return: nothing
        """
        self.lat = lat
        self.lon = lon
        self.alt = alt


class LinkOptions:
    """
    Options for creating and updating links within core.
    """

    def __init__(self, _type: LinkTypes = LinkTypes.WIRED) -> None:
        """
        Create a LinkOptions object.

        :param _type: type of link, defaults to
            wired
        """
        self.type = _type
        self.session = None
        self.delay = None
        self.bandwidth = None
        self.per = None
        self.dup = None
        self.jitter = None
        self.mer = None
        self.burst = None
        self.mburst = None
        self.gui_attributes = None
        self.unidirectional = None
        self.emulation_id = None
        self.network_id = None
        self.key = None
        self.opaque = None


class InterfaceData:
    """
    Convenience class for storing interface data.
    """

    def __init__(
        self,
        _id: int,
        name: str,
        mac: str,
        ip4: str,
        ip4_mask: int,
        ip6: str,
        ip6_mask: int,
    ) -> None:
        """
        Creates an InterfaceData object.

        :param _id: interface id
        :param name: name for interface
        :param mac: mac address
        :param ip4: ipv4 address
        :param ip4_mask: ipv4 bit mask
        :param ip6: ipv6 address
        :param ip6_mask: ipv6 bit mask
        """
        self.id = _id
        self.name = name
        self.mac = mac
        self.ip4 = ip4
        self.ip4_mask = ip4_mask
        self.ip6 = ip6
        self.ip6_mask = ip6_mask

    def has_ip4(self) -> bool:
        """
        Determines if interface has an ip4 address.

        :return: True if has ip4, False otherwise
        """
        return all([self.ip4, self.ip4_mask])

    def has_ip6(self) -> bool:
        """
        Determines if interface has an ip6 address.

        :return: True if has ip6, False otherwise
        """
        return all([self.ip6, self.ip6_mask])

    def ip4_address(self) -> Optional[str]:
        """
        Retrieve a string representation of the ip4 address and netmask.

        :return: ip4 string or None
        """
        if self.has_ip4():
            return f"{self.ip4}/{self.ip4_mask}"
        else:
            return None

    def ip6_address(self) -> Optional[str]:
        """
        Retrieve a string representation of the ip6 address and netmask.

        :return: ip4 string or None
        """
        if self.has_ip6():
            return f"{self.ip6}/{self.ip6_mask}"
        else:
            return None

    def get_addresses(self) -> List[str]:
        """
        Returns a list of ip4 and ip6 address when present.

        :return: list of addresses
        """
        ip4 = self.ip4_address()
        ip6 = self.ip6_address()
        return [i for i in [ip4, ip6] if i]


class IpPrefixes:
    """
    Convenience class to help generate IP4 and IP6 addresses for nodes within CORE.
    """

    def __init__(self, ip4_prefix: str = None, ip6_prefix: str = None) -> None:
        """
        Creates an IpPrefixes object.

        :param ip4_prefix: ip4 prefix to use for generation
        :param ip6_prefix: ip6 prefix to use for generation
        :raises ValueError: when both ip4 and ip6 prefixes have not been provided
        """
        if not ip4_prefix and not ip6_prefix:
            raise ValueError("ip4 or ip6 must be provided")

        self.ip4 = None
        if ip4_prefix:
            self.ip4 = netaddr.IPNetwork(ip4_prefix)
        self.ip6 = None
        if ip6_prefix:
            self.ip6 = netaddr.IPNetwork(ip6_prefix)

    def ip4_address(self, node: CoreNode) -> str:
        """
        Convenience method to return the IP4 address for a node.

        :param node: node to get IP4 address for
        :return: IP4 address or None
        """
        if not self.ip4:
            raise ValueError("ip4 prefixes have not been set")
        return str(self.ip4[node.id])

    def ip6_address(self, node: CoreNode) -> str:
        """
        Convenience method to return the IP6 address for a node.

        :param node: node to get IP6 address for
        :return: IP4 address or None
        """
        if not self.ip6:
            raise ValueError("ip6 prefixes have not been set")
        return str(self.ip6[node.id])

    def create_interface(
        self, node: CoreNode, name: str = None, mac: str = None
    ) -> InterfaceData:
        """
        Creates interface data for linking nodes, using the nodes unique id for
        generation, along with a random mac address, unless provided.

        :param node: node to create interface for
        :param name: name to set for interface, default is eth{id}
        :param mac: mac address to use for this interface, default is random
            generation
        :return: new interface data for the provided node
        """
        # interface id
        inteface_id = node.newifindex()

        # generate ip4 data
        ip4 = None
        ip4_mask = None
        if self.ip4:
            ip4 = self.ip4_address(node)
            ip4_mask = self.ip4.prefixlen

        # generate ip6 data
        ip6 = None
        ip6_mask = None
        if self.ip6:
            ip6 = self.ip6_address(node)
            ip6_mask = self.ip6.prefixlen

        # random mac
        if not mac:
            mac = utils.random_mac()

        return InterfaceData(
            _id=inteface_id,
            name=name,
            ip4=ip4,
            ip4_mask=ip4_mask,
            ip6=ip6,
            ip6_mask=ip6_mask,
            mac=mac,
        )


def create_interface(
    node: CoreNode, network: CoreNetworkBase, interface_data: InterfaceData
):
    """
    Create an interface for a node on a network using provided interface data.

    :param node: node to create interface for
    :param network: network to associate interface with
    :param interface_data: interface data
    :return: created interface
    """
    node.newnetif(
        network,
        addrlist=interface_data.get_addresses(),
        hwaddr=interface_data.mac,
        ifindex=interface_data.id,
        ifname=interface_data.name,
    )
    return node.netif(interface_data.id)
