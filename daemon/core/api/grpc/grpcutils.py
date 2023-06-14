import logging
import time
from pathlib import Path
from typing import Any, Optional, Union

import grpc
from grpc import ServicerContext

from core import utils
from core.api.grpc import common_pb2, core_pb2, wrappers
from core.api.grpc.configservices_pb2 import ConfigServiceConfig
from core.api.grpc.emane_pb2 import NodeEmaneConfig
from core.api.grpc.services_pb2 import (
    NodeServiceConfig,
    NodeServiceData,
    ServiceConfig,
    ServiceDefaults,
)
from core.config import ConfigurableOptions
from core.emane.nodes import EmaneNet, EmaneOptions
from core.emulator.data import InterfaceData, LinkData, LinkOptions
from core.emulator.enumerations import LinkTypes, NodeTypes
from core.emulator.links import CoreLink
from core.emulator.session import Session
from core.errors import CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import (
    CoreNode,
    CoreNodeBase,
    CoreNodeOptions,
    NodeBase,
    NodeOptions,
    Position,
)
from core.nodes.docker import DockerNode, DockerOptions
from core.nodes.interface import CoreInterface
from core.nodes.lxd import LxcNode, LxcOptions
from core.nodes.network import CoreNetwork, CtrlNet, PtpNet, WlanNode
from core.nodes.podman import PodmanNode, PodmanOptions
from core.nodes.wireless import WirelessNode
from core.services.coreservices import CoreService

logger = logging.getLogger(__name__)
WORKERS = 10


class CpuUsage:
    def __init__(self) -> None:
        self.stat_file: Path = Path("/proc/stat")
        self.prev_idle: int = 0
        self.prev_total: int = 0

    def run(self) -> float:
        lines = self.stat_file.read_text().splitlines()[0]
        values = [int(x) for x in lines.split()[1:]]
        idle = sum(values[3:5])
        non_idle = sum(values[:3] + values[5:8])
        total = idle + non_idle
        total_diff = total - self.prev_total
        idle_diff = idle - self.prev_idle
        self.prev_idle = idle
        self.prev_total = total
        return (total_diff - idle_diff) / total_diff


def add_node_data(
    _class: type[NodeBase], node_proto: core_pb2.Node
) -> tuple[Position, NodeOptions]:
    """
    Convert node protobuf message to data for creating a node.

    :param _class: node class to create options from
    :param node_proto: node proto message
    :return: node type, id, and options
    """
    options = _class.create_options()
    options.icon = node_proto.icon
    options.canvas = node_proto.canvas
    if isinstance(options, CoreNodeOptions):
        options.model = node_proto.model
        options.services = node_proto.services
        options.config_services = node_proto.config_services
    if isinstance(options, EmaneOptions):
        options.emane_model = node_proto.emane
    if isinstance(options, (DockerOptions, LxcOptions, PodmanOptions)):
        options.image = node_proto.image
    position = Position()
    position.set(node_proto.position.x, node_proto.position.y)
    if node_proto.HasField("geo"):
        geo = node_proto.geo
        position.set_geo(geo.lon, geo.lat, geo.alt)
    return position, options


def link_iface(iface_proto: core_pb2.Interface) -> InterfaceData:
    """
    Create interface data from interface proto.

    :param iface_proto: interface proto
    :return: interface data
    """
    iface_data = None
    if iface_proto:
        name = iface_proto.name if iface_proto.name else None
        mac = iface_proto.mac if iface_proto.mac else None
        ip4 = iface_proto.ip4 if iface_proto.ip4 else None
        ip6 = iface_proto.ip6 if iface_proto.ip6 else None
        iface_data = InterfaceData(
            id=iface_proto.id,
            name=name,
            mac=mac,
            ip4=ip4,
            ip4_mask=iface_proto.ip4_mask,
            ip6=ip6,
            ip6_mask=iface_proto.ip6_mask,
        )
    return iface_data


