import atexit
import logging
import os
import tempfile
import time
from Queue import Queue, Empty
from itertools import repeat

import grpc
from concurrent import futures

from core.conf import ConfigShim
from core.data import ConfigData, FileData
from core.emulator.emudata import NodeOptions, InterfaceData, LinkOptions
from core.enumerations import NodeTypes, EventTypes, LinkTypes, MessageFlags, ConfigFlags, ConfigDataTypes
from core.grpc import core_pb2
from core.grpc import core_pb2_grpc
from core.misc import nodeutils
from core.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.service import ServiceManager, ServiceShim

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
        type=link_data.link_type, node_one=link_data.node1_id, node_two=link_data.node2_id,
        interface_one=interface_one, interface_two=interface_two, options=options
    )


def send_objects(session):
    time.sleep(1)
    # find all nodes and links
    nodes_data = []
    links_data = []
    with session._objects_lock:
        for obj in session.objects.itervalues():
            node_data = obj.data(message_type=MessageFlags.ADD.value)
            if node_data:
                nodes_data.append(node_data)

            node_links = obj.all_link_data(flags=MessageFlags.ADD.value)
            for link_data in node_links:
                links_data.append(link_data)

    # send all nodes first, so that they will exist for any links
    for node_data in nodes_data:
        session.broadcast_node(node_data)

    for link_data in links_data:
        session.broadcast_link(link_data)

    # send mobility model info
    for node_id in session.mobility.nodes():
        for model_name, config in session.mobility.get_all_configs(node_id).iteritems():
            model_class = session.mobility.models[model_name]
            logging.debug("mobility config: node(%s) class(%s) values(%s)", node_id, model_class, config)
            config_data = ConfigShim.config_data(0, node_id, ConfigFlags.UPDATE.value, model_class, config)
            session.broadcast_config(config_data)

    # send emane model info
    for node_id in session.emane.nodes():
        for model_name, config in session.emane.get_all_configs(node_id).iteritems():
            model_class = session.emane.models[model_name]
            logging.debug("emane config: node(%s) class(%s) values(%s)", node_id, model_class, config)
            config_data = ConfigShim.config_data(0, node_id, ConfigFlags.UPDATE.value, model_class, config)
            session.broadcast_config(config_data)

    # service customizations
    service_configs = session.services.all_configs()
    for node_id, service in service_configs:
        opaque = "service:%s" % service.name
        data_types = tuple(repeat(ConfigDataTypes.STRING.value, len(ServiceShim.keys)))
        node = session.get_object(node_id)
        values = ServiceShim.tovaluelist(node, service)
        config_data = ConfigData(
            message_type=0,
            node=node_id,
            object=session.services.name,
            type=ConfigFlags.UPDATE.value,
            data_types=data_types,
            data_values=values,
            session=str(session.session_id),
            opaque=opaque
        )
        session.broadcast_config(config_data)

        for file_name, config_data in session.services.all_files(service):
            file_data = FileData(
                message_type=MessageFlags.ADD.value,
                node=node_id,
                name=str(file_name),
                type=opaque,
                data=str(config_data)
            )
            session.broadcast_file(file_data)

    # TODO: send location info

    # send hook scripts
    for state in sorted(session._hooks.keys()):
        for file_name, config_data in session._hooks[state]:
            file_data = FileData(
                message_type=MessageFlags.ADD.value,
                name=str(file_name),
                type="hook:%s" % state,
                data=str(config_data)
            )
            session.broadcast_file(file_data)

    # send session configuration
    session_config = session.options.get_configs()
    config_data = ConfigShim.config_data(0, None, ConfigFlags.UPDATE.value, session.options, session_config)
    session.broadcast_config(config_data)

    # send session metadata
    configs = session.metadata.get_configs()
    if configs:
        data_values = "|".join(["%s=%s" % item for item in configs.iteritems()])
        data_types = tuple(ConfigDataTypes.STRING.value for _ in session.metadata.get_configs())
        config_data = ConfigData(
            message_type=0,
            object=session.metadata.name,
            type=ConfigFlags.NONE.value,
            data_types=data_types,
            data_values=data_values
        )
        session.broadcast_config(config_data)

    logging.debug("informed GUI about %d nodes and %d links", len(nodes_data), len(links_data))


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

    def get_session(self, _id, context):
        session = self.coreemu.sessions.get(_id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "session not found")
        return session

    def get_node(self, session, _id, context):
        node = session.get_object(_id)
        if not node:
            context.abort(grpc.StatusCode.NOT_FOUND, "node not found")
        return node

    def CreateSession(self, request, context):
        logging.debug("create session: %s", request)
        session = self.coreemu.create_session(request.id)
        session.set_state(EventTypes.DEFINITION_STATE)
        session.location.setrefgeo(47.57917, -122.13232, 2.0)
        session.location.refscale = 150000.0
        return core_pb2.CreateSessionResponse(id=session.session_id, state=session.state)

    def DeleteSession(self, request, context):
        logging.debug("delete session: %s", request)
        result = self.coreemu.delete_session(request.id)
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
        session = self.get_session(request.id, context)
        x, y, z = session.location.refxyz
        lat, lon, alt = session.location.refgeo
        position = core_pb2.Position(x=x, y=y, z=z, lat=lat, lon=lon, alt=alt)
        return core_pb2.GetSessionLocationResponse(position=position, scale=session.location.refscale)

    def SetSessionLocation(self, request, context):
        logging.debug("set session location: %s", request)
        session = self.get_session(request.id, context)
        session.location.refxyz = (request.position.x, request.position.y, request.position.z)
        session.location.setrefgeo(request.position.lat, request.position.lon, request.position.alt)
        session.location.refscale = request.scale
        return core_pb2.SetSessionLocationResponse(result=True)

    def SetSessionState(self, request, context):
        logging.debug("set session state: %s", request)
        session = self.get_session(request.id, context)

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
        session = self.get_session(request.id, context)
        config = session.options.get_configs()
        defaults = session.options.default_values()
        defaults.update(config)
        groups = get_config_groups(defaults, session.options)
        return core_pb2.GetSessionOptionsResponse(groups=groups)

    def SetSessionOptions(self, request, context):
        logging.debug("set session options: %s", request)
        session = self.get_session(request.id, context)
        session.options.set_configs(request.config)
        return core_pb2.SetSessionOptionsResponse(result=True)

    def GetSession(self, request, context):
        logging.debug("get session: %s", request)
        session = self.get_session(request.id, context)

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

    def NodeEvents(self, request, context):
        session = self.get_session(request.id, context)
        queue = Queue()
        session.node_handlers.append(lambda x: queue.put(x))

        while self._is_running(context):
            try:
                node = queue.get(timeout=1)
                position = core_pb2.Position(x=node.x_position, y=node.y_position)
                services = node.services or ""
                services = services.split("|")
                node_proto = core_pb2.Node(
                    id=node.id, name=node.name, model=node.model, position=position, services=services)
                node_event = core_pb2.NodeEvent(node=node_proto)
                yield node_event
            except Empty:
                continue

        self._cancel_stream(context)

    def LinkEvents(self, request, context):
        session = self.get_session(request.id, context)
        queue = Queue()
        session.link_handlers.append(lambda x: queue.put(x))

        while self._is_running(context):
            try:
                event = queue.get(timeout=1)
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
                    type=event.link_type, node_one=event.node1_id, node_two=event.node2_id,
                    interface_one=interface_one, interface_two=interface_two, options=options)
                link_event = core_pb2.LinkEvent(message_type=event.message_type, link=link)
                yield link_event
            except Empty:
                continue

        self._cancel_stream(context)

    def SessionEvents(self, request, context):
        session = self.get_session(request.id, context)
        queue = Queue()
        session.event_handlers.append(lambda x: queue.put(x))

        while self._is_running(context):
            try:
                event = queue.get(timeout=1)
                event_time = event.time
                if event_time is not None:
                    event_time = float(event_time)
                session_event = core_pb2.SessionEvent(
                    node=event.node,
                    event=event.event_type,
                    name=event.name,
                    data=event.data,
                    time=event_time,
                    session=session.session_id
                )
                yield session_event
            except Empty:
                continue

        self._cancel_stream(context)

    def ConfigEvents(self, request, context):
        session = self.get_session(request.id, context)
        queue = Queue()
        session.config_handlers.append(lambda x: queue.put(x))

        while self._is_running(context):
            try:
                event = queue.get(timeout=1)
                config_event = core_pb2.ConfigEvent(
                    message_type=event.message_type,
                    node=event.node,
                    object=event.object,
                    type=event.type,
                    captions=event.captions,
                    bitmap=event.bitmap,
                    data_values=event.data_values,
                    possible_values=event.possible_values,
                    groups=event.groups,
                    session=event.session,
                    interface=event.interface_number,
                    network_id=event.network_id,
                    opaque=event.opaque,
                    data_types=event.data_types
                )
                yield config_event
            except Empty:
                continue

        self._cancel_stream(context)

    def ExceptionEvents(self, request, context):
        session = self.get_session(request.id, context)
        queue = Queue()
        session.exception_handlers.append(lambda x: queue.put(x))

        while self._is_running(context):
            try:
                event = queue.get(timeout=1)
                exception_event = core_pb2.ExceptionEvent(
                    node=event.node,
                    session=int(event.session),
                    level=event.level.value,
                    source=event.source,
                    date=event.date,
                    text=event.text,
                    opaque=event.opaque
                )
                yield exception_event
            except Empty:
                continue

        self._cancel_stream(context)

    def FileEvents(self, request, context):
        session = self.get_session(request.id, context)
        queue = Queue()
        session.file_handlers.append(lambda x: queue.put(x))

        while self._is_running(context):
            try:
                event = queue.get(timeout=1)
                file_event = core_pb2.FileEvent(
                    message_type=event.message_type,
                    node=event.node,
                    name=event.name,
                    mode=event.mode,
                    number=event.number,
                    type=event.type,
                    source=event.source,
                    session=event.session,
                    data=event.data,
                    compressed_data=event.compressed_data
                )
                yield file_event
            except Empty:
                continue

        self._cancel_stream(context)

    def CreateNode(self, request, context):
        logging.debug("create node: %s", request)
        session = self.get_session(request.session, context)

        node_id = request.id
        node_type = request.type
        if node_type is None:
            node_type = NodeTypes.DEFAULT.value
        node_type = NodeTypes(node_type)

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

        return core_pb2.CreateNodeResponse(id=node.objid)

    def GetNode(self, request, context):
        logging.debug("get node: %s", request)
        session = self.get_session(request.session, context)
        node = self.get_node(session, request.id, context)

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
        session = self.get_session(request.session, context)
        node_id = request.id
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
        session = self.get_session(request.session, context)
        result = session.delete_node(request.id)
        return core_pb2.DeleteNodeResponse(result=result)

    def GetNodeLinks(self, request, context):
        logging.debug("get node links: %s", request)
        session = self.get_session(request.session, context)
        node = self.get_node(session, request.id, context)
        links = get_links(session, node)
        return core_pb2.GetNodeLinksResponse(links=links)

    def CreateLink(self, request, context):
        logging.debug("create link: %s", request)
        session = self.get_session(request.session, context)
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
        return core_pb2.CreateLinkResponse(result=True)

    def EditLink(self, request, context):
        logging.debug("edit link: %s", request)
        session = self.get_session(request.session, context)
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
        return core_pb2.EditLinkResponse(result=True)

    def DeleteLink(self, request, context):
        logging.debug("delete link: %s", request)
        session = self.get_session(request.session, context)
        node_one = request.node_one
        node_two = request.node_two
        interface_one = request.interface_one
        interface_two = request.interface_two
        session.delete_link(node_one, node_two, interface_one, interface_two)
        return core_pb2.DeleteLinkResponse(result=True)

    def GetHooks(self, request, context):
        logging.debug("get hooks: %s", request)
        session = self.get_session(request.session, context)
        hooks = []
        for state, state_hooks in session._hooks.iteritems():
            for file_name, file_data in state_hooks:
                hook = core_pb2.Hook(state=state, file=file_name, data=file_data)
                hooks.append(hook)
        return core_pb2.GetHooksResponse(hooks=hooks)

    def AddHook(self, request, context):
        logging.debug("add hook: %s", request)
        session = self.get_session(request.session, context)
        hook = request.hook
        session.add_hook(hook.state, hook.file, None, hook.data)
        return core_pb2.AddHookResponse(result=True)

    def GetMobilityConfigs(self, request, context):
        logging.debug("get mobility configs: %s", request)
        session = self.get_session(request.session, context)
        mobility_configs = {}
        for node_id, model_config in session.mobility.node_configurations.iteritems():
            if node_id == -1:
                continue
            for model_name in model_config.iterkeys():
                if model_name != Ns2ScriptedMobility.name:
                    continue
                config = session.mobility.get_model_config(node_id, model_name)
                groups = get_config_groups(config, Ns2ScriptedMobility)
                mobility_configs[node_id] = groups
        return core_pb2.GetMobilityConfigsResponse(configs=mobility_configs)

    def GetMobilityConfig(self, request, context):
        logging.debug("get mobility config: %s", request)
        session = self.get_session(request.session, context)
        config = session.mobility.get_model_config(request.id, Ns2ScriptedMobility.name)
        groups = get_config_groups(config, Ns2ScriptedMobility)
        return core_pb2.GetMobilityConfigResponse(groups=groups)

    def SetMobilityConfig(self, request, context):
        logging.debug("set mobility config: %s", request)
        session = self.get_session(request.session, context)
        session.mobility.set_model_config(request.id, Ns2ScriptedMobility.name, request.config)
        return core_pb2.SetMobilityConfigResponse(result=True)

    def MobilityAction(self, request, context):
        logging.debug("mobility action: %s", request)
        session = self.get_session(request.session, context)
        node = self.get_node(session, request.id, context)
        result = True
        if request.action == core_pb2.MOBILITY_START:
            node.mobility.start()
        elif request.action == core_pb2.MOBILITY_PAUSE:
            node.mobility.pause()
        elif request.action == core_pb2.MOBILITY_STOP:
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
        session = self.get_session(request.session, context)
        all_service_defaults = []
        for node_type in session.services.default_services:
            services = session.services.default_services[node_type]
            service_defaults = core_pb2.ServiceDefaults(node_type=node_type, services=services)
            all_service_defaults.append(service_defaults)
        return core_pb2.GetServiceDefaultsResponse(defaults=all_service_defaults)

    def SetServiceDefaults(self, request, context):
        logging.debug("set service defaults: %s", request)
        session = self.get_session(request.session, context)
        session.services.default_services.clear()
        for service_defaults in request.defaults:
            session.services.default_services[service_defaults.node_type] = service_defaults.services
        return core_pb2.SetServiceDefaultsResponse(result=True)

    def GetNodeService(self, request, context):
        logging.debug("get node service: %s", request)
        session = self.get_session(request.session, context)
        service = session.services.get_service(request.id, request.service, default_service=True)
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
        session = self.get_session(request.session, context)
        node = self.get_node(session, request.id, context)
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
        session = self.get_session(request.session, context)
        session.services.set_service(request.id, request.service)
        service = session.services.get_service(request.id, request.service)
        service.startup = tuple(request.startup)
        service.validate = tuple(request.validate)
        service.shutdown = tuple(request.shutdown)
        return core_pb2.SetNodeServiceResponse(result=True)

    def SetNodeServiceFile(self, request, context):
        logging.debug("set node service file: %s", request)
        session = self.get_session(request.session, context)
        session.services.set_service_file(request.id, request.service, request.file, request.data)
        return core_pb2.SetNodeServiceFileResponse(result=True)

    def ServiceAction(self, request, context):
        logging.debug("service action: %s", request)
        session = self.get_session(request.session, context)
        node = self.get_node(session, request.id, context)
        service = None
        for current_service in node.services:
            if current_service.name == request.service:
                service = current_service
                break

        if not service:
            context.abort(grpc.StatusCode.NOT_FOUND, "service not found")

        status = -1
        if request.action == core_pb2.START:
            status = session.services.startup_service(node, service, wait=True)
        elif request.action == core_pb2.STOP:
            status = session.services.stop_service(node, service)
        elif request.action == core_pb2.RESTART:
            status = session.services.stop_service(node, service)
            if not status:
                status = session.services.startup_service(node, service, wait=True)
        elif request.action == core_pb2.VALIDATE:
            status = session.services.validate_service(node, service)

        result = False
        if not status:
            result = True

        return core_pb2.ServiceActionResponse(result=result)

    def GetWlanConfig(self, request, context):
        logging.debug("get wlan config: %s", request)
        session = self.get_session(request.session, context)
        config = session.mobility.get_model_config(request.id, BasicRangeModel.name)
        groups = get_config_groups(config, BasicRangeModel)
        return core_pb2.GetWlanConfigResponse(groups=groups)

    def SetWlanConfig(self, request, context):
        logging.debug("set wlan config: %s", request)
        session = self.get_session(request.session, context)
        session.mobility.set_model_config(request.id, BasicRangeModel.name, request.config)
        return core_pb2.SetWlanConfigResponse(result=True)

    def GetEmaneConfig(self, request, context):
        logging.debug("get emane config: %s", request)
        session = self.get_session(request.session, context)
        config = session.emane.get_configs()
        groups = get_config_groups(config, session.emane.emane_config)
        return core_pb2.GetEmaneConfigResponse(groups=groups)

    def SetEmaneConfig(self, request, context):
        logging.debug("set emane config: %s", request)
        session = self.get_session(request.session, context)
        session.emane.set_configs(request.config)
        return core_pb2.SetEmaneConfigResponse(result=True)

    def GetEmaneModels(self, request, context):
        logging.debug("get emane models: %s", request)
        session = self.get_session(request.session, context)
        models = []
        for model in session.emane.models.keys():
            if len(model.split("_")) != 2:
                continue
            models.append(model)
        return core_pb2.GetEmaneModelsResponse(models=models)

    def GetEmaneModelConfig(self, request, context):
        logging.debug("get emane model config: %s", request)
        session = self.get_session(request.session, context)
        model = session.emane.models[request.model]
        config = session.emane.get_model_config(request.id, request.model)
        groups = get_config_groups(config, model)
        return core_pb2.GetEmaneModelConfigResponse(groups=groups)

    def SetEmaneModelConfig(self, request, context):
        logging.debug("set emane model config: %s", request)
        session = self.get_session(request.session, context)
        session.emane.set_model_config(request.id, request.model, request.config)
        return core_pb2.SetEmaneModelConfigResponse(result=True)

    def GetEmaneModelConfigs(self, request, context):
        logging.debug("get emane model configs: %s", request)
        session = self.get_session(request.session, context)
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
        session = self.get_session(request.session, context)

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
            return core_pb2.OpenXmlResponse(session=session.session_id, result=True)
        except IOError:
            logging.exception("error opening session file")
            self.coreemu.delete_session(session.session_id)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid xml file")
