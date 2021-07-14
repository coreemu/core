import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type, Union

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
from core.emane.nodes import EmaneNet
from core.emulator.data import InterfaceData, LinkData, LinkOptions, NodeOptions
from core.emulator.enumerations import LinkTypes, NodeTypes
from core.emulator.session import Session
from core.errors import CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import CoreNode, CoreNodeBase, NodeBase
from core.nodes.docker import DockerNode
from core.nodes.interface import CoreInterface
from core.nodes.lxd import LxcNode
from core.nodes.network import CtrlNet, PtpNet, WlanNode
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


def add_node_data(node_proto: core_pb2.Node) -> Tuple[NodeTypes, int, NodeOptions]:
    """
    Convert node protobuf message to data for creating a node.

    :param node_proto: node proto message
    :return: node type, id, and options
    """
    _id = node_proto.id
    _type = NodeTypes(node_proto.type)
    options = NodeOptions(
        name=node_proto.name,
        model=node_proto.model,
        icon=node_proto.icon,
        image=node_proto.image,
        services=node_proto.services,
        config_services=node_proto.config_services,
        canvas=node_proto.canvas,
    )
    if node_proto.emane:
        options.emane = node_proto.emane
    if node_proto.server:
        options.server = node_proto.server
    position = node_proto.position
    options.set_position(position.x, position.y)
    if node_proto.HasField("geo"):
        geo = node_proto.geo
        options.set_location(geo.lat, geo.lon, geo.alt)
    return _type, _id, options


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
    link_proto: core_pb2.Link
) -> Tuple[InterfaceData, InterfaceData, LinkOptions, LinkTypes]:
    """
    Convert link proto to link interfaces and options data.

    :param link_proto: link  proto
    :return: link interfaces and options
    """
    iface1_data = link_iface(link_proto.iface1)
    iface2_data = link_iface(link_proto.iface2)
    link_type = LinkTypes(link_proto.type)
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
    return iface1_data, iface2_data, options, link_type


def create_nodes(
    session: Session, node_protos: List[core_pb2.Node]
) -> Tuple[List[NodeBase], List[Exception]]:
    """
    Create nodes using a thread pool and wait for completion.

    :param session: session to create nodes in
    :param node_protos: node proto messages
    :return: results and exceptions for created nodes
    """
    funcs = []
    for node_proto in node_protos:
        _type, _id, options = add_node_data(node_proto)
        _class = session.get_node_class(_type)
        args = (_class, _id, options)
        funcs.append((session.add_node, args, {}))
    start = time.monotonic()
    results, exceptions = utils.threadpool(funcs)
    total = time.monotonic() - start
    logger.debug("grpc created nodes time: %s", total)
    return results, exceptions


def create_links(
    session: Session, link_protos: List[core_pb2.Link]
) -> Tuple[List[NodeBase], List[Exception]]:
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
        iface1, iface2, options, link_type = add_link_data(link_proto)
        args = (node1_id, node2_id, iface1, iface2, options, link_type)
        funcs.append((session.add_link, args, {}))
    start = time.monotonic()
    results, exceptions = utils.threadpool(funcs)
    total = time.monotonic() - start
    logger.debug("grpc created links time: %s", total)
    return results, exceptions


def edit_links(
    session: Session, link_protos: List[core_pb2.Link]
) -> Tuple[List[None], List[Exception]]:
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
        iface1, iface2, options, link_type = add_link_data(link_proto)
        args = (node1_id, node2_id, iface1.id, iface2.id, options, link_type)
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


def get_config_options(
    config: Dict[str, str],
    configurable_options: Union[ConfigurableOptions, Type[ConfigurableOptions]],
) -> Dict[str, common_pb2.ConfigOption]:
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
    session: Session, node: NodeBase, emane_configs: List[NodeEmaneConfig]
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
    model = node.type
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
        emane_model = node.model.name
    image = None
    if isinstance(node, (DockerNode, LxcNode)):
        image = node.image
    # check for wlan config
    wlan_config = session.mobility.get_configs(
        node.id, config_type=BasicRangeModel.name
    )
    if wlan_config:
        wlan_config = get_config_options(wlan_config, BasicRangeModel)
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
        model=model,
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
        mobility_config=mobility_config,
        service_configs=service_configs,
        config_service_configs=config_service_configs,
        emane_configs=emane_configs,
    )


def get_links(node: NodeBase):
    """
    Retrieve a list of links for grpc to use.

    :param node: node to get links from
    :return: protobuf links
    """
    links = []
    for link in node.links():
        link_proto = convert_link(link)
        links.append(link_proto)
    return links


def convert_iface(iface_data: InterfaceData) -> core_pb2.Interface:
    return core_pb2.Interface(
        id=iface_data.id,
        name=iface_data.name,
        mac=iface_data.mac,
        ip4=iface_data.ip4,
        ip4_mask=iface_data.ip4_mask,
        ip6=iface_data.ip6,
        ip6_mask=iface_data.ip6_mask,
    )


