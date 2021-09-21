import atexit
import logging
import os
import re
import tempfile
import threading
import time
from concurrent import futures
from typing import Iterable, Optional, Pattern, Type

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
    GetConfigServicesRequest,
    GetConfigServicesResponse,
    GetNodeConfigServiceConfigsRequest,
    GetNodeConfigServiceConfigsResponse,
    GetNodeConfigServiceRequest,
    GetNodeConfigServiceResponse,
    GetNodeConfigServicesRequest,
    GetNodeConfigServicesResponse,
    SetNodeConfigServiceRequest,
    SetNodeConfigServiceResponse,
)
from core.api.grpc.core_pb2 import ExecuteScriptResponse
from core.api.grpc.emane_pb2 import (
    EmaneLinkRequest,
    EmaneLinkResponse,
    EmanePathlossesRequest,
    EmanePathlossesResponse,
    GetEmaneConfigRequest,
    GetEmaneConfigResponse,
    GetEmaneEventChannelRequest,
    GetEmaneEventChannelResponse,
    GetEmaneModelConfigRequest,
    GetEmaneModelConfigResponse,
    GetEmaneModelConfigsRequest,
    GetEmaneModelConfigsResponse,
    GetEmaneModelsRequest,
    GetEmaneModelsResponse,
    SetEmaneConfigRequest,
    SetEmaneConfigResponse,
    SetEmaneModelConfigRequest,
    SetEmaneModelConfigResponse,
)
from core.api.grpc.events import EventStreamer
from core.api.grpc.grpcutils import get_config_options, get_links, get_net_stats
from core.api.grpc.mobility_pb2 import (
    GetMobilityConfigRequest,
    GetMobilityConfigResponse,
    GetMobilityConfigsRequest,
    GetMobilityConfigsResponse,
    MobilityAction,
    MobilityActionRequest,
    MobilityActionResponse,
    SetMobilityConfigRequest,
    SetMobilityConfigResponse,
)
from core.api.grpc.services_pb2 import (
    GetNodeServiceConfigsRequest,
    GetNodeServiceConfigsResponse,
    GetNodeServiceFileRequest,
    GetNodeServiceFileResponse,
    GetNodeServiceRequest,
    GetNodeServiceResponse,
    GetServiceDefaultsRequest,
    GetServiceDefaultsResponse,
    GetServicesRequest,
    GetServicesResponse,
    Service,
    ServiceAction,
    ServiceActionRequest,
    ServiceActionResponse,
    SetNodeServiceFileRequest,
    SetNodeServiceFileResponse,
    SetNodeServiceRequest,
    SetNodeServiceResponse,
    SetServiceDefaultsRequest,
    SetServiceDefaultsResponse,
)
from core.api.grpc.wlan_pb2 import (
    GetWlanConfigRequest,
    GetWlanConfigResponse,
    GetWlanConfigsRequest,
    GetWlanConfigsResponse,
    SetWlanConfigRequest,
    SetWlanConfigResponse,
    WlanLinkRequest,
    WlanLinkResponse,
)
from core.emulator.coreemu import CoreEmu
from core.emulator.data import InterfaceData, LinkData, LinkOptions, NodeOptions
from core.emulator.enumerations import (
    EventTypes,
    ExceptionLevels,
    LinkTypes,
    MessageFlags,
)
from core.emulator.session import NT, Session
from core.errors import CoreCommandError, CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import CoreNode, NodeBase
from core.nodes.network import CtrlNet, PtpNet, WlanNode
from core.services.coreservices import ServiceManager

