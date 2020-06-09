from dataclasses import dataclass, field
from typing import List, Optional, Union

import netaddr

from core import utils
from core.api.grpc.core_pb2 import LinkOptions
from core.emulator.enumerations import LinkTypes
from core.nodes.base import CoreNetworkBase, CoreNode
from core.nodes.interface import CoreInterface
from core.nodes.physical import PhysicalNode


def link_config(
    node: Union[CoreNetworkBase, PhysicalNode],
    interface: CoreInterface,
    link_options: LinkOptions,
    interface_two: CoreInterface = None,
) -> None:
    """
    Convenience method for configuring a link,

    :param node: network to configure link for
    :param interface: interface to configure
    :param link_options: data to configure link with
    :param interface_two: other interface associated, default is None
    :return: nothing
    """
    node.linkconfig(
        interface,
        link_options.bandwidth,
        link_options.delay,
        link_options.per,
        link_options.dup,
        link_options.jitter,
        interface_two,
    )


@dataclass
class NodeOptions:
    """
    Options for creating and updating nodes within core.
    """

    name: str = None
    model: Optional[str] = "PC"
    canvas: int = None
    icon: str = None
    opaque: str = None
    services: List[str] = field(default_factory=list)
    config_services: List[str] = field(default_factory=list)
    x: float = None
    y: float = None
    lat: float = None
    lon: float = None
    alt: float = None
    emulation_id: int = None
    server: str = None
    image: str = None
    emane: str = None

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


@dataclass
class LinkOptions:
    """
    Options for creating and updating links within core.
    """

    type: LinkTypes = LinkTypes.WIRED
    session: int = None
    delay: int = None
    bandwidth: int = None
    per: float = None
    dup: int = None
    jitter: int = None
    mer: int = None
    burst: int = None
    mburst: int = None
    gui_attributes: str = None
    unidirectional: bool = None
    emulation_id: int = None
    network_id: int = None
    key: int = None
    opaque: str = None


@dataclass
class InterfaceData:
    """
    Convenience class for storing interface data.
    """

    id: int = None
    name: str = None
    mac: str = None
    ip4: str = None
    ip4_mask: int = None
    ip6: str = None
    ip6_mask: int = None

    def get_addresses(self) -> List[str]:
        """
        Returns a list of ip4 and ip6 addresses when present.

        :return: list of addresses
        """
        addresses = []
        if self.ip4 and self.ip4_mask:
            addresses.append(f"{self.ip4}/{self.ip4_mask}")
        if self.ip6 and self.ip6_mask:
            addresses.append(f"{self.ip6}/{self.ip6_mask}")
        return addresses


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
            id=inteface_id,
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