def convert_link_options(options_data: LinkOptions) -> core_pb2.LinkOptions:
    return core_pb2.LinkOptions(
        jitter=options_data.jitter,
        key=options_data.key,
        mburst=options_data.mburst,
        mer=options_data.mer,
        loss=options_data.loss,
        bandwidth=options_data.bandwidth,
        burst=options_data.burst,
        delay=options_data.delay,
        dup=options_data.dup,
        buffer=options_data.buffer,
        unidirectional=options_data.unidirectional,
    )


def convert_link(link_data: LinkData) -> core_pb2.Link:
    """
    Convert link_data into core protobuf link.

    :param link_data: link to convert
    :return: core protobuf Link
    """
    iface1 = None
    if link_data.iface1 is not None:
        iface1 = convert_iface(link_data.iface1)
    iface2 = None
    if link_data.iface2 is not None:
        iface2 = convert_iface(link_data.iface2)
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


def get_net_stats() -> Dict[str, Dict]:
    """
    Retrieve status about the current interfaces in the system

    :return: send and receive status of the interfaces in the system
    """
    with open("/proc/net/dev", "r") as f:
        data = f.readlines()[2:]

    stats = {}
    for line in data:
        line = line.strip()
        if not line:
            continue
        line = line.split()
        line[0] = line[0].strip(":")
        stats[line[0]] = {"rx": float(line[1]), "tx": float(line[9])}

    return stats


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


def iface_to_data(iface: CoreInterface) -> InterfaceData:
    ip4 = iface.get_ip4()
    ip4_addr = str(ip4.ip) if ip4 else None
    ip4_mask = ip4.prefixlen if ip4 else None
    ip6 = iface.get_ip6()
    ip6_addr = str(ip6.ip) if ip6 else None
    ip6_mask = ip6.prefixlen if ip6 else None
    return InterfaceData(
        id=iface.node_id,
        name=iface.name,
        mac=str(iface.mac),
        ip4=ip4_addr,
        ip4_mask=ip4_mask,
        ip6=ip6_addr,
        ip6_mask=ip6_mask,
    )


def iface_to_proto(node_id: int, iface: CoreInterface) -> core_pb2.Interface:
    """
    Convenience for converting a core interface to the protobuf representation.

    :param node_id: id of node to convert interface for
    :param iface: interface to convert
    :return: interface proto
    """
    if iface.node and iface.node.id == node_id:
        _id = iface.node_id
    else:
        _id = iface.net_id
    net_id = iface.net.id if iface.net else None
    node_id = iface.node.id if iface.node else None
    net2_id = iface.othernet.id if iface.othernet else None
    ip4_net = iface.get_ip4()
    ip4 = str(ip4_net.ip) if ip4_net else None
    ip4_mask = ip4_net.prefixlen if ip4_net else None
    ip6_net = iface.get_ip6()
    ip6 = str(ip6_net.ip) if ip6_net else None
    ip6_mask = ip6_net.prefixlen if ip6_net else None
    mac = str(iface.mac) if iface.mac else None
    return core_pb2.Interface(
        id=_id,
        net_id=net_id,
        net2_id=net2_id,
        node_id=node_id,
        name=iface.name,
        mac=mac,
        mtu=iface.mtu,
        flow_id=iface.flow_id,
        ip4=ip4,
        ip4_mask=ip4_mask,
        ip6=ip6,
        ip6_mask=ip6_mask,
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


def get_emane_model_configs_dict(session: Session) -> Dict[int, List[NodeEmaneConfig]]:
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


def get_hooks(session: Session) -> List[core_pb2.Hook]:
    hooks = []
    for state in session.hooks:
        state_hooks = session.hooks[state]
        for file_name, file_data in state_hooks:
            hook = core_pb2.Hook(state=state.value, file=file_name, data=file_data)
            hooks.append(hook)
    return hooks


def get_default_services(session: Session) -> List[ServiceDefaults]:
    default_services = []
    for name, services in session.services.default_services.items():
        default_service = ServiceDefaults(node_type=name, services=services)
        default_services.append(default_service)
    return default_services


def get_mobility_node(
    session: Session, node_id: int, context: ServicerContext
) -> Union[WlanNode, EmaneNet]:
    try:
        return session.get_node(node_id, WlanNode)
    except CoreError:
        try:
            return session.get_node(node_id, EmaneNet)
        except CoreError:
            context.abort(grpc.StatusCode.NOT_FOUND, "node id is not for wlan or emane")


def convert_session(session: Session) -> wrappers.Session:
    links = []
    nodes = []
    emane_configs = get_emane_model_configs_dict(session)
    for _id in session.nodes:
        node = session.nodes[_id]
        if not isinstance(node, (PtpNet, CtrlNet)):
            node_emane_configs = emane_configs.get(node.id, [])
            node_proto = get_node_proto(session, node, node_emane_configs)
            nodes.append(node_proto)
        node_links = get_links(node)
        links.extend(node_links)
    default_services = get_default_services(session)
    x, y, z = session.location.refxyz
    lat, lon, alt = session.location.refgeo
    location = core_pb2.SessionLocation(
        x=x, y=y, z=z, lat=lat, lon=lon, alt=alt, scale=session.location.refscale
    )
    hooks = get_hooks(session)
    session_file = str(session.file_path) if session.file_path else None
    options = get_config_options(session.options.get_configs(), session.options)
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
