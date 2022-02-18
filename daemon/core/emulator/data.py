"""
CORE data objects.
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

import netaddr

from core import utils
from core.emulator.enumerations import (
    EventTypes,
    ExceptionLevels,
    LinkTypes,
    MessageFlags,
)

if TYPE_CHECKING:
    from core.nodes.base import CoreNode, NodeBase


@dataclass
class ConfigData:
    message_type: int = None
    node: int = None
    object: str = None
    type: int = None
    data_types: Tuple[int] = None
    data_values: str = None
    captions: str = None
    bitmap: str = None
    possible_values: str = None
    groups: str = None
    session: int = None
    iface_id: int = None
    network_id: int = None
    opaque: str = None


@dataclass
class EventData:
    node: int = None
    event_type: EventTypes = None
    name: str = None
    data: str = None
    time: str = None
    session: int = None


@dataclass
class ExceptionData:
    node: int = None
    session: int = None
    level: ExceptionLevels = None
    source: str = None
    date: str = None
    text: str = None
    opaque: str = None


@dataclass
class FileData:
    message_type: MessageFlags = None
    node: int = None
    name: str = None
    mode: str = None
    number: int = None
    type: str = None
    source: str = None
    session: int = None
    data: str = None
    compressed_data: str = None


@dataclass
class NodeOptions:
    """
    Options for creating and updating nodes within core.
    """

    name: str = None
    model: Optional[str] = "PC"
    canvas: int = None
    icon: str = None
    services: List[str] = field(default_factory=list)
    config_services: List[str] = field(default_factory=list)
    x: float = None
    y: float = None
    lat: float = None
    lon: float = None
    alt: float = None
    server: str = None
    image: str = None
    emane: str = None
    legacy: bool = False

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
class NodeData:
    """
    Node to broadcast.
    """

    node: "NodeBase"
    message_type: MessageFlags = None
    source: str = None


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
    mtu: int = None

    def get_ips(self) -> List[str]:
        """
        Returns a list of ip4 and ip6 addresses when present.

        :return: list of ip addresses
        """
        ips = []
        if self.ip4 and self.ip4_mask:
            ips.append(f"{self.ip4}/{self.ip4_mask}")
        if self.ip6 and self.ip6_mask:
            ips.append(f"{self.ip6}/{self.ip6_mask}")
        return ips


@dataclass
class LinkOptions:
    """
    Options for creating and updating links within core.
    """

    delay: int = None
    bandwidth: int = None
    loss: float = None
    dup: int = None
    jitter: int = None
    mer: int = None
    burst: int = None
    mburst: int = None
    unidirectional: int = None
    key: int = None
    buffer: int = None

    def update(self, options: "LinkOptions") -> bool:
        """
        Updates current options with values from other options.

        :param options: options to update with
        :return: True if any value has changed, False otherwise
        """
        changed = False
        if options.delay is not None and 0 <= options.delay != self.delay:
            self.delay = options.delay
            changed = True
        if options.bandwidth is not None and 0 <= options.bandwidth != self.bandwidth:
            self.bandwidth = options.bandwidth
            changed = True
        if options.loss is not None and 0 <= options.loss != self.loss:
            self.loss = options.loss
            changed = True
        if options.dup is not None and 0 <= options.dup != self.dup:
            self.dup = options.dup
            changed = True
        if options.jitter is not None and 0 <= options.jitter != self.jitter:
            self.jitter = options.jitter
            changed = True
        if options.buffer is not None and 0 <= options.buffer != self.buffer:
            self.buffer = options.buffer
            changed = True
        return changed

    def is_clear(self) -> bool:
        """
        Checks if the current option values represent a clear state.

        :return: True if the current values should clear, False otherwise
        """
        clear = self.delay is None or self.delay <= 0
        clear &= self.jitter is None or self.jitter <= 0
        clear &= self.loss is None or self.loss <= 0
        clear &= self.dup is None or self.dup <= 0
        clear &= self.bandwidth is None or self.bandwidth <= 0
        clear &= self.buffer is None or self.buffer <= 0
        return clear

    def __eq__(self, other: Any) -> bool:
        """
        Custom logic to check if this link options is equivalent to another.

        :param other: other object to check
        :return: True if they are both link options with the same values,
            False otherwise
        """
        if not isinstance(other, LinkOptions):
            return False
        return (
            self.delay == other.delay
            and self.jitter == other.jitter
            and self.loss == other.loss
            and self.dup == other.dup
            and self.bandwidth == other.bandwidth
            and self.buffer == other.buffer
        )


@dataclass
class LinkData:
    """
    Represents all data associated with a link.
    """

    message_type: MessageFlags = None
    type: LinkTypes = LinkTypes.WIRED
    label: str = None
    node1_id: int = None
    node2_id: int = None
    network_id: int = None
    iface1: InterfaceData = None
    iface2: InterfaceData = None
    options: LinkOptions = LinkOptions()
    color: str = None
    source: str = None


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

    def ip4_address(self, node_id: int) -> str:
        """
        Convenience method to return the IP4 address for a node.

        :param node_id: node id to get IP4 address for
        :return: IP4 address or None
        """
        if not self.ip4:
            raise ValueError("ip4 prefixes have not been set")
        return str(self.ip4[node_id])

    def ip6_address(self, node_id: int) -> str:
        """
        Convenience method to return the IP6 address for a node.

        :param node_id: node id to get IP6 address for
        :return: IP4 address or None
        """
        if not self.ip6:
            raise ValueError("ip6 prefixes have not been set")
        return str(self.ip6[node_id])

    def gen_iface(self, node_id: int, name: str = None, mac: str = None):
        """
        Creates interface data for linking nodes, using the nodes unique id for
        generation, along with a random mac address, unless provided.

        :param node_id: node id to create an interface for
        :param name: name to set for interface, default is eth{id}
        :param mac: mac address to use for this interface, default is random
            generation
        :return: new interface data for the provided node
        """
        # generate ip4 data
        ip4 = None
        ip4_mask = None
        if self.ip4:
            ip4 = self.ip4_address(node_id)
            ip4_mask = self.ip4.prefixlen

        # generate ip6 data
        ip6 = None
        ip6_mask = None
        if self.ip6:
            ip6 = self.ip6_address(node_id)
            ip6_mask = self.ip6.prefixlen

        # random mac
        if not mac:
            mac = utils.random_mac()

        return InterfaceData(
            name=name, ip4=ip4, ip4_mask=ip4_mask, ip6=ip6, ip6_mask=ip6_mask, mac=mac
        )

    def create_iface(
        self, node: "CoreNode", name: str = None, mac: str = None
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
        iface_data = self.gen_iface(node.id, name, mac)
        iface_data.id = node.next_iface_id()
        return iface_data
