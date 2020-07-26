from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

from core.api.grpc import common_pb2, configservices_pb2, core_pb2, services_pb2


class ConfigServiceValidationMode(Enum):
    BLOCKING = 0
    NON_BLOCKING = 1
    TIMER = 2


class ServiceValidationMode(Enum):
    BLOCKING = 0
    NON_BLOCKING = 1
    TIMER = 2


class MobilityAction(Enum):
    START = 0
    PAUSE = 1
    STOP = 2


class ConfigOptionType(Enum):
    UINT8 = 1
    UINT16 = 2
    UINT32 = 3
    UINT64 = 4
    INT8 = 5
    INT16 = 6
    INT32 = 7
    INT64 = 8
    FLOAT = 9
    STRING = 10
    BOOL = 11


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


class LinkType(Enum):
    WIRELESS = 0
    WIRED = 1


class ExceptionLevel(Enum):
    DEFAULT = 0
    FATAL = 1
    ERROR = 2
    WARNING = 3
    NOTICE = 4


class MessageType(Enum):
    NONE = 0
    ADD = 1
    DELETE = 2
    CRI = 4
    LOCAL = 8
    STRING = 16
    TEXT = 32
    TTY = 64


@dataclass
class ConfigService:
    group: str
    name: str
    executables: List[str]
    dependencies: List[str]
    directories: List[str]
    files: List[str]
    startup: List[str]
    validate: List[str]
    shutdown: List[str]
    validation_mode: ConfigServiceValidationMode
    validation_timer: int
    validation_period: float

    @classmethod
    def from_proto(cls, proto: configservices_pb2.ConfigService) -> "ConfigService":
        return ConfigService(
            group=proto.group,
            name=proto.name,
            executables=proto.executables,
            dependencies=proto.dependencies,
            directories=proto.directories,
            files=proto.files,
            startup=proto.startup,
            validate=proto.validate,
            shutdown=proto.shutdown,
            validation_mode=ConfigServiceValidationMode(proto.validation_mode),
            validation_timer=proto.validation_timer,
            validation_period=proto.validation_period,
        )


@dataclass
class NodeServiceData:
    executables: List[str]
    dependencies: List[str]
    dirs: List[str]
    configs: List[str]
    startup: List[str]
    validate: List[str]
    validation_mode: ServiceValidationMode
    validation_timer: int
    shutdown: List[str]
    meta: str

    @classmethod
    def from_proto(cls, proto: services_pb2.NodeServiceData) -> "NodeServiceData":
        return NodeServiceData(
            executables=proto.executables,
            dependencies=proto.dependencies,
            dirs=proto.dirs,
            configs=proto.configs,
            startup=proto.startup,
            validate=proto.validate,
            validation_mode=proto.validation_mode,
            validation_timer=proto.validation_timer,
            shutdown=proto.shutdown,
            meta=proto.meta,
        )


@dataclass
class BridgeThroughput:
    node_id: int
    throughput: float

    @classmethod
    def from_proto(cls, proto: core_pb2.BridgeThroughput) -> "BridgeThroughput":
        return BridgeThroughput(node_id=proto.node_id, throughput=proto.throughput)


@dataclass
class InterfaceThroughput:
    node_id: int
    iface_id: int
    throughput: float

    @classmethod
    def from_proto(cls, proto: core_pb2.InterfaceThroughput) -> "InterfaceThroughput":
        return InterfaceThroughput(
            node_id=proto.node_id, iface_id=proto.iface_id, throughput=proto.throughput
        )


@dataclass
class ThroughputsEvent:
    session_id: int
    bridge_throughputs: List[BridgeThroughput]
    iface_throughputs: List[InterfaceThroughput]

    @classmethod
    def from_proto(cls, proto: core_pb2.ThroughputsEvent) -> "ThroughputsEvent":
        bridges = [BridgeThroughput.from_proto(x) for x in proto.bridge_throughputs]
        ifaces = [InterfaceThroughput.from_proto(x) for x in proto.iface_throughputs]
        return ThroughputsEvent(
            session_id=proto.session_id,
            bridge_throughputs=bridges,
            iface_throughputs=ifaces,
        )


