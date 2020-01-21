import logging
import time
from typing import Any, Dict, List, Tuple, Type

from core import utils
from core.api.grpc import common_pb2, core_pb2
from core.config import ConfigurableOptions
from core.emulator.data import LinkData
from core.emulator.emudata import InterfaceData, LinkOptions, NodeOptions
from core.emulator.enumerations import LinkTypes, NodeTypes
from core.emulator.session import Session
from core.nodes.base import CoreNetworkBase, NodeBase
from core.services.coreservices import CoreService

WORKERS = 10


def add_node_data(node_proto: core_pb2.Node) -> Tuple[NodeTypes, int, NodeOptions]:
    """
    Convert node protobuf message to data for creating a node.

    :param node_proto: node proto message
    :return: node type, id, and options
    """
    _id = node_proto.id
    _type = node_proto.type
    if _type is None:
        _type = NodeTypes.DEFAULT.value
    _type = NodeTypes(_type)

    options = NodeOptions(name=node_proto.name, model=node_proto.model)
    options.icon = node_proto.icon
    options.opaque = node_proto.opaque
    options.image = node_proto.image
    options.services = node_proto.services
    if node_proto.emane:
        options.emane = node_proto.emane
    if node_proto.server:
        options.server = node_proto.server

    position = node_proto.position
    options.set_position(position.x, position.y)
    options.set_location(position.lat, position.lon, position.alt)
    return _type, _id, options


def link_interface(interface_proto: core_pb2.Interface) -> InterfaceData:
    """
    Create interface data from interface proto.

    :param interface_proto: interface proto
    :return: interface data
    """
    interface = None
    if interface_proto:
        name = interface_proto.name
        if name == "":
            name = None
        mac = interface_proto.mac
        if mac == "":
            mac = None
        interface = InterfaceData(
            _id=interface_proto.id,
            name=name,
            mac=mac,
            ip4=interface_proto.ip4,
            ip4_mask=interface_proto.ip4mask,
            ip6=interface_proto.ip6,
            ip6_mask=interface_proto.ip6mask,
        )
    return interface


def add_link_data(
    link_proto: core_pb2.Link
) -> Tuple[InterfaceData, InterfaceData, LinkOptions]:
    """
    Convert link proto to link interfaces and options data.

    :param link_proto: link  proto
    :return: link interfaces and options
    """
    interface_one = link_interface(link_proto.interface_one)
    interface_two = link_interface(link_proto.interface_two)

    link_type = None
    link_type_value = link_proto.type
    if link_type_value is not None:
        link_type = LinkTypes(link_type_value)

    options = LinkOptions(_type=link_type)
    options_data = link_proto.options
    if options_data:
        options.delay = options_data.delay
        options.bandwidth = options_data.bandwidth
        options.per = options_data.per
        options.dup = options_data.dup
        options.jitter = options_data.jitter
        options.mer = options_data.mer
        options.burst = options_data.burst
        options.mburst = options_data.mburst
        options.unidirectional = options_data.unidirectional
        options.key = options_data.key
        options.opaque = options_data.opaque

    return interface_one, interface_two, options


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
        args = (_type, _id, options)
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
        node_one_id = link_proto.node_one_id
        node_two_id = link_proto.node_two_id
        interface_one, interface_two, options = add_link_data(link_proto)
        args = (node_one_id, node_two_id, interface_one, interface_two, options)
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
        node_one_id = link_proto.node_one_id
        node_two_id = link_proto.node_two_id
        interface_one, interface_two, options = add_link_data(link_proto)
        args = (node_one_id, node_two_id, interface_one.id, interface_two.id, options)
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
    config: Dict[str, str], configurable_options: Type[ConfigurableOptions]
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


def get_links(session: Session, node: NodeBase):
    """
    Retrieve a list of links for grpc to use

    :param session: node's section
    :param node: node to get links from
    :return: [core.api.grpc.core_pb2.Link]
    """
    links = []
    for link_data in node.all_link_data(0):
        link = convert_link(session, link_data)
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


def convert_link(session: Session, link_data: LinkData) -> core_pb2.Link:
    """
    Convert link_data into core protobuf Link

    :param session:
    :param link_data:
    :return: core protobuf Link
    """
    interface_one = None
    if link_data.interface1_id is not None:
        node = session.get_node(link_data.node1_id)
        interface_name = None
        if not isinstance(node, CoreNetworkBase):
            interface = node.netif(link_data.interface1_id)
            interface_name = interface.name
        interface_one = core_pb2.Interface(
            id=link_data.interface1_id,
            name=interface_name,
            mac=convert_value(link_data.interface1_mac),
            ip4=convert_value(link_data.interface1_ip4),
            ip4mask=link_data.interface1_ip4_mask,
            ip6=convert_value(link_data.interface1_ip6),
            ip6mask=link_data.interface1_ip6_mask,
        )

    interface_two = None
    if link_data.interface2_id is not None:
        node = session.get_node(link_data.node2_id)
        interface_name = None
        if not isinstance(node, CoreNetworkBase):
            interface = node.netif(link_data.interface2_id)
            interface_name = interface.name
        interface_two = core_pb2.Interface(
            id=link_data.interface2_id,
            name=interface_name,
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
        per=link_data.per,
        bandwidth=link_data.bandwidth,
        burst=link_data.burst,
        delay=link_data.delay,
        dup=link_data.dup,
        unidirectional=link_data.unidirectional,
    )

    return core_pb2.Link(
        type=link_data.link_type,
        node_one_id=link_data.node1_id,
        node_two_id=link_data.node2_id,
        interface_one=interface_one,
        interface_two=interface_two,
        options=options,
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


def service_configuration(session: Session, config: core_pb2.ServiceConfig) -> None:
    """
    Convenience method for setting a node service configuration.

    :param session: session for service configuration
    :param config: service configuration
    :return:
    """
    session.services.set_service(config.node_id, config.service)
    service = session.services.get_service(config.node_id, config.service)
    service.startup = tuple(config.startup)
    service.validate = tuple(config.validate)
    service.shutdown = tuple(config.shutdown)


def get_service_configuration(service: Type[CoreService]) -> core_pb2.NodeServiceData:
    """
    Convenience for converting a service to service data proto.

    :param service: service to get proto data for
    :return: service proto data
    """
    return core_pb2.NodeServiceData(
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