_ONE_DAY_IN_SECONDS: int = 60 * 60 * 24
_INTERFACE_REGEX: Pattern = re.compile(r"veth(?P<node>[0-9a-fA-F]+)")
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
        atexit.register(self._exit_handler)

    def _exit_handler(self) -> None:
        logging.debug("catching exit, stop running")
        self.running = False

    def _is_running(self, context) -> bool:
        return self.running and context.is_active()

    def _cancel_stream(self, context) -> None:
        context.abort(grpc.StatusCode.CANCELLED, "server stopping")

    def listen(self, address: str) -> None:
        logging.info("CORE gRPC API listening on: %s", address)
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
        self, session: Session, node_id: int, context: ServicerContext, _class: Type[NT]
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

    def validate_service(
        self, name: str, context: ServicerContext
    ) -> Type[ConfigService]:
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

    def StartSession(
        self, request: core_pb2.StartSessionRequest, context: ServicerContext
    ) -> core_pb2.StartSessionResponse:
        """
        Start a session.

        :param request: start session request
        :param context: grpc context
        :return: start session response
        """
        logging.debug("start session: %s", request)
        session = self.get_session(request.session_id, context)

        # clear previous state and setup for creation
        session.clear()
        if not os.path.exists(session.session_dir):
            os.mkdir(session.session_dir)
        session.set_state(EventTypes.CONFIGURATION_STATE)

        # location
        if request.HasField("location"):
            grpcutils.session_location(session, request.location)

        # add all hooks
        for hook in request.hooks:
            state = EventTypes(hook.state)
            session.add_hook(state, hook.file, hook.data)

        # create nodes
        _, exceptions = grpcutils.create_nodes(session, request.nodes)
        if exceptions:
            exceptions = [str(x) for x in exceptions]
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)

        # emane configs
        config = session.emane.get_configs()
        config.update(request.emane_config)
        for config in request.emane_model_configs:
            _id = utils.iface_config_id(config.node_id, config.iface_id)
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

        # config service configs
        for config in request.config_service_configs:
            node = self.get_node(session, config.node_id, context, CoreNode)
            service = node.config_services[config.name]
            if config.config:
                service.set_config(config.config)
            for name, template in config.templates.items():
                service.set_template(name, template)

        # service file configs
        for config in request.service_file_configs:
            session.services.set_service_file(
                config.node_id, config.service, config.file, config.data
            )

        # create links
        _, exceptions = grpcutils.create_links(session, request.links)
        if exceptions:
            exceptions = [str(x) for x in exceptions]
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)

        # asymmetric links
        _, exceptions = grpcutils.edit_links(session, request.asymmetric_links)
        if exceptions:
            exceptions = [str(x) for x in exceptions]
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)

        # set to instantiation and start
        session.set_state(EventTypes.INSTANTIATION_STATE)

        # boot services
        boot_exceptions = session.instantiate()
        if boot_exceptions:
            exceptions = []
            for boot_exception in boot_exceptions:
                for service_exception in boot_exception.args:
                    exceptions.append(str(service_exception))
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)
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
        logging.debug("stop session: %s", request)
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
        logging.debug("create session: %s", request)
        session = self.coreemu.create_session(request.session_id)
        session.set_state(EventTypes.DEFINITION_STATE)
        session.location.setrefgeo(47.57917, -122.13232, 2.0)
        session.location.refscale = 150.0
        return core_pb2.CreateSessionResponse(
            session_id=session.id, state=session.state.value
        )

    def DeleteSession(
        self, request: core_pb2.DeleteSessionRequest, context: ServicerContext
    ) -> core_pb2.DeleteSessionResponse:
        """
        Delete the session

        :param request: delete-session request
        :param context: context object
        :return: a delete-session response
        """
        logging.debug("delete session: %s", request)
        result = self.coreemu.delete_session(request.session_id)
        return core_pb2.DeleteSessionResponse(result=result)

    def GetSessions(
        self, request: core_pb2.GetSessionsRequest, context: ServicerContext
    ) -> core_pb2.GetSessionsResponse:
        """
        Retrieve running session's

        :param request: get-session request
        :param context: context object
        :return: a delete-session response
        """
        logging.debug("get sessions: %s", request)
        sessions = []
        for session_id in self.coreemu.sessions:
            session = self.coreemu.sessions[session_id]
            session_summary = core_pb2.SessionSummary(
                id=session_id,
                state=session.state.value,
                nodes=session.get_node_count(),
                file=session.file_name,
                dir=session.session_dir,
            )
            sessions.append(session_summary)
        return core_pb2.GetSessionsResponse(sessions=sessions)

    def GetSessionLocation(
        self, request: core_pb2.GetSessionLocationRequest, context: ServicerContext
    ) -> core_pb2.GetSessionLocationResponse:
        """
        Retrieve a requested session location

        :param request: get-session-location request
        :param context: context object
        :return: a get-session-location response
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

    def SetSessionLocation(
        self, request: core_pb2.SetSessionLocationRequest, context: ServicerContext
    ) -> core_pb2.SetSessionLocationResponse:
        """
        Set session location

        :param request: set-session-location request
        :param context: context object
        :return: a set-session-location-response
        """
        logging.debug("set session location: %s", request)
        session = self.get_session(request.session_id, context)
        grpcutils.session_location(session, request.location)
        return core_pb2.SetSessionLocationResponse(result=True)

    def SetSessionState(
        self, request: core_pb2.SetSessionStateRequest, context: ServicerContext
    ) -> core_pb2.SetSessionStateResponse:
        """
        Set session state

        :param request: set-session-state request
        :param context:context object
        :return: set-session-state response
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

    def SetSessionUser(
        self, request: core_pb2.SetSessionUserRequest, context: ServicerContext
    ) -> core_pb2.SetSessionUserResponse:
        """
        Sets the user for a session.

        :param request: set session user request
        :param context: context object
        :return: set session user response
        """
        logging.debug("set session user: %s", request)
        session = self.get_session(request.session_id, context)
        session.user = request.user
        return core_pb2.SetSessionUserResponse(result=True)

    def GetSessionOptions(
        self, request: core_pb2.GetSessionOptionsRequest, context: ServicerContext
    ) -> core_pb2.GetSessionOptionsResponse:
        """
        Retrieve session options.

        :param request:
            get-session-options request
        :param context: context object
        :return: get-session-options response about all session's options
        """
        logging.debug("get session options: %s", request)
        session = self.get_session(request.session_id, context)
        current_config = session.options.get_configs()
        default_config = session.options.default_values()
        default_config.update(current_config)
        config = get_config_options(default_config, session.options)
        return core_pb2.GetSessionOptionsResponse(config=config)

    def SetSessionOptions(
        self, request: core_pb2.SetSessionOptionsRequest, context: ServicerContext
    ) -> core_pb2.SetSessionOptionsResponse:
        """
        Update a session's configuration

        :param request: set-session-options request
        :param context: context object
        :return: set-session-options response
        """
        logging.debug("set session options: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.options.get_configs()
        config.update(request.config)
        return core_pb2.SetSessionOptionsResponse(result=True)

    def GetSessionMetadata(
        self, request: core_pb2.GetSessionMetadataRequest, context: ServicerContext
    ) -> core_pb2.GetSessionMetadataResponse:
        """
        Retrieve session metadata.

        :param request: get session metadata
            request
        :param context: context object
        :return: get session metadata response
        """
        logging.debug("get session metadata: %s", request)
        session = self.get_session(request.session_id, context)
        return core_pb2.GetSessionMetadataResponse(config=session.metadata)

    def SetSessionMetadata(
        self, request: core_pb2.SetSessionMetadataRequest, context: ServicerContext
    ) -> core_pb2.SetSessionMetadataResponse:
        """
        Update a session's metadata.

        :param request: set metadata request
        :param context: context object
        :return: set metadata response
        """
        logging.debug("set session metadata: %s", request)
        session = self.get_session(request.session_id, context)
        session.metadata = dict(request.config)
        return core_pb2.SetSessionMetadataResponse(result=True)

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
        logging.debug("get session: %s", request)
        session = self.get_session(request.session_id, context)
        links = []
        nodes = []
        for _id in session.nodes:
            node = session.nodes[_id]
            if not isinstance(node, (PtpNet, CtrlNet)):
                node_proto = grpcutils.get_node_proto(session, node)
                nodes.append(node_proto)
            node_links = get_links(node)
            links.extend(node_links)
        default_services = grpcutils.get_default_services(session)
        x, y, z = session.location.refxyz
        lat, lon, alt = session.location.refgeo
        location = core_pb2.SessionLocation(
            x=x, y=y, z=z, lat=lat, lon=lon, alt=alt, scale=session.location.refscale
        )
        hooks = grpcutils.get_hooks(session)
        emane_models = grpcutils.get_emane_models(session)
        emane_config = grpcutils.get_emane_config(session)
        emane_model_configs = grpcutils.get_emane_model_configs(session)
        wlan_configs = grpcutils.get_wlan_configs(session)
        mobility_configs = grpcutils.get_mobility_configs(session)
        service_configs = grpcutils.get_node_service_configs(session)
        config_service_configs = grpcutils.get_node_config_service_configs(session)
        session_proto = core_pb2.Session(
            id=session.id,
            state=session.state.value,
            nodes=nodes,
            links=links,
            dir=session.session_dir,
            user=session.user,
            default_services=default_services,
            location=location,
            hooks=hooks,
            emane_models=emane_models,
            emane_config=emane_config,
            emane_model_configs=emane_model_configs,
            wlan_configs=wlan_configs,
            service_configs=service_configs,
            config_service_configs=config_service_configs,
            mobility_configs=mobility_configs,
            metadata=session.metadata,
            file=session.file_name,
        )
        return core_pb2.GetSessionResponse(session=session_proto)

    def AddSessionServer(
        self, request: core_pb2.AddSessionServerRequest, context: ServicerContext
    ) -> core_pb2.AddSessionServerResponse:
        """
        Add distributed server to a session.

        :param request: get-session
            request
        :param context: context object
        :return: add session server response
        """
        session = self.get_session(request.session_id, context)
        session.distributed.add_server(request.name, request.host)
        return core_pb2.AddSessionServerResponse(result=True)

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
                    if key.startswith("veth"):
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
        logging.debug("add node: %s", request)
        session = self.get_session(request.session_id, context)
        _type, _id, options = grpcutils.add_node_data(request.node)
        _class = session.get_node_class(_type)
        node = session.add_node(_class, _id, options)
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
        logging.debug("get node: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, NodeBase)
        ifaces = []
        for iface_id in node.ifaces:
            iface = node.ifaces[iface_id]
            iface_proto = grpcutils.iface_to_proto(request.node_id, iface)
            ifaces.append(iface_proto)
        node_proto = grpcutils.get_node_proto(session, node)
        return core_pb2.GetNodeResponse(node=node_proto, ifaces=ifaces)

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
            if not request.WhichOneof("move_type"):
                raise CoreError("move nodes must provide a move type")
            session = self.get_session(request.session_id, context)
            node = self.get_node(session, request.node_id, context, NodeBase)
            options = NodeOptions()
            has_geo = request.HasField("geo")
            if has_geo:
                logging.info("has geo")
                lat = request.geo.lat
                lon = request.geo.lon
                alt = request.geo.alt
                options.set_location(lat, lon, alt)
            else:
                x = request.position.x
                y = request.position.y
                logging.info("has pos: %s,%s", x, y)
                options.set_position(x, y)
            session.edit_node(node.id, options)
            source = request.source if request.source else None
            if not has_geo:
                session.broadcast_node(node, source=source)
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
        logging.debug("edit node: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, NodeBase)
        options = NodeOptions(icon=request.icon)
        if request.HasField("position"):
            x = request.position.x
            y = request.position.y
            options.set_position(x, y)
        has_geo = request.HasField("geo")
        if has_geo:
            lat = request.geo.lat
            lon = request.geo.lon
            alt = request.geo.alt
            options.set_location(lat, lon, alt)
        result = True
        try:
            session.edit_node(node.id, options)
            source = None
            if request.source:
                source = request.source
            if not has_geo:
                session.broadcast_node(node, source=source)
        except CoreError:
            result = False
        return core_pb2.EditNodeResponse(result=result)

    def DeleteNode(
        self, request: core_pb2.DeleteNodeRequest, context: ServicerContext
    ) -> core_pb2.DeleteNodeResponse:
        """
        Delete node

        :param request: delete-node request
        :param context: context object
        :return: core.api.grpc.core_pb2.DeleteNodeResponse
        """
        logging.debug("delete node: %s", request)
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
        logging.debug("sending node command: %s", request)
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
        logging.debug("getting node terminal: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        terminal = node.termcmdstring("/bin/bash")
        return core_pb2.GetNodeTerminalResponse(terminal=terminal)

    def GetNodeLinks(
        self, request: core_pb2.GetNodeLinksRequest, context: ServicerContext
    ) -> core_pb2.GetNodeLinksResponse:
        """
        Retrieve all links form a requested node

        :param request: get-node-links request
        :param context: context object
        :return: get-node-links response
        """
        logging.debug("get node links: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, NodeBase)
        links = get_links(node)
        return core_pb2.GetNodeLinksResponse(links=links)

    def AddLink(
        self, request: core_pb2.AddLinkRequest, context: ServicerContext
    ) -> core_pb2.AddLinkResponse:
        """
        Add link to a session

        :param request: add-link request
        :param context: context object
        :return: add-link response
        """
        logging.debug("add link: %s", request)
        session = self.get_session(request.session_id, context)
        node1_id = request.link.node1_id
        node2_id = request.link.node2_id
        self.get_node(session, node1_id, context, NodeBase)
        self.get_node(session, node2_id, context, NodeBase)
        iface1_data, iface2_data, options, link_type = grpcutils.add_link_data(
            request.link
        )
        node1_iface, node2_iface = session.add_link(
            node1_id, node2_id, iface1_data, iface2_data, options, link_type
        )
        iface1_data = None
        if node1_iface:
            iface1_data = grpcutils.iface_to_data(node1_iface)
        iface2_data = None
        if node2_iface:
            iface2_data = grpcutils.iface_to_data(node2_iface)
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
            iface1_proto = grpcutils.iface_to_proto(node1_id, node1_iface)
        if node2_iface:
            iface2_proto = grpcutils.iface_to_proto(node2_id, node2_iface)
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
        logging.debug("edit link: %s", request)
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
        logging.debug("delete link: %s", request)
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

    def GetHooks(
        self, request: core_pb2.GetHooksRequest, context: ServicerContext
    ) -> core_pb2.GetHooksResponse:
        """
        Retrieve all hooks from a session

        :param request: get-hook request
        :param context: context object
        :return: get-hooks response about all the hooks in all session states
        """
        logging.debug("get hooks: %s", request)
        session = self.get_session(request.session_id, context)
        hooks = grpcutils.get_hooks(session)
        return core_pb2.GetHooksResponse(hooks=hooks)

    def AddHook(
        self, request: core_pb2.AddHookRequest, context: ServicerContext
    ) -> core_pb2.AddHookResponse:
        """
        Add hook to a session

        :param request: add-hook request
        :param context: context object
        :return: add-hook response
        """
        logging.debug("add hook: %s", request)
        session = self.get_session(request.session_id, context)
        hook = request.hook
        state = EventTypes(hook.state)
        session.add_hook(state, hook.file, hook.data)
        return core_pb2.AddHookResponse(result=True)

    def GetMobilityConfigs(
        self, request: GetMobilityConfigsRequest, context: ServicerContext
    ) -> GetMobilityConfigsResponse:
        """
        Retrieve all mobility configurations from a session

        :param request:
            get-mobility-configurations request
        :param context: context object
        :return: get-mobility-configurations response that has a list of configurations
        """
        logging.debug("get mobility configs: %s", request)
        session = self.get_session(request.session_id, context)
        configs = grpcutils.get_mobility_configs(session)
        return GetMobilityConfigsResponse(configs=configs)

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
        logging.debug("get mobility config: %s", request)
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
        logging.debug("set mobility config: %s", request)
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
        logging.debug("mobility action: %s", request)
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

    def GetServices(
        self, request: GetServicesRequest, context: ServicerContext
    ) -> GetServicesResponse:
        """
        Retrieve all the services that are running

        :param request: get-service request
        :param context: context object
        :return: get-services response
        """
        logging.debug("get services: %s", request)
        services = []
        for name in ServiceManager.services:
            service = ServiceManager.services[name]
            service_proto = Service(group=service.group, name=service.name)
            services.append(service_proto)
        return GetServicesResponse(services=services)

    def GetServiceDefaults(
        self, request: GetServiceDefaultsRequest, context: ServicerContext
    ) -> GetServiceDefaultsResponse:
        """
        Retrieve all the default services of all node types in a session

        :param request: get-default-service request
        :param context: context object
        :return: get-service-defaults response about all the available default services
        """
        logging.debug("get service defaults: %s", request)
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
        logging.debug("set service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        session.services.default_services.clear()
        for service_defaults in request.defaults:
            session.services.default_services[
                service_defaults.node_type
            ] = service_defaults.services
        return SetServiceDefaultsResponse(result=True)

    def GetNodeServiceConfigs(
        self, request: GetNodeServiceConfigsRequest, context: ServicerContext
    ) -> GetNodeServiceConfigsResponse:
        """
        Retrieve all node service configurations.

        :param request:
            get-node-service request
        :param context: context object
        :return: all node service configs response
        """
        logging.debug("get node service configs: %s", request)
        session = self.get_session(request.session_id, context)
        configs = grpcutils.get_node_service_configs(session)
        return GetNodeServiceConfigsResponse(configs=configs)

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
        logging.debug("get node service: %s", request)
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
        logging.debug("get node service file: %s", request)
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        file_data = session.services.get_service_file(
            node, request.service, request.file
        )
        return GetNodeServiceFileResponse(data=file_data.data)

    def SetNodeService(
        self, request: SetNodeServiceRequest, context: ServicerContext
    ) -> SetNodeServiceResponse:
        """
        Set a node service for a node

        :param request: set-node-service
            request that has info to set a node service
        :param context: context object
        :return: set-node-service response
        """
        logging.debug("set node service: %s", request)
        session = self.get_session(request.session_id, context)
        config = request.config
        grpcutils.service_configuration(session, config)
        return SetNodeServiceResponse(result=True)

    def SetNodeServiceFile(
        self, request: SetNodeServiceFileRequest, context: ServicerContext
    ) -> SetNodeServiceFileResponse:
        """
        Store the customized service file in the service config

        :param request:
            set-node-service-file request
        :param context: context object
        :return: set-node-service-file response
        """
        logging.debug("set node service file: %s", request)
        session = self.get_session(request.session_id, context)
        config = request.config
        session.services.set_service_file(
            config.node_id, config.service, config.file, config.data
        )
        return SetNodeServiceFileResponse(result=True)

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
        logging.debug("service action: %s", request)
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

    def GetWlanConfigs(
        self, request: GetWlanConfigsRequest, context: ServicerContext
    ) -> GetWlanConfigsResponse:
        """
        Retrieve all wireless-lan configurations.

        :param request: request
        :param context: core.api.grpc.core_pb2.GetWlanConfigResponse
        :return: all wlan configurations
        """
        logging.debug("get wlan configs: %s", request)
        session = self.get_session(request.session_id, context)
        configs = grpcutils.get_wlan_configs(session)
        return GetWlanConfigsResponse(configs=configs)

    def GetWlanConfig(
        self, request: GetWlanConfigRequest, context: ServicerContext
    ) -> GetWlanConfigResponse:
        """
        Retrieve wireless-lan configuration of a node

        :param request: get-wlan-configuration request
        :param context: core.api.grpc.core_pb2.GetWlanConfigResponse
        :return: get-wlan-configuration response about the wlan configuration of a node
        """
        logging.debug("get wlan config: %s", request)
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
        logging.debug("set wlan config: %s", request)
        session = self.get_session(request.session_id, context)
        node_id = request.wlan_config.node_id
        config = request.wlan_config.config
        session.mobility.set_model_config(node_id, BasicRangeModel.name, config)
        if session.state == EventTypes.RUNTIME_STATE:
            node = self.get_node(session, node_id, context, WlanNode)
            node.updatemodel(config)
        return SetWlanConfigResponse(result=True)

    def GetEmaneConfig(
        self, request: GetEmaneConfigRequest, context: ServicerContext
    ) -> GetEmaneConfigResponse:
        """
        Retrieve EMANE configuration of a session

        :param request: get-EMANE-configuration request
        :param context: context object
        :return: get-EMANE-configuration response
        """
        logging.debug("get emane config: %s", request)
        session = self.get_session(request.session_id, context)
        config = grpcutils.get_emane_config(session)
        return GetEmaneConfigResponse(config=config)

    def SetEmaneConfig(
        self, request: SetEmaneConfigRequest, context: ServicerContext
    ) -> SetEmaneConfigResponse:
        """
        Set EMANE configuration of a session

        :param request: set-EMANE-configuration request
        :param context: context object
        :return: set-EMANE-configuration response
        """
        logging.debug("set emane config: %s", request)
        session = self.get_session(request.session_id, context)
        config = session.emane.get_configs()
        config.update(request.config)
        return SetEmaneConfigResponse(result=True)

    def GetEmaneModels(
        self, request: GetEmaneModelsRequest, context: ServicerContext
    ) -> GetEmaneModelsResponse:
        """
        Retrieve all the EMANE models in the session

        :param request: get-emane-model request
        :param context: context object
        :return: get-EMANE-models response that has all the models
        """
        logging.debug("get emane models: %s", request)
        session = self.get_session(request.session_id, context)
        models = grpcutils.get_emane_models(session)
        return GetEmaneModelsResponse(models=models)

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
        logging.debug("get emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        model = session.emane.models.get(request.model)
        if not model:
            raise CoreError(f"invalid emane model: {request.model}")
        _id = utils.iface_config_id(request.node_id, request.iface_id)
        current_config = session.emane.get_model_config(_id, request.model)
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
        logging.debug("set emane model config: %s", request)
        session = self.get_session(request.session_id, context)
        model_config = request.emane_model_config
        _id = utils.iface_config_id(model_config.node_id, model_config.iface_id)
        session.emane.set_model_config(_id, model_config.model, model_config.config)
        return SetEmaneModelConfigResponse(result=True)

    def GetEmaneModelConfigs(
        self, request: GetEmaneModelConfigsRequest, context: ServicerContext
    ) -> GetEmaneModelConfigsResponse:
        """
        Retrieve all EMANE model configurations of a session

        :param request:
            get-EMANE-model-configurations request
        :param context: context object
        :return: get-EMANE-model-configurations response that has all the EMANE
            configurations
        """
        logging.debug("get emane model configs: %s", request)
        session = self.get_session(request.session_id, context)
        configs = grpcutils.get_emane_model_configs(session)
        return GetEmaneModelConfigsResponse(configs=configs)

    def SaveXml(
        self, request: core_pb2.SaveXmlRequest, context: ServicerContext
    ) -> core_pb2.SaveXmlResponse:
        """
        Export the session into the EmulationScript XML format

        :param request: save xml request
        :param context: context object
        :return: save-xml response
        """
        logging.debug("save xml: %s", request)
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

    def GetInterfaces(
        self, request: core_pb2.GetInterfacesRequest, context: ServicerContext
    ) -> core_pb2.GetInterfacesResponse:
        """
        Retrieve all the interfaces of the system including bridges, virtual ethernet, and loopback

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
        logging.debug("emane link: %s", request)
        session = self.get_session(request.session_id, context)
        nem1 = request.nem1
        iface1 = session.emane.get_iface(nem1)
        if not iface1:
            context.abort(grpc.StatusCode.NOT_FOUND, f"nem one {nem1} not found")
        node1 = iface1.node

        nem2 = request.nem2
        iface2 = session.emane.get_iface(nem2)
        if not iface2:
            context.abort(grpc.StatusCode.NOT_FOUND, f"nem two {nem2} not found")
        node2 = iface2.node

        if iface1.net == iface2.net:
            if request.linked:
                flag = MessageFlags.ADD
            else:
                flag = MessageFlags.DELETE
            color = session.get_link_color(iface1.net.id)
            link = LinkData(
                message_type=flag,
                type=LinkTypes.WIRELESS,
                node1_id=node1.id,
                node2_id=node2.id,
                network_id=iface1.net.id,
                color=color,
            )
            session.broadcast_link(link)
            return EmaneLinkResponse(result=True)
        else:
            return EmaneLinkResponse(result=False)

    def GetConfigServices(
        self, request: GetConfigServicesRequest, context: ServicerContext
    ) -> GetConfigServicesResponse:
        """
        Gets all currently known configuration services.

        :param request: get config services request
        :param context: grpc context
        :return: get config services response
        """
        services = []
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
            services.append(service_proto)
        return GetConfigServicesResponse(services=services)

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

    def GetConfigServiceDefaults(
        self, request: GetConfigServiceDefaultsRequest, context: ServicerContext
    ) -> GetConfigServiceDefaultsResponse:
        """
        Get default values for a given configuration service.

        :param request: get config service defaults request
        :param context: grpc context
        :return: get config service defaults response
        """
        service_class = self.validate_service(request.name, context)
        service = service_class(None)
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

    def GetNodeConfigServiceConfigs(
        self, request: GetNodeConfigServiceConfigsRequest, context: ServicerContext
    ) -> GetNodeConfigServiceConfigsResponse:
        """
        Get current custom templates and config for configuration services for a given
        node.

        :param request: get node config service configs request
        :param context: grpc context
        :return: get node config service configs response
        """
        session = self.get_session(request.session_id, context)
        configs = grpcutils.get_node_config_service_configs(session)
        return GetNodeConfigServiceConfigsResponse(configs=configs)

    def GetNodeConfigServices(
        self, request: GetNodeConfigServicesRequest, context: ServicerContext
    ) -> GetNodeConfigServicesResponse:
        """
        Get configuration services for a given node.

        :param request: get node config services request
        :param context: grpc context
        :return: get node config services response
        """
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        services = node.config_services.keys()
        return GetNodeConfigServicesResponse(services=services)

    def SetNodeConfigService(
        self, request: SetNodeConfigServiceRequest, context: ServicerContext
    ) -> SetNodeConfigServiceResponse:
        """
        Set custom config, for a given configuration service, for a given node.

        :param request: set node config service request
        :param context: grpc context
        :return: set node config service response
        """
        session = self.get_session(request.session_id, context)
        node = self.get_node(session, request.node_id, context, CoreNode)
        self.validate_service(request.name, context)
        service = node.config_services.get(request.name)
        if service:
            service.set_config(request.config)
            return SetNodeConfigServiceResponse(result=True)
        else:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"node {node.name} missing service {request.name}",
            )

    def GetEmaneEventChannel(
        self, request: GetEmaneEventChannelRequest, context: ServicerContext
    ) -> GetEmaneEventChannelResponse:
        session = self.get_session(request.session_id, context)
        group = None
        port = None
        device = None
        if session.emane.eventchannel:
            group, port, device = session.emane.eventchannel
        return GetEmaneEventChannelResponse(group=group, port=port, device=device)

    def ExecuteScript(self, request, context):
        existing_sessions = set(self.coreemu.sessions.keys())
        thread = threading.Thread(
            target=utils.execute_file,
            args=(
                request.script,
                {"__file__": request.script, "coreemu": self.coreemu},
            ),
            daemon=True,
        )
        thread.start()
        thread.join()
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
        if not isinstance(wlan.model, BasicRangeModel):
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"wlan node {request.wlan} does not using BasicRangeModel",
            )
        node1 = self.get_node(session, request.node1_id, context, CoreNode)
        node2 = self.get_node(session, request.node2_id, context, CoreNode)
        node1_iface, node2_iface = None, None
        for net, iface1, iface2 in node1.commonnets(node2):
            if net == wlan:
                node1_iface = iface1
                node2_iface = iface2
                break
        result = False
        if node1_iface and node2_iface:
            if request.linked:
                wlan.link(node1_iface, node2_iface)
            else:
                wlan.unlink(node1_iface, node2_iface)
            wlan.model.sendlinkmsg(node1_iface, node2_iface, unlink=not request.linked)
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
