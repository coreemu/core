import atexit
import logging
import os
import tempfile
import time
from Queue import Queue, Empty
from core.data import NodeData, LinkData, EventData, ConfigData, ExceptionData, FileData

import grpc
from concurrent import futures

from core.emulator.emudata import NodeOptions, InterfaceData, LinkOptions
from core.enumerations import NodeTypes, EventTypes, LinkTypes
from core.grpc import core_pb2
from core.grpc import core_pb2_grpc
from core.misc import nodeutils
from core.misc.ipaddress import MacAddress
from core.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.service import ServiceManager

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def convert_value(value):
    if value is not None:
        value = str(value)
    return value


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
        options = config_options[start: stop]
        config_group_proto = core_pb2.ConfigGroup(name=config_group.name, options=options)
        groups.append(config_group_proto)

    return groups


def get_links(session, node):
    links = []
    for link_data in node.all_link_data(0):
        link = convert_link(session, link_data)
        links.append(link)
    return links


def get_emane_model_id(node_id, interface_id):
    if interface_id >= 0:
        return node_id * 1000 + interface_id
    else:
        return node_id


def convert_link(session, link_data):
    interface_one = None
    if link_data.interface1_id is not None:
        node = session.get_object(link_data.node1_id)
        interface = node.netif(link_data.interface1_id)
        interface_one = core_pb2.Interface(
            id=link_data.interface1_id, name=interface.name, mac=convert_value(link_data.interface1_mac),
            ip4=convert_value(link_data.interface1_ip4), ip4mask=link_data.interface1_ip4_mask,
            ip6=convert_value(link_data.interface1_ip6), ip6mask=link_data.interface1_ip6_mask)

    interface_two = None
    if link_data.interface2_id is not None:
        node = session.get_object(link_data.node2_id)
        interface = node.netif(link_data.interface2_id)
        interface_two = core_pb2.Interface(
            id=link_data.interface2_id, name=interface.name, mac=convert_value(link_data.interface2_mac),
            ip4=convert_value(link_data.interface2_ip4), ip4mask=link_data.interface2_ip4_mask,
            ip6=convert_value(link_data.interface2_ip6), ip6mask=link_data.interface2_ip6_mask)

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
        unidirectional=link_data.unidirectional
    )

    return core_pb2.Link(
        type=link_data.link_type, node_one_id=link_data.node1_id, node_two_id=link_data.node2_id,
        interface_one=interface_one, interface_two=interface_two, options=options
    )


