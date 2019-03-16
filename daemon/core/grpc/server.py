import os
import tempfile

from core.emulator.emudata import NodeOptions, InterfaceData, LinkOptions
from core.enumerations import NodeTypes, EventTypes, LinkTypes

from concurrent import futures
import time
import logging

import grpc

import core_pb2
import core_pb2_grpc
from core.misc import nodeutils
from core.service import ServiceManager

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
            setattr(obj, key, value)


def get_config_groups(config, configurable_options):
    groups = []
    config_options = []

    for configuration in configurable_options.configurations():
        value = config[configuration.id]
        config_option = core_pb2.ConfigOption()
        config_option.label = configuration.label
        config_option.name = configuration.id
        config_option.value = value
        config_option.type = configuration.type.value
        config_option.select.extend(configuration.options)
        config_options.append(config_option)

    for config_group in configurable_options.config_groups():
        start = config_group.start - 1
        stop = config_group.stop
        config_group_proto = core_pb2.ConfigGroup()
        config_group_proto.name = config_group.name
        config_group_proto.options.extend(config_options[start: stop])
        groups.append(config_group_proto)

    return groups


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

        response = core_pb2.SetSessionLocationResponse()
        response.result = True
        return response

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
        defaults = session.options.default_values()
        defaults.update(config)

        groups = get_config_groups(defaults, session.options)

        response = core_pb2.SessionOptionsResponse()
        response.groups.extend(groups)
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

    def GetNode(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")
        node = session.get_object(request.id)
        if not node:
            raise Exception("no node found")

        response = core_pb2.GetNodeResponse()

        for interface_id, interface in node._netif.iteritems():
            net_id = None
            if interface.net:
                net_id = interface.net.objid

            interface_proto = response.interfaces.add()
            interface_proto.id = interface_id
            interface_proto.netid = net_id
            interface_proto.name = interface.name
            interface_proto.mac = str(interface.hwaddr)
            interface_proto.mtu = interface.mtu
            interface_proto.flowid = interface.flow_id

        emane_model = None
        if nodeutils.is_node(node, NodeTypes.EMANE):
            emane_model = node.model.name

        update_proto(
            response.node,
            name=node.name,
            type=nodeutils.get_node_type(node.__class__).value,
            emane=emane_model,
            model=node.type
        )

        update_proto(
            response.node.position,
            x=node.position.x,
            y=node.position.y,
            z=node.position.z,
        )

        services = [x.name for x in getattr(node, "services", [])]
        response.node.services.extend(services)
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

    def DeleteNode(self, request, context):
        logging.info("delete node: %s", request)
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        response = core_pb2.DeleteNodeResponse()
        response.result = session.delete_node(request.id)
        return response

    def GetNodeLinks(self, request, context):
        logging.info("get node links: %s", request)
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")
        node = session.get_object(request.id)
        if not node:
            raise Exception("no node found")

        response = core_pb2.GetNodeLinksResponse()
        links_data = node.all_link_data(0)
        for link_data in links_data:
            link = response.links.add()
            convert_link(session, link_data, link)

        return response

    def CreateLink(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        logging.info("adding link: %s", request)

        node_one = request.link.node_one
        node_two = request.link.node_two

        interface_one = None
        interface_one_data = request.link.interface_one
        if interface_one_data:
            name = interface_one_data.name
            if name == "":
                name = None
            mac = interface_one_data.mac
            if mac == "":
                mac = None
            interface_one = InterfaceData(
                _id=interface_one_data.id,
                name=name,
                mac=mac,
                ip4=interface_one_data.ip4,
                ip4_mask=interface_one_data.ip4mask,
                ip6=interface_one_data.ip6,
                ip6_mask=interface_one_data.ip6mask,
            )

        interface_two = None
        interface_two_data = request.link.interface_two
        if interface_two_data:
            name = interface_two_data.name
            if name == "":
                name = None
            mac = interface_two_data.mac
            if mac == "":
                mac = None
            interface_two = InterfaceData(
                _id=interface_two_data.id,
                name=name,
                mac=mac,
                ip4=interface_two_data.ip4,
                ip4_mask=interface_two_data.ip4mask,
                ip6=interface_two_data.ip6,
                ip6_mask=interface_two_data.ip6mask,
            )

        link_type = None
        link_type_value = request.link.type
        if link_type_value is not None:
            link_type = LinkTypes(link_type_value)

        options_data = request.link.options
        link_options = LinkOptions(_type=link_type)
        if options_data:
            link_options.delay = options_data.delay
            link_options.bandwidth = options_data.bandwidth
            link_options.per = options_data.per
            link_options.dup = options_data.dup
            link_options.jitter = options_data.jitter
            link_options.mer = options_data.mer
            link_options.burst = options_data.burst
            link_options.mburst = options_data.mburst
            link_options.unidirectional = options_data.unidirectional
            link_options.key = options_data.key
            link_options.opaque = options_data.opaque

        session.add_link(node_one, node_two, interface_one, interface_two, link_options=link_options)

        response = core_pb2.CreateLinkResponse()
        response.result = True
        return response

    def EditLink(self, request, context):
        logging.info("edit link: %s", request)
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        node_one = request.node_one
        node_two = request.node_two
        interface_one_id = request.interface_one
        interface_two_id = request.interface_two

        options_data = request.options
        link_options = LinkOptions()
        link_options.delay = options_data.delay
        link_options.bandwidth = options_data.bandwidth
        link_options.per = options_data.per
        link_options.dup = options_data.dup
        link_options.jitter = options_data.jitter
        link_options.mer = options_data.mer
        link_options.burst = options_data.burst
        link_options.mburst = options_data.mburst
        link_options.unidirectional = options_data.unidirectional
        link_options.key = options_data.key
        link_options.opaque = options_data.opaque

        session.update_link(node_one, node_two, interface_one_id, interface_two_id, link_options)

        response = core_pb2.EditLinkResponse()
        response.result = True
        return response

    def DeleteLink(self, request, context):
        logging.info("delete link: %s", request)
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        node_one = request.node_one
        node_two = request.node_two
        interface_one = request.interface_one
        interface_two = request.interface_two
        session.delete_link(node_one, node_two, interface_one, interface_two)

        response = core_pb2.DeleteLinkResponse()
        response.result = True
        return response

    def GetHooks(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        response = core_pb2.GetHooksResponse()
        for state, state_hooks in session._hooks.iteritems():
            for file_name, file_data in state_hooks:
                hook = response.hooks.add()
                hook.state = state
                hook.file = file_name
                hook.data = file_data

        return response

    def AddHook(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        hook = request.hook
        session.add_hook(hook.state, hook.file, None, hook.data)
        response = core_pb2.AddHookResponse()
        response.result = True
        return response

    def GetServices(self, request, context):
        response = core_pb2.GetServicesResponse()
        for service in ServiceManager.services.itervalues():
            service_proto = response.services.add()
            service_proto.group = service.group
            service_proto.name = service.name
        return response

    def GetServiceDefaults(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        response = core_pb2.GetServiceDefaultsResponse()
        for node_type in session.services.default_services:
            services = session.services.default_services[node_type]
            service_defaults = response.defaults.add()
            service_defaults.node_type = node_type
            service_defaults.services.extend(services)
        return response

    def SetServiceDefaults(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        session.services.default_services.clear()
        for service_defaults in request.defaults:
            session.services.default_services[service_defaults.node_type] = service_defaults.services

        response = core_pb2.SetServiceDefaultsResponse()
        response.result = True
        return response

    def GetNodeService(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")
        node = session.get_object(request.id)
        if not node:
            raise Exception("no node found")

        service = session.services.get_service(node.objid, request.service, default_service=True)
        response = core_pb2.GetNodeServiceResponse()
        response.service.executables.extend(service.executables)
        response.service.dependencies.extend(service.dependencies)
        response.service.dirs.extend(service.dirs)
        response.service.configs.extend(service.configs)
        response.service.startup.extend(service.startup)
        response.service.validate.extend(service.validate)
        response.service.validation_mode = service.validation_mode.value
        response.service.validation_timer = service.validation_timer
        response.service.shutdown.extend(service.shutdown)
        if service.meta:
            response.service.meta = service.meta
        return response

    def GetEmaneConfig(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")
        config = session.emane.get_configs()
        groups = get_config_groups(config, session.emane.emane_config)
        response = core_pb2.GetEmaneConfigResponse()
        response.groups.extend(groups)
        return response

    def SetEmaneConfig(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        session.emane.set_configs(request.config)
        response = core_pb2.SetEmaneConfigResponse()
        response.result = True
        return response

    def GetEmaneModels(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        models = []
        for model in session.emane.models.keys():
            if len(model.split("_")) != 2:
                continue
            models.append(model)

        response = core_pb2.GetEmaneModelsResponse()
        response.models.extend(models)
        return response

    def GetEmaneModelConfig(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")
        node = session.get_object(request.id)
        if not node:
            raise Exception("no node found")

        model = session.emane.models[request.model]
        config = session.emane.get_model_config(node.objid, request.model)
        groups = get_config_groups(config, model)
        response = core_pb2.GetEmaneModelConfigResponse()
        response.groups.extend(groups)
        return response

    def SetEmaneModelConfig(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        session.emane.set_model_config(request.id, request.model, request.config)
        response = core_pb2.SetEmaneModelConfigResponse()
        response.result = True
        return response

    def GetEmaneModelConfigs(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        response = core_pb2.GetEmaneModelConfigsResponse()
        for node_id, model_config in session.emane.node_configurations.iteritems():
            if node_id == -1:
                continue

            for model_name in model_config.iterkeys():
                model = session.emane.models[model_name]
                config = session.emane.get_model_config(node_id, model_name)
                config_groups = get_config_groups(config, model)
                # node_configurations = response.setdefault(node_id, {})
                node_configurations = response.configs[node_id]
                node_configurations.model = model_name
                node_configurations.groups.extend(config_groups)
                # node_configurations[model_name] = config_groups
        return response

    def SaveXml(self, request, context):
        session = self.coreemu.sessions.get(request.session)
        if not session:
            raise Exception("no session found")

        _, temp_path = tempfile.mkstemp()
        session.save_xml(temp_path)

        with open(temp_path, "rb") as xml_file:
            data = xml_file.read()

        response = core_pb2.SaveXmlResponse()
        response.data = data
        return response

    def OpenXml(self, request, context):
        session = self.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)

        _, temp_path = tempfile.mkstemp()
        with open(temp_path, "wb") as xml_file:
            xml_file.write(request.data)

        response = core_pb2.OpenXmlResponse()
        try:
            session.open_xml(temp_path, start=True)
            response.session = session.session_id
            response.result = True
        except:
            response.result = False
            logging.exception("error opening session file")
            self.coreemu.delete_session(session.session_id)

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