def add_link_data(
    link_proto: core_pb2.Link,
) -> tuple[InterfaceData, InterfaceData, LinkOptions]:
    """
    Convert link proto to link interfaces and options data.

    :param link_proto: link  proto
    :return: link interfaces and options
    """
    iface1_data = link_iface(link_proto.iface1)
    iface2_data = link_iface(link_proto.iface2)
    options = LinkOptions()
    options_proto = link_proto.options
    if options_proto:
        options.delay = options_proto.delay
        options.bandwidth = options_proto.bandwidth
        options.loss = options_proto.loss
        options.dup = options_proto.dup
        options.jitter = options_proto.jitter
        options.mer = options_proto.mer
        options.burst = options_proto.burst
        options.mburst = options_proto.mburst
        options.buffer = options_proto.buffer
        options.unidirectional = options_proto.unidirectional
        options.key = options_proto.key
    return iface1_data, iface2_data, options


def create_nodes(
    session: Session, node_protos: list[core_pb2.Node]
) -> tuple[list[NodeBase], list[Exception]]:
    """
    Create nodes using a thread pool and wait for completion.

    :param session: session to create nodes in
    :param node_protos: node proto messages
    :return: results and exceptions for created nodes
    """
    funcs = []
    for node_proto in node_protos:
        _type = NodeTypes(node_proto.type)
        _class = session.get_node_class(_type)
        position, options = add_node_data(_class, node_proto)
        args = (
            _class,
            node_proto.id or None,
            node_proto.name or None,
            node_proto.server or None,
            position,
            options,
        )
        funcs.append((session.add_node, args, {}))
    start = time.monotonic()
    results, exceptions = utils.threadpool(funcs)
    total = time.monotonic() - start
    logger.debug("grpc created nodes time: %s", total)
    return results, exceptions


def create_links(
    session: Session, link_protos: list[core_pb2.Link]
) -> tuple[list[NodeBase], list[Exception]]:
    """
    Create links using a thread pool and wait for completion.

    :param session: session to create nodes in
    :param link_protos: link proto messages
    :return: results and exceptions for created links
    """
    funcs = []
    for link_proto in link_protos:
        node1_id = link_proto.node1_id
        node2_id = link_proto.node2_id
        iface1, iface2, options = add_link_data(link_proto)
        args = (node1_id, node2_id, iface1, iface2, options)
        funcs.append((session.add_link, args, {}))
    start = time.monotonic()
    results, exceptions = utils.threadpool(funcs)
    total = time.monotonic() - start
    logger.debug("grpc created links time: %s", total)
    return results, exceptions


def edit_links(
    session: Session, link_protos: list[core_pb2.Link]
) -> tuple[list[None], list[Exception]]:
    """
    Edit links using a thread pool and wait for completion.

    :param session: session to create nodes in
    :param link_protos: link proto messages
    :return: results and exceptions for created links
    """
    funcs = []
    for link_proto in link_protos:
        node1_id = link_proto.node1_id
        node2_id = link_proto.node2_id
        iface1, iface2, options = add_link_data(link_proto)
        args = (node1_id, node2_id, iface1.id, iface2.id, options)
        funcs.append((session.update_link, args, {}))
    start = time.monotonic()
    results, exceptions = utils.threadpool(funcs)
    total = time.monotonic() - start
    logger.debug("grpc edit links time: %s", total)
    return results, exceptions


def convert_value(value: Any) -> str:
    """
    Convert value into string.

    :param value: value
    :return: string conversion of the value
    """
    if value is not None:
        value = str(value)
    return value


def convert_session_options(session: Session) -> dict[str, common_pb2.ConfigOption]:
    config_options = {}
    for option in session.options.options:
        value = session.options.get(option.id)
        config_option = common_pb2.ConfigOption(
            label=option.label,
            name=option.id,
            value=value,
            type=option.type.value,
            select=option.options,
            group="Options",
        )
        config_options[option.id] = config_option
    return config_options