class CoreGrpcServer(core_pb2_grpc.CoreApiServicer):
    def __init__(self, coreemu):
        super(CoreGrpcServer, self).__init__()
        self.coreemu = coreemu
        self.running = True
        self.server = None
        atexit.register(self._exit_handler)

    def _exit_handler(self):
        logging.debug("catching exit, stop running")
        self.running = False

    def _is_running(self, context):
        return self.running and context.is_active()

    def _cancel_stream(self, context):
        context.abort(grpc.StatusCode.CANCELLED, "server stopping")

    def listen(self, address="[::]:50051"):
        logging.info("starting grpc api: %s", address)
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        core_pb2_grpc.add_CoreApiServicer_to_server(self, self.server)
        self.server.add_insecure_port(address)
        self.server.start()

        try:
            while True:
                time.sleep(_ONE_DAY_IN_SECONDS)
        except KeyboardInterrupt:
            self.server.stop(None)

    def get_session(self, session_id, context):
        session = self.coreemu.sessions.get(session_id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "session {} not found".format(session_id))
        return session

    def get_node(self, session, node_id, context):
        try:
            return session.get_object(node_id)
        except KeyError:
            context.abort(grpc.StatusCode.NOT_FOUND, "node {} not found".format(node_id))

    def CreateSession(self, request, context):
        logging.debug("create session: %s", request)
        session = self.coreemu.create_session(request.session_id)
        session.set_state(EventTypes.DEFINITION_STATE)
        session.location.setrefgeo(47.57917, -122.13232, 2.0)
        session.location.refscale = 150000.0
        return core_pb2.CreateSessionResponse(session_id=session.id, state=session.state)

    def DeleteSession(self, request, context):
        logging.debug("delete session: %s", request)
        result = self.coreemu.delete_session(request.session_id)
        return core_pb2.DeleteSessionResponse(result=result)

    def GetSessions(self, request, context):
        logging.debug("get sessions: %s", request)
        sessions = []
        for session_id in self.coreemu.sessions:
            session = self.coreemu.sessions[session_id]
            session_summary = core_pb2.SessionSummary(
                id=session_id, state=session.state, nodes=session.get_node_count())
            sessions.append(session_summary)
        return core_pb2.GetSessionsResponse(sessions=sessions)

    def GetSessionLocation(self, request, context):
        logging.debug("get session location: %s", request)
        session = self.get_session(request.session_id, context)
        x, y, z = session.location.refxyz
        lat, lon, alt = session.location.refgeo
        position = core_pb2.Position(x=x, y=y, z=z, lat=lat, lon=lon, alt=alt)
        return core_pb2.GetSessionLocationResponse(position=position, scale=session.location.refscale)

    def SetSessionLocation(self, request, context):
        logging.debug("set session location: %s", request)
        session = self.get_session(request.session_id, context)
        session.location.refxyz = (request.position.x, request.position.y, request.position.z)
        session.location.setrefgeo(request.position.lat, request.position.lon, request.position.alt)
        session.location.refscale = request.scale
        return core_pb2.SetSessionLocationResponse(result=True)

    def SetSessionState(self, request, context):
        logging.debug("set session state: %s", request)
        session = self.get_session(request.session_id, context)

        try:
            state = EventTypes(request.state)
            session.set_state(state)

            if state == EventTypes.INSTANTIATION_STATE:
                if not os.path.exists(session.session_dir):
                    os.mkdir(session.session_dir)
                session.instantiate()
            elif state == EventTypes.SHUTDOWN_STATE:
                session.shutdown()
            elif state == EventTypes.DATACOLLECT_STATE:
                session.data_collect()
            elif state == EventTypes.DEFINITION_STATE:
                session.clear()

            result = True
        except KeyError:
            result = False

        return core_pb2.SetSessionStateResponse(result=result)

    def GetSessionOptions(self, request, context):
        logging.debug("get session options: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.options.get_configs()
        defaults = session.options.default_values()
        defaults.update(config)
        groups = get_config_groups(defaults, session.options)
        return core_pb2.GetSessionOptionsResponse(groups=groups)

    def SetSessionOptions(self, request, context):
        logging.debug("set session options: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.options.get_configs()
        config.update(request.config)
        return core_pb2.SetSessionOptionsResponse(result=True)

    def GetSession(self, request, context):
        logging.debug("get session: %s", request)
        session = self.get_session(request.session_id, context)

        links = []
        nodes = []
        for node_id in session.objects:
            node = session.objects[node_id]
            if not isinstance(node.objid, int):
                continue

            node_type = nodeutils.get_node_type(node.__class__).value
            model = getattr(node, "type", None)
            position = core_pb2.Position(x=node.position.x, y=node.position.y, z=node.position.z)

            services = getattr(node, "services", [])
            if services is None:
                services = []
            services = [x.name for x in services]

            emane_model = None
            if nodeutils.is_node(node, NodeTypes.EMANE):
                emane_model = node.model.name

            node_proto = core_pb2.Node(
                id=node.objid, name=node.name, emane=emane_model, model=model,
                type=node_type, position=position, services=services)
            nodes.append(node_proto)

            node_links = get_links(session, node)
            links.extend(node_links)

        session_proto = core_pb2.Session(state=session.state, nodes=nodes, links=links)
        return core_pb2.GetSessionResponse(session=session_proto)

    def Events(self, request, context):
        session = self.get_session(request.session_id, context)
        queue = Queue()
        session.node_handlers.append(queue.put)
        session.link_handlers.append(queue.put)
        session.config_handlers.append(queue.put)
        session.file_handlers.append(queue.put)
        session.exception_handlers.append(queue.put)
        session.event_handlers.append(queue.put)

        while self._is_running(context):
            event = core_pb2.Event()
            try:
                data = queue.get(timeout=1)
                if isinstance(data, NodeData):
                    event.node_event.CopyFrom(self._handle_node_event(data))
                elif isinstance(data, LinkData):
                    event.link_event.CopyFrom(self._handle_link_event(data))
                elif isinstance(data, EventData):
                    event.session_event.CopyFrom(self._handle_session_event(data))
                elif isinstance(data, ConfigData):
                    event.config_event.CopyFrom(self._handle_config_event(data))
                    # TODO: remove when config events are fixed
                    event.config_event.session_id = session.id
                elif isinstance(data, ExceptionData):
                    event.exception_event.CopyFrom(self._handle_exception_event(data))
                elif isinstance(data, FileData):
                    event.file_event.CopyFrom(self._handle_file_event(data))
                else:
                    logging.error("unknown event: %s", data)
                    continue

                yield event
            except Empty:
                continue

        session.node_handlers.remove(queue.put)
        session.link_handlers.remove(queue.put)
        session.config_handlers.remove(queue.put)
        session.file_handlers.remove(queue.put)
        session.exception_handlers.remove(queue.put)
        session.event_handlers.remove(queue.put)
        self._cancel_stream(context)

    def _handle_node_event(self, event):
        position = core_pb2.Position(x=event.x_position, y=event.y_position)
        services = event.services or ""
        services = services.split("|")
        node_proto = core_pb2.Node(
            id=event.id, name=event.name, model=event.model, position=position, services=services)
        return core_pb2.NodeEvent(node=node_proto)

    def _handle_link_event(self, event):
        interface_one = None
        if event.interface1_id is not None:
            interface_one = core_pb2.Interface(
                id=event.interface1_id, name=event.interface1_name, mac=convert_value(event.interface1_mac),
                ip4=convert_value(event.interface1_ip4), ip4mask=event.interface1_ip4_mask,
                ip6=convert_value(event.interface1_ip6), ip6mask=event.interface1_ip6_mask)

        interface_two = None
        if event.interface2_id is not None:
            interface_two = core_pb2.Interface(
                id=event.interface2_id, name=event.interface2_name, mac=convert_value(event.interface2_mac),
                ip4=convert_value(event.interface2_ip4), ip4mask=event.interface2_ip4_mask,
                ip6=convert_value(event.interface2_ip6), ip6mask=event.interface2_ip6_mask)

        options = core_pb2.LinkOptions(
            opaque=event.opaque,
            jitter=event.jitter,
            key=event.key,
            mburst=event.mburst,
            mer=event.mer,
            per=event.per,
            bandwidth=event.bandwidth,
            burst=event.burst,
            delay=event.delay,
            dup=event.dup,
            unidirectional=event.unidirectional
        )
        link = core_pb2.Link(
            type=event.link_type, node_one_id=event.node1_id, node_two_id=event.node2_id,
            interface_one=interface_one, interface_two=interface_two, options=options)
        return core_pb2.LinkEvent(message_type=event.message_type, link=link)

    def _handle_session_event(self, event):
        event_time = event.time
        if event_time is not None:
            event_time = float(event_time)
        return core_pb2.SessionEvent(
            node_id=event.node,
            event=event.event_type,
            name=event.name,
            data=event.data,
            time=event_time,
            session_id=event.session
        )

    def _handle_config_event(self, event):
        session_id = None
        if event.session is not None:
            session_id = int(event.session)
        return core_pb2.ConfigEvent(
            message_type=event.message_type,
            node_id=event.node,
            object=event.object,
            type=event.type,
            captions=event.captions,
            bitmap=event.bitmap,
            data_values=event.data_values,
            possible_values=event.possible_values,
            groups=event.groups,
            session_id=session_id,
            interface=event.interface_number,
            network_id=event.network_id,
            opaque=event.opaque,
            data_types=event.data_types
        )

    def _handle_exception_event(self, event):
        return core_pb2.ExceptionEvent(
            node_id=event.node,
            session_id=int(event.session),
            level=event.level.value,
            source=event.source,
            date=event.date,
            text=event.text,
            opaque=event.opaque
        )

    def _handle_file_event(self, event):
        return core_pb2.FileEvent(
            message_type=event.message_type,
            node_id=event.node,
            name=event.name,
            mode=event.mode,
            number=event.number,
            type=event.type,
            source=event.source,
            session_id=event.session,
            data=event.data,
            compressed_data=event.compressed_data
        )

    def AddNode(self, request, context):
        logging.debug("add node: %s", request)
        session = self.get_session(request.session_id, context)

        node_proto = request.node
        node_id = node_proto.id
        node_type = node_proto.type
        if node_type is None:
            node_type = NodeTypes.DEFAULT.value
        node_type = NodeTypes(node_type)

        node_options = NodeOptions(name=node_proto.name, model=node_proto.model)
        node_options.icon = node_proto.icon
        node_options.opaque = node_proto.opaque
        node_options.services = node_proto.services

        position = node_proto.position
        node_options.set_position(position.x, position.y)
        node_options.set_location(position.lat, position.lon, position.alt)
        node = session.add_node(_type=node_type, _id=node_id, node_options=node_options)

        # configure emane if provided
        emane_model = node_proto.emane
        if emane_model:
            session.emane.set_model_config(node_id, emane_model)

        return core_pb2.AddNodeResponse(node_id=node.objid)

    def GetNode(self, request, context):
        logging.debug("get node: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)

        interfaces = []
        for interface_id, interface in node._netif.iteritems():
            net_id = None
            if interface.net:
                net_id = interface.net.objid
            interface_proto = core_pb2.Interface(
                id=interface_id, netid=net_id, name=interface.name, mac=str(interface.hwaddr),
                mtu=interface.mtu, flowid=interface.flow_id)
            interfaces.append(interface_proto)

        emane_model = None
        if nodeutils.is_node(node, NodeTypes.EMANE):
            emane_model = node.model.name

        services = [x.name for x in getattr(node, "services", [])]
        position = core_pb2.Position(x=node.position.x, y=node.position.y, z=node.position.z)
        node_type = nodeutils.get_node_type(node.__class__).value
        node = core_pb2.Node(
            id=node.objid, name=node.name, type=node_type, emane=emane_model, model=node.type, position=position,
            services=services)

        return core_pb2.GetNodeResponse(node=node, interfaces=interfaces)

    def EditNode(self, request, context):
        logging.debug("edit node: %s", request)
        session = self.get_session(request.session_id, context)
        node_id = request.node_id
        node_options = NodeOptions()
        x = request.position.x
        y = request.position.y
        node_options.set_position(x, y)
        lat = request.position.lat
        lon = request.position.lon
        alt = request.position.alt
        node_options.set_location(lat, lon, alt)
        result = session.update_node(node_id, node_options)
        return core_pb2.EditNodeResponse(result=result)

    def DeleteNode(self, request, context):
        logging.debug("delete node: %s", request)
        session = self.get_session(request.session_id, context)
        result = session.delete_node(request.node_id)
        return core_pb2.DeleteNodeResponse(result=result)

    def GetNodeLinks(self, request, context):
        logging.debug("get node links: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        links = get_links(session, node)
        return core_pb2.GetNodeLinksResponse(links=links)

    def AddLink(self, request, context):
        logging.debug("add link: %s", request)
        session = self.get_session(request.session_id, context)

        # validate node exist
        self.get_node(session, request.link.node_one_id, context)
        self.get_node(session, request.link.node_two_id, context)
        node_one_id = request.link.node_one_id
        node_two_id = request.link.node_two_id

        interface_one = None
        interface_one_data = request.link.interface_one
        if interface_one_data:
            name = interface_one_data.name
            if name == "":
                name = None
            mac = interface_one_data.mac
            if mac == "":
                mac = None
            else:
                mac = MacAddress.from_string(mac)
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
            else:
                mac = MacAddress.from_string(mac)
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

        session.add_link(node_one_id, node_two_id, interface_one, interface_two, link_options=link_options)
        return core_pb2.AddLinkResponse(result=True)

    def EditLink(self, request, context):
        logging.debug("edit link: %s", request)
        session = self.get_session(request.session_id, context)
        node_one_id = request.node_one_id
        node_two_id = request.node_two_id
        interface_one_id = request.interface_one_id
        interface_two_id = request.interface_two_id
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
        session.update_link(node_one_id, node_two_id, interface_one_id, interface_two_id, link_options)
        return core_pb2.EditLinkResponse(result=True)

    def DeleteLink(self, request, context):
        logging.debug("delete link: %s", request)
        session = self.get_session(request.session_id, context)
        node_one_id = request.node_one_id
        node_two_id = request.node_two_id
        interface_one_id = request.interface_one_id
        interface_two_id = request.interface_two_id
        session.delete_link(node_one_id, node_two_id, interface_one_id, interface_two_id)
        return core_pb2.DeleteLinkResponse(result=True)

    def GetHooks(self, request, context):
        logging.debug("get hooks: %s", request)
        session = self.get_session(request.session_id, context)
        hooks = []
        for state, state_hooks in session._hooks.iteritems():
            for file_name, file_data in state_hooks:
                hook = core_pb2.Hook(state=state, file=file_name, data=file_data)
                hooks.append(hook)
        return core_pb2.GetHooksResponse(hooks=hooks)

    def AddHook(self, request, context):
        logging.debug("add hook: %s", request)
        session = self.get_session(request.session_id, context)
        hook = request.hook
        session.add_hook(hook.state, hook.file, None, hook.data)
        return core_pb2.AddHookResponse(result=True)

    def GetMobilityConfigs(self, request, context):
        logging.debug("get mobility configs: %s", request)
        session = self.get_session(request.session_id, context)
        response = core_pb2.GetMobilityConfigsResponse()
        for node_id, model_config in session.mobility.node_configurations.iteritems():
            if node_id == -1:
                continue
            for model_name in model_config.iterkeys():
                if model_name != Ns2ScriptedMobility.name:
                    continue
                config = session.mobility.get_model_config(node_id, model_name)
                groups = get_config_groups(config, Ns2ScriptedMobility)
                response.configs[node_id].groups.extend(groups)
        return response

    def GetMobilityConfig(self, request, context):
        logging.debug("get mobility config: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.mobility.get_model_config(request.node_id, Ns2ScriptedMobility.name)
        groups = get_config_groups(config, Ns2ScriptedMobility)
        return core_pb2.GetMobilityConfigResponse(groups=groups)

    def SetMobilityConfig(self, request, context):
        logging.debug("set mobility config: %s", request)
        session = self.get_session(request.session_id, context)
        session.mobility.set_model_config(request.node_id, Ns2ScriptedMobility.name, request.config)
        return core_pb2.SetMobilityConfigResponse(result=True)

    def MobilityAction(self, request, context):
        logging.debug("mobility action: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        result = True
        if request.action == core_pb2.MobilityAction.START:
            node.mobility.start()
        elif request.action == core_pb2.MobilityAction.PAUSE:
            node.mobility.pause()
        elif request.action == core_pb2.MobilityAction.STOP:
            node.mobility.stop(move_initial=True)
        else:
            result = False
        return core_pb2.MobilityActionResponse(result=result)

    def GetServices(self, request, context):
        logging.debug("get services: %s", request)
        services = []
        for service in ServiceManager.services.itervalues():
            service_proto = core_pb2.Service(group=service.group, name=service.name)
            services.append(service_proto)
        return core_pb2.GetServicesResponse(services=services)

    def GetServiceDefaults(self, request, context):
        logging.debug("get service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        all_service_defaults = []
        for node_type in session.services.default_services:
            services = session.services.default_services[node_type]
            service_defaults = core_pb2.ServiceDefaults(node_type=node_type, services=services)
            all_service_defaults.append(service_defaults)
        return core_pb2.GetServiceDefaultsResponse(defaults=all_service_defaults)

    def SetServiceDefaults(self, request, context):
        logging.debug("set service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        session.services.default_services.clear()
        for service_defaults in request.defaults:
            session.services.default_services[service_defaults.node_type] = service_defaults.services
        return core_pb2.SetServiceDefaultsResponse(result=True)

    def GetNodeService(self, request, context):
        logging.debug("get node service: %s", request)
        session = self.get_session(request.session_id, context)
        service = session.services.get_service(request.node_id, request.service, default_service=True)
        service_proto = core_pb2.NodeServiceData(
            executables=service.executables,
            dependencies=service.dependencies,
            dirs=service.dirs,
            configs=service.configs,
            startup=service.startup,
            validate=service.validate,
            validation_mode=service.validation_mode.value,
            validation_timer=service.validation_timer,
            shutdown=service.shutdown,
            meta=service.meta
        )
        return core_pb2.GetNodeServiceResponse(service=service_proto)

    def GetNodeServiceFile(self, request, context):
        logging.debug("get node service file: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        service = None
        for current_service in node.services:
            if current_service.name == request.service:
                service = current_service
                break
        if not service:
            context.abort(grpc.StatusCode.NOT_FOUND, "service not found")
        file_data = session.services.get_service_file(node, request.service, request.file)
        return core_pb2.GetNodeServiceFileResponse(data=file_data.data)

    def SetNodeService(self, request, context):
        logging.debug("set node service: %s", request)
        session = self.get_session(request.session_id, context)
        session.services.set_service(request.node_id, request.service)
        service = session.services.get_service(request.node_id, request.service)
        service.startup = tuple(request.startup)
        service.validate = tuple(request.validate)
        service.shutdown = tuple(request.shutdown)
        return core_pb2.SetNodeServiceResponse(result=True)

    def SetNodeServiceFile(self, request, context):
        logging.debug("set node service file: %s", request)
        session = self.get_session(request.session_id, context)
        session.services.set_service_file(request.node_id, request.service, request.file, request.data)
        return core_pb2.SetNodeServiceFileResponse(result=True)

    def ServiceAction(self, request, context):
        logging.debug("service action: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        service = None
        for current_service in node.services:
            if current_service.name == request.service:
                service = current_service
                break

        if not service:
            context.abort(grpc.StatusCode.NOT_FOUND, "service not found")

        status = -1
        if request.action == core_pb2.ServiceAction.START:
            status = session.services.startup_service(node, service, wait=True)
        elif request.action == core_pb2.ServiceAction.STOP:
            status = session.services.stop_service(node, service)
        elif request.action == core_pb2.ServiceAction.RESTART:
            status = session.services.stop_service(node, service)
            if not status:
                status = session.services.startup_service(node, service, wait=True)
        elif request.action == core_pb2.ServiceAction.VALIDATE:
            status = session.services.validate_service(node, service)

        result = False
        if not status:
            result = True

        return core_pb2.ServiceActionResponse(result=result)

    def GetWlanConfig(self, request, context):
        logging.debug("get wlan config: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.mobility.get_model_config(request.node_id, BasicRangeModel.name)
        groups = get_config_groups(config, BasicRangeModel)
        return core_pb2.GetWlanConfigResponse(groups=groups)

    def SetWlanConfig(self, request, context):
        logging.debug("set wlan config: %s", request)
        session = self.get_session(request.session_id, context)
        session.mobility.set_model_config(request.node_id, BasicRangeModel.name, request.config)
        return core_pb2.SetWlanConfigResponse(result=True)

    def GetEmaneConfig(self, request, context):
        logging.debug("get emane config: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.emane.get_configs()
        groups = get_config_groups(config, session.emane.emane_config)
        return core_pb2.GetEmaneConfigResponse(groups=groups)

    def SetEmaneConfig(self, request, context):
        logging.debug("set emane config: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.emane.get_configs()
        config.update(request.config)
        return core_pb2.SetEmaneConfigResponse(result=True)

    def GetEmaneModels(self, request, context):
        logging.debug("get emane models: %s", request)
        session = self.get_session(request.session_id, context)
        models = []
        for model in session.emane.models.keys():
            if len(model.split("_")) != 2:
                continue
            models.append(model)
        return core_pb2.GetEmaneModelsResponse(models=models)

    def GetEmaneModelConfig(self, request, context):
        logging.debug("get emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        model = session.emane.models[request.model]
        _id = get_emane_model_id(request.node_id, request.interface)
        config = session.emane.get_model_config(_id, request.model)
        groups = get_config_groups(config, model)
        return core_pb2.GetEmaneModelConfigResponse(groups=groups)

    def SetEmaneModelConfig(self, request, context):
        logging.debug("set emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        _id = get_emane_model_id(request.node_id, request.interface_id)
        session.emane.set_model_config(_id, request.model, request.config)
        return core_pb2.SetEmaneModelConfigResponse(result=True)

    def GetEmaneModelConfigs(self, request, context):
        logging.debug("get emane model configs: %s", request)
        session = self.get_session(request.session_id, context)
        response = core_pb2.GetEmaneModelConfigsResponse()
        for node_id, model_config in session.emane.node_configurations.iteritems():
            if node_id == -1:
                continue

            for model_name in model_config.iterkeys():
                model = session.emane.models[model_name]
                config = session.emane.get_model_config(node_id, model_name)
                config_groups = get_config_groups(config, model)
                node_configurations = response.configs[node_id]
                node_configurations.model = model_name
                node_configurations.groups.extend(config_groups)
        return response

    def SaveXml(self, request, context):
        logging.debug("save xml: %s", request)
        session = self.get_session(request.session_id, context)

        _, temp_path = tempfile.mkstemp()
        session.save_xml(temp_path)

        with open(temp_path, "rb") as xml_file:
            data = xml_file.read()

        return core_pb2.SaveXmlResponse(data=data)

    def OpenXml(self, request, context):
        logging.debug("open xml: %s", request)
        session = self.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)

        _, temp_path = tempfile.mkstemp()
        with open(temp_path, "wb") as xml_file:
            xml_file.write(request.data)

        try:
            session.open_xml(temp_path, start=True)
            return core_pb2.OpenXmlResponse(session_id=session.id, result=True)
        except IOError:
            logging.exception("error opening session file")
            self.coreemu.delete_session(session.id)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid xml file")
