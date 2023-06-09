import logging
import os
import re
import signal
import sys
import tempfile
import time
from collections.abc import Iterable
from concurrent import futures
from pathlib import Path
from re import Pattern
from typing import Optional

import grpc
from grpc import ServicerContext

from core import utils
from core.api.grpc import (
    common_pb2,
    configservices_pb2,
    core_pb2,
    core_pb2_grpc,
    grpcutils,
)
from core.api.grpc.configservices_pb2 import (
    ConfigService,
    GetConfigServiceDefaultsRequest,
    GetConfigServiceDefaultsResponse,
    GetConfigServiceRenderedRequest,
    GetConfigServiceRenderedResponse,
    GetNodeConfigServiceRequest,
    GetNodeConfigServiceResponse,
)
from core.api.grpc.core_pb2 import (
    ExecuteScriptResponse,
    GetWirelessConfigRequest,
    GetWirelessConfigResponse,
    LinkedRequest,
    LinkedResponse,
    WirelessConfigRequest,
    WirelessConfigResponse,
    WirelessLinkedRequest,
    WirelessLinkedResponse,
)
from core.api.grpc.emane_pb2 import (
    EmaneLinkRequest,
    EmaneLinkResponse,
    EmanePathlossesRequest,
    EmanePathlossesResponse,
    GetEmaneEventChannelRequest,
    GetEmaneEventChannelResponse,
    GetEmaneModelConfigRequest,
    GetEmaneModelConfigResponse,
    SetEmaneModelConfigRequest,
    SetEmaneModelConfigResponse,
)
from core.api.grpc.events import EventStreamer
from core.api.grpc.grpcutils import get_config_options, get_links, get_net_stats
from core.api.grpc.mobility_pb2 import (
    GetMobilityConfigRequest,
    GetMobilityConfigResponse,
    MobilityAction,
    MobilityActionRequest,
    MobilityActionResponse,
    SetMobilityConfigRequest,
    SetMobilityConfigResponse,
)
from core.api.grpc.services_pb2 import (
    GetNodeServiceFileRequest,
    GetNodeServiceFileResponse,
    GetNodeServiceRequest,
    GetNodeServiceResponse,
    GetServiceDefaultsRequest,
    GetServiceDefaultsResponse,
    Service,
    ServiceAction,
    ServiceActionRequest,
    ServiceActionResponse,
    SetServiceDefaultsRequest,
    SetServiceDefaultsResponse,
)
from core.api.grpc.wlan_pb2 import (
    GetWlanConfigRequest,
    GetWlanConfigResponse,
    SetWlanConfigRequest,
    SetWlanConfigResponse,
    WlanLinkRequest,
    WlanLinkResponse,
)
from core.configservice.base import ConfigServiceBootError
from core.emane.modelmanager import EmaneModelManager
from core.emulator.coreemu import CoreEmu
from core.emulator.data import InterfaceData, LinkData, LinkOptions
from core.emulator.enumerations import (
    EventTypes,
    ExceptionLevels,
    MessageFlags,
    NodeTypes,
)
from core.emulator.session import NT, Session
from core.errors import CoreCommandError, CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import CoreNode, NodeBase
from core.nodes.network import CoreNetwork, WlanNode
from core.nodes.wireless import WirelessNode
from core.services.coreservices import ServiceManager

logger = logging.getLogger(__name__)
_ONE_DAY_IN_SECONDS: int = 60 * 60 * 24
_INTERFACE_REGEX: Pattern[str] = re.compile(r"beth(?P<node>[0-9a-fA-F]+)")
_MAX_WORKERS = 1000


