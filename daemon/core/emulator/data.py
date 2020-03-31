"""
CORE data objects.
"""

from dataclasses import dataclass
from typing import List, Tuple

from core.emulator.enumerations import (
    EventTypes,
    ExceptionLevels,
    LinkTypes,
    MessageFlags,
    NodeTypes,
)


@dataclass
class ConfigData:
    message_type: MessageFlags = None
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
    interface_number: int = None
    network_id: int = None
    opaque: str = None


@dataclass
class EventData:
    node: int = None
    event_type: EventTypes = None
    name: str = None
    data: str = None
    time: float = None
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
class NodeData:
    message_type: MessageFlags = None
    id: int = None
    node_type: NodeTypes = None
    name: str = None
    ip_address: str = None
    mac_address: str = None
    ip6_address: str = None
    model: str = None
    emulation_id: int = None
    server: str = None
    session: int = None
    x_position: float = None
    y_position: float = None
    canvas: int = None
    network_id: int = None
    services: List[str] = None
    latitude: float = None
    longitude: float = None
    altitude: float = None
    icon: str = None
    opaque: str = None
    source: str = None


@dataclass
class LinkData:
    message_type: MessageFlags = None
    node1_id: int = None
    node2_id: int = None
    delay: float = None
    bandwidth: float = None
    per: float = None
    dup: float = None
    jitter: float = None
    mer: float = None
    burst: float = None
    session: int = None
    mburst: float = None
    link_type: LinkTypes = None
    gui_attributes: str = None
    unidirectional: int = None
    emulation_id: int = None
    network_id: int = None
    key: int = None
    interface1_id: int = None
    interface1_name: str = None
    interface1_ip4: str = None
    interface1_ip4_mask: int = None
    interface1_mac: str = None
    interface1_ip6: str = None
    interface1_ip6_mask: int = None
    interface2_id: int = None
    interface2_name: str = None
    interface2_ip4: str = None
    interface2_ip4_mask: int = None
    interface2_mac: str = None
    interface2_ip6: str = None
    interface2_ip6_mask: int = None
    opaque: str = None