def get_config_options(
    config: dict[str, str],
    configurable_options: Union[ConfigurableOptions, type[ConfigurableOptions]],
) -> dict[str, common_pb2.ConfigOption]:
    """
    Retrieve configuration options in a form that is used by the grpc server.

    :param config: configuration
    :param configurable_options: configurable options
    :return: mapping of configuration ids to configuration options
    """
    results = {}
    for configuration in configurable_options.configurations():
        value = config.get(configuration.id, configuration.default)
        config_option = common_pb2.ConfigOption(
            label=configuration.label,
            name=configuration.id,
            value=value,
            type=configuration.type.value,
            select=configuration.options,
        )
        results[configuration.id] = config_option
    for config_group in configurable_options.config_groups():
        start = config_group.start - 1
        stop = config_group.stop
        options = list(results.values())[start:stop]
        for option in options:
            option.group = config_group.name
    return results


def get_node_proto(
    session: Session, node: NodeBase, emane_configs: list[NodeEmaneConfig]
) -> core_pb2.Node:
    """
    Convert CORE node to protobuf representation.

    :param session: session containing node
    :param node: node to convert
    :param emane_configs: emane configs related to node
    :return: node proto
    """
    node_type = session.get_node_type(node.__class__)
    position = core_pb2.Position(
        x=node.position.x, y=node.position.y, z=node.position.z
    )
    geo = core_pb2.Geo(
        lat=node.position.lat, lon=node.position.lon, alt=node.position.alt
    )
    services = [x.name for x in node.services]
    node_dir = None
    config_services = []
    if isinstance(node, CoreNodeBase):
        node_dir = str(node.directory)
        config_services = [x for x in node.config_services]
    channel = None
    if isinstance(node, CoreNode):
        channel = str(node.ctrlchnlname)
    emane_model = None
    if isinstance(node, EmaneNet):
        emane_model = node.wireless_model.name
    image = None
    if isinstance(node, (DockerNode, LxcNode, PodmanNode)):
        image = node.image
    # check for wlan config
    wlan_config = session.mobility.get_configs(
        node.id, config_type=BasicRangeModel.name
    )
    if wlan_config:
        wlan_config = get_config_options(wlan_config, BasicRangeModel)
    # check for wireless config
    wireless_config = None
    if isinstance(node, WirelessNode):
        configs = node.get_config()
        wireless_config = {}
        for config in configs.values():
            config_option = common_pb2.ConfigOption(
                label=config.label,
                name=config.id,
                value=config.default,
                type=config.type.value,
                select=config.options,
                group=config.group,
            )
            wireless_config[config.id] = config_option
    # check for mobility config
    mobility_config = session.mobility.get_configs(
        node.id, config_type=Ns2ScriptedMobility.name
    )
    if mobility_config:
        mobility_config = get_config_options(mobility_config, Ns2ScriptedMobility)
    # check for service configs
    custom_services = session.services.custom_services.get(node.id)
    service_configs = {}
    if custom_services:
        for service in custom_services.values():
            service_proto = get_service_configuration(service)
            service_configs[service.name] = NodeServiceConfig(
                node_id=node.id,
                service=service.name,
                data=service_proto,
                files=service.config_data,
            )
    # check for config service configs
    config_service_configs = {}
    if isinstance(node, CoreNode):
        for service in node.config_services.values():
            if not service.custom_templates and not service.custom_config:
                continue
            config_service_configs[service.name] = ConfigServiceConfig(
                node_id=node.id,
                name=service.name,
                templates=service.custom_templates,
                config=service.custom_config,
            )
    return core_pb2.Node(
        id=node.id,
        name=node.name,
        emane=emane_model,
        model=node.model,
        type=node_type.value,
        position=position,
        geo=geo,
        services=services,
        icon=node.icon,
        image=image,
        config_services=config_services,
        dir=node_dir,
        channel=channel,
        canvas=node.canvas,
        wlan_config=wlan_config,
        wireless_config=wireless_config,
        mobility_config=mobility_config,
        service_configs=service_configs,
        config_service_configs=config_service_configs,
        emane_configs=emane_configs,
    )


