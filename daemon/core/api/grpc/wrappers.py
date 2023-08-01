from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from core.api.grpc import (
    common_pb2,
    configservices_pb2,
    core_pb2,
    emane_pb2,
    services_pb2,
)


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
    WIRELESS = 17
    PODMAN = 18


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


class ServiceAction(Enum):
    START = 0
    STOP = 1
    RESTART = 2
    VALIDATE = 3


class EventType:
    SESSION = 0
    NODE = 1
    LINK = 2
    CONFIG = 3
    EXCEPTION = 4
    FILE = 5


@dataclass
class ConfigService:
    group: str
    name: str
    executables: list[str]
    dependencies: list[str]
    directories: list[str]
    files: list[str]
    startup: list[str]
    validate: list[str]
    shutdown: list[str]
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
class ConfigServiceConfig:
    node_id: int
    name: str
    templates: dict[str, str]
    config: dict[str, str]

    @classmethod
    def from_proto(
        cls, proto: configservices_pb2.ConfigServiceConfig
    ) -> "ConfigServiceConfig":
        return ConfigServiceConfig(
            node_id=proto.node_id,
            name=proto.name,
            templates=dict(proto.templates),
            config=dict(proto.config),
        )


@dataclass
class ConfigServiceData:
    templates: dict[str, str] = field(default_factory=dict)
    config: dict[str, str] = field(default_factory=dict)


@dataclass
class ConfigServiceDefaults:
    templates: dict[str, str]
    config: dict[str, "ConfigOption"]
    modes: dict[str, dict[str, str]]

    @classmethod
    def from_proto(
        cls, proto: configservices_pb2.GetConfigServiceDefaultsResponse
    ) -> "ConfigServiceDefaults":
        config = ConfigOption.from_dict(proto.config)
        modes = {x.name: dict(x.config) for x in proto.modes}
        return ConfigServiceDefaults(
            templates=dict(proto.templates), config=config, modes=modes
        )


@dataclass
class Server:
    name: str
    host: str

    @classmethod
    def from_proto(cls, proto: core_pb2.Server) -> "Server":
        return Server(name=proto.name, host=proto.host)

    def to_proto(self) -> core_pb2.Server:
        return core_pb2.Server(name=self.name, host=self.host)


@dataclass
class Service:
    group: str
    name: str

    @classmethod
    def from_proto(cls, proto: services_pb2.Service) -> "Service":
        return Service(group=proto.group, name=proto.name)


@dataclass
class ServiceDefault:
    model: str
    services: list[str]

    @classmethod
    def from_proto(cls, proto: services_pb2.ServiceDefaults) -> "ServiceDefault":
        return ServiceDefault(model=proto.model, services=list(proto.services))


@dataclass
class NodeServiceData:
    executables: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    dirs: list[str] = field(default_factory=list)
    configs: list[str] = field(default_factory=list)
    startup: list[str] = field(default_factory=list)
    validate: list[str] = field(default_factory=list)
    validation_mode: ServiceValidationMode = ServiceValidationMode.NON_BLOCKING
    validation_timer: int = 5
    shutdown: list[str] = field(default_factory=list)
    meta: str = None

    @classmethod
    def from_proto(cls, proto: services_pb2.NodeServiceData) -> "NodeServiceData":
        return NodeServiceData(
            executables=proto.executables,
            dependencies=proto.dependencies,
            dirs=proto.dirs,
            configs=proto.configs,
            startup=proto.startup,
            validate=proto.validate,
            validation_mode=ServiceValidationMode(proto.validation_mode),
            validation_timer=proto.validation_timer,
            shutdown=proto.shutdown,
            meta=proto.meta,
        )

    def to_proto(self) -> services_pb2.NodeServiceData:
        return services_pb2.NodeServiceData(
            executables=self.executables,
            dependencies=self.dependencies,
            dirs=self.dirs,
            configs=self.configs,
            startup=self.startup,
            validate=self.validate,
            validation_mode=self.validation_mode.value,
            validation_timer=self.validation_timer,
            shutdown=self.shutdown,
            meta=self.meta,
        )


@dataclass
class NodeServiceConfig:
    node_id: int
    service: str
    data: NodeServiceData
    files: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_proto(cls, proto: services_pb2.NodeServiceConfig) -> "NodeServiceConfig":
        return NodeServiceConfig(
            node_id=proto.node_id,
            service=proto.service,
            data=NodeServiceData.from_proto(proto.data),
            files=dict(proto.files),
        )


