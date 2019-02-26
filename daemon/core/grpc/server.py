import os

from core.emulator.emudata import NodeOptions
from core.enumerations import NodeTypes, EventTypes

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

    def CreateSession(self, request, context):
        session = self.coreemu.create_session()
        session.set_state(EventTypes.DEFINITION_STATE)

        # default set session location
        session.location.setrefgeo(47.57917, -122.13232, 2.0)
        session.location.refscale = 150000.0

        # grpc stream handlers
        # session.event_handlers.append(websocket_routes.broadcast_event)
        # session.node_handlers.append(websocket_routes.broadcast_node)
        # session.config_handlers.append(websocket_routes.broadcast_config)
        # session.link_handlers.append(websocket_routes.broadcast_link)
        # session.exception_handlers.append(websocket_routes.broadcast_exception)
        # session.file_handlers.append(websocket_routes.broadcast_file)

        response = core_pb2.CreateSessionResponse()
        response.id = session.session_id
        response.state = session.state
        return response

    def DeleteSession(self, request, context):
        response = core_pb2.DeleteSessionResponse()
        response.result = self.coreemu.delete_session(request.id)
        return response

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
        response = core_pb2.GetSessionLocationResponse()
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

    def SetSessionLocation(self, request, context):
        session = self.coreemu.sessions.get(request.id)

        session.location.refxyz = (request.position.x, request.position.y, request.position.z)
        session.location.setrefgeo(request.position.lat, request.position.lon, request.position.alt)
        session.location.refscale = request.scale

        return core_pb2.SetSessionLocationResponse()

    def SetSessionState(self, request, context):
        response = core_pb2.SetSessionStateResponse()
        session = self.coreemu.sessions.get(request.id)

        try:
            state = EventTypes(request.state)
            session.set_state(state)

            if state == EventTypes.INSTANTIATION_STATE:
                # create session directory if it does not exist
                if not os.path.exists(session.session_dir):
                    os.mkdir(session.session_dir)
                session.instantiate()
            elif state == EventTypes.SHUTDOWN_STATE:
                session.shutdown()
            elif state == EventTypes.DATACOLLECT_STATE:
                session.data_collect()
            elif state == EventTypes.DEFINITION_STATE:
                session.clear()

            response.result = True
        except KeyError:
            response.result = False

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
        if not session:
            raise Exception("no session found")

        response = core_pb2.SessionResponse()
        response.state = session.state

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

    def CreateNode(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        node_id = request.id
        node_type = request.type
        if node_type is None:
            node_type = NodeTypes.DEFAULT.value
        node_type = NodeTypes(node_type)
        logging.info("creating node: %s - %s", node_type.name, request)

        node_options = NodeOptions(name=request.name, model=request.model)
        node_options.icon = request.icon
        node_options.opaque = request.opaque
        node_options.services = request.services

        position = request.position
        node_options.set_position(position.x, position.y)
        node_options.set_location(position.lat, position.lon, position.alt)
        node = session.add_node(_type=node_type, _id=node_id, node_options=node_options)

        # configure emane if provided
        emane_model = request.emane
        if emane_model:
            session.emane.set_model_config(node_id, emane_model)

        response = core_pb2.CreateNodeResponse()
        response.id = node.objid
        return response

    def EditNode(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        node_id = request.id
        node_options = NodeOptions()
        x = request.position.x
        y = request.position.y
        node_options.set_position(x, y)
        lat = request.position.lat
        lon = request.position.lon
        alt = request.position.alt
        node_options.set_location(lat, lon, alt)
        logging.debug("updating node(%s) - pos(%s, %s) geo(%s, %s, %s)", node_id, x, y, lat, lon, alt)

        result = session.update_node(node_id, node_options)
        response = core_pb2.EditNodeResponse()
        response.result = result
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