def get_links(session: Session, node: NodeBase) -> list[core_pb2.Link]:
    """
    Retrieve a list of links for grpc to use.

    :param session: session to get links for node
    :param node: node to get links from
    :return: protobuf links
    """
    link_protos = []
    for core_link in session.link_manager.node_links(node):
        link_protos.extend(convert_core_link(core_link))
    if isinstance(node, (WlanNode, EmaneNet)):
        for link_data in node.links():
            link_protos.append(convert_link_data(link_data))
    return link_protos


def convert_iface(iface: CoreInterface) -> core_pb2.Interface:
    """
    Convert interface to protobuf.

    :param iface: interface to convert
    :return: protobuf interface
    """
    if isinstance(iface.node, CoreNetwork):
        return core_pb2.Interface(id=iface.id)
    else:
        ip4 = iface.get_ip4()
        ip4_mask = ip4.prefixlen if ip4 else None
        ip4 = str(ip4.ip) if ip4 else None
        ip6 = iface.get_ip6()
        ip6_mask = ip6.prefixlen if ip6 else None
        ip6 = str(ip6.ip) if ip6 else None
        mac = str(iface.mac) if iface.mac else None
        return core_pb2.Interface(
            id=iface.id,
            name=iface.name,
            mac=mac,
            ip4=ip4,
            ip4_mask=ip4_mask,
            ip6=ip6,
            ip6_mask=ip6_mask,
        )


def convert_core_link(core_link: CoreLink) -> list[core_pb2.Link]:
    """
    Convert core link to protobuf data.

    :param core_link: core link to convert
    :return: protobuf link data
    """
    links = []
    node1, iface1 = core_link.node1, core_link.iface1
    node2, iface2 = core_link.node2, core_link.iface2
    unidirectional = core_link.is_unidirectional()
    link = convert_link(node1, iface1, node2, iface2, iface1.options, unidirectional)
    links.append(link)
    if unidirectional:
        link = convert_link(
            node2, iface2, node1, iface1, iface2.options, unidirectional
        )
        links.append(link)
    return links


def convert_link_data(link_data: LinkData) -> core_pb2.Link:
    """
    Convert link_data into core protobuf link.
    :param link_data: link to convert
    :return: core protobuf Link
    """
    iface1 = None
    if link_data.iface1 is not None:
        iface1 = convert_iface_data(link_data.iface1)
    iface2 = None
    if link_data.iface2 is not None:
        iface2 = convert_iface_data(link_data.iface2)
    options = convert_link_options(link_data.options)
    return core_pb2.Link(
        type=link_data.type.value,
        node1_id=link_data.node1_id,
        node2_id=link_data.node2_id,
        iface1=iface1,
        iface2=iface2,
        options=options,
        network_id=link_data.network_id,
        label=link_data.label,
        color=link_data.color,
    )


def convert_iface_data(iface_data: InterfaceData) -> core_pb2.Interface:
    """
    Convert interface data to protobuf.

    :param iface_data: interface data to convert
    :return: interface protobuf
    """
    return core_pb2.Interface(
        id=iface_data.id,
        name=iface_data.name,
        mac=iface_data.mac,
        ip4=iface_data.ip4,
        ip4_mask=iface_data.ip4_mask,
        ip6=iface_data.ip6,
        ip6_mask=iface_data.ip6_mask,
    )


def convert_link_options(options: LinkOptions) -> core_pb2.LinkOptions:
    """
    Convert link options to protobuf.

    :param options: link options to convert
    :return: link options protobuf
    """
    return core_pb2.LinkOptions(
        jitter=options.jitter,
        key=options.key,
        mburst=options.mburst,
        mer=options.mer,
        loss=options.loss,
        bandwidth=options.bandwidth,
        burst=options.burst,
        delay=options.delay,
        dup=options.dup,
        buffer=options.buffer,
        unidirectional=options.unidirectional,
    )