class CoreGrpcServer(core_pb2_grpc.CoreApiServicer):
    """
    Create CoreGrpcServer instance

    :param coreemu: coreemu object
    """

    def __init__(self, coreemu: CoreEmu) -> None:
        super().__init__()
        self.coreemu: CoreEmu = coreemu
        self.running: bool = True
        self.server: Optional[grpc.Server] = None
        # catch signals
        signal.signal(signal.SIGHUP, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGUSR1, self._signal_handler)
        signal.signal(signal.SIGUSR2, self._signal_handler)

    def _signal_handler(self, signal_number: int, _) -> None:
        logger.info("caught signal: %s", signal_number)
        self.coreemu.shutdown()
        self.running = False
        if self.server:
            self.server.stop(None)
        sys.exit(signal_number)

    def _is_running(self, context) -> bool:
        return self.running and context.is_active()

    def _cancel_stream(self, context) -> None:
        context.abort(grpc.StatusCode.CANCELLED, "server stopping")

    def listen(self, address: str) -> None:
        logger.info("CORE gRPC API listening on: %s", address)
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS))
        core_pb2_grpc.add_CoreApiServicer_to_server(self, self.server)
        self.server.add_insecure_port(address)
        self.server.start()

        try:
            while True:
                time.sleep(_ONE_DAY_IN_SECONDS)
        except KeyboardInterrupt:
            self.server.stop(None)

    def get_session(self, session_id: int, context: ServicerContext) -> Session:
        """
        Retrieve session given the session id

        :param session_id: session id
        :param context:
        :return: session object that satisfies, if session not found then raise an
            exception
        :raises Exception: raises grpc exception when session does not exist
        """
        session = self.coreemu.sessions.get(session_id)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, f"session {session_id} not found")
        return session

    def get_node(
        self, session: Session, node_id: int, context: ServicerContext, _class: type[NT]
    ) -> NT:
        """
        Retrieve node given session and node id

        :param session: session that has the node
        :param node_id: node id
        :param context: request
        :param _class: type of node we are expecting
        :return: node object that satisfies. If node not found then raise an exception.
        :raises Exception: raises grpc exception when node does not exist
        """
        try:
            return session.get_node(node_id, _class)
        except CoreError as e:
            context.abort(grpc.StatusCode.NOT_FOUND, str(e))

    def move_node(
        self,
        context: ServicerContext,
        session_id: int,
        node_id: int,
        geo: core_pb2.Geo = None,
        position: core_pb2.Position = None,
        source: str = None,
    ):
        if not geo and not position:
            raise CoreError("move node must provide a geo or position to move")
        session = self.get_session(session_id, context)
        node = self.get_node(session, node_id, context, NodeBase)
        if geo:
            session.set_node_geo(node, geo.lon, geo.lat, geo.alt)
        else:
            session.set_node_pos(node, position.x, position.y)
        source = source if source else None
        session.broadcast_node(node, source=source)

    def validate_service(
        self, name: str, context: ServicerContext
    ) -> type[ConfigService]:
        """
        Validates a configuration service is a valid known service.

        :param name: name of service to validate
        :param context: grpc context
        :return: class for service to validate
        :raises Exception: raises grpc exception when service does not exist
        """
        service = self.coreemu.service_manager.services.get(name)
        if not service:
            context.abort(grpc.StatusCode.NOT_FOUND, f"unknown service {name}")
        return service

    def GetConfig(
        self, request: core_pb2.GetConfigRequest, context: ServicerContext
    ) -> core_pb2.GetConfigResponse:
        services = []
        for name in ServiceManager.services:
            service = ServiceManager.services[name]
            service_proto = Service(group=service.group, name=service.name)
            services.append(service_proto)
        config_services = []
        for service in self.coreemu.service_manager.services.values():
            service_proto = ConfigService(
                name=service.name,
                group=service.group,
                executables=service.executables,
                dependencies=service.dependencies,
                directories=service.directories,
                files=service.files,
                startup=service.startup,
                validate=service.validate,
                shutdown=service.shutdown,
                validation_mode=service.validation_mode.value,
                validation_timer=service.validation_timer,
                validation_period=service.validation_period,
            )
            config_services.append(service_proto)
        emane_models = [x.name for x in EmaneModelManager.models.values()]
        return core_pb2.GetConfigResponse(
            services=services,
            config_services=config_services,
            emane_models=emane_models,
        )

    def StartSession(
        self, request: core_pb2.StartSessionRequest, context: ServicerContext
    ) -> core_pb2.StartSessionResponse:
        """
        Start a session.

        :param request: start session request
        :param context: grpc context
        :return: start session response
        """
        logger.debug("start session: %s", request)
        session = self.get_session(request.session.id, context)

        # clear previous state and setup for creation
        session.clear()
        session.directory.mkdir(exist_ok=True)
        if request.definition:
            state = EventTypes.DEFINITION_STATE
        else:
            state = EventTypes.CONFIGURATION_STATE
        session.set_state(state)
        if request.session.user:
            session.set_user(request.session.user)

        # session options
        for option in request.session.options.values():
            if option.value:
                session.options.set(option.name, option.value)
        session.metadata = dict(request.session.metadata)

        # add servers
        for server in request.session.servers:
            session.distributed.add_server(server.name, server.host)

        # location
        if request.session.HasField("location"):
            grpcutils.session_location(session, request.session.location)

        # add all hooks
        for hook in request.session.hooks:
            state = EventTypes(hook.state)
            session.add_hook(state, hook.file, hook.data)

        # create nodes
        _, exceptions = grpcutils.create_nodes(session, request.session.nodes)
        if exceptions:
            exceptions = [str(x) for x in exceptions]
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)

        # check for configurations
        for node in request.session.nodes:
            core_node = self.get_node(session, node.id, context, NodeBase)
            grpcutils.configure_node(session, node, core_node, context)

        # create links
        links = []
        edit_links = []
        known_links = set()
        for link in request.session.links:
            iface1 = link.iface1.id if link.iface1 else None
            iface2 = link.iface2.id if link.iface2 else None
            if link.node1_id < link.node2_id:
                link_id = (link.node1_id, iface1, link.node2_id, iface2)
            else:
                link_id = (link.node2_id, iface2, link.node1_id, iface1)
            if link_id in known_links:
                edit_links.append(link)
            else:
                known_links.add(link_id)
                links.append(link)
        _, exceptions = grpcutils.create_links(session, links)
        if exceptions:
            exceptions = [str(x) for x in exceptions]
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)
        _, exceptions = grpcutils.edit_links(session, edit_links)
        if exceptions:
            exceptions = [str(x) for x in exceptions]
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)

        # set to instantiation and start
        if not request.definition:
            session.set_state(EventTypes.INSTANTIATION_STATE)
            # boot services
            boot_exceptions = session.instantiate()
            if boot_exceptions:
                exceptions = []
                for boot_exception in boot_exceptions:
                    for service_exception in boot_exception.args:
                        exceptions.append(str(service_exception))
                return core_pb2.StartSessionResponse(
                    result=False, exceptions=exceptions
                )
        return core_pb2.StartSessionResponse(result=True)

    def StopSession(
        self, request: core_pb2.StopSessionRequest, context: ServicerContext
    ) -> core_pb2.StopSessionResponse:
        """
        Stop a running session.

        :param request: stop session request
        :param context: grpc context
        :return: stop session response
        """
        logger.debug("stop session: %s", request)
        session = self.get_session(request.session_id, context)
        session.data_collect()
        session.shutdown()
        return core_pb2.StopSessionResponse(result=True)

    def CreateSession(
        self, request: core_pb2.CreateSessionRequest, context: ServicerContext
    ) -> core_pb2.CreateSessionResponse:
        """
        Create a session

        :param request: create-session request
        :param context:
        :return: a create-session response
        """
        logger.debug("create session: %s", request)
        session = self.coreemu.create_session(request.session_id)
        session.set_state(EventTypes.DEFINITION_STATE)
        session.location.setrefgeo(47.57917, -122.13232, 2.0)
        session.location.refscale = 150.0
        session_proto = grpcutils.convert_session(session)
        return core_pb2.CreateSessionResponse(session=session_proto)

    def DeleteSession(
        self, request: core_pb2.DeleteSessionRequest, context: ServicerContext
    ) -> core_pb2.DeleteSessionResponse:
        """
        Delete the session

        :param request: delete-session request
        :param context: context object
        :return: a delete-session response
        """
        logger.debug("delete session: %s", request)
        result = self.coreemu.delete_session(request.session_id)
        return core_pb2.DeleteSessionResponse(result=result)

    def GetSessions(
        self, request: core_pb2.GetSessionsRequest, context: ServicerContext
    ) -> core_pb2.GetSessionsResponse:
        """
        Get all currently known session overviews.

        :param request: get sessions request
        :param context: context object
        :return: a get sessions response
        """
        logger.debug("get sessions: %s", request)
        sessions = []
        for session_id in self.coreemu.sessions:
            session = self.coreemu.sessions[session_id]
            session_file = str(session.file_path) if session.file_path else None
            session_summary = core_pb2.SessionSummary(
                id=session_id,
                state=session.state.value,
                nodes=session.get_node_count(),
                file=session_file,
                dir=str(session.directory),
            )
            sessions.append(session_summary)
        return core_pb2.GetSessionsResponse(sessions=sessions)

    def CheckSession(
        self, request: core_pb2.GetSessionRequest, context: ServicerContext
    ) -> core_pb2.CheckSessionResponse:
        """
        Checks if a session exists.

        :param request: check session request
        :param context: context object
        :return: check session response
        """
        result = request.session_id in self.coreemu.sessions
        return core_pb2.CheckSessionResponse(result=result)

    def GetSession(
        self, request: core_pb2.GetSessionRequest, context: ServicerContext
    ) -> core_pb2.GetSessionResponse:
        """
        Retrieve requested session

        :param request: get-session request
        :param context: context object
        :return: get-session response
        """
        logger.debug("get session: %s", request)
        session = self.get_session(request.session_id, context)
        session_proto = grpcutils.convert_session(session)
        return core_pb2.GetSessionResponse(session=session_proto)

    def SessionAlert(
        self, request: core_pb2.SessionAlertRequest, context: ServicerContext
    ) -> core_pb2.SessionAlertResponse:
        session = self.get_session(request.session_id, context)
        level = ExceptionLevels(request.level)
        node_id = request.node_id if request.node_id else None
        session.exception(level, request.source, request.text, node_id)
        return core_pb2.SessionAlertResponse(result=True)

    def Events(self, request: core_pb2.EventsRequest, context: ServicerContext) -> None:
        session = self.get_session(request.session_id, context)
        event_types = set(request.events)
        if not event_types:
            event_types = set(core_pb2.EventType.Enum.values())

        streamer = EventStreamer(session, event_types)
        while self._is_running(context):
            event = streamer.process()
            if event:
                yield event

        streamer.remove_handlers()
        self._cancel_stream(context)

    def Throughputs(
        self, request: core_pb2.ThroughputsRequest, context: ServicerContext
    ) -> None:
        """
        Calculate average throughput after every certain amount of delay time

        :param request: throughputs request
        :param context: context object
        :return: nothing
        """
        session = self.get_session(request.session_id, context)
        delay = 3
        last_check = None
        last_stats = None

        while self._is_running(context):
            now = time.monotonic()
            stats = get_net_stats()
            # calculate average
            if last_check is not None:
                interval = now - last_check
                throughputs_event = core_pb2.ThroughputsEvent(session_id=session.id)
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
                    if key.startswith("beth"):
                        key = key.split(".")
                        node_id = _INTERFACE_REGEX.search(key[0]).group("node")
                        node_id = int(node_id, base=16)
                        iface_id = int(key[1])
                        session_id = key[2]
                        if session.short_session_id() != session_id:
                            continue
                        iface_throughput = throughputs_event.iface_throughputs.add()
                        iface_throughput.node_id = node_id
                        iface_throughput.iface_id = iface_id
                        iface_throughput.throughput = throughput
                    elif key.startswith("b."):
                        try:
                            key = key.split(".")
                            node_id = int(key[1], base=16)
                            session_id = key[2]
                            if session.short_session_id() != session_id:
                                continue
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

    def CpuUsage(
        self, request: core_pb2.CpuUsageRequest, context: ServicerContext
    ) -> None:
        cpu_usage = grpcutils.CpuUsage()
        while self._is_running(context):
            usage = cpu_usage.run()
            yield core_pb2.CpuUsageEvent(usage=usage)
            time.sleep(request.delay)

    def AddNode(
        self, request: core_pb2.AddNodeRequest, context: ServicerContext
    ) -> core_pb2.AddNodeResponse:
        """
        Add node to requested session

        :param request: add-node request
        :param context: context object
        :return: add-node response
        """
        logger.debug("add node: %s", request)
        session = self.get_session(request.session_id, context)
        _type = NodeTypes(request.node.type)
        _class = session.get_node_class(_type)
        position, options = grpcutils.add_node_data(_class, request.node)
        node = session.add_node(
            _class,
            request.node.id or None,
            request.node.name or None,
            request.node.server or None,
            position,
            options,
        )
        grpcutils.configure_node(session, request.node, node, context)
        source = request.source if request.source else None
        session.broadcast_node(node, MessageFlags.ADD, source)
        return core_pb2.AddNodeResponse(node_id=node.id)

    def GetNode(
        self, request: core_pb2.GetNodeRequest, context: ServicerContext
    ) -> core_pb2.GetNodeResponse:
        """
        Retrieve node

        :param request: get-node request
        :param context: context object
        :return: get-node response
        """
        logger.debug("get node: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, NodeBase)
        ifaces = []
        for iface_id in node.ifaces:
            iface = node.ifaces[iface_id]
            iface_proto = grpcutils.iface_to_proto(session, iface)
            ifaces.append(iface_proto)
        emane_configs = grpcutils.get_emane_model_configs_dict(session)
        node_emane_configs = emane_configs.get(node.id, [])
        node_proto = grpcutils.get_node_proto(session, node, node_emane_configs)
        links = get_links(session, node)
        return core_pb2.GetNodeResponse(node=node_proto, ifaces=ifaces, links=links)

    def MoveNode(
        self, request: core_pb2.MoveNodeRequest, context: ServicerContext
    ) -> core_pb2.MoveNodeResponse:
        """
        Move node, either by x,y position or geospatial.

        :param request: move node request
        :param context: context object
        :return: move nodes response
        """
        geo = request.geo if request.HasField("geo") else None
        position = request.position if request.HasField("position") else None
        self.move_node(
            context, request.session_id, request.node_id, geo, position, request.source
        )
        return core_pb2.MoveNodeResponse(result=True)

    def MoveNodes(
        self,
        request_iterator: Iterable[core_pb2.MoveNodesRequest],
        context: ServicerContext,
    ) -> core_pb2.MoveNodesResponse:
        """
        Stream node movements

        :param request_iterator: move nodes request iterator
        :param context: context object
        :return: move nodes response
        """
        for request in request_iterator:
            geo = request.geo if request.HasField("geo") else None
            position = request.position if request.HasField("position") else None
            self.move_node(
                context,
                request.session_id,
                request.node_id,
                geo,
                position,
                request.source,
            )
        return core_pb2.MoveNodesResponse()

    def EditNode(
        self, request: core_pb2.EditNodeRequest, context: ServicerContext
    ) -> core_pb2.EditNodeResponse:
        """
        Edit node

        :param request: edit-node request
        :param context: context object
        :return: edit-node response
        """
        logger.debug("edit node: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, NodeBase)
        node.icon = request.icon or None
        source = request.source or None
        session.broadcast_node(node, source=source)
        return core_pb2.EditNodeResponse(result=True)

    def DeleteNode(
        self, request: core_pb2.DeleteNodeRequest, context: ServicerContext
    ) -> core_pb2.DeleteNodeResponse:
        """
        Delete node

        :param request: delete-node request
        :param context: context object
        :return: core.api.grpc.core_pb2.DeleteNodeResponse
        """
        logger.debug("delete node: %s", request)
        session = self.get_session(request.session_id, context)
        result = False
        if request.node_id in session.nodes:
            node = self.get_node(session, request.node_id, context, NodeBase)
            result = session.delete_node(node.id)
            source = request.source if request.source else None
            session.broadcast_node(node, MessageFlags.DELETE, source)
        return core_pb2.DeleteNodeResponse(result=result)

    def NodeCommand(
        self, request: core_pb2.NodeCommandRequest, context: ServicerContext
    ) -> core_pb2.NodeCommandResponse:
        """
        Run command on a node

        :param request: node-command request
        :param context: context object
        :return: core.api.grpc.core_pb2.NodeCommandResponse
        """
        logger.debug("sending node command: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        try:
            output = node.cmd(request.command, request.wait, request.shell)
            return_code = 0
        except CoreCommandError as e:
            output = e.stderr
            return_code = e.returncode
        return core_pb2.NodeCommandResponse(output=output, return_code=return_code)

    def GetNodeTerminal(
        self, request: core_pb2.GetNodeTerminalRequest, context: ServicerContext
    ) -> core_pb2.GetNodeTerminalResponse:
        """
        Retrieve terminal command string of a node

        :param request: get-node-terminal request
        :param context: context object
        :return:  get-node-terminal response
        """
        logger.debug("getting node terminal: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        terminal = node.termcmdstring("/bin/bash")
        return core_pb2.GetNodeTerminalResponse(terminal=terminal)

    def AddLink(
        self, request: core_pb2.AddLinkRequest, context: ServicerContext
    ) -> core_pb2.AddLinkResponse:
        """
        Add link to a session

        :param request: add-link request
        :param context: context object
        :return: add-link response
        """
        logger.debug("add link: %s", request)
        session = self.get_session(request.session_id, context)
        node1_id = request.link.node1_id
        node2_id = request.link.node2_id
        self.get_node(session, node1_id, context, NodeBase)
        self.get_node(session, node2_id, context, NodeBase)
        iface1_data, iface2_data, options = grpcutils.add_link_data(request.link)
        node1_iface, node2_iface = session.add_link(
            node1_id, node2_id, iface1_data, iface2_data, options
        )
        iface1_data = None
        if node1_iface:
            if isinstance(node1_iface.node, CoreNetwork):
                iface1_data = InterfaceData(id=node1_iface.id)
            else:
                iface1_data = node1_iface.get_data()
        iface2_data = None
        if node2_iface:
            if isinstance(node2_iface.node, CoreNetwork):
                iface2_data = InterfaceData(id=node2_iface.id)
            else:
                iface2_data = node2_iface.get_data()
        source = request.source if request.source else None
        link_data = LinkData(
            message_type=MessageFlags.ADD,
            node1_id=node1_id,
            node2_id=node2_id,
            iface1=iface1_data,
            iface2=iface2_data,
            options=options,
            source=source,
        )
        session.broadcast_link(link_data)
        iface1_proto = None
        iface2_proto = None
        if node1_iface:
            iface1_proto = grpcutils.iface_to_proto(session, node1_iface)
        if node2_iface:
            iface2_proto = grpcutils.iface_to_proto(session, node2_iface)
        return core_pb2.AddLinkResponse(
            result=True, iface1=iface1_proto, iface2=iface2_proto
        )

    def EditLink(
        self, request: core_pb2.EditLinkRequest, context: ServicerContext
    ) -> core_pb2.EditLinkResponse:
        """
        Edit a link

        :param request: edit-link request
        :param context: context object
        :return: edit-link response
        """
        logger.debug("edit link: %s", request)
        session = self.get_session(request.session_id, context)
        node1_id = request.node1_id
        node2_id = request.node2_id
        iface1_id = request.iface1_id
        iface2_id = request.iface2_id
        options_proto = request.options
        options = LinkOptions(
            delay=options_proto.delay,
            bandwidth=options_proto.bandwidth,
            loss=options_proto.loss,
            dup=options_proto.dup,
            jitter=options_proto.jitter,
            mer=options_proto.mer,
            burst=options_proto.burst,
            mburst=options_proto.mburst,
            unidirectional=options_proto.unidirectional,
            key=options_proto.key,
            buffer=options_proto.buffer,
        )
        session.update_link(node1_id, node2_id, iface1_id, iface2_id, options)
        iface1 = InterfaceData(id=iface1_id)
        iface2 = InterfaceData(id=iface2_id)
        source = request.source if request.source else None
        link_data = LinkData(
            message_type=MessageFlags.NONE,
            node1_id=node1_id,
            node2_id=node2_id,
            iface1=iface1,
            iface2=iface2,
            options=options,
            source=source,
        )
        session.broadcast_link(link_data)
        return core_pb2.EditLinkResponse(result=True)

    def DeleteLink(
        self, request: core_pb2.DeleteLinkRequest, context: ServicerContext
    ) -> core_pb2.DeleteLinkResponse:
        """
        Delete a link

        :param request: delete-link request
        :param context: context object
        :return: delete-link response
        """
        logger.debug("delete link: %s", request)
        session = self.get_session(request.session_id, context)
        node1_id = request.node1_id
        node2_id = request.node2_id
        iface1_id = request.iface1_id
        iface2_id = request.iface2_id
        session.delete_link(node1_id, node2_id, iface1_id, iface2_id)
        iface1 = InterfaceData(id=iface1_id)
        iface2 = InterfaceData(id=iface2_id)
        source = request.source if request.source else None
        link_data = LinkData(
            message_type=MessageFlags.DELETE,
            node1_id=node1_id,
            node2_id=node2_id,
            iface1=iface1,
            iface2=iface2,
            source=source,
        )
        session.broadcast_link(link_data)
        return core_pb2.DeleteLinkResponse(result=True)

    def GetMobilityConfig(
        self, request: GetMobilityConfigRequest, context: ServicerContext
    ) -> GetMobilityConfigResponse:
        """
        Retrieve mobility configuration of a node

        :param request:
            get-mobility-configuration request
        :param context: context object
        :return: get-mobility-configuration response
        """
        logger.debug("get mobility config: %s", request)
        session = self.get_session(request.session_id, context)
        current_config = session.mobility.get_model_config(
            request.node_id, Ns2ScriptedMobility.name
        )
        config = get_config_options(current_config, Ns2ScriptedMobility)
        return GetMobilityConfigResponse(config=config)

    def SetMobilityConfig(
        self, request: SetMobilityConfigRequest, context: ServicerContext
    ) -> SetMobilityConfigResponse:
        """
        Set mobility configuration of a node

        :param request:
            set-mobility-configuration request
        :param context: context object
        :return: set-mobility-configuration response
        """
        logger.debug("set mobility config: %s", request)
        session = self.get_session(request.session_id, context)
        mobility_config = request.mobility_config
        session.mobility.set_model_config(
            mobility_config.node_id, Ns2ScriptedMobility.name, mobility_config.config
        )
        return SetMobilityConfigResponse(result=True)

    def MobilityAction(
        self, request: MobilityActionRequest, context: ServicerContext
    ) -> MobilityActionResponse:
        """
        Take mobility action whether to start, pause, stop or none of those

        :param request: mobility-action
            request
        :param context: context object
        :return: mobility-action response
        """
        logger.debug("mobility action: %s", request)
        session = self.get_session(request.session_id, context)
        node = grpcutils.get_mobility_node(session, request.node_id, context)
        if not node.mobility:
            context.abort(
                grpc.StatusCode.NOT_FOUND, f"node({node.name}) does not have mobility"
            )
        result = True
        if request.action == MobilityAction.START:
            node.mobility.start()
        elif request.action == MobilityAction.PAUSE:
            node.mobility.pause()
        elif request.action == MobilityAction.STOP:
            node.mobility.stop(move_initial=True)
        else:
            result = False
        return MobilityActionResponse(result=result)

    def GetServiceDefaults(
        self, request: GetServiceDefaultsRequest, context: ServicerContext
    ) -> GetServiceDefaultsResponse:
        """
        Retrieve all the default services of all node types in a session

        :param request: get-default-service request
        :param context: context object
        :return: get-service-defaults response about all the available default services
        """
        logger.debug("get service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        defaults = grpcutils.get_default_services(session)
        return GetServiceDefaultsResponse(defaults=defaults)

    def SetServiceDefaults(
        self, request: SetServiceDefaultsRequest, context: ServicerContext
    ) -> SetServiceDefaultsResponse:
        """
        Set new default services to the session after whipping out the old ones

        :param request: set-service-defaults request
        :param context: context object
        :return: set-service-defaults response
        """
        logger.debug("set service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        session.services.default_services.clear()
        for service_defaults in request.defaults:
            session.services.default_services[
                service_defaults.model
            ] = service_defaults.services
        return SetServiceDefaultsResponse(result=True)

    def GetNodeService(
        self, request: GetNodeServiceRequest, context: ServicerContext
    ) -> GetNodeServiceResponse:
        """
        Retrieve a requested service from a node

        :param request: get-node-service
            request
        :param context: context object
        :return: get-node-service response about the requested service
        """
        logger.debug("get node service: %s", request)
        session = self.get_session(request.session_id, context)
        service = session.services.get_service(
            request.node_id, request.service, default_service=True
        )
        service_proto = grpcutils.get_service_configuration(service)
        return GetNodeServiceResponse(service=service_proto)

    def GetNodeServiceFile(
        self, request: GetNodeServiceFileRequest, context: ServicerContext
    ) -> GetNodeServiceFileResponse:
        """
        Retrieve a requested service file from a node

        :param request:
            get-node-service request
        :param context: context object
        :return: get-node-service response about the requested service
        """
        logger.debug("get node service file: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        file_data = session.services.get_service_file(
            node, request.service, request.file
        )
        return GetNodeServiceFileResponse(data=file_data.data)

    def ServiceAction(
        self, request: ServiceActionRequest, context: ServicerContext
    ) -> ServiceActionResponse:
        """
        Take action whether to start, stop, restart, validate the service or none of
        the above.

        :param request: service-action request
        :param context: context object
        :return: service-action response about status of action
        """
        logger.debug("service action: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        service = None
        for current_service in node.services:
            if current_service.name == request.service:
                service = current_service
                break

        if not service:
            context.abort(grpc.StatusCode.NOT_FOUND, "service not found")

        status = -1
        if request.action == ServiceAction.START:
            status = session.services.startup_service(node, service, wait=True)
        elif request.action == ServiceAction.STOP:
            status = session.services.stop_service(node, service)
        elif request.action == ServiceAction.RESTART:
            status = session.services.stop_service(node, service)
            if not status:
                status = session.services.startup_service(node, service, wait=True)
        elif request.action == ServiceAction.VALIDATE:
            status = session.services.validate_service(node, service)

        result = False
        if not status:
            result = True

        return ServiceActionResponse(result=result)

    def ConfigServiceAction(
        self, request: ServiceActionRequest, context: ServicerContext
    ) -> ServiceActionResponse:
        """
        Take action whether to start, stop, restart, validate the config service or
        none of the above.

        :param request: service action request
        :param context: context object
        :return: service action response about status of action
        """
        logger.debug("service action: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        service = node.config_services.get(request.service)
        if not service:
            context.abort(grpc.StatusCode.NOT_FOUND, "config service not found")
        result = False
        if request.action == ServiceAction.START:
            try:
                service.start()
                result = True
            except ConfigServiceBootError:
                pass
        elif request.action == ServiceAction.STOP:
            service.stop()
            result = True
        elif request.action == ServiceAction.RESTART:
            service.stop()
            try:
                service.start()
                result = True
            except ConfigServiceBootError:
                pass
        elif request.action == ServiceAction.VALIDATE:
            try:
                service.run_validation()
                result = True
            except ConfigServiceBootError:
                pass
        return ServiceActionResponse(result=result)

    def GetWlanConfig(
        self, request: GetWlanConfigRequest, context: ServicerContext
    ) -> GetWlanConfigResponse:
        """
        Retrieve wireless-lan configuration of a node

        :param request: get-wlan-configuration request
        :param context: core.api.grpc.core_pb2.GetWlanConfigResponse
        :return: get-wlan-configuration response about the wlan configuration of a node
        """
        logger.debug("get wlan config: %s", request)
        session = self.get_session(request.session_id, context)
        current_config = session.mobility.get_model_config(
            request.node_id, BasicRangeModel.name
        )
        config = get_config_options(current_config, BasicRangeModel)
        return GetWlanConfigResponse(config=config)

    def SetWlanConfig(
        self, request: SetWlanConfigRequest, context: ServicerContext
    ) -> SetWlanConfigResponse:
        """
        Set configuration data for a model

        :param request: set-wlan-configuration request
        :param context: context object
        :return: set-wlan-configuration response
        """
        logger.debug("set wlan config: %s", request)
        session = self.get_session(request.session_id, context)
        node_id = request.wlan_config.node_id
        config = request.wlan_config.config
        session.mobility.set_model_config(node_id, BasicRangeModel.name, config)
        if session.is_running():
            node = self.get_node(session, node_id, context, WlanNode)
            node.updatemodel(config)
        return SetWlanConfigResponse(result=True)

    def GetEmaneModelConfig(
        self, request: GetEmaneModelConfigRequest, context: ServicerContext
    ) -> GetEmaneModelConfigResponse:
        """
        Retrieve EMANE model configuration of a node

        :param request:
            get-EMANE-model-configuration request
        :param context: context object
        :return: get-EMANE-model-configuration response
        """
        logger.debug("get emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        model = session.emane.get_model(request.model)
        _id = utils.iface_config_id(request.node_id, request.iface_id)
        current_config = session.emane.get_config(_id, request.model)
        config = get_config_options(current_config, model)
        return GetEmaneModelConfigResponse(config=config)

    def SetEmaneModelConfig(
        self, request: SetEmaneModelConfigRequest, context: ServicerContext
    ) -> SetEmaneModelConfigResponse:
        """
        Set EMANE model configuration of a node

        :param request:
            set-EMANE-model-configuration request
        :param context: context object
        :return: set-EMANE-model-configuration response
        """
        logger.debug("set emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        model_config = request.emane_model_config
        _id = utils.iface_config_id(model_config.node_id, model_config.iface_id)
        session.emane.set_config(_id, model_config.model, model_config.config)
        return SetEmaneModelConfigResponse(result=True)

    def SaveXml(
        self, request: core_pb2.SaveXmlRequest, context: ServicerContext
    ) -> core_pb2.SaveXmlResponse:
        """
        Export the session into the EmulationScript XML format

        :param request: save xml request
        :param context: context object
        :return: save-xml response
        """
        logger.debug("save xml: %s", request)
        session = self.get_session(request.session_id, context)
        _, temp_path = tempfile.mkstemp()
        session.save_xml(temp_path)
        with open(temp_path, "r") as xml_file:
            data = xml_file.read()
        return core_pb2.SaveXmlResponse(data=data)

    def OpenXml(
        self, request: core_pb2.OpenXmlRequest, context: ServicerContext
    ) -> core_pb2.OpenXmlResponse:
        """
        Import a session from the EmulationScript XML format

        :param request: open-xml request
        :param context: context object
        :return: Open-XML response or raise an exception if invalid XML file
        """
        logger.debug("open xml: %s", request)
        session = self.coreemu.create_session()
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(request.data.encode())
        temp.close()
        temp_path = Path(temp.name)
        file_path = Path(request.file)
        try:
            session.open_xml(temp_path, request.start)
            session.name = file_path.name
            session.file_path = file_path
            return core_pb2.OpenXmlResponse(session_id=session.id, result=True)
        except IOError:
            logger.exception("error opening session file")
            self.coreemu.delete_session(session.id)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid xml file")
        finally:
            os.unlink(temp.name)

    def GetInterfaces(
        self, request: core_pb2.GetInterfacesRequest, context: ServicerContext
    ) -> core_pb2.GetInterfacesResponse:
        """
        Retrieve all the interfaces of the system including bridges, virtual ethernet,
        and loopback.

        :param request: get-interfaces request
        :param context: context object
        :return: get-interfaces response that has all the system's interfaces
        """
        ifaces = []
        for iface in os.listdir("/sys/class/net"):
            if iface.startswith("b.") or iface.startswith("veth") or iface == "lo":
                continue
            ifaces.append(iface)
        return core_pb2.GetInterfacesResponse(ifaces=ifaces)

    def EmaneLink(
        self, request: EmaneLinkRequest, context: ServicerContext
    ) -> EmaneLinkResponse:
        """
        Helps broadcast wireless link/unlink between EMANE nodes.

        :param request: get-interfaces request
        :param context: context object
        :return: emane link response with success status
        """
        logger.debug("emane link: %s", request)
        session = self.get_session(request.session_id, context)
        flag = MessageFlags.ADD if request.linked else MessageFlags.DELETE
        link = session.emane.get_nem_link(request.nem1, request.nem2, flag)
        if link:
            session.broadcast_link(link)
            return EmaneLinkResponse(result=True)
        else:
            return EmaneLinkResponse(result=False)

    def GetNodeConfigService(
        self, request: GetNodeConfigServiceRequest, context: ServicerContext
    ) -> GetNodeConfigServiceResponse:
        """
        Gets configuration, for a given configuration service, for a given node.

        :param request: get node config service request
        :param context: grpc context
        :return: get node config service response
        """
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        self.validate_service(request.name, context)
        service = node.config_services.get(request.name)
        if service:
            config = service.render_config()
        else:
            service = self.coreemu.service_manager.get_service(request.name)
            config = {x.id: x.default for x in service.default_configs}
        return GetNodeConfigServiceResponse(config=config)

    def GetConfigServiceRendered(
        self, request: GetConfigServiceRenderedRequest, context: ServicerContext
    ) -> GetConfigServiceRenderedResponse:
        """
        Retrieves the rendered file data for a given config service on a node.

        :param request: config service render request
        :param context: grpc context
        :return: rendered config service files
        """
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        self.validate_service(request.name, context)
        service = node.config_services.get(request.name)
        if not service:
            context.abort(
                grpc.StatusCode.NOT_FOUND, f"unknown node service {request.name}"
            )
        rendered = service.get_rendered_templates()
        return GetConfigServiceRenderedResponse(rendered=rendered)

    def GetConfigServiceDefaults(
        self, request: GetConfigServiceDefaultsRequest, context: ServicerContext
    ) -> GetConfigServiceDefaultsResponse:
        """
        Get default values for a given configuration service.

        :param request: get config service defaults request
        :param context: grpc context
        :return: get config service defaults response
        """
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        service_class = self.validate_service(request.name, context)
        service = service_class(node)
        templates = service.get_templates()
        config = {}
        for configuration in service.default_configs:
            config_option = common_pb2.ConfigOption(
                label=configuration.label,
                name=configuration.id,
                value=configuration.default,
                type=configuration.type.value,
                select=configuration.options,
                group="Settings",
            )
            config[configuration.id] = config_option
        modes = []
        for name, mode_config in service.modes.items():
            mode = configservices_pb2.ConfigMode(name=name, config=mode_config)
            modes.append(mode)
        return GetConfigServiceDefaultsResponse(
            templates=templates, config=config, modes=modes
        )

    def GetEmaneEventChannel(
        self, request: GetEmaneEventChannelRequest, context: ServicerContext
    ) -> GetEmaneEventChannelResponse:
        session = self.get_session(request.session_id, context)
        service = session.emane.nem_service.get(request.nem_id)
        if not service:
            context.abort(grpc.StatusCode.NOT_FOUND, f"unknown nem id {request.nem_id}")
        return GetEmaneEventChannelResponse(
            group=service.group, port=service.port, device=service.device
        )

    def ExecuteScript(self, request, context):
        existing_sessions = set(self.coreemu.sessions.keys())
        file_path = Path(request.script)
        utils.execute_script(self.coreemu, file_path, request.args)
        current_sessions = set(self.coreemu.sessions.keys())
        new_sessions = list(current_sessions.difference(existing_sessions))
        new_session = -1
        if new_sessions:
            new_session = new_sessions[0]
        return ExecuteScriptResponse(session_id=new_session)

    def WlanLink(
        self, request: WlanLinkRequest, context: ServicerContext
    ) -> WlanLinkResponse:
        session = self.get_session(request.session_id, context)
        wlan = self.get_node(session, request.wlan, context, WlanNode)
        if not isinstance(wlan.wireless_model, BasicRangeModel):
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"wlan node {request.wlan} is not using BasicRangeModel",
            )
        node1 = self.get_node(session, request.node1_id, context, CoreNode)
        node2 = self.get_node(session, request.node2_id, context, CoreNode)
        node1_iface, node2_iface = None, None
        for iface in node1.get_ifaces(control=False):
            if iface.net == wlan:
                node1_iface = iface
                break
        for iface in node2.get_ifaces(control=False):
            if iface.net == wlan:
                node2_iface = iface
                break
        result = False
        if node1_iface and node2_iface:
            if request.linked:
                wlan.link(node1_iface, node2_iface)
            else:
                wlan.unlink(node1_iface, node2_iface)
            wlan.wireless_model.sendlinkmsg(
                node1_iface, node2_iface, unlink=not request.linked
            )
            result = True
        return WlanLinkResponse(result=result)

    def EmanePathlosses(
        self,
        request_iterator: Iterable[EmanePathlossesRequest],
        context: ServicerContext,
    ) -> EmanePathlossesResponse:
        for request in request_iterator:
            session = self.get_session(request.session_id, context)
            node1 = self.get_node(session, request.node1_id, context, CoreNode)
            nem1 = grpcutils.get_nem_id(session, node1, request.iface1_id, context)
            node2 = self.get_node(session, request.node2_id, context, CoreNode)
            nem2 = grpcutils.get_nem_id(session, node2, request.iface2_id, context)
            session.emane.publish_pathloss(nem1, nem2, request.rx1, request.rx2)
        return EmanePathlossesResponse()

    def Linked(
        self, request: LinkedRequest, context: ServicerContext
    ) -> LinkedResponse:
        session = self.get_session(request.session_id, context)
        session.linked(
            request.node1_id,
            request.node2_id,
            request.iface1_id,
            request.iface2_id,
            request.linked,
        )
        return LinkedResponse()

    def WirelessLinked(
        self, request: WirelessLinkedRequest, context: ServicerContext
    ) -> WirelessLinkedResponse:
        session = self.get_session(request.session_id, context)
        wireless = self.get_node(session, request.wireless_id, context, WirelessNode)
        wireless.link_control(request.node1_id, request.node2_id, request.linked)
        return WirelessLinkedResponse()

    def WirelessConfig(
        self, request: WirelessConfigRequest, context: ServicerContext
    ) -> WirelessConfigResponse:
        session = self.get_session(request.session_id, context)
        wireless = self.get_node(session, request.wireless_id, context, WirelessNode)
        options1 = request.options1
        options2 = options1
        if request.HasField("options2"):
            options2 = request.options2
        options1 = grpcutils.convert_options_proto(options1)
        options2 = grpcutils.convert_options_proto(options2)
        wireless.link_config(request.node1_id, request.node2_id, options1, options2)
        return WirelessConfigResponse()

    def GetWirelessConfig(
        self, request: GetWirelessConfigRequest, context: ServicerContext
    ) -> GetWirelessConfigResponse:
        session = self.get_session(request.session_id, context)
        try:
            wireless = session.get_node(request.node_id, WirelessNode)
            configs = wireless.get_config()
        except CoreError:
            configs = {x.id: x for x in WirelessNode.options}
        config_options = {}
        for config in configs.values():
            config_option = common_pb2.ConfigOption(
                label=config.label,
                name=config.id,
                value=config.default,
                type=config.type.value,
                select=config.options,
                group=config.group,
            )
            config_options[config.id] = config_option
        return GetWirelessConfigResponse(config=config_options)
