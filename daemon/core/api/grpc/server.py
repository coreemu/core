import atexit
import logging
import os
import re
import tempfile
import threading
import time
from concurrent import futures
from typing import Type

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
from core.api.grpc.common_pb2 import MappedConfig
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
from core.api.grpc.grpcutils import (
    get_config_options,
    get_emane_model_id,
    get_links,
    get_net_stats,
)
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
    ServiceDefaults,
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
)
from core.emulator.coreemu import CoreEmu
from core.emulator.data import LinkData
from core.emulator.emudata import LinkOptions, NodeOptions
from core.emulator.enumerations import EventTypes, LinkTypes, MessageFlags
from core.emulator.session import Session
from core.errors import CoreCommandError, CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import CoreNodeBase, NodeBase
from core.services.coreservices import ServiceManager

_ONE_DAY_IN_SECONDS = 60 * 60 * 24
_INTERFACE_REGEX = re.compile(r"veth(?P<node>[0-9a-fA-F]+)")


class CoreGrpcServer(core_pb2_grpc.CoreApiServicer):
    """
    Create CoreGrpcServer instance

    :param coreemu: coreemu object
    """

    def __init__(self, coreemu: CoreEmu) -> None:
        super().__init__()
        self.coreemu = coreemu
        self.running = True
        self.server = None
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
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
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
        self, session: Session, node_id: int, context: ServicerContext
    ) -> NodeBase:
        """
        Retrieve node given session and node id

        :param session: session that has the node
        :param node_id: node id
        :param context:
        :return: node object that satisfies. If node not found then raise an exception.
        :raises Exception: raises grpc exception when node does not exist
        """
        try:
            return session.get_node(node_id)
        except CoreError:
            context.abort(grpc.StatusCode.NOT_FOUND, f"node {node_id} not found")

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
        session.set_state(EventTypes.CONFIGURATION_STATE)
        if not os.path.exists(session.session_dir):
            os.mkdir(session.session_dir)

        # location
        if request.HasField("location"):
            grpcutils.session_location(session, request.location)

        # add all hooks
        for hook in request.hooks:
            state = EventTypes(hook.state)
            session.add_hook(state, hook.file, None, hook.data)

        # create nodes
        _, exceptions = grpcutils.create_nodes(session, request.nodes)
        if exceptions:
            exceptions = [str(x) for x in exceptions]
            return core_pb2.StartSessionResponse(result=False, exceptions=exceptions)

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

        # config service configs
        for config in request.config_service_configs:
            node = self.get_node(session, config.node_id, context)
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
        session.set_state(EventTypes.DATACOLLECT_STATE, send_event=True)
        session.clear()
        session.set_state(EventTypes.SHUTDOWN_STATE, send_event=True)
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
        session.location.refscale = 150000.0
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
        Delete the session

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
            if not isinstance(node.id, int):
                continue
            node_proto = grpcutils.get_node_proto(session, node)
            nodes.append(node_proto)
            node_links = get_links(node)
            links.extend(node_links)

        session_proto = core_pb2.Session(
            state=session.state.value, nodes=nodes, links=links, dir=session.session_dir
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
                        interface_id = int(key[1], base=16)
                        session_id = int(key[2], base=16)
                        if session.id != session_id:
                            continue
                        interface_throughput = (
                            throughputs_event.interface_throughputs.add()
                        )
                        interface_throughput.node_id = node_id
                        interface_throughput.interface_id = interface_id
                        interface_throughput.throughput = throughput
                    elif key.startswith("b."):
                        try:
                            key = key.split(".")
                            node_id = int(key[1], base=16)
                            session_id = int(key[2], base=16)
                            if session.id != session_id:
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
        node = session.add_node(_type=_type, _id=_id, options=options)
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
        node = self.get_node(session, request.node_id, context)
        interfaces = []
        for interface_id in node._netif:
            interface = node._netif[interface_id]
            interface_proto = grpcutils.interface_to_proto(interface)
            interfaces.append(interface_proto)
        node_proto = grpcutils.get_node_proto(session, node)
        return core_pb2.GetNodeResponse(node=node_proto, interfaces=interfaces)

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
        node = self.get_node(session, request.node_id, context)
        options = NodeOptions()
        options.icon = request.icon
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
        result = session.delete_node(request.node_id)
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
        node = self.get_node(session, request.node_id, context)
        try:
            output = node.cmd(request.command)
        except CoreCommandError as e:
            output = e.stderr
        return core_pb2.NodeCommandResponse(output=output)

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
        node = self.get_node(session, request.node_id, context)
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
        node = self.get_node(session, request.node_id, context)
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
        # validate session and nodes
        session = self.get_session(request.session_id, context)
        self.get_node(session, request.link.node_one_id, context)
        self.get_node(session, request.link.node_two_id, context)

        node_one_id = request.link.node_one_id
        node_two_id = request.link.node_two_id
        interface_one, interface_two, options = grpcutils.add_link_data(request.link)
        node_one_interface, node_two_interface = session.add_link(
            node_one_id, node_two_id, interface_one, interface_two, link_options=options
        )
        interface_one_proto = None
        interface_two_proto = None
        if node_one_interface:
            interface_one_proto = grpcutils.interface_to_proto(node_one_interface)
        if node_two_interface:
            interface_two_proto = grpcutils.interface_to_proto(node_two_interface)
        return core_pb2.AddLinkResponse(
            result=True,
            interface_one=interface_one_proto,
            interface_two=interface_two_proto,
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
        node_one_id = request.node_one_id
        node_two_id = request.node_two_id
        interface_one_id = request.interface_one_id
        interface_two_id = request.interface_two_id
        session.delete_link(
            node_one_id, node_two_id, interface_one_id, interface_two_id
        )
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
        hooks = []
        for state in session._hooks:
            state_hooks = session._hooks[state]
            for file_name, file_data in state_hooks:
                hook = core_pb2.Hook(state=state.value, file=file_name, data=file_data)
                hooks.append(hook)
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
        session.add_hook(state, hook.file, None, hook.data)
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
        response = GetMobilityConfigsResponse()
        for node_id in session.mobility.node_configurations:
            model_config = session.mobility.node_configurations[node_id]
            if node_id == -1:
                continue
            for model_name in model_config:
                if model_name != Ns2ScriptedMobility.name:
                    continue
                current_config = session.mobility.get_model_config(node_id, model_name)
                config = get_config_options(current_config, Ns2ScriptedMobility)
                mapped_config = MappedConfig(config=config)
                response.configs[node_id].CopyFrom(mapped_config)
        return response

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
        node = self.get_node(session, request.node_id, context)
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

        :param request:
            get-default-service request
        :param context: context object
        :return: get-service-defaults response about all the available default services
        """
        logging.debug("get service defaults: %s", request)
        session = self.get_session(request.session_id, context)
        all_service_defaults = []
        for node_type in session.services.default_services:
            services = session.services.default_services[node_type]
            service_defaults = ServiceDefaults(node_type=node_type, services=services)
            all_service_defaults.append(service_defaults)
        return GetServiceDefaultsResponse(defaults=all_service_defaults)

    def SetServiceDefaults(
        self, request: SetServiceDefaultsRequest, context: ServicerContext
    ) -> SetServiceDefaultsResponse:
        """
        Set new default services to the session after whipping out the old ones
        :param request: set-service-defaults
            request
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
        configs = []
        for node_id, service_configs in session.services.custom_services.items():
            for name in service_configs:
                service = session.services.get_service(node_id, name)
                service_proto = grpcutils.get_service_configuration(service)
                config = GetNodeServiceConfigsResponse.ServiceConfig(
                    node_id=node_id,
                    service=name,
                    data=service_proto,
                    files=service.config_data,
                )
                configs.append(config)
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
        node = self.get_node(session, request.node_id, context)
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
        node = self.get_node(session, request.node_id, context)
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
        response = GetWlanConfigsResponse()
        for node_id in session.mobility.node_configurations:
            model_config = session.mobility.node_configurations[node_id]
            if node_id == -1:
                continue
            for model_name in model_config:
                if model_name != BasicRangeModel.name:
                    continue
                current_config = session.mobility.get_model_config(node_id, model_name)
                config = get_config_options(current_config, BasicRangeModel)
                mapped_config = MappedConfig(config=config)
                response.configs[node_id].CopyFrom(mapped_config)
        return response

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
        wlan_config = request.wlan_config
        session.mobility.set_model_config(
            wlan_config.node_id, BasicRangeModel.name, wlan_config.config
        )
        if session.state == EventTypes.RUNTIME_STATE:
            node = self.get_node(session, wlan_config.node_id, context)
            node.updatemodel(wlan_config.config)
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
        current_config = session.emane.get_configs()
        config = get_config_options(current_config, session.emane.emane_config)
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
        models = []
        for model in session.emane.models.keys():
            if len(model.split("_")) != 2:
                continue
            models.append(model)
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
        model = session.emane.models[request.model]
        _id = get_emane_model_id(request.node_id, request.interface)
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
        _id = get_emane_model_id(model_config.node_id, model_config.interface_id)
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

        configs = []
        for _id in session.emane.node_configurations:
            if _id == -1:
                continue

            model_configs = session.emane.node_configurations[_id]
            for model_name in model_configs:
                model = session.emane.models[model_name]
                current_config = session.emane.get_model_config(_id, model_name)
                config = get_config_options(current_config, model)
                node_id, interface = grpcutils.parse_emane_model_id(_id)
                model_config = GetEmaneModelConfigsResponse.ModelConfig(
                    node_id=node_id,
                    model=model_name,
                    interface=interface,
                    config=config,
                )
                configs.append(model_config)
        return GetEmaneModelConfigsResponse(configs=configs)

    def SaveXml(
        self, request: core_pb2.SaveXmlRequest, context: ServicerContext
    ) -> core_pb2.SaveXmlResponse:
        """
        Export the session nto the EmulationScript XML format

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
                flag = MessageFlags.ADD
            else:
                flag = MessageFlags.DELETE
            color = session.get_link_color(emane_one.id)
            link = LinkData(
                message_type=flag,
                link_type=LinkTypes.WIRELESS,
                node1_id=node_one.id,
                node2_id=node_two.id,
                network_id=emane_one.id,
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
        node = self.get_node(session, request.node_id, context)
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
        configs = []
        for node in session.nodes.values():
            if not isinstance(node, CoreNodeBase):
                continue

            for name, service in node.config_services.items():
                if not service.custom_templates and not service.custom_config:
                    continue
                config_proto = configservices_pb2.ConfigServiceConfig(
                    node_id=node.id,
                    name=name,
                    templates=service.custom_templates,
                    config=service.custom_config,
                )
                configs.append(config_proto)
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
        node = self.get_node(session, request.node_id, context)
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
        node = self.get_node(session, request.node_id, context)
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