def convert_options_proto(options: core_pb2.LinkOptions) -> LinkOptions:
    return LinkOptions(
        delay=options.delay,
        bandwidth=options.bandwidth,
        loss=options.loss,
        dup=options.dup,
        jitter=options.jitter,
        mer=options.mer,
        burst=options.burst,
        mburst=options.mburst,
        buffer=options.buffer,
        unidirectional=options.unidirectional,
        key=options.key,
    )


def convert_link(
    node1: NodeBase,
    iface1: Optional[CoreInterface],
    node2: NodeBase,
    iface2: Optional[CoreInterface],
    options: LinkOptions,
    unidirectional: bool,
) -> core_pb2.Link:
    """
    Convert link objects to link protobuf.

    :param node1: first node in link
    :param iface1: node1 interface
    :param node2: second node in link
    :param iface2: node2 interface
    :param options: link options
    :param unidirectional: if this link is considered unidirectional
    :return: protobuf link
    """
    if iface1 is not None:
        iface1 = convert_iface(iface1)
    if iface2 is not None:
        iface2 = convert_iface(iface2)
    is_node1_wireless = isinstance(node1, (WlanNode, EmaneNet))
    is_node2_wireless = isinstance(node2, (WlanNode, EmaneNet))
    if not (is_node1_wireless or is_node2_wireless):
        options = convert_link_options(options)
        options.unidirectional = unidirectional
    else:
        options = None
    return core_pb2.Link(
        type=LinkTypes.WIRED.value,
        node1_id=node1.id,
        node2_id=node2.id,
        iface1=iface1,
        iface2=iface2,
        options=options,
        network_id=None,
        label=None,
        color=None,
    )


def parse_proc_net_dev(lines: list[str]) -> dict[str, dict[str, float]]:
    """
    Parse lines of output from /proc/net/dev.

    :param lines: lines of /proc/net/dev
    :return: parsed device to tx/rx values
    """
    stats = {}
    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue
        line = line.split()
        line[0] = line[0].strip(":")
        stats[line[0]] = {"rx": float(line[1]), "tx": float(line[9])}
    return stats


def get_net_stats() -> dict[str, dict[str, float]]:
    """
    Retrieve status about the current interfaces in the system

    :return: send and receive status of the interfaces in the system
    """
    with open("/proc/net/dev", "r") as f:
        lines = f.readlines()[2:]
    return parse_proc_net_dev(lines)


def session_location(session: Session, location: core_pb2.SessionLocation) -> None:
    """
    Set session location based on location proto.

    :param session: session for location
    :param location: location to set
    :return: nothing
    """
    session.location.refxyz = (location.x, location.y, location.z)
    session.location.setrefgeo(location.lat, location.lon, location.alt)
    session.location.refscale = location.scale


def service_configuration(session: Session, config: ServiceConfig) -> None:
    """
    Convenience method for setting a node service configuration.

    :param session: session for service configuration
    :param config: service configuration
    :return:
    """
    session.services.set_service(config.node_id, config.service)
    service = session.services.get_service(config.node_id, config.service)
    if config.files:
        service.configs = tuple(config.files)
    if config.directories:
        service.dirs = tuple(config.directories)
    if config.startup:
        service.startup = tuple(config.startup)
    if config.validate:
        service.validate = tuple(config.validate)
    if config.shutdown:
        service.shutdown = tuple(config.shutdown)


def get_service_configuration(service: CoreService) -> NodeServiceData:
    """
    Convenience for converting a service to service data proto.

    :param service: service to get proto data for
    :return: service proto data
    """
    return NodeServiceData(
        executables=service.executables,
        dependencies=service.dependencies,
        dirs=service.dirs,
        configs=service.configs,
        startup=service.startup,
        validate=service.validate,
        validation_mode=service.validation_mode.value,
        validation_timer=service.validation_timer,
        shutdown=service.shutdown,
        meta=service.meta,
    )


