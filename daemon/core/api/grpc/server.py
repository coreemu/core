import atexit
import logging
import os
import re
import tempfile
import time
from concurrent import futures
from queue import Empty, Queue

import grpc

from core.api.grpc import core_pb2, core_pb2_grpc, grpcutils
from core.api.grpc.grpcutils import (
    convert_value,
    get_config_options,
    get_emane_model_id,
    get_links,
    get_net_stats,
)
from core.emane.nodes import EmaneNet
from core.emulator.data import (
    ConfigData,
    EventData,
    ExceptionData,
    FileData,
    LinkData,
    NodeData,
)
from core.emulator.emudata import LinkOptions, NodeOptions
from core.emulator.enumerations import EventTypes, LinkTypes, MessageFlags
from core.errors import CoreCommandError, CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.docker import DockerNode
from core.nodes.lxd import LxcNode
from core.services.coreservices import ServiceManager

_ONE_DAY_IN_SECONDS = 60 * 60 * 24
_INTERFACE_REGEX = re.compile(r"\d+")


class CoreGrpcServer(core_pb2_grpc.CoreApiServicer):
    """
    Create CoreGrpcServer instance

    :param core.emulator.coreemu.CoreEmu coreemu: coreemu object
    """

    def __init__(self, coreemu):
        super().__init__()
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

    def listen(self, address):
        logging.info("CORE gRPC API listening on: %s", address)
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
        """
        Retrieve session given the session id

        :param int session_id: session id
        :param grpc.ServicerContext context:
        :return: session object that satisfies, if session not found then raise an
            exception
        :rtype: core.emulator.session.Session
        """
        session = self.coreemu.sessions.get(session_id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, f"session {session_id} not found")
        return session

    def get_node(self, session, node_id, context):
        """
        Retrieve node given session and node id

        :param core.emulator.session.Session session: session that has the node
        :param int node_id: node id
        :param grpc.ServicerContext context:
        :return: node object that satisfies. If node not found then raise an exception.
        :rtype: core.nodes.base.CoreNode
        """
        try:
            return session.get_node(node_id)
        except CoreError:
            context.abort(grpc.StatusCode.NOT_FOUND, f"node {node_id} not found")

    def StartSession(self, request, context):
        """
        Start a session.

        :param core.api.grpc.core_pb2.StartSessionRequest request: start session request
        :param context: grcp context
        :return: start session response
        :rtype: core.api.grpc.core_pb2.StartSessionResponse
        """
        logging.debug("start session: %s", request)
        session = self.get_session(request.session_id, context)

        # clear previous state and setup for creation
        session.clear()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        if not os.path.exists(session.session_dir):
            os.mkdir(session.session_dir)

        # location
        if request.HasField("location"):
            grpcutils.session_location(session, request.location)

        # add all hooks
        for hook in request.hooks:
            session.add_hook(hook.state, hook.file, None, hook.data)

        # create nodes
        grpcutils.create_nodes(session, request.nodes)

        # emane configs
        config = session.emane.get_configs()
        config.update(request.emane_config)
        for config in request.emane_model_configs:
            _id = get_emane_model_id(config.node_id, config.interface_id)
            session.emane.set_model_config(_id, config.model, config.config)

        # wlan configs
        for config in request.wlan_configs:
            session.mobility.set_model_config(
                config.node_id, BasicRangeModel.name, config.config
            )

        # mobility configs
        for config in request.mobility_configs:
            session.mobility.set_model_config(
                config.node_id, Ns2ScriptedMobility.name, config.config
            )

        # service configs
        for config in request.service_configs:
            grpcutils.service_configuration(session, config)

        # service file configs
        for config in request.service_file_configs:
            session.services.set_service_file(
                config.node_id, config.service, config.file, config.data
            )

        # create links
        grpcutils.create_links(session, request.links)

        # set to instantiation and start
        session.set_state(EventTypes.INSTANTIATION_STATE)
        session.instantiate()

        return core_pb2.StartSessionResponse(result=True)

    def StopSession(self, request, context):
        """
        Stop a running session.

        :param core.api.grpc.core_pb2.StopSessionRequest request: stop session request
        :param context: grcp context
        :return: stop session response
        :rtype: core.api.grpc.core_pb2.StopSessionResponse
        """
        logging.debug("stop session: %s", request)
        session = self.get_session(request.session_id, context)
        session.data_collect()
        session.set_state(EventTypes.DATACOLLECT_STATE, send_event=True)
        session.clear()
        session.set_state(EventTypes.SHUTDOWN_STATE, send_event=True)
        return core_pb2.StopSessionResponse(result=True)

    def CreateSession(self, request, context):
        """
        Create a session

        :param core.api.grpc.core_pb2.CreateSessionRequest request: create-session request
        :param grpc.ServicerContext context:
        :return: a create-session response
        :rtype: core.api.grpc.core_pb2.CreateSessionResponse
        """
        logging.debug("create session: %s", request)
        session = self.coreemu.create_session(request.session_id)
        session.set_state(EventTypes.DEFINITION_STATE)
        session.location.setrefgeo(47.57917, -122.13232, 2.0)
        session.location.refscale = 150000.0
        return core_pb2.CreateSessionResponse(
            session_id=session.id, state=session.state
        )

    def DeleteSession(self, request, context):
        """
        Delete the session

        :param core.api.grpc.core_pb2.DeleteSessionRequest request: delete-session request
        :param grpc.ServicerContext context: context object
        :return: a delete-session response
        :rtype: core.api.grpc.core_pb2.DeleteSessionResponse
        """
        logging.debug("delete session: %s", request)
        result = self.coreemu.delete_session(request.session_id)
        return core_pb2.DeleteSessionResponse(result=result)

    def GetSessions(self, request, context):
        """
        Delete the session

        :param core.api.grpc.core_pb2.GetSessionRequest request: get-session request
        :param grpc.ServicerContext context: context object
        :return: a delete-session response
        :rtype: core.api.grpc.core_pb2.DeleteSessionResponse
        """
        logging.debug("get sessions: %s", request)
        sessions = []
        for session_id in self.coreemu.sessions:
            session = self.coreemu.sessions[session_id]
            session_summary = core_pb2.SessionSummary(
                id=session_id,
                state=session.state,
                nodes=session.get_node_count(),
                file=session.file_name,
            )
            sessions.append(session_summary)
        return core_pb2.GetSessionsResponse(sessions=sessions)

    def GetSessionLocation(self, request, context):
        """
        Retrieve a requested session location

        :param core.api.grpc.core_pb2.GetSessionLocationRequest request: get-session-location request
        :param grpc.ServicerContext context: context object
        :return: a get-session-location response
        :rtype: core.api.grpc.core_pb2.GetSessionLocationResponse
        """
        logging.debug("get session location: %s", request)
        session = self.get_session(request.session_id, context)
        x, y, z = session.location.refxyz
        lat, lon, alt = session.location.refgeo
        scale = session.location.refscale
        location = core_pb2.SessionLocation(
            x=x, y=y, z=z, lat=lat, lon=lon, alt=alt, scale=scale
        )
        return core_pb2.GetSessionLocationResponse(location=location)

    def SetSessionLocation(self, request, context):
        """
        Set session location

        :param core.api.grpc.core_pb2.SetSessionLocationRequest request: set-session-location request
        :param grpc.ServicerContext context: context object
        :return: a set-session-location-response
        :rtype: core.api.grpc.core_pb2.SetSessionLocationResponse
        """
        logging.debug("set session location: %s", request)
        session = self.get_session(request.session_id, context)
        grpcutils.session_location(session, request.location)
        return core_pb2.SetSessionLocationResponse(result=True)

    def SetSessionState(self, request, context):
        """
        Set session state

        :param core.api.grpc.core_pb2.SetSessionStateRequest request: set-session-state request
        :param grpc.ServicerContext context:context object
        :return: set-session-state response
        :rtype: core.api.grpc.core_pb2.SetSessionStateResponse
        """
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
        """
        Retrieve session options.

        :param core.api.grpc.core_pb2.GetSessionOptions request:
            get-session-options request
        :param grpc.ServicerContext context: context object
        :return: get-session-options response about all session's options
        :rtype: core.api.grpc.core_pb2.GetSessionOptions
        """
        logging.debug("get session options: %s", request)
        session = self.get_session(request.session_id, context)
        current_config = session.options.get_configs()
        default_config = session.options.default_values()
        default_config.update(current_config)
        config = get_config_options(default_config, session.options)
        return core_pb2.GetSessionOptionsResponse(config=config)

    def SetSessionOptions(self, request, context):
        """
        Update a session's configuration

        :param core.api.grpc.core_pb2.SetSessionOptions request: set-session-options request
        :param grpc.ServicerContext context: context object
        :return: set-session-options response
        :rtype: core.api.grpc.core_pb2.SetSessionOptionsResponse
        """
        logging.debug("set session options: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.options.get_configs()
        config.update(request.config)
        return core_pb2.SetSessionOptionsResponse(result=True)

    def GetSessionMetadata(self, request, context):
        """
        Retrieve session metadata.

        :param core.api.grpc.core_pb2.GetSessionMetadata request: get session metadata
            request
        :param grpc.ServicerContext context: context object
        :return: get session metadata response
        :rtype: core.api.grpc.core_pb2.GetSessionMetadata
        """
        logging.debug("get session metadata: %s", request)
        session = self.get_session(request.session_id, context)
        return core_pb2.GetSessionMetadataResponse(config=session.metadata)

    def SetSessionMetadata(self, request, context):
        """
        Update a session's metadata.

        :param core.api.grpc.core_pb2.SetSessionMetadata request: set metadata request
        :param grpc.ServicerContext context: context object
        :return: set metadata response
        :rtype: core.api.grpc.core_pb2.SetSessionMetadataResponse
        """
        logging.debug("set session metadata: %s", request)
        session = self.get_session(request.session_id, context)
        session.metadata = dict(request.config)
        return core_pb2.SetSessionMetadataResponse(result=True)

    def GetSession(self, request, context):
        """
        Retrieve requested session

        :param core.api.grpc.core_pb2.GetSessionRequest request: get-session request
        :param grpc.ServicerContext context: context object
        :return: get-session response
        :rtype: core.api.grpc.core_bp2.GetSessionResponse
        """
        logging.debug("get session: %s", request)
        session = self.get_session(request.session_id, context)

        links = []
        nodes = []
        for _id in session.nodes:
            node = session.nodes[_id]
            if not isinstance(node.id, int):
                continue

            node_type = session.get_node_type(node.__class__)
            model = getattr(node, "type", None)
            position = core_pb2.Position(
                x=node.position.x, y=node.position.y, z=node.position.z
            )

            services = getattr(node, "services", [])
            if services is None:
                services = []
            services = [x.name for x in services]

            emane_model = None
            if isinstance(node, EmaneNet):
                emane_model = node.model.name

            node_proto = core_pb2.Node(
                id=node.id,
                name=node.name,
                emane=emane_model,
                model=model,
                type=node_type.value,
                position=position,
                services=services,
            )
            if isinstance(node, (DockerNode, LxcNode)):
                node_proto.image = node.image
            nodes.append(node_proto)

            node_links = get_links(session, node)
            links.extend(node_links)

        session_proto = core_pb2.Session(state=session.state, nodes=nodes, links=links)
        return core_pb2.GetSessionResponse(session=session_proto)

    def AddSessionServer(self, request, context):
        """
        Add distributed server to a session.

        :param core.api.grpc.core_pb2.AddSessionServerRequest request: get-session
            request
        :param grpc.ServicerContext context: context object
        :return: add session server response
        :rtype: core.api.grpc.core_bp2.AddSessionServerResponse
        """
        session = self.get_session(request.session_id, context)
        session.distributed.add_server(request.name, request.host)
        return core_pb2.AddSessionServerResponse(result=True)

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
        """
        Handle node event when there is a node event

        :param core.emulator.data.NodeData event: node data
        :return: node event that contains node id, name, model, position, and services
        :rtype: core.api.grpc.core_pb2.NodeEvent
        """
        position = core_pb2.Position(x=event.x_position, y=event.y_position)
        services = event.services or ""
        services = services.split("|")
        node_proto = core_pb2.Node(
            id=event.id,
            name=event.name,
            model=event.model,
            position=position,
            services=services,
        )
        return core_pb2.NodeEvent(node=node_proto)

    def _handle_link_event(self, event):
        """
        Handle link event when there is a link event

        :param core.emulator.data.LinkData event: link data
        :return: link event that has message type and link information
        :rtype: core.api.grpc.core_pb2.LinkEvent
        """
        interface_one = None
        if event.interface1_id is not None:
            interface_one = core_pb2.Interface(
                id=event.interface1_id,
                name=event.interface1_name,
                mac=convert_value(event.interface1_mac),
                ip4=convert_value(event.interface1_ip4),
                ip4mask=event.interface1_ip4_mask,
                ip6=convert_value(event.interface1_ip6),
                ip6mask=event.interface1_ip6_mask,
            )

        interface_two = None
        if event.interface2_id is not None:
            interface_two = core_pb2.Interface(
                id=event.interface2_id,
                name=event.interface2_name,
                mac=convert_value(event.interface2_mac),
                ip4=convert_value(event.interface2_ip4),
                ip4mask=event.interface2_ip4_mask,
                ip6=convert_value(event.interface2_ip6),
                ip6mask=event.interface2_ip6_mask,
            )

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
            unidirectional=event.unidirectional,
        )
        link = core_pb2.Link(
            type=event.link_type,
            node_one_id=event.node1_id,
            node_two_id=event.node2_id,
            interface_one=interface_one,
            interface_two=interface_two,
            options=options,
        )
        return core_pb2.LinkEvent(message_type=event.message_type, link=link)

    def _handle_session_event(self, event):
        """
        Handle session event when there is a session event

        :param core.emulator.data.EventData event: event data
        :return: session event
        :rtype: core.api.grpc.core_pb2.SessionEvent
        """
        event_time = event.time
        if event_time is not None:
            event_time = float(event_time)
        return core_pb2.SessionEvent(
            node_id=event.node,
            event=event.event_type,
            name=event.name,
            data=event.data,
            time=event_time,
            session_id=event.session,
        )

    def _handle_config_event(self, event):
        """
        Handle configuration event when there is configuration event

        :param core.emulator.data.ConfigData event: configuration data
        :return: configuration event
        :rtype: core.api.grpc.core_pb2.ConfigEvent
        """
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
            data_types=event.data_types,
        )

    def _handle_exception_event(self, event):
        """
        Handle exception event when there is exception event

        :param core.emulator.data.ExceptionData event: exception data
        :return: exception event
        :rtype: core.api.grpc.core_pb2.ExceptionEvent
        """
        return core_pb2.ExceptionEvent(
            node_id=event.node,
            session_id=int(event.session),
            level=event.level.value,
            source=event.source,
            date=event.date,
            text=event.text,
            opaque=event.opaque,
        )

    def _handle_file_event(self, event):
        """
        Handle file event

        :param core.emulator.data.FileData event: file data
        :return: file event
        :rtype: core.api.grpc.core_pb2.FileEvent
        """
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
            compressed_data=event.compressed_data,
        )

    def Throughputs(self, request, context):
        """
        Calculate average throughput after every certain amount of delay time

        :param core.api.grpc.core_pb2.ThroughputsRequest request: throughputs request
        :param grpc.SrevicerContext context: context object
        :return: nothing
        """
        delay = 3
        last_check = None
        last_stats = None
        while self._is_running(context):
            now = time.time()
            stats = get_net_stats()

            # calculate average
            if last_check is not None:
                interval = now - last_check
                throughputs_event = core_pb2.ThroughputsEvent()
                for key in stats:
                    current_rxtx = stats[key]
                    previous_rxtx = last_stats.get(key)
                    if not previous_rxtx:
                        continue
                    rx_kbps = (
                        (current_rxtx["rx"] - previous_rxtx["rx"]) * 8.0 / interval
                    )
                    tx_kbps = (
                        (current_rxtx["tx"] - previous_rxtx["tx"]) * 8.0 / interval
                    )
                    throughput = rx_kbps + tx_kbps
                    if key.startswith("veth"):
                        key = key.split(".")
                        node_id = int(_INTERFACE_REGEX.search(key[0]).group())
                        interface_id = int(key[1])
                        interface_throughput = (
                            throughputs_event.interface_throughputs.add()
                        )
                        interface_throughput.node_id = node_id
                        interface_throughput.interface_id = interface_id
                        interface_throughput.throughput = throughput
                    elif key.startswith("b."):
                        try:
                            node_id = int(key.split(".")[1])
                            bridge_throughput = (
                                throughputs_event.bridge_throughputs.add()
                            )
                            bridge_throughput.node_id = node_id
                            bridge_throughput.throughput = throughput
                        except ValueError:
                            pass

                yield throughputs_event

            last_check = now
            last_stats = stats
            time.sleep(delay)

    def AddNode(self, request, context):
        """
        Add node to requested session

        :param core.api.grpc.core_pb2.AddNodeRequest request: add-node request
        :param grpc.ServicerContext context: context object
        :return: add-node response
        :rtype: core.api.grpc.core_pb2.AddNodeResponse
        """
        logging.debug("add node: %s", request)
        session = self.get_session(request.session_id, context)
        _type, _id, options = grpcutils.add_node_data(request.node)
        node = session.add_node(_type=_type, _id=_id, options=options)
        # configure emane if provided
        emane_model = request.node.emane
        if emane_model:
            session.emane.set_model_config(id, emane_model)
        return core_pb2.AddNodeResponse(node_id=node.id)

    def GetNode(self, request, context):
        """
        Retrieve node

        :param core.api.grpc.core_pb2.GetNodeRequest request: get-node request
        :param grpc.ServicerContext context: context object
        :return: get-node response
        :rtype: core.api.grpc.core_pb2.GetNodeResponse
        """
        logging.debug("get node: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)

        interfaces = []
        for interface_id in node._netif:
            interface = node._netif[interface_id]
            net_id = None
            if interface.net:
                net_id = interface.net.id
            interface_proto = core_pb2.Interface(
                id=interface_id,
                netid=net_id,
                name=interface.name,
                mac=str(interface.hwaddr),
                mtu=interface.mtu,
                flowid=interface.flow_id,
            )
            interfaces.append(interface_proto)

        emane_model = None
        if isinstance(node, EmaneNet):
            emane_model = node.model.name

        services = []
        if node.services:
            services = [x.name for x in node.services]

        position = core_pb2.Position(
            x=node.position.x, y=node.position.y, z=node.position.z
        )
        node_type = session.get_node_type(node.__class__)
        node_proto = core_pb2.Node(
            id=node.id,
            name=node.name,
            type=node_type.value,
            emane=emane_model,
            model=node.type,
            position=position,
            services=services,
        )
        if isinstance(node, (DockerNode, LxcNode)):
            node_proto.image = node.image

        return core_pb2.GetNodeResponse(node=node_proto, interfaces=interfaces)

    def EditNode(self, request, context):
        """
        Edit node

        :param core.api.grpc.core_bp2.EditNodeRequest request: edit-node request
        :param grpc.ServicerContext context: context object
        :return: edit-node response
        :rtype: core.api.grpc.core_pb2.EditNodeResponse
        """
        logging.debug("edit node: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        options = NodeOptions()
        options.icon = request.icon
        x = request.position.x
        y = request.position.y
        options.set_position(x, y)
        lat = request.position.lat
        lon = request.position.lon
        alt = request.position.alt
        options.set_location(lat, lon, alt)
        result = True
        try:
            session.edit_node(node.id, options)
            node_data = node.data(0)
            session.broadcast_node(node_data)
        except CoreError:
            result = False
        return core_pb2.EditNodeResponse(result=result)

    def DeleteNode(self, request, context):
        """
        Delete node

        :param core.api.grpc.core_pb2.DeleteNodeRequest request: delete-node request
        :param grpc.ServicerContext context: context object
        :return: core.api.grpc.core_pb2.DeleteNodeResponse
        """
        logging.debug("delete node: %s", request)
        session = self.get_session(request.session_id, context)
        result = session.delete_node(request.node_id)
        return core_pb2.DeleteNodeResponse(result=result)

    def NodeCommand(self, request, context):
        """
        Run command on a node

        :param core.api.grpc.core_pb2.NodeCommandRequest request: node-command request
        :param grpc.ServicerContext context: context object
        :return: core.api.grpc.core_pb2.NodeCommandResponse
        """
        logging.debug("sending node command: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        try:
            output = node.cmd(request.command)
        except CoreCommandError as e:
            output = e.stderr
        return core_pb2.NodeCommandResponse(output=output)

    def GetNodeTerminal(self, request, context):
        """
        Retrieve terminal command string of a node

        :param core.api.grpc.core_pb2.GetNodeTerminalRequest request: get-node-terminal request
        :param grpc.ServicerContext context: context object
        :return:  get-node-terminal response
        :rtype: core.api.grpc.core_bp2.GetNodeTerminalResponse
        """
        logging.debug("getting node terminal: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        terminal = node.termcmdstring("/bin/bash")
        return core_pb2.GetNodeTerminalResponse(terminal=terminal)

    def GetNodeLinks(self, request, context):
        """
        Retrieve all links form a requested node

        :param core.api.grpc.core_pb2.GetNodeLinksRequest request: get-node-links request
        :param grpc.ServicerContext context: context object
        :return: get-node-links response
        :rtype: core.api.grpc.core_pb2.GetNodeLinksResponse
        """
        logging.debug("get node links: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context)
        links = get_links(session, node)
        return core_pb2.GetNodeLinksResponse(links=links)

    def AddLink(self, request, context):
        """
        Add link to a session

        :param core.api.grpc.core_pb2.AddLinkRequest request: add-link request
        :param grpc.ServicerContext context: context object
        :return: add-link response
        :rtype: core.api.grpc.AddLinkResponse
        """
        logging.debug("add link: %s", request)
        # validate session and nodes
        session = self.get_session(request.session_id, context)
        self.get_node(session, request.link.node_one_id, context)
        self.get_node(session, request.link.node_two_id, context)

        node_one_id = request.link.node_one_id
        node_two_id = request.link.node_two_id
        interface_one, interface_two, options = grpcutils.add_link_data(request.link)
        session.add_link(
            node_one_id, node_two_id, interface_one, interface_two, link_options=options
        )
        return core_pb2.AddLinkResponse(result=True)

    def EditLink(self, request, context):
        """
        Edit a link

        :param core.api.grpc.core_pb2.EditLinkRequest request: edit-link request
        :param grpc.ServicerContext context: context object
        :return: edit-link response
        :rtype: core.api.grpc.core_pb2.EditLinkResponse
        """
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
        session.update_link(
            node_one_id, node_two_id, interface_one_id, interface_two_id, link_options
        )
        return core_pb2.EditLinkResponse(result=True)

    def DeleteLink(self, request, context):
        """
        Delete a link

        :param core.api.grpc.core_pb2.DeleteLinkRequest request: delete-link request
        :param grpc.ServicerContext context: context object
        :return: delete-link response
         :rtype: core.api.grpc.core_pb2.DeleteLinkResponse
        """
        logging.debug("delete link: %s", request)
        session = self.get_session(request.session_id, context)
        node_one_id = request.node_one_id
        node_two_id = request.node_two_id
        interface_one_id = request.interface_one_id
        interface_two_id = request.interface_two_id
        session.delete_link(
            node_one_id, node_two_id, interface_one_id, interface_two_id
        )
        return core_pb2.DeleteLinkResponse(result=True)

    def GetHooks(self, request, context):
        """
        Retrieve all hooks from a session

        :param core.api.grpc.core_pb2.GetHooksRequest request: get-hook request
        :param grpc.ServicerContext context: context object
        :return: get-hooks response about all the hooks in all session states
        :rtype: core.api.grpc.core_pb2.GetHooksResponse
        """
        logging.debug("get hooks: %s", request)
        session = self.get_session(request.session_id, context)
        hooks = []
        for state in session._hooks:
            state_hooks = session._hooks[state]
            for file_name, file_data in state_hooks:
                hook = core_pb2.Hook(state=state, file=file_name, data=file_data)
                hooks.append(hook)
        return core_pb2.GetHooksResponse(hooks=hooks)

    def AddHook(self, request, context):
        """
        Add hook to a session

        :param core.api.grpc.core_pb2.AddHookRequest request: add-hook request
        :param grpc.ServicerContext context: context object
        :return: add-hook response
        :rtype: core.api.grpc.core_pb2.AddHookResponse
        """
        logging.debug("add hook: %s", request)
        session = self.get_session(request.session_id, context)
        hook = request.hook
        session.add_hook(hook.state, hook.file, None, hook.data)
        return core_pb2.AddHookResponse(result=True)

    def GetMobilityConfigs(self, request, context):
        """
        Retrieve all mobility configurations from a session

        :param core.api.grpc.core_pb2.GetMobilityConfigsRequest request:
            get-mobility-configurations request
        :param grpc.ServicerContext context: context object
        :return: get-mobility-configurations response that has a list of configurations
        :rtype: core.api.grpc.core_pb2.GetMobilityConfigsResponse
        """
        logging.debug("get mobility configs: %s", request)
        session = self.get_session(request.session_id, context)
        response = core_pb2.GetMobilityConfigsResponse()
        for node_id in session.mobility.node_configurations:
            model_config = session.mobility.node_configurations[node_id]
            if node_id == -1:
                continue
            for model_name in model_config:
                if model_name != Ns2ScriptedMobility.name:
                    continue
                current_config = session.mobility.get_model_config(node_id, model_name)
                config = get_config_options(current_config, Ns2ScriptedMobility)
                mapped_config = core_pb2.MappedConfig(config=config)
                response.configs[node_id].CopyFrom(mapped_config)
        return response

    def GetMobilityConfig(self, request, context):
        """
        Retrieve mobility configuration of a node

        :param core.api.grpc.core_pb2.GetMobilityConfigRequest request:
            get-mobility-configuration request
        :param grpc.ServicerContext context: context object
        :return: get-mobility-configuration response
        :rtype: core.api.grpc.core_pb2.GetMobilityConfigResponse
        """
        logging.debug("get mobility config: %s", request)
        session = self.get_session(request.session_id, context)
        current_config = session.mobility.get_model_config(
            request.node_id, Ns2ScriptedMobility.name
        )
        config = get_config_options(current_config, Ns2ScriptedMobility)
        return core_pb2.GetMobilityConfigResponse(config=config)

    def SetMobilityConfig(self, request, context):
        """
        Set mobility configuration of a node

        :param core.api.grpc.core_pb2.SetMobilityConfigRequest request:
            set-mobility-configuration request
        :param grpc.ServicerContext context: context object
        :return: set-mobility-configuration response
        "rtype" core.api.grpc.SetMobilityConfigResponse
        """
        logging.debug("set mobility config: %s", request)
        session = self.get_session(request.session_id, context)
        mobility_config = request.mobility_config
        session.mobility.set_model_config(
            mobility_config.node_id, Ns2ScriptedMobility.name, mobility_config.config
        )
        return core_pb2.SetMobilityConfigResponse(result=True)

    def MobilityAction(self, request, context):
        """
        Take mobility action whether to start, pause, stop or none of those

        :param core.api.grpc.core_pb2.MobilityActionRequest request: mobility-action
            request
        :param grpc.ServicerContext context: context object
        :return: mobility-action response
        :rtype: core.api.grpc.core_pb2.MobilityActionResponse
        """
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
        """
        Retrieve all the services that are running

        :param core.api.grpc.core_pb2.GetServicesRequest request: get-service request
        :param grpc.ServicerContext context: context object
        :return: get-services response
        :rtype: core.api.grpc.core_pb2.GetServicesResponse
        """
        logging.debug("get services: %s", request)
        services = []
        for name in ServiceManager.services:
            service = ServiceManager.services[name]
            service_proto = core_pb2.Service(group=service.group, name=service.name)
            services.append(service_proto)
        return core_pb2.GetServicesResponse(services=services)

    def GetServiceDefaults(self, request, context):
        """
        Retrieve all the default services of all node types in a session

        :param core.api.grpc.core_pb2.GetServiceDefaultsRequest request:
            get-default-service request
        :param grpc.ServicerContext context: context object
        :return: get-service-defaults response about all the available default services
        :rtype: core.api.grpc.core_pb2.GetServiceDefaultsResponse
        """
        logging.debug("get service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        all_service_defaults = []
        for node_type in session.services.default_services:
            services = session.services.default_services[node_type]
            service_defaults = core_pb2.ServiceDefaults(
                node_type=node_type, services=services
            )
            all_service_defaults.append(service_defaults)
        return core_pb2.GetServiceDefaultsResponse(defaults=all_service_defaults)

    def SetServiceDefaults(self, request, context):
        """
        Set new default services to the session after whipping out the old ones
        :param core.api.grpc.core_pb2.SetServiceDefaults request: set-service-defaults
            request
        :param grpc.ServicerContext context: context object
        :return: set-service-defaults response
        :rtype: core.api.grpc.core_pb2 SetServiceDefaultsResponse
        """
        logging.debug("set service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        session.services.default_services.clear()
        for service_defaults in request.defaults:
            session.services.default_services[
                service_defaults.node_type
            ] = service_defaults.services
        return core_pb2.SetServiceDefaultsResponse(result=True)

    def GetNodeService(self, request, context):
        """
        Retrieve a requested service from a node

        :param core.api.grpc.core_pb2.GetNodeServiceRequest request: get-node-service
            request
        :param grpc.ServicerContext context: context object
        :return: get-node-service response about the requested service
        :rtype: core.api.grpc.core_pb2.GetNodeServiceResponse
        """
        logging.debug("get node service: %s", request)
        session = self.get_session(request.session_id, context)
        service = session.services.get_service(
            request.node_id, request.service, default_service=True
        )
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
            meta=service.meta,
        )
        return core_pb2.GetNodeServiceResponse(service=service_proto)

    def GetNodeServiceFile(self, request, context):
        """
        Retrieve a requested service file from a node

        :param core.api.grpc.core_pb2.GetNodeServiceFileRequest request:
            get-node-service request
        :param grpc.ServicerContext context: context object
        :return: get-node-service response about the requested service
        :rtype: core.api.grpc.core_pb2.GetNodeServiceFileResponse
        """
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
        file_data = session.services.get_service_file(
            node, request.service, request.file
        )
        return core_pb2.GetNodeServiceFileResponse(data=file_data.data)

    def SetNodeService(self, request, context):
        """
        Set a node service for a node

        :param core.api.grpc.core_pb2.SetNodeServiceRequest request: set-node-service
            request that has info to set a node service
        :param grpc.ServicerContext context: context object
        :return: set-node-service response
        :rtype: core.api.grpc.core_pb2.SetNodeServiceResponse
        """
        logging.debug("set node service: %s", request)
        session = self.get_session(request.session_id, context)
        config = request.config
        grpcutils.service_configuration(session, config)
        return core_pb2.SetNodeServiceResponse(result=True)

    def SetNodeServiceFile(self, request, context):
        """
        Store the customized service file in the service config

        :param core.api.grpc.core_pb2.SetNodeServiceFileRequest request:
            set-node-service-file request
        :param grpc.ServicerContext context: context object
        :return: set-node-service-file response
        :rtype: core.api.grpc.core_pb2.SetNodeServiceFileResponse
        """
        logging.debug("set node service file: %s", request)
        session = self.get_session(request.session_id, context)
        config = request.config
        session.services.set_service_file(
            config.node_id, config.service, config.file, config.data
        )
        return core_pb2.SetNodeServiceFileResponse(result=True)

    def ServiceAction(self, request, context):
        """
        Take action whether to start, stop, restart, validate the service or none of the above

        :param core.api.grpc.core_pb2.ServiceActionRequest  request: service-action request
        :param grpcServicerContext context: context object
        :return: service-action response about status of action
        :rtype: core.api.grpc.core_pb2.ServiceActionResponse
        """
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
        """
        Retrieve wireless-lan configuration of a node

        :param core.api.grpc.core_pb2.GetWlanConfigRequest request: get-wlan-configuration request
        :param context: core.api.grpc.core_pb2.GetWlanConfigResponse
        :return: get-wlan-configuration response about the wlan configuration of a node
        :rtype: core.api.grpc.core_pb2.GetWlanConfigResponse
        """
        logging.debug("get wlan config: %s", request)
        session = self.get_session(request.session_id, context)
        current_config = session.mobility.get_model_config(
            request.node_id, BasicRangeModel.name
        )
        config = get_config_options(current_config, BasicRangeModel)
        return core_pb2.GetWlanConfigResponse(config=config)

    def SetWlanConfig(self, request, context):
        """
        Set configuration data for a model

        :param core.api.grpc.core_pb2.SetWlanConfigRequest request: set-wlan-configuration request
        :param grpc.ServicerContext context: context object
        :return: set-wlan-configuration response
        :rtype: core.api.grpc.core_pb2.SetWlanConfigResponse
        """
        logging.debug("set wlan config: %s", request)
        session = self.get_session(request.session_id, context)
        wlan_config = request.wlan_config
        session.mobility.set_model_config(
            wlan_config.node_id, BasicRangeModel.name, wlan_config.config
        )
        if session.state == EventTypes.RUNTIME_STATE.value:
            node = self.get_node(session, wlan_config.node_id, context)
            node.updatemodel(wlan_config.config)
        return core_pb2.SetWlanConfigResponse(result=True)

    def GetEmaneConfig(self, request, context):
        """
        Retrieve EMANE configuration of a session

        :param core.api.grpc.core_pb2.GetEmanConfigRequest request: get-EMANE-configuration request
        :param grpc.ServicerContext context: context object
        :return: get-EMANE-configuration response
        :rtype: core.api.grpc.core_pb2.GetEmaneConfigResponse
        """
        logging.debug("get emane config: %s", request)
        session = self.get_session(request.session_id, context)
        current_config = session.emane.get_configs()
        config = get_config_options(current_config, session.emane.emane_config)
        return core_pb2.GetEmaneConfigResponse(config=config)

    def SetEmaneConfig(self, request, context):
        """
        Set EMANE configuration of a session

        :param core.api.grpc.core_pb2.SetEmaneConfigRequest request: set-EMANE-configuration request
        :param grpc.ServicerContext context: context object
        :return: set-EMANE-configuration response
        :rtype: core.api.grpc.core_pb2.SetEmaneConfigResponse
        """
        logging.debug("set emane config: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.emane.get_configs()
        config.update(request.config)
        return core_pb2.SetEmaneConfigResponse(result=True)

    def GetEmaneModels(self, request, context):
        """
        Retrieve all the EMANE models in the session

        :param core.api.grpc.core_pb2.GetEmaneModelRequest request: get-emane-model request
        :param grpc.ServicerContext context: context object
        :return: get-EMANE-models response that has all the models
        :rtype: core.api.grpc.core_pb2.GetEmaneModelsResponse
        """
        logging.debug("get emane models: %s", request)
        session = self.get_session(request.session_id, context)
        models = []
        for model in session.emane.models.keys():
            if len(model.split("_")) != 2:
                continue
            models.append(model)
        return core_pb2.GetEmaneModelsResponse(models=models)

    def GetEmaneModelConfig(self, request, context):
        """
        Retrieve EMANE model configuration of a node

        :param core.api.grpc.core_pb2.GetEmaneModelConfigRequest request:
            get-EMANE-model-configuration request
        :param grpc.ServicerContext context: context object
        :return: get-EMANE-model-configuration response
        :rtype: core.api.grpc.core_pb2.GetEmaneModelConfigResponse
        """
        logging.debug("get emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        model = session.emane.models[request.model]
        _id = get_emane_model_id(request.node_id, request.interface)
        current_config = session.emane.get_model_config(_id, request.model)
        config = get_config_options(current_config, model)
        return core_pb2.GetEmaneModelConfigResponse(config=config)

    def SetEmaneModelConfig(self, request, context):
        """
        Set EMANE model configuration of a node

        :param core.api.grpc.core_pb2.SetEmaneModelConfigRequest request:
            set-EMANE-model-configuration request
        :param grpc.ServicerContext context: context object
        :return: set-EMANE-model-configuration response
        :rtype: core.api.grpc.core_pb2.SetEmaneModelConfigResponse
        """
        logging.debug("set emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        model_config = request.emane_model_config
        _id = get_emane_model_id(model_config.node_id, model_config.interface_id)
        session.emane.set_model_config(_id, model_config.model, model_config.config)
        return core_pb2.SetEmaneModelConfigResponse(result=True)

    def GetEmaneModelConfigs(self, request, context):
        """
        Retrieve all EMANE model configurations of a session

        :param core.api.grpc.core_pb2.GetEmaneModelConfigsRequest request:
            get-EMANE-model-configurations request
        :param grpc.ServicerContext context: context object
        :return: get-EMANE-model-configurations response that has all the EMANE
            configurations
        :rtype: core.api.grpc.core_pb2.GetEmaneModelConfigsResponse
        """
        logging.debug("get emane model configs: %s", request)
        session = self.get_session(request.session_id, context)
        response = core_pb2.GetEmaneModelConfigsResponse()
        for node_id in session.emane.node_configurations:
            model_config = session.emane.node_configurations[node_id]
            if node_id == -1:
                continue

            for model_name in model_config:
                model = session.emane.models[model_name]
                current_config = session.emane.get_model_config(node_id, model_name)
                config = get_config_options(current_config, model)
                model_config = core_pb2.GetEmaneModelConfigsResponse.ModelConfig(
                    model=model_name, config=config
                )
                response.configs[node_id].CopyFrom(model_config)
        return response

    def SaveXml(self, request, context):
        """
        Export the session nto the EmulationScript XML format

        :param core.api.grpc.core_pb2.SaveXmlRequest request: save xml request
        :param grpc SrvicerContext context: context object
        :return: save-xml response
        :rtype: core.api.grpc.core_pb2.SaveXmlResponse
        """
        logging.debug("save xml: %s", request)
        session = self.get_session(request.session_id, context)

        _, temp_path = tempfile.mkstemp()
        session.save_xml(temp_path)

        with open(temp_path, "r") as xml_file:
            data = xml_file.read()

        return core_pb2.SaveXmlResponse(data=data)

    def OpenXml(self, request, context):
        """
        Import a session from the EmulationScript XML format

        :param core.api.grpc.OpenXmlRequest request: open-xml request
        :param grpc.ServicerContext context: context object
        :return: Open-XML response or raise an exception if invalid XML file
        :rtype: core.api.grpc.core_pb2.OpenXMLResponse
        """
        logging.debug("open xml: %s", request)
        session = self.coreemu.create_session()

        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(request.data.encode("utf-8"))
        temp.close()

        try:
            session.open_xml(temp.name, request.start)
            session.name = os.path.basename(request.file)
            session.file_name = request.file
            return core_pb2.OpenXmlResponse(session_id=session.id, result=True)
        except IOError:
            logging.exception("error opening session file")
            self.coreemu.delete_session(session.id)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid xml file")
        finally:
            os.unlink(temp.name)

    def GetInterfaces(self, request, context):
        """
        Retrieve all the interfaces of the system including bridges, virtual ethernet, and loopback

        :param core.api.grpc.core_pb2.GetInterfacesRequest request: get-interfaces request
        :param grpc.ServicerContext context: context object
        :return: get-interfaces response that has all the system's interfaces
        :rtype: core.api.grpc.core_pb2.GetInterfacesResponse
        """
        interfaces = []
        for interface in os.listdir("/sys/class/net"):
            if (
                interface.startswith("b.")
                or interface.startswith("veth")
                or interface == "lo"
            ):
                continue
            interfaces.append(interface)
        return core_pb2.GetInterfacesResponse(interfaces=interfaces)

    def EmaneLink(self, request, context):
        """
        Helps broadcast wireless link/unlink between EMANE nodes.

        :param core.api.grpc.core_pb2.EmaneLinkRequest request: get-interfaces request
        :param grpc.ServicerContext context: context object
        :return: emane link response with success status
        :rtype: core.api.grpc.core_pb2.EmaneLinkResponse
        """
        logging.debug("emane link: %s", request)
        session = self.get_session(request.session_id, context)
        nem_one = request.nem_one
        emane_one, netif = session.emane.nemlookup(nem_one)
        if not emane_one or not netif:
            context.abort(grpc.StatusCode.NOT_FOUND, f"nem one {nem_one} not found")
        node_one = netif.node

        nem_two = request.nem_two
        emane_two, netif = session.emane.nemlookup(nem_two)
        if not emane_two or not netif:
            context.abort(grpc.StatusCode.NOT_FOUND, f"nem two {nem_two} not found")
        node_two = netif.node

        if emane_one.id == emane_two.id:
            if request.linked:
                flag = MessageFlags.ADD.value
            else:
                flag = MessageFlags.DELETE.value
            link = LinkData(
                message_type=flag,
                link_type=LinkTypes.WIRELESS.value,
                node1_id=node_one.id,
                node2_id=node_two.id,
                network_id=emane_one.id,
            )
            session.broadcast_link(link)
            return core_pb2.EmaneLinkResponse(result=True)
        else:
            return core_pb2.EmaneLinkResponse(result=False)
