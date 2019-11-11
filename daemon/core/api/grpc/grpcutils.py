import logging
import time

from core import utils
from core.api.grpc import core_pb2
from core.emulator.emudata import InterfaceData, LinkOptions, NodeOptions
from core.emulator.enumerations import LinkTypes, NodeTypes
from core.nodes.base import CoreNetworkBase
from core.nodes.ipaddress import MacAddress

WORKERS = 10


def add_node_data(node_proto):
    """
    Convert node protobuf message to data for creating a node.

    :param core_pb2.Node node_proto: node proto message
    :return: node type, id, and options
    :rtype: tuple
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
    if node_proto.server:
        options.server = node_proto.server

    position = node_proto.position
    options.set_position(position.x, position.y)
    options.set_location(position.lat, position.lon, position.alt)
    return _type, _id, options


def link_interface(interface_proto):
    """
    Create interface data from interface proto.

    :param core_pb2.Interface interface_proto: interface proto
    :return: interface data
    :rtype: InterfaceData
    """
    interface = None
    if interface_proto:
        name = interface_proto.name
        if name == "":
            name = None
        mac = interface_proto.mac
        if mac == "":
            mac = None
        else:
            mac = MacAddress.from_string(mac)
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


def add_link_data(link_proto):
    """
    Convert link proto to link interfaces and options data.

    :param core_pb2.Link link_proto: link  proto
    :return: link interfaces and options
    :rtype: tuple
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


def create_nodes(session, node_protos):
    """
    Create nodes using a thread pool and wait for completion.

    :param core.emulator.session.Session session: session to create nodes in
    :param list[core_pb2.Node] node_protos: node proto messages
    :return: results and exceptions for created nodes
    :rtype: tuple
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


def create_links(session, link_protos):
    """
    Create nodes using a thread pool and wait for completion.

    :param core.emulator.session.Session session: session to create nodes in
    :param list[core_pb2.Link] link_protos: link proto messages
    :return: results and exceptions for created links
    :rtype: tuple
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


def convert_value(value):
    """
    Convert value into string.

    :param value: value
    :return: string conversion of the value
    :rtype: str
    """
    if value is not None:
        value = str(value)
    return value


def get_config_options(config, configurable_options):
    """
    Retrieve configuration options in a form that is used by the grpc server.

    :param dict config: configuration
    :param core.config.ConfigurableOptions configurable_options: configurable options
    :return: mapping of configuration ids to configuration options
    :rtype: dict[str,core.api.grpc.core_pb2.ConfigOption]
    """
    results = {}
    for configuration in configurable_options.configurations():
        value = config[configuration.id]
        config_option = core_pb2.ConfigOption(
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


def get_links(session, node):
    """
    Retrieve a list of links for grpc to use

    :param core.emulator.Session session: node's section
    :param core.nodes.base.CoreNode node: node to get links from
    :return: [core.api.grpc.core_pb2.Link]
    """
    links = []
    for link_data in node.all_link_data(0):
        link = convert_link(session, link_data)
        links.append(link)
    return links


def get_emane_model_id(node_id, interface_id):
    """
    Get EMANE model id

    :param int node_id: node id
    :param int interface_id: interface id
    :return: EMANE model id
    :rtype: int
    """
    if interface_id >= 0:
        return node_id * 1000 + interface_id
    else:
        return node_id


def convert_link(session, link_data):
    """
    Convert link_data into core protobuf Link

    :param core.emulator.session.Session session:
    :param core.emulator.data.LinkData link_data:
    :return: core protobuf Link
    :rtype: core.api.grpc.core_pb2.Link
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


def get_net_stats():
    """
    Retrieve status about the current interfaces in the system

    :return: send and receive status of the interfaces in the system
    :rtype: dict
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


def session_location(session, location):
    """
    Set session location based on location proto.

    :param core.emulator.session.Session session: session for location
    :param core_pb2.SessionLocation location: location to set
    :return: nothing
    """
    session.location.refxyz = (location.x, location.y, location.z)
    session.location.setrefgeo(location.lat, location.lon, location.alt)
    session.location.refscale = location.scale


def service_configuration(session, config):
    """
    Convenience method for setting a node service configuration.

    :param core.emulator.session.Session session: session for service configuration
    :param core_pb2.ServiceConfig config: service configuration
    :return:
    """
    session.services.set_service(config.node_id, config.service)
    service = session.services.get_service(config.node_id, config.service)
    service.startup = tuple(config.startup)
    service.validate = tuple(config.validate)
    service.shutdown = tuple(config.shutdown)