@dataclass
class SessionLocation:
    x: float
    y: float
    z: float
    lat: float
    lon: float
    alt: float
    scale: float

    @classmethod
    def from_proto(cls, proto: core_pb2.SessionLocation) -> "SessionLocation":
        return SessionLocation(
            x=proto.x,
            y=proto.y,
            z=proto.z,
            lat=proto.lat,
            lon=proto.lon,
            alt=proto.alt,
            scale=proto.scale,
        )

    def to_proto(self) -> core_pb2.SessionLocation:
        return core_pb2.SessionLocation(
            x=self.x,
            y=self.y,
            z=self.z,
            lat=self.lat,
            lon=self.lon,
            alt=self.alt,
            scale=self.scale,
        )


@dataclass
class ExceptionEvent:
    session_id: int
    node_id: int
    level: ExceptionLevel
    source: str
    date: str
    text: str
    opaque: str

    @classmethod
    def from_proto(
        cls, session_id: int, proto: core_pb2.ExceptionEvent
    ) -> "ExceptionEvent":
        return ExceptionEvent(
            session_id=session_id,
            node_id=proto.node_id,
            level=ExceptionLevel(proto.level),
            source=proto.source,
            date=proto.date,
            text=proto.text,
            opaque=proto.opaque,
        )


@dataclass
class ConfigOption:
    label: str
    name: str
    value: str
    type: ConfigOptionType
    group: str
    select: List[str] = None

    @classmethod
    def from_dict(
        cls, config: Dict[str, common_pb2.ConfigOption]
    ) -> Dict[str, "ConfigOption"]:
        d = {}
        for key, value in config.items():
            d[key] = ConfigOption.from_proto(value)
        return d

    @classmethod
    def to_dict(cls, config: Dict[str, "ConfigOption"]) -> Dict[str, str]:
        return {k: v.value for k, v in config.items()}

    @classmethod
    def from_proto(cls, proto: common_pb2.ConfigOption) -> "ConfigOption":
        return ConfigOption(
            label=proto.label,
            name=proto.name,
            value=proto.value,
            type=ConfigOptionType(proto.type),
            group=proto.group,
            select=proto.select,
        )


@dataclass
class Interface:
    id: int
    name: str = None
    mac: str = None
    ip4: str = None
    ip4_mask: int = None
    ip6: str = None
    ip6_mask: int = None
    net_id: int = None
    flow_id: int = None
    mtu: int = None
    node_id: int = None
    net2_id: int = None

    @classmethod
    def from_proto(cls, proto: core_pb2.Interface) -> "Interface":
        return Interface(
            id=proto.id,
            name=proto.name,
            mac=proto.mac,
            ip4=proto.ip4,
            ip4_mask=proto.ip4_mask,
            ip6=proto.ip6,
            ip6_mask=proto.ip6_mask,
            net_id=proto.net_id,
            flow_id=proto.flow_id,
            mtu=proto.mtu,
            node_id=proto.node_id,
            net2_id=proto.net2_id,
        )

    def to_proto(self) -> core_pb2.Interface:
        return core_pb2.Interface(
            id=self.id,
            name=self.name,
            mac=self.mac,
            ip4=self.ip4,
            ip4_mask=self.ip4_mask,
            ip6=self.ip6,
            ip6_mask=self.ip6_mask,
            net_id=self.net_id,
            flow_id=self.flow_id,
            mtu=self.mtu,
            node_id=self.node_id,
            net2_id=self.net2_id,
        )


@dataclass
class LinkOptions:
    jitter: int = 0
    key: int = 0
    mburst: int = 0
    mer: int = 0
    loss: float = 0.0
    bandwidth: int = 0
    burst: int = 0
    delay: int = 0
    dup: int = 0
    unidirectional: bool = False

    @classmethod
    def from_proto(cls, proto: core_pb2.LinkOptions) -> "LinkOptions":
        return LinkOptions(
            jitter=proto.jitter,
            key=proto.key,
            mburst=proto.mburst,
            mer=proto.mer,
            loss=proto.loss,
            bandwidth=proto.bandwidth,
            burst=proto.burst,
            delay=proto.delay,
            dup=proto.dup,
            unidirectional=proto.unidirectional,
        )

    def to_proto(self) -> core_pb2.LinkOptions:
        return core_pb2.LinkOptions(
            jitter=self.jitter,
            key=self.key,
            mburst=self.mburst,
            mer=self.mer,
            loss=self.loss,
            bandwidth=self.bandwidth,
            burst=self.burst,
            delay=self.delay,
            dup=self.dup,
            unidirectional=self.unidirectional,
        )


