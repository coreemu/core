from core.enumerations import NodeTypes

from concurrent import futures
import time
import logging

import grpc

import core_pb2
import core_pb2_grpc
from core.misc import nodeutils

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def convert_value(value):
    if value is None:
        return value
    else:
        return str(value)


def update_proto(obj, **kwargs):
    for key in kwargs:
        value = kwargs[key]
        if value is not None:
            logging.info("setting proto key(%s) value(%s)", key, value)
            setattr(obj, key, value)


def convert_link(session, link_data, link):
    if link_data.interface1_id is not None:
        node = session.get_object(link_data.node1_id)
        interface = node.netif(link_data.interface1_id)
        link.interface_one.id = link_data.interface1_id
        link.interface_one.name = interface.name
        update_proto(
            link.interface_one,
            mac=convert_value(link_data.interface1_mac),
            ip4=convert_value(link_data.interface1_ip4),
            ip4mask=link_data.interface1_ip4_mask,
            ip6=convert_value(link_data.interface1_ip6),
            ip6mask=link_data.interface1_ip6_mask
        )

    if link_data.interface2_id is not None:
        node = session.get_object(link_data.node2_id)
        interface = node.netif(link_data.interface2_id)
        link.interface_two.id = link_data.interface2_id
        link.interface_two.name = interface.name
        update_proto(
            link.interface_two,
            mac=convert_value(link_data.interface2_mac),
            ip4=convert_value(link_data.interface2_ip4),
            ip4mask=link_data.interface2_ip4_mask,
            ip6=convert_value(link_data.interface2_ip6),
            ip6mask=link_data.interface2_ip6_mask
        )

    link.node_one = link_data.node1_id
    link.node_two = link_data.node2_id
    link.type = link_data.link_type
    update_proto(
        link.options,
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
        unidirectional=link_data.unidirectional
    )


class CoreApiServer(core_pb2_grpc.CoreApiServicer):
    def __init__(self, coreemu):
        super(CoreApiServer, self).__init__()
        self.coreemu = coreemu

    def GetSessions(self, request, context):
        response = core_pb2.SessionsResponse()
        for session_id in self.coreemu.sessions:
            session = self.coreemu.sessions[session_id]
            session_data = response.sessions.add()
            session_data.id = session_id
            session_data.state = session.state
            session_data.nodes = session.get_node_count()
        return response

    def GetSessionLocation(self, request, context):
        session = self.coreemu.sessions.get(request.id)
        x, y, z = session.location.refxyz
        lat, lon, alt = session.location.refgeo
        response = core_pb2.SessionLocationResponse()
        update_proto(
            response.position,
            x=x,
            y=y,
            z=z,
            lat=lat,
            lon=lon,
            alt=alt
        )
        update_proto(response, scale=session.location.refscale)
        return response

    def GetSessionOptions(self, request, context):
        session = self.coreemu.sessions.get(request.id)
        config = session.options.get_configs()

        response = core_pb2.SessionOptionsResponse()
        config_options = []
        for configuration in session.options.configurations():
            value = config[configuration.id]
            config_option = core_pb2.ConfigOption()
            config_option.label = configuration.label
            config_option.name = configuration.id
            config_option.value = value
            config_option.type = configuration.type.value
            config_option.select.extend(configuration.options)
            config_options.append(config_option)

        for config_group in session.options.config_groups():
            start = config_group.start - 1
            stop = config_group.stop
            config_group_proto = response.groups.add()
            config_group_proto.name = config_group.name
            config_group_proto.options.extend(config_options[start: stop])

        return response

    def GetSession(self, request, context):
        session = self.coreemu.sessions.get(request.id)
        if not request:
            pass

        response = core_pb2.SessionResponse()
        for node_id in session.objects:
            node = session.objects[node_id]

            if not isinstance(node.objid, int):
                continue

            node_proto = response.nodes.add()
            node_proto.id = node.objid
            node_proto.name = node.name
            node_proto.type = nodeutils.get_node_type(node.__class__).value
            model = getattr(node, "type", None)
            if model is not None:
                node_proto.model = model

            update_proto(
                node_proto.position,
                x=node.position.x,
                y=node.position.y,
                z=node.position.z
            )

            services = getattr(node, "services", [])
            if services is None:
                services = []
            services = [x.name for x in services]
            node_proto.services.extend(services)

            emane_model = None
            if nodeutils.is_node(node, NodeTypes.EMANE):
                emane_model = node.model.name
            if emane_model is not None:
                node_proto.emane = emane_model

            links_data = node.all_link_data(0)
            for link_data in links_data:
                link = response.links.add()
                convert_link(session, link_data, link)

        return response


def listen(coreemu, address="[::]:50051"):
    logging.info("starting grpc api: %s", address)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    core_pb2_grpc.add_CoreApiServicer_to_server(CoreApiServer(coreemu), server)
    server.add_insecure_port(address)
    server.start()

    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)
