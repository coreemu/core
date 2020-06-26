"""
gRpc client for interfacing with CORE.
"""

import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional

import grpc

from core.api.grpc import configservices_pb2, core_pb2, core_pb2_grpc
from core.api.grpc.configservices_pb2 import (
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
from core.api.grpc.core_pb2 import ExecuteScriptRequest, ExecuteScriptResponse
from core.api.grpc.emane_pb2 import (
    EmaneLinkRequest,
    EmaneLinkResponse,
    EmaneModelConfig,
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
from core.api.grpc.mobility_pb2 import (
    GetMobilityConfigRequest,
    GetMobilityConfigResponse,
    GetMobilityConfigsRequest,
    GetMobilityConfigsResponse,
    MobilityActionRequest,
    MobilityActionResponse,
    MobilityConfig,
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
    ServiceAction,
    ServiceActionRequest,
    ServiceActionResponse,
    ServiceConfig,
    ServiceDefaults,
    ServiceFileConfig,
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
    WlanConfig,
    WlanLinkRequest,
    WlanLinkResponse,
)
from core.emulator.data import IpPrefixes


class InterfaceHelper:
    """
    Convenience class to help generate IP4 and IP6 addresses for gRPC clients.
    """

    def __init__(self, ip4_prefix: str = None, ip6_prefix: str = None) -> None:
        """
        Creates an InterfaceHelper object.

        :param ip4_prefix: ip4 prefix to use for generation
        :param ip6_prefix: ip6 prefix to use for generation
        :raises ValueError: when both ip4 and ip6 prefixes have not been provided
        """
        self.prefixes: IpPrefixes = IpPrefixes(ip4_prefix, ip6_prefix)

    def create_iface(
        self, node_id: int, iface_id: int, name: str = None, mac: str = None
    ) -> core_pb2.Interface:
        """
        Create an interface protobuf object.

        :param node_id: node id to create interface for
        :param iface_id: interface id
        :param name: name of interface
        :param mac: mac address for interface
        :return: interface protobuf
        """
        iface_data = self.prefixes.gen_iface(node_id, name, mac)
        return core_pb2.Interface(
            id=iface_id,
            name=iface_data.name,
            ip4=iface_data.ip4,
            ip4_mask=iface_data.ip4_mask,
            ip6=iface_data.ip6,
            ip6_mask=iface_data.ip6_mask,
            mac=iface_data.mac,
        )


def stream_listener(stream: Any, handler: Callable[[core_pb2.Event], None]) -> None:
    """
    Listen for stream events and provide them to the handler.

    :param stream: grpc stream that will provide events
    :param handler: function that handles an event
    :return: nothing
    """
    try:
        for event in stream:
            handler(event)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.CANCELLED:
            logging.debug("stream closed")
        else:
            logging.exception("stream error")


def start_streamer(stream: Any, handler: Callable[[core_pb2.Event], None]) -> None:
    """
    Convenience method for starting a grpc stream thread for handling streamed events.

    :param stream: grpc stream that will provide events
    :param handler: function that handles an event
    :return: nothing
    """
    thread = threading.Thread(
        target=stream_listener, args=(stream, handler), daemon=True
    )
    thread.start()


class CoreGrpcClient:
    """
    Provides convenience methods for interfacing with the CORE grpc server.
    """

    def __init__(self, address: str = "localhost:50051", proxy: bool = False) -> None:
        """
        Creates a CoreGrpcClient instance.

        :param address: grpc server address to connect to
        """
        self.address: str = address
        self.stub: Optional[core_pb2_grpc.CoreApiStub] = None
        self.channel: Optional[grpc.Channel] = None
        self.proxy: bool = proxy

    def start_session(
        self,
        session_id: int,
        nodes: List[core_pb2.Node],
        links: List[core_pb2.Link],
        location: core_pb2.SessionLocation = None,
        hooks: List[core_pb2.Hook] = None,
        emane_config: Dict[str, str] = None,
        emane_model_configs: List[EmaneModelConfig] = None,
        wlan_configs: List[WlanConfig] = None,
        mobility_configs: List[MobilityConfig] = None,
        service_configs: List[ServiceConfig] = None,
        service_file_configs: List[ServiceFileConfig] = None,
        asymmetric_links: List[core_pb2.Link] = None,
        config_service_configs: List[configservices_pb2.ConfigServiceConfig] = None,
    ) -> core_pb2.StartSessionResponse:
        """
        Start a session.

        :param session_id: id of session
        :param nodes: list of nodes to create
        :param links: list of links to create
        :param location: location to set
        :param hooks: session hooks to set
        :param emane_config: emane configuration to set
        :param emane_model_configs: node emane model configurations
        :param wlan_configs: node wlan configurations
        :param mobility_configs: node mobility configurations
        :param service_configs: node service configurations
        :param service_file_configs: node service file configurations
        :param asymmetric_links: asymmetric links to edit
        :param config_service_configs: config service configurations
        :return: start session response
        """
        request = core_pb2.StartSessionRequest(
            session_id=session_id,
            nodes=nodes,
            links=links,
            location=location,
            hooks=hooks,
            emane_config=emane_config,
            emane_model_configs=emane_model_configs,
            wlan_configs=wlan_configs,
            mobility_configs=mobility_configs,
            service_configs=service_configs,
            service_file_configs=service_file_configs,
            asymmetric_links=asymmetric_links,
            config_service_configs=config_service_configs,
        )
        return self.stub.StartSession(request)

    def stop_session(self, session_id: int) -> core_pb2.StopSessionResponse:
        """
        Stop a running session.

        :param session_id: id of session
        :return: stop session response
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.StopSessionRequest(session_id=session_id)
        return self.stub.StopSession(request)

    def create_session(self, session_id: int = None) -> core_pb2.CreateSessionResponse:
        """
        Create a session.

        :param session_id: id for session, default is None and one will be created
            for you
        :return: response with created session id
        """
        request = core_pb2.CreateSessionRequest(session_id=session_id)
        return self.stub.CreateSession(request)

    def delete_session(self, session_id: int) -> core_pb2.DeleteSessionResponse:
        """
        Delete a session.

        :param session_id: id of session
        :return: response with result of deletion success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteSessionRequest(session_id=session_id)
        return self.stub.DeleteSession(request)

    def get_sessions(self) -> core_pb2.GetSessionsResponse:
        """
        Retrieves all currently known sessions.

        :return: response with a list of currently known session, their state and
            number of nodes
        """
        return self.stub.GetSessions(core_pb2.GetSessionsRequest())

    def check_session(self, session_id: int) -> core_pb2.CheckSessionResponse:
        """
        Check if a session exists.

        :param session_id: id of session to check for
        :return: response with result if session was found
        """
        request = core_pb2.CheckSessionRequest(session_id=session_id)
        return self.stub.CheckSession(request)

    def get_session(self, session_id: int) -> core_pb2.GetSessionResponse:
        """
        Retrieve a session.

        :param session_id: id of session
        :return: response with sessions state, nodes, and links
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionRequest(session_id=session_id)
        return self.stub.GetSession(request)

    def get_session_options(
        self, session_id: int
    ) -> core_pb2.GetSessionOptionsResponse:
        """
        Retrieve session options as a dict with id mapping.

        :param session_id: id of session
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionOptionsRequest(session_id=session_id)
        return self.stub.GetSessionOptions(request)

    def set_session_options(
        self, session_id: int, config: Dict[str, str]
    ) -> core_pb2.SetSessionOptionsResponse:
        """
        Set options for a session.

        :param session_id: id of session
        :param config: configuration values to set
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionOptionsRequest(
            session_id=session_id, config=config
        )
        return self.stub.SetSessionOptions(request)

    def get_session_metadata(
        self, session_id: int
    ) -> core_pb2.GetSessionMetadataResponse:
        """
        Retrieve session metadata as a dict with id mapping.

        :param session_id: id of session
        :return: response with metadata dict
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionMetadataRequest(session_id=session_id)
        return self.stub.GetSessionMetadata(request)

    def set_session_metadata(
        self, session_id: int, config: Dict[str, str]
    ) -> core_pb2.SetSessionMetadataResponse:
        """
        Set metadata for a session.

        :param session_id: id of session
        :param config: configuration values to set
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionMetadataRequest(
            session_id=session_id, config=config
        )
        return self.stub.SetSessionMetadata(request)

    def get_session_location(
        self, session_id: int
    ) -> core_pb2.GetSessionLocationResponse:
        """
        Get session location.

        :param session_id: id of session
        :return: response with session position reference and scale
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionLocationRequest(session_id=session_id)
        return self.stub.GetSessionLocation(request)

    def set_session_location(
        self,
        session_id: int,
        x: float = None,
        y: float = None,
        z: float = None,
        lat: float = None,
        lon: float = None,
        alt: float = None,
        scale: float = None,
    ) -> core_pb2.SetSessionLocationResponse:
        """
        Set session location.

        :param session_id: id of session
        :param x: x position
        :param y: y position
        :param z: z position
        :param lat: latitude position
        :param lon: longitude  position
        :param alt: altitude position
        :param scale: geo scale
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        location = core_pb2.SessionLocation(
            x=x, y=y, z=z, lat=lat, lon=lon, alt=alt, scale=scale
        )
        request = core_pb2.SetSessionLocationRequest(
            session_id=session_id, location=location
        )
        return self.stub.SetSessionLocation(request)

    def set_session_state(
        self, session_id: int, state: core_pb2.SessionState
    ) -> core_pb2.SetSessionStateResponse:
        """
        Set session state.

        :param session_id: id of session
        :param state: session state to transition to
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionStateRequest(session_id=session_id, state=state)
        return self.stub.SetSessionState(request)

    def add_session_server(
        self, session_id: int, name: str, host: str
    ) -> core_pb2.AddSessionServerResponse:
        """
        Add distributed session server.

        :param session_id: id of session
        :param name: name of server to add
        :param host: host address to connect to
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.AddSessionServerRequest(
            session_id=session_id, name=name, host=host
        )
        return self.stub.AddSessionServer(request)

    def events(
        self,
        session_id: int,
        handler: Callable[[core_pb2.Event], None],
        events: List[core_pb2.Event] = None,
    ) -> grpc.Channel:
        """
        Listen for session events.

        :param session_id: id of session
        :param handler: handler for received events
        :param events: events to listen to, defaults to all
        :return: stream processing events, can be used to cancel stream
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.EventsRequest(session_id=session_id, events=events)
        stream = self.stub.Events(request)
        start_streamer(stream, handler)
        return stream

    def throughputs(
        self, session_id: int, handler: Callable[[core_pb2.ThroughputsEvent], None]
    ) -> grpc.Channel:
        """
        Listen for throughput events with information for interfaces and bridges.

        :param session_id: session id
        :param handler: handler for every event
        :return: stream processing events, can be used to cancel stream
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.ThroughputsRequest(session_id=session_id)
        stream = self.stub.Throughputs(request)
        start_streamer(stream, handler)
        return stream

    def add_node(
        self, session_id: int, node: core_pb2.Node
    ) -> core_pb2.AddNodeResponse:
        """
        Add node to session.

        :param session_id: session id
        :param node: node to add
        :return: response with node id
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.AddNodeRequest(session_id=session_id, node=node)
        return self.stub.AddNode(request)

    def get_node(self, session_id: int, node_id: int) -> core_pb2.GetNodeResponse:
        """
        Get node details.

        :param session_id: session id
        :param node_id: node id
        :return: response with node details
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetNode(request)

    def edit_node(
        self,
        session_id: int,
        node_id: int,
        position: core_pb2.Position = None,
        icon: str = None,
        source: str = None,
        geo: core_pb2.Geo = None,
    ) -> core_pb2.EditNodeResponse:
        """
        Edit a node, currently only changes position.

        :param session_id: session id
        :param node_id: node id
        :param position: position to set node to
        :param icon: path to icon for gui to use for node
        :param source: application source
        :param geo: lon,lat,alt location for node
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.EditNodeRequest(
            session_id=session_id,
            node_id=node_id,
            position=position,
            icon=icon,
            source=source,
            geo=geo,
        )
        return self.stub.EditNode(request)

    def move_nodes(
        self, move_iterator: Iterable[core_pb2.MoveNodesRequest]
    ) -> core_pb2.MoveNodesResponse:
        """
        Stream node movements using the provided iterator.

        :param move_iterator: iterator for generating node movements
        :return: move nodes response
        :raises grpc.RpcError: when session or nodes do not exist
        """
        return self.stub.MoveNodes(move_iterator)

    def delete_node(self, session_id: int, node_id: int) -> core_pb2.DeleteNodeResponse:
        """
        Delete node from session.

        :param session_id: session id
        :param node_id: node id
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteNodeRequest(session_id=session_id, node_id=node_id)
        return self.stub.DeleteNode(request)

    def node_command(
        self,
        session_id: int,
        node_id: int,
        command: str,
        wait: bool = True,
        shell: bool = False,
    ) -> core_pb2.NodeCommandResponse:
        """
        Send command to a node and get the output.

        :param session_id: session id
        :param node_id: node id
        :param command: command to run on node
        :param wait: wait for command to complete
        :param shell: send shell command
        :return: response with command combined stdout/stderr
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.NodeCommandRequest(
            session_id=session_id,
            node_id=node_id,
            command=command,
            wait=wait,
            shell=shell,
        )
        return self.stub.NodeCommand(request)

    def get_node_terminal(
        self, session_id: int, node_id: int
    ) -> core_pb2.GetNodeTerminalResponse:
        """
        Retrieve terminal command string for launching a local terminal.

        :param session_id: session id
        :param node_id: node id
        :return: response with a node terminal command
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeTerminalRequest(
            session_id=session_id, node_id=node_id
        )
        return self.stub.GetNodeTerminal(request)

    def get_node_links(
        self, session_id: int, node_id: int
    ) -> core_pb2.GetNodeLinksResponse:
        """
        Get current links for a node.

        :param session_id: session id
        :param node_id: node id
        :return: response with a list of links
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeLinksRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetNodeLinks(request)

    def add_link(
        self,
        session_id: int,
        node1_id: int,
        node2_id: int,
        iface1: core_pb2.Interface = None,
        iface2: core_pb2.Interface = None,
        options: core_pb2.LinkOptions = None,
        source: str = None,
    ) -> core_pb2.AddLinkResponse:
        """
        Add a link between nodes.

        :param session_id: session id
        :param node1_id: node one id
        :param node2_id: node two id
        :param iface1: node one interface data
        :param iface2: node two interface data
        :param options: options for link (jitter, bandwidth, etc)
        :param source: application source
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or one of the nodes don't exist
        """
        link = core_pb2.Link(
            node1_id=node1_id,
            node2_id=node2_id,
            type=core_pb2.LinkType.WIRED,
            iface1=iface1,
            iface2=iface2,
            options=options,
        )
        request = core_pb2.AddLinkRequest(
            session_id=session_id, link=link, source=source
        )
        return self.stub.AddLink(request)

    def edit_link(
        self,
        session_id: int,
        node1_id: int,
        node2_id: int,
        options: core_pb2.LinkOptions,
        iface1_id: int = None,
        iface2_id: int = None,
        source: str = None,
    ) -> core_pb2.EditLinkResponse:
        """
        Edit a link between nodes.

        :param session_id: session id
        :param node1_id: node one id
        :param node2_id: node two id
        :param options: options for link (jitter, bandwidth, etc)
        :param iface1_id: node one interface id
        :param iface2_id: node two interface id
        :param source: application source
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or one of the nodes don't exist
        """
        request = core_pb2.EditLinkRequest(
            session_id=session_id,
            node1_id=node1_id,
            node2_id=node2_id,
            options=options,
            iface1_id=iface1_id,
            iface2_id=iface2_id,
            source=source,
        )
        return self.stub.EditLink(request)

    def delete_link(
        self,
        session_id: int,
        node1_id: int,
        node2_id: int,
        iface1_id: int = None,
        iface2_id: int = None,
        source: str = None,
    ) -> core_pb2.DeleteLinkResponse:
        """
        Delete a link between nodes.

        :param session_id: session id
        :param node1_id: node one id
        :param node2_id: node two id
        :param iface1_id: node one interface id
        :param iface2_id: node two interface id
        :param source: application source
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteLinkRequest(
            session_id=session_id,
            node1_id=node1_id,
            node2_id=node2_id,
            iface1_id=iface1_id,
            iface2_id=iface2_id,
            source=source,
        )
        return self.stub.DeleteLink(request)

    def get_hooks(self, session_id: int) -> core_pb2.GetHooksResponse:
        """
        Get all hook scripts.

        :param session_id: session id
        :return: response with a list of hooks
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetHooksRequest(session_id=session_id)
        return self.stub.GetHooks(request)

    def add_hook(
        self,
        session_id: int,
        state: core_pb2.SessionState,
        file_name: str,
        file_data: str,
    ) -> core_pb2.AddHookResponse:
        """
        Add hook scripts.

        :param session_id: session id
        :param state: state to trigger hook
        :param file_name: name of file for hook script
        :param file_data: hook script contents
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        hook = core_pb2.Hook(state=state, file=file_name, data=file_data)
        request = core_pb2.AddHookRequest(session_id=session_id, hook=hook)
        return self.stub.AddHook(request)

    def get_mobility_configs(self, session_id: int) -> GetMobilityConfigsResponse:
        """
        Get all mobility configurations.

        :param session_id: session id
        :return: response with a dict of node ids to mobility configurations
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetMobilityConfigsRequest(session_id=session_id)
        return self.stub.GetMobilityConfigs(request)

    def get_mobility_config(
        self, session_id: int, node_id: int
    ) -> GetMobilityConfigResponse:
        """
        Get mobility configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = GetMobilityConfigRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetMobilityConfig(request)

    def set_mobility_config(
        self, session_id: int, node_id: int, config: Dict[str, str]
    ) -> SetMobilityConfigResponse:
        """
        Set mobility configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :param config: mobility configuration
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        mobility_config = MobilityConfig(node_id=node_id, config=config)
        request = SetMobilityConfigRequest(
            session_id=session_id, mobility_config=mobility_config
        )
        return self.stub.SetMobilityConfig(request)

    def mobility_action(
        self, session_id: int, node_id: int, action: ServiceAction
    ) -> MobilityActionResponse:
        """
        Send a mobility action for a node.

        :param session_id: session id
        :param node_id: node id
        :param action: action to take
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = MobilityActionRequest(
            session_id=session_id, node_id=node_id, action=action
        )
        return self.stub.MobilityAction(request)

    def get_services(self) -> GetServicesResponse:
        """
        Get all currently loaded services.

        :return: response with a list of services
        """
        request = GetServicesRequest()
        return self.stub.GetServices(request)

    def get_service_defaults(self, session_id: int) -> GetServiceDefaultsResponse:
        """
        Get default services for different default node models.

        :param session_id: session id
        :return: response with a dict of node model to a list of services
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetServiceDefaultsRequest(session_id=session_id)
        return self.stub.GetServiceDefaults(request)

    def set_service_defaults(
        self, session_id: int, service_defaults: Dict[str, List[str]]
    ) -> SetServiceDefaultsResponse:
        """
        Set default services for node models.

        :param session_id: session id
        :param service_defaults: node models to lists of services
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        defaults = []
        for node_type in service_defaults:
            services = service_defaults[node_type]
            default = ServiceDefaults(node_type=node_type, services=services)
            defaults.append(default)
        request = SetServiceDefaultsRequest(session_id=session_id, defaults=defaults)
        return self.stub.SetServiceDefaults(request)

    def get_node_service_configs(
        self, session_id: int
    ) -> GetNodeServiceConfigsResponse:
        """
        Get service data for a node.

        :param session_id: session id
        :return: response with all node service configs
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetNodeServiceConfigsRequest(session_id=session_id)
        return self.stub.GetNodeServiceConfigs(request)

    def get_node_service(
        self, session_id: int, node_id: int, service: str
    ) -> GetNodeServiceResponse:
        """
        Get service data for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :return: response with node service data
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = GetNodeServiceRequest(
            session_id=session_id, node_id=node_id, service=service
        )
        return self.stub.GetNodeService(request)

    def get_node_service_file(
        self, session_id: int, node_id: int, service: str, file_name: str
    ) -> GetNodeServiceFileResponse:
        """
        Get a service file for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :param file_name: file name to get data for
        :return: response with file data
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = GetNodeServiceFileRequest(
            session_id=session_id, node_id=node_id, service=service, file=file_name
        )
        return self.stub.GetNodeServiceFile(request)

    def set_node_service(
        self,
        session_id: int,
        node_id: int,
        service: str,
        files: List[str] = None,
        directories: List[str] = None,
        startup: List[str] = None,
        validate: List[str] = None,
        shutdown: List[str] = None,
    ) -> SetNodeServiceResponse:
        """
        Set service data for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :param files: service files
        :param directories: service directories
        :param startup: startup commands
        :param validate: validation commands
        :param shutdown: shutdown commands
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        config = ServiceConfig(
            node_id=node_id,
            service=service,
            files=files,
            directories=directories,
            startup=startup,
            validate=validate,
            shutdown=shutdown,
        )
        request = SetNodeServiceRequest(session_id=session_id, config=config)
        return self.stub.SetNodeService(request)

    def set_node_service_file(
        self, session_id: int, node_id: int, service: str, file_name: str, data: str
    ) -> SetNodeServiceFileResponse:
        """
        Set a service file for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :param file_name: file name to save
        :param data: data to save for file
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        config = ServiceFileConfig(
            node_id=node_id, service=service, file=file_name, data=data
        )
        request = SetNodeServiceFileRequest(session_id=session_id, config=config)
        return self.stub.SetNodeServiceFile(request)

    def service_action(
        self, session_id: int, node_id: int, service: str, action: ServiceAction
    ) -> ServiceActionResponse:
        """
        Send an action to a service for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :param action: action for service (start, stop, restart,
            validate)
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = ServiceActionRequest(
            session_id=session_id, node_id=node_id, service=service, action=action
        )
        return self.stub.ServiceAction(request)

    def get_wlan_configs(self, session_id: int) -> GetWlanConfigsResponse:
        """
        Get all wlan configurations.

        :param session_id: session id
        :return: response with a dict of node ids to wlan configurations
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetWlanConfigsRequest(session_id=session_id)
        return self.stub.GetWlanConfigs(request)

    def get_wlan_config(self, session_id: int, node_id: int) -> GetWlanConfigResponse:
        """
        Get wlan configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetWlanConfigRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetWlanConfig(request)

    def set_wlan_config(
        self, session_id: int, node_id: int, config: Dict[str, str]
    ) -> SetWlanConfigResponse:
        """
        Set wlan configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :param config: wlan configuration
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        wlan_config = WlanConfig(node_id=node_id, config=config)
        request = SetWlanConfigRequest(session_id=session_id, wlan_config=wlan_config)
        return self.stub.SetWlanConfig(request)

    def get_emane_config(self, session_id: int) -> GetEmaneConfigResponse:
        """
        Get session emane configuration.

        :param session_id: session id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetEmaneConfigRequest(session_id=session_id)
        return self.stub.GetEmaneConfig(request)

    def set_emane_config(
        self, session_id: int, config: Dict[str, str]
    ) -> SetEmaneConfigResponse:
        """
        Set session emane configuration.

        :param session_id: session id
        :param config: emane configuration
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = SetEmaneConfigRequest(session_id=session_id, config=config)
        return self.stub.SetEmaneConfig(request)

    def get_emane_models(self, session_id: int) -> GetEmaneModelsResponse:
        """
        Get session emane models.

        :param session_id: session id
        :return: response with a list of emane models
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetEmaneModelsRequest(session_id=session_id)
        return self.stub.GetEmaneModels(request)

    def get_emane_model_config(
        self, session_id: int, node_id: int, model: str, iface_id: int = -1
    ) -> GetEmaneModelConfigResponse:
        """
        Get emane model configuration for a node or a node's interface.

        :param session_id: session id
        :param node_id: node id
        :param model: emane model name
        :param iface_id: node interface id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetEmaneModelConfigRequest(
            session_id=session_id, node_id=node_id, model=model, iface_id=iface_id
        )
        return self.stub.GetEmaneModelConfig(request)

    def set_emane_model_config(
        self,
        session_id: int,
        node_id: int,
        model: str,
        config: Dict[str, str] = None,
        iface_id: int = -1,
    ) -> SetEmaneModelConfigResponse:
        """
        Set emane model configuration for a node or a node's interface.

        :param session_id: session id
        :param node_id: node id
        :param model: emane model name
        :param config: emane model configuration
        :param iface_id: node interface id
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        model_config = EmaneModelConfig(
            node_id=node_id, model=model, config=config, iface_id=iface_id
        )
        request = SetEmaneModelConfigRequest(
            session_id=session_id, emane_model_config=model_config
        )
        return self.stub.SetEmaneModelConfig(request)

    def get_emane_model_configs(self, session_id: int) -> GetEmaneModelConfigsResponse:
        """
        Get all EMANE model configurations for a session.

        :param session_id: session to get emane model configs
        :return: response with a dictionary of node/interface ids to configurations
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetEmaneModelConfigsRequest(session_id=session_id)
        return self.stub.GetEmaneModelConfigs(request)

    def save_xml(self, session_id: int, file_path: str) -> core_pb2.SaveXmlResponse:
        """
        Save the current scenario to an XML file.

        :param session_id: session to save xml file for
        :param file_path: local path to save scenario XML file to
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SaveXmlRequest(session_id=session_id)
        response = self.stub.SaveXml(request)
        with open(file_path, "w") as xml_file:
            xml_file.write(response.data)

    def open_xml(self, file_path: str, start: bool = False) -> core_pb2.OpenXmlResponse:
        """
        Load a local scenario XML file to open as a new session.

        :param file_path: path of scenario XML file
        :param start: True to start session, False otherwise
        :return: response with opened session id
        """
        with open(file_path, "r") as xml_file:
            data = xml_file.read()
        request = core_pb2.OpenXmlRequest(data=data, start=start, file=file_path)
        return self.stub.OpenXml(request)

    def emane_link(
        self, session_id: int, nem1: int, nem2: int, linked: bool
    ) -> EmaneLinkResponse:
        """
        Helps broadcast wireless link/unlink between EMANE nodes.

        :param session_id: session to emane link
        :param nem1: first nem for emane link
        :param nem2: second nem for emane link
        :param linked: True to link, False to unlink
        :return: get emane link response
        :raises grpc.RpcError: when session or nodes related to nems do not exist
        """
        request = EmaneLinkRequest(
            session_id=session_id, nem1=nem1, nem2=nem2, linked=linked
        )
        return self.stub.EmaneLink(request)

    def get_ifaces(self) -> core_pb2.GetInterfacesResponse:
        """
        Retrieves a list of interfaces available on the host machine that are not
        a part of a CORE session.

        :return: get interfaces response
        """
        request = core_pb2.GetInterfacesRequest()
        return self.stub.GetInterfaces(request)

    def get_config_services(self) -> GetConfigServicesResponse:
        """
        Retrieve all known config services.

        :return: get config services response
        """
        request = GetConfigServicesRequest()
        return self.stub.GetConfigServices(request)

    def get_config_service_defaults(
        self, name: str
    ) -> GetConfigServiceDefaultsResponse:
        """
        Retrieves config service default values.

        :param name: name of service to get defaults for
        :return: get config service defaults
        """
        request = GetConfigServiceDefaultsRequest(name=name)
        return self.stub.GetConfigServiceDefaults(request)

    def get_node_config_service_configs(
        self, session_id: int
    ) -> GetNodeConfigServiceConfigsResponse:
        """
        Retrieves all node config service configurations for a session.

        :param session_id: session to get config service configurations for
        :return: get node config service configs response
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetNodeConfigServiceConfigsRequest(session_id=session_id)
        return self.stub.GetNodeConfigServiceConfigs(request)

    def get_node_config_service(
        self, session_id: int, node_id: int, name: str
    ) -> GetNodeConfigServiceResponse:
        """
        Retrieves information for a specific config service on a node.

        :param session_id: session node belongs to
        :param node_id: id of node to get service information from
        :param name: name of service
        :return: get node config service response
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = GetNodeConfigServiceRequest(
            session_id=session_id, node_id=node_id, name=name
        )
        return self.stub.GetNodeConfigService(request)

    def get_node_config_services(
        self, session_id: int, node_id: int
    ) -> GetNodeConfigServicesResponse:
        """
        Retrieves the config services currently assigned to a node.

        :param session_id: session node belongs to
        :param node_id: id of node to get config services for
        :return: get node config services response
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = GetNodeConfigServicesRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetNodeConfigServices(request)

    def set_node_config_service(
        self, session_id: int, node_id: int, name: str, config: Dict[str, str]
    ) -> SetNodeConfigServiceResponse:
        """
        Assigns a config service to a node with the provided configuration.

        :param session_id: session node belongs to
        :param node_id: id of node to assign config service to
        :param name: name of service
        :param config: service configuration
        :return: set node config service response
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = SetNodeConfigServiceRequest(
            session_id=session_id, node_id=node_id, name=name, config=config
        )
        return self.stub.SetNodeConfigService(request)

    def get_emane_event_channel(self, session_id: int) -> GetEmaneEventChannelResponse:
        """
        Retrieves the current emane event channel being used for a session.

        :param session_id: session to get emane event channel for
        :return: emane event channel response
        :raises grpc.RpcError: when session doesn't exist
        """
        request = GetEmaneEventChannelRequest(session_id=session_id)
        return self.stub.GetEmaneEventChannel(request)

    def execute_script(self, script: str) -> ExecuteScriptResponse:
        """
        Executes a python script given context of the current CoreEmu object.

        :param script: script to execute
        :return: execute script response
        """
        request = ExecuteScriptRequest(script=script)
        return self.stub.ExecuteScript(request)

    def wlan_link(
        self, session_id: int, wlan_id: int, node1_id: int, node2_id: int, linked: bool
    ) -> WlanLinkResponse:
        """
        Links/unlinks nodes on the same WLAN.

        :param session_id: session id containing wlan and nodes
        :param wlan_id: wlan nodes must belong to
        :param node1_id: first node of pair to link/unlink
        :param node2_id: second node of pair to link/unlin
        :param linked: True to link, False to unlink
        :return: wlan link response
        :raises grpc.RpcError: when session or one of the nodes do not exist
        """
        request = WlanLinkRequest(
            session_id=session_id,
            wlan=wlan_id,
            node1_id=node1_id,
            node2_id=node2_id,
            linked=linked,
        )
        return self.stub.WlanLink(request)

    def emane_pathlosses(
        self, pathloss_iterator: Iterable[EmanePathlossesRequest]
    ) -> EmanePathlossesResponse:
        """
        Stream EMANE pathloss events.

        :param pathloss_iterator: iterator for sending emane pathloss events
        :return: emane pathloss response
        :raises grpc.RpcError: when a pathloss event session or one of the nodes do not
            exist
        """
        return self.stub.EmanePathlosses(pathloss_iterator)

    def connect(self) -> None:
        """
        Open connection to server, must be closed manually.

        :return: nothing
        """
        self.channel = grpc.insecure_channel(
            self.address, options=[("grpc.enable_http_proxy", self.proxy)]
        )
        self.stub = core_pb2_grpc.CoreApiStub(self.channel)

    def close(self) -> None:
        """
        Close currently opened server channel connection.

        :return: nothing
        """
        if self.channel:
            self.channel.close()
            self.channel = None

    @contextmanager
    def context_connect(self) -> Generator:
        """
        Makes a context manager based connection to the server, will close after
        context ends.

        :return: nothing
        """
        try:
            self.connect()
            yield
        finally:
            self.close()