@dataclass
class Link:
    node1_id: int
    node2_id: int
    type: LinkType = LinkType.WIRED
    iface1: Interface = None
    iface2: Interface = None
    options: LinkOptions = None
    network_id: int = None
    label: str = None
    color: str = None

    @classmethod
    def from_proto(cls, proto: core_pb2.Link) -> "Link":
        iface1 = None
        if proto.HasField("iface1"):
            iface1 = Interface.from_proto(proto.iface1)
        iface2 = None
        if proto.HasField("iface2"):
            iface2 = Interface.from_proto(proto.iface2)
        options = None
        if proto.HasField("options"):
            options = LinkOptions.from_proto(proto.options)
        return Link(
            type=LinkType(proto.type),
            node1_id=proto.node1_id,
            node2_id=proto.node2_id,
            iface1=iface1,
            iface2=iface2,
            options=options,
            network_id=proto.network_id,
            label=proto.label,
            color=proto.color,
        )

    def to_proto(self) -> core_pb2.Link:
        iface1 = self.iface1.to_proto() if self.iface1 else None
        iface2 = self.iface2.to_proto() if self.iface2 else None
        options = self.options.to_proto() if self.options else None
        return core_pb2.Link(
            type=self.type.value,
            node1_id=self.node1_id,
            node2_id=self.node2_id,
            iface1=iface1,
            iface2=iface2,
            options=options,
            network_id=self.network_id,
            label=self.label,
            color=self.color,
        )

    def is_symmetric(self) -> bool:
        result = True
        if self.options:
            result = self.options.unidirectional is False
        return result


@dataclass
class SessionSummary:
    id: int
    state: SessionState
    nodes: int
    file: str
    dir: str

    @classmethod
    def from_proto(cls, proto: core_pb2.SessionSummary) -> "SessionSummary":
        return SessionSummary(
            id=proto.id,
            state=SessionState(proto.state),
            nodes=proto.nodes,
            file=proto.file,
            dir=proto.dir,
        )


@dataclass
class Hook:
    state: SessionState
    file: str
    data: str

    @classmethod
    def from_proto(cls, proto: core_pb2.Hook) -> "Hook":
        return Hook(state=SessionState(proto.state), file=proto.file, data=proto.data)

    def to_proto(self) -> core_pb2.Hook:
        return core_pb2.Hook(state=self.state.value, file=self.file, data=self.data)


@dataclass
class Position:
    x: float
    y: float

    @classmethod
    def from_proto(cls, proto: core_pb2.Position) -> "Position":
        return Position(x=proto.x, y=proto.y)

    def to_proto(self) -> core_pb2.Position:
        return core_pb2.Position(x=self.x, y=self.y)


@dataclass
class Geo:
    lat: float = None
    lon: float = None
    alt: float = None

    @classmethod
    def from_proto(cls, proto: core_pb2.Geo) -> "Geo":
        return Geo(lat=proto.lat, lon=proto.lon, alt=proto.alt)

    def to_proto(self) -> core_pb2.Geo:
        return core_pb2.Geo(lat=self.lat, lon=self.lon, alt=self.alt)


@dataclass
class Node:
    id: int
    name: str
    type: NodeType
    model: str = None
    position: Position = None
    services: List[str] = field(default_factory=list)
    config_services: List[str] = field(default_factory=list)
    emane: str = None
    icon: str = None
    image: str = None
    server: str = None
    geo: Geo = None
    dir: str = None
    channel: str = None

    @classmethod
    def from_proto(cls, proto: core_pb2.Node) -> "Node":
        return Node(
            id=proto.id,
            name=proto.name,
            type=NodeType(proto.type),
            model=proto.model,
            position=Position.from_proto(proto.position),
            services=list(proto.services),
            config_services=list(proto.config_services),
            emane=proto.emane,
            icon=proto.icon,
            image=proto.image,
            server=proto.server,
            geo=Geo.from_proto(proto.geo),
            dir=proto.dir,
            channel=proto.channel,
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
            dir=self.dir,
            channel=self.channel,
        )


@dataclass
class LinkEvent:
    message_type: MessageType
    link: Link

    @classmethod
    def from_proto(cls, proto: core_pb2.LinkEvent) -> "LinkEvent":
        return LinkEvent(
            message_type=MessageType(proto.message_type),
            link=Link.from_proto(proto.link),
        )


@dataclass
class NodeEvent:
    message_type: MessageType
    node: Node

    @classmethod
    def from_proto(cls, proto: core_pb2.NodeEvent) -> "NodeEvent":
        return NodeEvent(
            message_type=MessageType(proto.message_type),
            node=Node.from_proto(proto.node),
        )
