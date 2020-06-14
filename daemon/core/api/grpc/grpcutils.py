import logging
import time
from typing import Any, Dict, List, Tuple, Type, Union

import grpc
import netaddr
from grpc import ServicerContext

from core import utils
from core.api.grpc import common_pb2, core_pb2
from core.api.grpc.services_pb2 import NodeServiceData, ServiceConfig
from core.config import ConfigurableOptions
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData
from core.emulator.emudata import InterfaceData, LinkOptions, NodeOptions
from core.emulator.enumerations import LinkTypes, NodeTypes
from core.emulator.session import Session
from core.nodes.base import CoreNode, NodeBase
from core.nodes.interface import CoreInterface
from core.services.coreservices import CoreService

WORKERS = 10


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
        opaque=node_proto.opaque,
        image=node_proto.image,
        services=node_proto.services,
        config_services=node_proto.config_services,
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


def link_interface(interface_proto: core_pb2.Interface) -> InterfaceData:
    """
    Create interface data from interface proto.

    :param interface_proto: interface proto
    :return: interface data
    """
    interface_data = None
    if interface_proto:
        name = interface_proto.name if interface_proto.name else None
        mac = interface_proto.mac if interface_proto.mac else None
        ip4 = interface_proto.ip4 if interface_proto.ip4 else None
        ip6 = interface_proto.ip6 if interface_proto.ip6 else None
        interface_data = InterfaceData(
            id=interface_proto.id,
            name=name,
            mac=mac,
            ip4=ip4,
            ip4_mask=interface_proto.ip4mask,
            ip6=ip6,
            ip6_mask=interface_proto.ip6mask,
        )
    return interface_data


def add_link_data(
    link_proto: core_pb2.Link
) -> Tuple[InterfaceData, InterfaceData, LinkOptions]:
    """
    Convert link proto to link interfaces and options data.

    :param link_proto: link  proto
    :return: link interfaces and options
    """
    interface1_data = link_interface(link_proto.interface1)
    interface2_data = link_interface(link_proto.interface2)
    link_type = LinkTypes(link_proto.type)
    options = LinkOptions(type=link_type)
    options_data = link_proto.options
    if options_data:
        options.delay = options_data.delay
        options.bandwidth = options_data.bandwidth
        options.loss = options_data.loss
        options.dup = options_data.dup
        options.jitter = options_data.jitter
        options.mer = options_data.mer
        options.burst = options_data.burst
        options.mburst = options_data.mburst
        options.unidirectional = options_data.unidirectional
        options.key = options_data.key
        options.opaque = options_data.opaque
    return interface1_data, interface2_data, options


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
    logging.debug("grpc created nodes time: %s", total)
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
        interface1, interface2, options = add_link_data(link_proto)
        args = (node1_id, node2_id, interface1, interface2, options)
        funcs.append((session.add_link, args, {}))
    start = time.monotonic()
    results, exceptions = utils.threadpool(funcs)
    total = time.monotonic() - start
    logging.debug("grpc created links time: %s", total)
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
        interface1, interface2, options = add_link_data(link_proto)
        args = (node1_id, node2_id, interface1.id, interface2.id, options)
        funcs.append((session.update_link, args, {}))
    start = time.monotonic()
    results, exceptions = utils.threadpool(funcs)
    total = time.monotonic() - start
    logging.debug("grpc edit links time: %s", total)
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
        value = config[configuration.id]
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


def get_node_proto(session: Session, node: NodeBase) -> core_pb2.Node:
    """
    Convert CORE node to protobuf representation.

    :param session: session containing node
    :param node: node to convert
    :return: node proto
    """
    node_type = session.get_node_type(node.__class__)
    position = core_pb2.Position(
        x=node.position.x, y=node.position.y, z=node.position.z
    )
    geo = core_pb2.Geo(
        lat=node.position.lat, lon=node.position.lon, alt=node.position.alt
    )
    services = getattr(node, "services", [])
    if services is None:
        services = []
    services = [x.name for x in services]
    config_services = getattr(node, "config_services", {})
    config_services = [x for x in config_services]
    emane_model = None
    if isinstance(node, EmaneNet):
        emane_model = node.model.name
    model = getattr(node, "type", None)
    node_dir = getattr(node, "nodedir", None)
    channel = getattr(node, "ctrlchnlname", None)
    image = getattr(node, "image", None)
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
    )