@dataclass
class ServiceConfig:
    node_id: int
    service: str
    files: list[str] = None
    directories: list[str] = None
    startup: list[str] = None
    validate: list[str] = None
    shutdown: list[str] = None

    def to_proto(self) -> services_pb2.ServiceConfig:
        return services_pb2.ServiceConfig(
            node_id=self.node_id,
            service=self.service,
            files=self.files,
            directories=self.directories,
            startup=self.startup,
            validate=self.validate,
            shutdown=self.shutdown,
        )


@dataclass
class ServiceFileConfig:
    node_id: int
    service: str
    file: str
    data: str = field(repr=False)

    def to_proto(self) -> services_pb2.ServiceFileConfig:
        return services_pb2.ServiceFileConfig(
            node_id=self.node_id, service=self.service, file=self.file, data=self.data
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
    bridge_throughputs: list[BridgeThroughput]
    iface_throughputs: list[InterfaceThroughput]

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
class CpuUsageEvent:
    usage: float

    @classmethod
    def from_proto(cls, proto: core_pb2.CpuUsageEvent) -> "CpuUsageEvent":
        return CpuUsageEvent(usage=proto.usage)


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
    name: str
    value: str
    label: str = None
    type: ConfigOptionType = None
    group: str = None
    select: list[str] = None

    @classmethod
    def from_dict(
        cls, config: dict[str, common_pb2.ConfigOption]
    ) -> dict[str, "ConfigOption"]:
        d = {}
        for key, value in config.items():
            d[key] = ConfigOption.from_proto(value)
        return d

    @classmethod
    def to_dict(cls, config: dict[str, "ConfigOption"]) -> dict[str, str]:
        return {k: v.value for k, v in config.items()}

    @classmethod
    def from_proto(cls, proto: common_pb2.ConfigOption) -> "ConfigOption":
        config_type = ConfigOptionType(proto.type) if proto.type is not None else None
        return ConfigOption(
            label=proto.label,
            name=proto.name,
            value=proto.value,
            type=config_type,
            group=proto.group,
            select=proto.select,
        )

    def to_proto(self) -> common_pb2.ConfigOption:
        config_type = self.type.value if self.type is not None else None
        return common_pb2.ConfigOption(
            label=self.label,
            name=self.name,
            value=self.value,
            type=config_type,
            select=self.select,
            group=self.group,
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
    nem_id: int = None
    nem_port: int = None

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
            nem_id=proto.nem_id,
            nem_port=proto.nem_port,
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
    buffer: int = 0

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
            buffer=proto.buffer,
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
            buffer=self.buffer,
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

    def to_proto(self) -> core_pb2.SessionSummary:
        return core_pb2.SessionSummary(
            id=self.id,
            state=self.state.value,
            nodes=self.nodes,
            file=self.file,
            dir=self.dir,
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
class EmaneModelConfig:
    node_id: int
    model: str
    iface_id: int = -1
    config: dict[str, ConfigOption] = None

    @classmethod
    def from_proto(cls, proto: emane_pb2.GetEmaneModelConfig) -> "EmaneModelConfig":
        iface_id = proto.iface_id if proto.iface_id != -1 else None
        config = ConfigOption.from_dict(proto.config)
        return EmaneModelConfig(
            node_id=proto.node_id, iface_id=iface_id, model=proto.model, config=config
        )

    def to_proto(self) -> emane_pb2.EmaneModelConfig:
        config = ConfigOption.to_dict(self.config)
        return emane_pb2.EmaneModelConfig(
            node_id=self.node_id,
            model=self.model,
            iface_id=self.iface_id,
            config=config,
        )


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
    id: int = None
    name: str = None
    type: NodeType = NodeType.DEFAULT
    model: str = None
    position: Position = Position(x=0, y=0)
    services: set[str] = field(default_factory=set)
    config_services: set[str] = field(default_factory=set)
    emane: str = None
    icon: str = None
    image: str = None
    server: str = None
    geo: Geo = None
    dir: str = None
    channel: str = None
    canvas: int = None

    # configurations
    emane_model_configs: dict[
        tuple[str, Optional[int]], dict[str, ConfigOption]
    ] = field(default_factory=dict, repr=False)
    wlan_config: dict[str, ConfigOption] = field(default_factory=dict, repr=False)
    wireless_config: dict[str, ConfigOption] = field(default_factory=dict, repr=False)
    mobility_config: dict[str, ConfigOption] = field(default_factory=dict, repr=False)
    service_configs: dict[str, NodeServiceData] = field(
        default_factory=dict, repr=False
    )
    service_file_configs: dict[str, dict[str, str]] = field(
        default_factory=dict, repr=False
    )
    config_service_configs: dict[str, ConfigServiceData] = field(
        default_factory=dict, repr=False
    )

    @classmethod
    def from_proto(cls, proto: core_pb2.Node) -> "Node":
        service_configs = {}
        service_file_configs = {}
        for service, node_config in proto.service_configs.items():
            service_configs[service] = NodeServiceData.from_proto(node_config.data)
            service_file_configs[service] = dict(node_config.files)
        emane_configs = {}
        for emane_config in proto.emane_configs:
            iface_id = None if emane_config.iface_id == -1 else emane_config.iface_id
            model = emane_config.model
            key = (model, iface_id)
            emane_configs[key] = ConfigOption.from_dict(emane_config.config)
        config_service_configs = {}
        for service, service_config in proto.config_service_configs.items():
            config_service_configs[service] = ConfigServiceData(
                templates=dict(service_config.templates),
                config=dict(service_config.config),
            )
        return Node(
            id=proto.id,
            name=proto.name,
            type=NodeType(proto.type),
            model=proto.model or None,
            position=Position.from_proto(proto.position),
            services=set(proto.services),
            config_services=set(proto.config_services),
            emane=proto.emane,
            icon=proto.icon,
            image=proto.image,
            server=proto.server,
            geo=Geo.from_proto(proto.geo),
            dir=proto.dir,
            channel=proto.channel,
            canvas=proto.canvas,
            wlan_config=ConfigOption.from_dict(proto.wlan_config),
            mobility_config=ConfigOption.from_dict(proto.mobility_config),
            service_configs=service_configs,
            service_file_configs=service_file_configs,
            config_service_configs=config_service_configs,
            emane_model_configs=emane_configs,
            wireless_config=ConfigOption.from_dict(proto.wireless_config),
        )

    def to_proto(self) -> core_pb2.Node:
        emane_configs = []
        for key, config in self.emane_model_configs.items():
            model, iface_id = key
            if iface_id is None:
                iface_id = -1
            config = {k: v.to_proto() for k, v in config.items()}
            emane_config = emane_pb2.NodeEmaneConfig(
                iface_id=iface_id, model=model, config=config
            )
            emane_configs.append(emane_config)
        service_configs = {}
        for service, service_data in self.service_configs.items():
            service_configs[service] = services_pb2.NodeServiceConfig(
                service=service, data=service_data.to_proto()
            )
        for service, file_configs in self.service_file_configs.items():
            service_config = service_configs.get(service)
            if service_config:
                service_config.files.update(file_configs)
            else:
                service_configs[service] = services_pb2.NodeServiceConfig(
                    service=service, files=file_configs
                )
        config_service_configs = {}
        for service, service_config in self.config_service_configs.items():
            config_service_configs[service] = configservices_pb2.ConfigServiceConfig(
                templates=service_config.templates, config=service_config.config
            )
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
            canvas=self.canvas,
            wlan_config={k: v.to_proto() for k, v in self.wlan_config.items()},
            mobility_config={k: v.to_proto() for k, v in self.mobility_config.items()},
            service_configs=service_configs,
            config_service_configs=config_service_configs,
            emane_configs=emane_configs,
            wireless_config={k: v.to_proto() for k, v in self.wireless_config.items()},
        )

    def set_wlan(self, config: dict[str, str]) -> None:
        for key, value in config.items():
            option = ConfigOption(name=key, value=value)
            self.wlan_config[key] = option

    def set_mobility(self, config: dict[str, str]) -> None:
        for key, value in config.items():
            option = ConfigOption(name=key, value=value)
            self.mobility_config[key] = option

    def set_emane_model(
        self, model: str, config: dict[str, str], iface_id: int = None
    ) -> None:
        key = (model, iface_id)
        config_options = self.emane_model_configs.setdefault(key, {})
        for key, value in config.items():
            option = ConfigOption(name=key, value=value)
            config_options[key] = option


@dataclass
class Session:
    id: int = None
    state: SessionState = SessionState.DEFINITION
    nodes: dict[int, Node] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    dir: str = None
    user: str = None
    default_services: dict[str, set[str]] = field(default_factory=dict)
    location: SessionLocation = SessionLocation(
        x=0.0, y=0.0, z=0.0, lat=47.57917, lon=-122.13232, alt=2.0, scale=150.0
    )
    hooks: dict[str, Hook] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    file: Path = None
    options: dict[str, ConfigOption] = field(default_factory=dict)
    servers: list[Server] = field(default_factory=list)

    @classmethod
    def from_proto(cls, proto: core_pb2.Session) -> "Session":
        nodes: dict[int, Node] = {x.id: Node.from_proto(x) for x in proto.nodes}
        links = [Link.from_proto(x) for x in proto.links]
        default_services = {x.model: set(x.services) for x in proto.default_services}
        hooks = {x.file: Hook.from_proto(x) for x in proto.hooks}
        file_path = Path(proto.file) if proto.file else None
        options = ConfigOption.from_dict(proto.options)
        servers = [Server.from_proto(x) for x in proto.servers]
        return Session(
            id=proto.id,
            state=SessionState(proto.state),
            nodes=nodes,
            links=links,
            dir=proto.dir,
            user=proto.user,
            default_services=default_services,
            location=SessionLocation.from_proto(proto.location),
            hooks=hooks,
            metadata=dict(proto.metadata),
            file=file_path,
            options=options,
            servers=servers,
        )

    def to_proto(self) -> core_pb2.Session:
        nodes = [x.to_proto() for x in self.nodes.values()]
        links = [x.to_proto() for x in self.links]
        hooks = [x.to_proto() for x in self.hooks.values()]
        options = {k: v.to_proto() for k, v in self.options.items()}
        servers = [x.to_proto() for x in self.servers]
        default_services = []
        for model, services in self.default_services.items():
            default_service = services_pb2.ServiceDefaults(
                model=model, services=services
            )
            default_services.append(default_service)
        file = str(self.file) if self.file else None
        return core_pb2.Session(
            id=self.id,
            state=self.state.value,
            nodes=nodes,
            links=links,
            dir=self.dir,
            user=self.user,
            default_services=default_services,
            location=self.location.to_proto(),
            hooks=hooks,
            metadata=self.metadata,
            file=file,
            options=options,
            servers=servers,
        )

    def add_node(
        self,
        _id: int,
        *,
        name: str = None,
        _type: NodeType = NodeType.DEFAULT,
        model: str = "PC",
        position: Position = None,
        geo: Geo = None,
        emane: str = None,
        image: str = None,
        server: str = None,
    ) -> Node:
        node = Node(
            id=_id,
            name=name,
            type=_type,
            model=model,
            position=position,
            geo=geo,
            emane=emane,
            image=image,
            server=server,
        )
        self.nodes[node.id] = node
        return node

    def add_link(
        self,
        *,
        node1: Node,
        node2: Node,
        iface1: Interface = None,
        iface2: Interface = None,
        options: LinkOptions = None,
    ) -> Link:
        link = Link(
            node1_id=node1.id,
            node2_id=node2.id,
            iface1=iface1,
            iface2=iface2,
            options=options,
        )
        self.links.append(link)
        return link

    def set_options(self, config: dict[str, str]) -> None:
        for key, value in config.items():
            option = ConfigOption(name=key, value=value)
            self.options[key] = option


@dataclass
class CoreConfig:
    services: list[Service] = field(default_factory=list)
    config_services: list[ConfigService] = field(default_factory=list)
    emane_models: list[str] = field(default_factory=list)

    @classmethod
    def from_proto(cls, proto: core_pb2.GetConfigResponse) -> "CoreConfig":
        services = [Service.from_proto(x) for x in proto.services]
        config_services = [ConfigService.from_proto(x) for x in proto.config_services]
        return CoreConfig(
            services=services,
            config_services=config_services,
            emane_models=list(proto.emane_models),
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


@dataclass
class SessionEvent:
    node_id: int
    event: int
    name: str
    data: str
    time: float

    @classmethod
    def from_proto(cls, proto: core_pb2.SessionEvent) -> "SessionEvent":
        return SessionEvent(
            node_id=proto.node_id,
            event=proto.event,
            name=proto.name,
            data=proto.data,
            time=proto.time,
        )


@dataclass
class FileEvent:
    message_type: MessageType
    node_id: int
    name: str
    mode: str
    number: int
    type: str
    source: str
    data: str
    compressed_data: str

    @classmethod
    def from_proto(cls, proto: core_pb2.FileEvent) -> "FileEvent":
        return FileEvent(
            message_type=MessageType(proto.message_type),
            node_id=proto.node_id,
            name=proto.name,
            mode=proto.mode,
            number=proto.number,
            type=proto.type,
            source=proto.source,
            data=proto.data,
            compressed_data=proto.compressed_data,
        )


@dataclass
class ConfigEvent:
    message_type: MessageType
    node_id: int
    object: str
    type: int
    data_types: list[int]
    data_values: str
    captions: str
    bitmap: str
    possible_values: str
    groups: str
    iface_id: int
    network_id: int
    opaque: str

    @classmethod
    def from_proto(cls, proto: core_pb2.ConfigEvent) -> "ConfigEvent":
        return ConfigEvent(
            message_type=MessageType(proto.message_type),
            node_id=proto.node_id,
            object=proto.object,
            type=proto.type,
            data_types=list(proto.data_types),
            data_values=proto.data_values,
            captions=proto.captions,
            possible_values=proto.possible_values,
            groups=proto.groups,
            iface_id=proto.iface_id,
            network_id=proto.network_id,
            opaque=proto.opaque,
        )


@dataclass
class Event:
    session_id: int
    source: str = None
    session_event: SessionEvent = None
    node_event: NodeEvent = None
    link_event: LinkEvent = None
    config_event: Any = None
    exception_event: ExceptionEvent = None
    file_event: FileEvent = None

    @classmethod
    def from_proto(cls, proto: core_pb2.Event) -> "Event":
        source = proto.source if proto.source else None
        node_event = None
        link_event = None
        exception_event = None
        session_event = None
        file_event = None
        config_event = None
        if proto.HasField("node_event"):
            node_event = NodeEvent.from_proto(proto.node_event)
        elif proto.HasField("link_event"):
            link_event = LinkEvent.from_proto(proto.link_event)
        elif proto.HasField("exception_event"):
            exception_event = ExceptionEvent.from_proto(
                proto.session_id, proto.exception_event
            )
        elif proto.HasField("session_event"):
            session_event = SessionEvent.from_proto(proto.session_event)
        elif proto.HasField("file_event"):
            file_event = FileEvent.from_proto(proto.file_event)
        elif proto.HasField("config_event"):
            config_event = ConfigEvent.from_proto(proto.config_event)
        return Event(
            session_id=proto.session_id,
            source=source,
            node_event=node_event,
            link_event=link_event,
            exception_event=exception_event,
            session_event=session_event,
            file_event=file_event,
            config_event=config_event,
        )


@dataclass
class EmaneEventChannel:
    group: str
    port: int
    device: str

    @classmethod
    def from_proto(
        cls, proto: emane_pb2.GetEmaneEventChannelResponse
    ) -> "EmaneEventChannel":
        return EmaneEventChannel(
            group=proto.group, port=proto.port, device=proto.device
        )


@dataclass
class EmanePathlossesRequest:
    session_id: int
    node1_id: int
    rx1: float
    iface1_id: int
    node2_id: int
    rx2: float
    iface2_id: int

    def to_proto(self) -> emane_pb2.EmanePathlossesRequest:
        return emane_pb2.EmanePathlossesRequest(
            session_id=self.session_id,
            node1_id=self.node1_id,
            rx1=self.rx1,
            iface1_id=self.iface1_id,
            node2_id=self.node2_id,
            rx2=self.rx2,
            iface2_id=self.iface2_id,
        )


@dataclass(frozen=True)
class MoveNodesRequest:
    session_id: int
    node_id: int
    source: str = field(compare=False, default=None)
    position: Position = field(compare=False, default=None)
    geo: Geo = field(compare=False, default=None)

    def to_proto(self) -> core_pb2.MoveNodesRequest:
        position = self.position.to_proto() if self.position else None
        geo = self.geo.to_proto() if self.geo else None
        return core_pb2.MoveNodesRequest(
            session_id=self.session_id,
            node_id=self.node_id,
            source=self.source,
            position=position,
            geo=geo,
        )