def iface_to_proto(session: Session, iface: CoreInterface) -> core_pb2.Interface:
    """
    Convenience for converting a core interface to the protobuf representation.

    :param session: session interface belongs to
    :param iface: interface to convert
    :return: interface proto
    """
    ip4_net = iface.get_ip4()
    ip4 = str(ip4_net.ip) if ip4_net else None
    ip4_mask = ip4_net.prefixlen if ip4_net else None
    ip6_net = iface.get_ip6()
    ip6 = str(ip6_net.ip) if ip6_net else None
    ip6_mask = ip6_net.prefixlen if ip6_net else None
    mac = str(iface.mac) if iface.mac else None
    nem_id = None
    nem_port = None
    if isinstance(iface.net, EmaneNet):
        nem_id = session.emane.get_nem_id(iface)
        nem_port = session.emane.get_nem_port(iface)
    return core_pb2.Interface(
        id=iface.id,
        name=iface.name,
        mac=mac,
        mtu=iface.mtu,
        flow_id=iface.flow_id,
        ip4=ip4,
        ip4_mask=ip4_mask,
        ip6=ip6,
        ip6_mask=ip6_mask,
        nem_id=nem_id,
        nem_port=nem_port,
    )


def get_nem_id(
    session: Session, node: CoreNode, iface_id: int, context: ServicerContext
) -> int:
    """
    Get nem id for a given node and interface id.

    :param session: session node belongs to
    :param node: node to get nem id for
    :param iface_id: id of interface on node to get nem id for
    :param context: request context
    :return: nem id
    """
    iface = node.ifaces.get(iface_id)
    if not iface:
        message = f"{node.name} missing interface {iface_id}"
        context.abort(grpc.StatusCode.NOT_FOUND, message)
    net = iface.net
    if not isinstance(net, EmaneNet):
        message = f"{node.name} interface {iface_id} is not an EMANE network"
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
    nem_id = session.emane.get_nem_id(iface)
    if nem_id is None:
        message = f"{node.name} interface {iface_id} nem id does not exist"
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
    return nem_id


def get_emane_model_configs_dict(session: Session) -> dict[int, list[NodeEmaneConfig]]:
    """
    Get emane model configuration protobuf data.

    :param session: session to get emane model configuration for
    :return: dict of emane model protobuf configurations
    """
    configs = {}
    for _id, model_configs in session.emane.node_configs.items():
        for model_name in model_configs:
            model_class = session.emane.get_model(model_name)
            current_config = session.emane.get_config(_id, model_name)
            config = get_config_options(current_config, model_class)
            node_id, iface_id = utils.parse_iface_config_id(_id)
            iface_id = iface_id if iface_id is not None else -1
            node_config = NodeEmaneConfig(
                model=model_name, iface_id=iface_id, config=config
            )
            node_configs = configs.setdefault(node_id, [])
            node_configs.append(node_config)
    return configs


def get_hooks(session: Session) -> list[core_pb2.Hook]:
    """
    Retrieve hook protobuf data for a session.

    :param session: session to get hooks for
    :return: list of hook protobufs
    """
    hooks = []
    for state in session.hooks:
        state_hooks = session.hooks[state]
        for file_name, file_data in state_hooks:
            hook = core_pb2.Hook(state=state.value, file=file_name, data=file_data)
            hooks.append(hook)
    return hooks


def get_default_services(session: Session) -> list[ServiceDefaults]:
    """
    Retrieve the default service sets for a given session.

    :param session: session to get default service sets for
    :return: list of default service sets
    """
    default_services = []
    for model, services in session.services.default_services.items():
        default_service = ServiceDefaults(model=model, services=services)
        default_services.append(default_service)
    return default_services


