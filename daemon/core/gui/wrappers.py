from dataclasses import dataclass
from enum import Enum
from typing import List

from core.api.grpc import core_pb2


class SessionState(Enum):
    DEFINITION = 1
    CONFIGURATION = 2
    INSTANTIATION = 3
    RUNTIME = 4
    DATACOLLECT = 5
    SHUTDOWN = 6


class NodeType(Enum):
    DEFAULT = 0
    PHYSICAL = 1
    SWITCH = 4
    HUB = 5
    WIRELESS_LAN = 6
    RJ45 = 7
    TUNNEL = 8
    EMANE = 10
    TAP_BRIDGE = 11
    PEER_TO_PEER = 12
    CONTROL_NET = 13
    DOCKER = 15
    LXC = 16


@dataclass
class Hook:
    state: SessionState
    file: str
    data: str

    @classmethod
    def from_proto(cls, hook: core_pb2.Hook) -> "Hook":
        return Hook(state=SessionState(hook.state), file=hook.file, data=hook.data)

    def to_proto(self) -> core_pb2.Hook:
        return core_pb2.Hook(state=self.state.value, file=self.file, data=self.data)


@dataclass
class Position:
    x: float
    y: float

    @classmethod
    def from_proto(cls, position: core_pb2.Position) -> "Position":
        return Position(x=position.x, y=position.y)

    def to_proto(self) -> core_pb2.Position:
        return core_pb2.Position(x=self.x, y=self.y)


@dataclass
class Geo:
    lat: float = None
    lon: float = None
    alt: float = None

    @classmethod
    def from_proto(cls, geo: core_pb2.Geo) -> "Geo":
        return Geo(lat=geo.lat, lon=geo.lon, alt=geo.alt)

    def to_proto(self) -> core_pb2.Geo:
        return core_pb2.Geo(lat=self.lat, lon=self.lon, alt=self.alt)


@dataclass
class Node:
    id: int
    name: str
    type: NodeType
    model: str = None
    position: Position = None
    services: List[str] = None
    config_services: List[str] = None
    emane: str = None
    icon: str = None
    image: str = None
    server: str = None
    geo: Geo = None
    dir: str = None
    channel: str = None

    @classmethod
    def from_proto(cls, node: core_pb2.Node) -> "Node":
        return Node(
            id=node.id,
            name=node.name,
            type=NodeType(node.type),
            model=node.model,
            position=Position.from_proto(node.position),
            services=list(node.services),
            config_services=list(node.config_services),
            emane=node.emane,
            icon=node.icon,
            image=node.image,
            server=node.server,
            geo=Geo.from_proto(node.geo),
            dir=node.dir,
            channel=node.channel,
        )

    def to_proto(self) -> core_pb2.Node:
        return core_pb2.Node(
            id=self.id,
            name=self.name,
            type=self.type.value,
            model=self.model,
            position=self.position.to_proto(),
            services=self.services,
            config_services=self.config_services,
            emane=self.emane,
            icon=self.icon,
            image=self.image,
            server=self.server,
            geo=self.geo.to_proto(),
            dir=self.dir,
            channel=self.channel,
        )