def get_links(node: NodeBase):
    """
    Retrieve a list of links for grpc to use.

    :param node: node to get links from
    :return: protobuf links
    """
    links = []
    for link_data in node.all_link_data():
        link = convert_link(link_data)
        links.append(link)
    return links


def get_emane_model_id(node_id: int, interface_id: int) -> int:
    """
    Get EMANE model id

    :param node_id: node id
    :param interface_id: interface id
    :return: EMANE model id
    """
    if interface_id >= 0:
        return node_id * 1000 + interface_id
    else:
        return node_id


def parse_emane_model_id(_id: int) -> Tuple[int, int]:
    """
    Parses EMANE model id to get true node id and interface id.

    :param _id: id to parse
    :return: node id and interface id
    """
    interface = -1
    node_id = _id
    if _id >= 1000:
        interface = _id % 1000
        node_id = int(_id / 1000)
    return node_id, interface


def convert_link(link_data: LinkData) -> core_pb2.Link:
    """
    Convert link_data into core protobuf link.

    :param link_data: link to convert
    :return: core protobuf Link
    """
    interface1 = None
    if link_data.interface1_id is not None:
        interface1 = core_pb2.Interface(
            id=link_data.interface1_id,
            name=link_data.interface1_name,
            mac=convert_value(link_data.interface1_mac),
            ip4=convert_value(link_data.interface1_ip4),
            ip4mask=link_data.interface1_ip4_mask,
            ip6=convert_value(link_data.interface1_ip6),
            ip6mask=link_data.interface1_ip6_mask,
        )
    interface2 = None
    if link_data.interface2_id is not None:
        interface2 = core_pb2.Interface(
            id=link_data.interface2_id,
            name=link_data.interface2_name,
            mac=convert_value(link_data.interface2_mac),
            ip4=convert_value(link_data.interface2_ip4),
            ip4mask=link_data.interface2_ip4_mask,
            ip6=convert_value(link_data.interface2_ip6),
            ip6mask=link_data.interface2_ip6_mask,
        )
    options = core_pb2.LinkOptions(
        opaque=link_data.opaque,
        jitter=link_data.jitter,
        key=link_data.key,
        mburst=link_data.mburst,
        mer=link_data.mer,
        loss=link_data.loss,
        bandwidth=link_data.bandwidth,
        burst=link_data.burst,
        delay=link_data.delay,
        dup=link_data.dup,
        unidirectional=link_data.unidirectional,
    )
    return core_pb2.Link(
        type=link_data.link_type.value,
        node1_id=link_data.node1_id,
        node2_id=link_data.node2_id,
        interface1=interface1,
        interface2=interface2,
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


def interface_to_proto(interface: CoreInterface) -> core_pb2.Interface:
    """
    Convenience for converting a core interface to the protobuf representation.
    :param interface: interface to convert
    :return: interface proto
    """
    net_id = None
    if interface.net:
        net_id = interface.net.id
    ip4 = None
    ip4mask = None
    ip6 = None
    ip6mask = None
    for addr in interface.addrlist:
        network = netaddr.IPNetwork(addr)
        mask = network.prefixlen
        ip = str(network.ip)
        if netaddr.valid_ipv4(ip) and not ip4:
            ip4 = ip
            ip4mask = mask
        elif netaddr.valid_ipv6(ip) and not ip6:
            ip6 = ip
            ip6mask = mask
    return core_pb2.Interface(
        id=interface.netindex,
        netid=net_id,
        name=interface.name,
        mac=str(interface.hwaddr),
        mtu=interface.mtu,
        flowid=interface.flow_id,
        ip4=ip4,
        ip4mask=ip4mask,
        ip6=ip6,
        ip6mask=ip6mask,
    )


def get_nem_id(node: CoreNode, netif_id: int, context: ServicerContext) -> int:
    """
    Get nem id for a given node and interface id.

    :param node: node to get nem id for
    :param netif_id: id of interface on node to get nem id for
    :param context: request context
    :return: nem id
    """
    netif = node.netif(netif_id)
    if not netif:
        message = f"{node.name} missing interface {netif_id}"
        context.abort(grpc.StatusCode.NOT_FOUND, message)
    net = netif.net
    if not isinstance(net, EmaneNet):
        message = f"{node.name} interface {netif_id} is not an EMANE network"
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
    return net.getnemid(netif)