def get_mobility_node(
    session: Session, node_id: int, context: ServicerContext
) -> Union[WlanNode, EmaneNet]:
    """
    Get mobility node.

    :param session: session to get node from
    :param node_id: id of node to get
    :param context: grpc context
    :return: wlan or emane node
    """
    try:
        return session.get_node(node_id, WlanNode)
    except CoreError:
        try:
            return session.get_node(node_id, EmaneNet)
        except CoreError:
            context.abort(grpc.StatusCode.NOT_FOUND, "node id is not for wlan or emane")


def convert_session(session: Session) -> wrappers.Session:
    """
    Convert session to its wrapped version.

    :param session: session to convert
    :return: wrapped session data
    """
    emane_configs = get_emane_model_configs_dict(session)
    nodes = []
    links = []
    for _id in session.nodes:
        node = session.nodes[_id]
        if not isinstance(node, (PtpNet, CtrlNet)):
            node_emane_configs = emane_configs.get(node.id, [])
            node_proto = get_node_proto(session, node, node_emane_configs)
            nodes.append(node_proto)
        if isinstance(node, (WlanNode, EmaneNet)):
            for link_data in node.links():
                links.append(convert_link_data(link_data))
    for core_link in session.link_manager.links():
        links.extend(convert_core_link(core_link))
    default_services = get_default_services(session)
    x, y, z = session.location.refxyz
    lat, lon, alt = session.location.refgeo
    location = core_pb2.SessionLocation(
        x=x, y=y, z=z, lat=lat, lon=lon, alt=alt, scale=session.location.refscale
    )
    hooks = get_hooks(session)
    session_file = str(session.file_path) if session.file_path else None
    options = convert_session_options(session)
    servers = [
        core_pb2.Server(name=x.name, host=x.host)
        for x in session.distributed.servers.values()
    ]
    return core_pb2.Session(
        id=session.id,
        state=session.state.value,
        nodes=nodes,
        links=links,
        dir=str(session.directory),
        user=session.user,
        default_services=default_services,
        location=location,
        hooks=hooks,
        metadata=session.metadata,
        file=session_file,
        options=options,
        servers=servers,
    )


def configure_node(
    session: Session, node: core_pb2.Node, core_node: NodeBase, context: ServicerContext
) -> None:
    """
    Configure a node using all provided protobuf data.

    :param session: session for node
    :param node: node protobuf data
    :param core_node: session node
    :param context: grpc context
    :return: nothing
    """
    for emane_config in node.emane_configs:
        _id = utils.iface_config_id(node.id, emane_config.iface_id)
        config = {k: v.value for k, v in emane_config.config.items()}
        session.emane.set_config(_id, emane_config.model, config)
    if node.wlan_config:
        config = {k: v.value for k, v in node.wlan_config.items()}
        session.mobility.set_model_config(node.id, BasicRangeModel.name, config)
    if node.mobility_config:
        config = {k: v.value for k, v in node.mobility_config.items()}
        session.mobility.set_model_config(node.id, Ns2ScriptedMobility.name, config)
    if isinstance(core_node, WirelessNode) and node.wireless_config:
        config = {k: v.value for k, v in node.wireless_config.items()}
        core_node.set_config(config)
    for service_name, service_config in node.service_configs.items():
        data = service_config.data
        config = ServiceConfig(
            node_id=node.id,
            service=service_name,
            startup=data.startup,
            validate=data.validate,
            shutdown=data.shutdown,
            files=data.configs,
            directories=data.dirs,
        )
        service_configuration(session, config)
        for file_name, file_data in service_config.files.items():
            session.services.set_service_file(
                node.id, service_name, file_name, file_data
            )
    if node.config_service_configs:
        if not isinstance(core_node, CoreNode):
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "invalid node type with config service configs",
            )
        for service_name, service_config in node.config_service_configs.items():
            service = core_node.config_services[service_name]
            if service_config.config:
                service.set_config(service_config.config)
            for name, template in service_config.templates.items():
                service.set_template(name, template)
