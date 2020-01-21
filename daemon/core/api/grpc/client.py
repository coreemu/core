"""
gRpc client for interfacing with CORE, when gRPC mode is enabled.
"""

import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List

import grpc
import netaddr

from core import utils
from core.api.grpc import configservices_pb2, core_pb2, core_pb2_grpc
from core.api.grpc.configservices_pb2 import (
    GetConfigServiceDefaultsRequest,
    GetConfigServiceDefaultsResponse,
    GetConfigServicesRequest,
    GetConfigServicesResponse,
    GetNodeConfigServiceRequest,
    GetNodeConfigServiceResponse,
    GetNodeConfigServicesRequest,
    GetNodeConfigServicesResponse,
    SetNodeConfigServiceRequest,
    SetNodeConfigServiceResponse,
)


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
        if not ip4_prefix and not ip6_prefix:
            raise ValueError("ip4 or ip6 must be provided")

        self.ip4 = None
        if ip4_prefix:
            self.ip4 = netaddr.IPNetwork(ip4_prefix)
        self.ip6 = None
        if ip6_prefix:
            self.ip6 = netaddr.IPNetwork(ip6_prefix)

    def ip4_address(self, node_id: int) -> str:
        """
        Convenience method to return the IP4 address for a node.

        :param node_id: node id to get IP4 address for
        :return: IP4 address or None
        """
        if not self.ip4:
            raise ValueError("ip4 prefixes have not been set")
        return str(self.ip4[node_id])

    def ip6_address(self, node_id: int) -> str:
        """
        Convenience method to return the IP6 address for a node.

        :param node_id: node id to get IP6 address for
        :return: IP4 address or None
        """
        if not self.ip6:
            raise ValueError("ip6 prefixes have not been set")
        return str(self.ip6[node_id])

    def create_interface(
        self, node_id: int, interface_id: int, name: str = None, mac: str = None
    ) -> core_pb2.Interface:
        """
        Creates interface data for linking nodes, using the nodes unique id for
        generation, along with a random mac address, unless provided.

        :param node_id: node id to create interface for
        :param interface_id: interface id for interface
        :param name: name to set for interface, default is eth{id}
        :param mac: mac address to use for this interface, default is random
            generation
        :return: new interface data for the provided node
        """
        # generate ip4 data
        ip4 = None
        ip4_mask = None
        if self.ip4:
            ip4 = self.ip4_address(node_id)
            ip4_mask = self.ip4.prefixlen

        # generate ip6 data
        ip6 = None
        ip6_mask = None
        if self.ip6:
            ip6 = self.ip6_address(node_id)
            ip6_mask = self.ip6.prefixlen

        # random mac
        if not mac:
            mac = utils.random_mac()

        return core_pb2.Interface(
            id=interface_id,
            name=name,
            ip4=ip4,
            ip4mask=ip4_mask,
            ip6=ip6,
            ip6mask=ip6_mask,
            mac=str(mac),
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
    thread = threading.Thread(target=stream_listener, args=(stream, handler))
    thread.daemon = True
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
        self.address = address
        self.stub = None
        self.channel = None
        self.proxy = proxy

    def start_session(
        self,
        session_id: int,
        nodes: List[core_pb2.Node],
        links: List[core_pb2.Link],
        location: core_pb2.SessionLocation = None,
        hooks: List[core_pb2.Hook] = None,
        emane_config: Dict[str, str] = None,
        emane_model_configs: List[core_pb2.EmaneModelConfig] = None,
        wlan_configs: List[core_pb2.WlanConfig] = None,
        mobility_configs: List[core_pb2.MobilityConfig] = None,
        service_configs: List[core_pb2.ServiceConfig] = None,
        service_file_configs: List[core_pb2.ServiceFileConfig] = None,
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
    ) -> Any:
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
        logging.info("STREAM TYPE: %s", type(stream))
        start_streamer(stream, handler)
        return stream

    def throughputs(
        self, session_id: int, handler: Callable[[core_pb2.ThroughputsEvent], None]
    ) -> Any:
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
        position: core_pb2.Position,
        icon: str = None,
        source: str = None,
    ) -> core_pb2.EditNodeResponse:
        """
        Edit a node, currently only changes position.

        :param session_id: session id
        :param node_id: node id
        :param position: position to set node to
        :param icon: path to icon for gui to use for node
        :param source: application source editing node
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.EditNodeRequest(
            session_id=session_id,
            node_id=node_id,
            position=position,
            icon=icon,
            source=source,
        )
        return self.stub.EditNode(request)

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
        self, session_id: int, node_id: int, command: str
    ) -> core_pb2.NodeCommandResponse:
        """
        Send command to a node and get the output.

        :param session_id: session id
        :param node_id: node id
        :param command: command to run on node
        :return: response with command combined stdout/stderr
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.NodeCommandRequest(
            session_id=session_id, node_id=node_id, command=command
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
        node_one_id: int,
        node_two_id: int,
        interface_one: core_pb2.Interface = None,
        interface_two: core_pb2.Interface = None,
        options: core_pb2.LinkOptions = None,
    ) -> core_pb2.AddLinkResponse:
        """
        Add a link between nodes.

        :param session_id: session id
        :param node_one_id: node one id
        :param node_two_id: node two id
        :param interface_one: node one interface data
        :param interface_two: node two interface data
        :param options: options for link (jitter, bandwidth, etc)
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or one of the nodes don't exist
        """
        link = core_pb2.Link(
            node_one_id=node_one_id,
            node_two_id=node_two_id,
            type=core_pb2.LinkType.WIRED,
            interface_one=interface_one,
            interface_two=interface_two,
            options=options,
        )
        request = core_pb2.AddLinkRequest(session_id=session_id, link=link)
        return self.stub.AddLink(request)

    def edit_link(
        self,
        session_id: int,
        node_one_id: int,
        node_two_id: int,
        options: core_pb2.LinkOptions,
        interface_one_id: int = None,
        interface_two_id: int = None,
    ) -> core_pb2.EditLinkResponse:
        """
        Edit a link between nodes.

        :param session_id: session id
        :param node_one_id: node one id
        :param node_two_id: node two id
        :param options: options for link (jitter, bandwidth, etc)
        :param interface_one_id: node one interface id
        :param interface_two_id: node two interface id
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or one of the nodes don't exist
        """
        request = core_pb2.EditLinkRequest(
            session_id=session_id,
            node_one_id=node_one_id,
            node_two_id=node_two_id,
            options=options,
            interface_one_id=interface_one_id,
            interface_two_id=interface_two_id,
        )
        return self.stub.EditLink(request)

    def delete_link(
        self,
        session_id: int,
        node_one_id: int,
        node_two_id: int,
        interface_one_id: int = None,
        interface_two_id: int = None,
    ) -> core_pb2.DeleteLinkResponse:
        """
        Delete a link between nodes.

        :param session_id: session id
        :param node_one_id: node one id
        :param node_two_id: node two id
        :param interface_one_id: node one interface id
        :param interface_two_id: node two interface id
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteLinkRequest(
            session_id=session_id,
            node_one_id=node_one_id,
            node_two_id=node_two_id,
            interface_one_id=interface_one_id,
            interface_two_id=interface_two_id,
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
        file_data: bytes,
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

    def get_mobility_configs(
        self, session_id: int
    ) -> core_pb2.GetMobilityConfigsResponse:
        """
        Get all mobility configurations.

        :param session_id: session id
        :return: response with a dict of node ids to mobility configurations
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetMobilityConfigsRequest(session_id=session_id)
        return self.stub.GetMobilityConfigs(request)

    def get_mobility_config(
        self, session_id: int, node_id: int
    ) -> core_pb2.GetMobilityConfigResponse:
        """
        Get mobility configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetMobilityConfigRequest(
            session_id=session_id, node_id=node_id
        )
        return self.stub.GetMobilityConfig(request)

    def set_mobility_config(
        self, session_id: int, node_id: int, config: Dict[str, str]
    ) -> core_pb2.SetMobilityConfigResponse:
        """
        Set mobility configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :param config: mobility configuration
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        mobility_config = core_pb2.MobilityConfig(node_id=node_id, config=config)
        request = core_pb2.SetMobilityConfigRequest(
            session_id=session_id, mobility_config=mobility_config
        )
        return self.stub.SetMobilityConfig(request)

    def mobility_action(
        self, session_id: int, node_id: int, action: core_pb2.ServiceAction
    ) -> core_pb2.MobilityActionResponse:
        """
        Send a mobility action for a node.

        :param session_id: session id
        :param node_id: node id
        :param action: action to take
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.MobilityActionRequest(
            session_id=session_id, node_id=node_id, action=action
        )
        return self.stub.MobilityAction(request)

    def get_services(self) -> core_pb2.GetServicesResponse:
        """
        Get all currently loaded services.

        :return: response with a list of services
        """
        request = core_pb2.GetServicesRequest()
        return self.stub.GetServices(request)

    def get_service_defaults(
        self, session_id: int
    ) -> core_pb2.GetServiceDefaultsResponse:
        """
        Get default services for different default node models.

        :param session_id: session id
        :return: response with a dict of node model to a list of services
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetServiceDefaultsRequest(session_id=session_id)
        return self.stub.GetServiceDefaults(request)

    def set_service_defaults(
        self, session_id: int, service_defaults: Dict[str, List[str]]
    ) -> core_pb2.SetServiceDefaultsResponse:
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
            default = core_pb2.ServiceDefaults(node_type=node_type, services=services)
            defaults.append(default)
        request = core_pb2.SetServiceDefaultsRequest(
            session_id=session_id, defaults=defaults
        )
        return self.stub.SetServiceDefaults(request)

    def get_node_service_configs(
        self, session_id: int
    ) -> core_pb2.GetNodeServiceConfigsResponse:
        """
        Get service data for a node.

        :param session_id: session id
        :return: response with all node service configs
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetNodeServiceConfigsRequest(session_id=session_id)
        return self.stub.GetNodeServiceConfigs(request)

    def get_node_service(
        self, session_id: int, node_id: int, service: str
    ) -> core_pb2.GetNodeServiceResponse:
        """
        Get service data for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :return: response with node service data
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeServiceRequest(
            session_id=session_id, node_id=node_id, service=service
        )
        return self.stub.GetNodeService(request)

    def get_node_service_file(
        self, session_id: int, node_id: int, service: str, file_name: str
    ) -> core_pb2.GetNodeServiceFileResponse:
        """
        Get a service file for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :param file_name: file name to get data for
        :return: response with file data
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeServiceFileRequest(
            session_id=session_id, node_id=node_id, service=service, file=file_name
        )
        return self.stub.GetNodeServiceFile(request)

    def set_node_service(
        self,
        session_id: int,
        node_id: int,
        service: str,
        startup: List[str],
        validate: List[str],
        shutdown: List[str],
    ) -> core_pb2.SetNodeServiceResponse:
        """
        Set service data for a node.

        :param session_id: session id
        :param node_id: node id
        :param service: service name
        :param startup: startup commands
        :param validate: validation commands
        :param shutdown: shutdown commands
        :return: response with result of success or failure
        :raises grpc.RpcError: when session or node doesn't exist
        """
        config = core_pb2.ServiceConfig(
            node_id=node_id,
            service=service,
            startup=startup,
            validate=validate,
            shutdown=shutdown,
        )
        request = core_pb2.SetNodeServiceRequest(session_id=session_id, config=config)
        return self.stub.SetNodeService(request)

    def set_node_service_file(
        self, session_id: int, node_id: int, service: str, file_name: str, data: bytes
    ) -> core_pb2.SetNodeServiceFileResponse:
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
        config = core_pb2.ServiceFileConfig(
            node_id=node_id, service=service, file=file_name, data=data
        )
        request = core_pb2.SetNodeServiceFileRequest(
            session_id=session_id, config=config
        )
        return self.stub.SetNodeServiceFile(request)

    def service_action(
        self,
        session_id: int,
        node_id: int,
        service: str,
        action: core_pb2.ServiceAction,
    ) -> core_pb2.ServiceActionResponse:
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
        request = core_pb2.ServiceActionRequest(
            session_id=session_id, node_id=node_id, service=service, action=action
        )
        return self.stub.ServiceAction(request)

    def get_wlan_configs(self, session_id: int) -> core_pb2.GetWlanConfigsResponse:
        """
        Get all wlan configurations.

        :param session_id: session id
        :return: response with a dict of node ids to wlan configurations
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetWlanConfigsRequest(session_id=session_id)
        return self.stub.GetWlanConfigs(request)

    def get_wlan_config(
        self, session_id: int, node_id: int
    ) -> core_pb2.GetWlanConfigResponse:
        """
        Get wlan configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetWlanConfigRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetWlanConfig(request)

    def set_wlan_config(
        self, session_id: int, node_id: int, config: Dict[str, str]
    ) -> core_pb2.SetWlanConfigResponse:
        """
        Set wlan configuration for a node.

        :param session_id: session id
        :param node_id: node id
        :param config: wlan configuration
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        wlan_config = core_pb2.WlanConfig(node_id=node_id, config=config)
        request = core_pb2.SetWlanConfigRequest(
            session_id=session_id, wlan_config=wlan_config
        )
        return self.stub.SetWlanConfig(request)

    def get_emane_config(self, session_id: int) -> core_pb2.GetEmaneConfigResponse:
        """
        Get session emane configuration.

        :param session_id: session id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneConfigRequest(session_id=session_id)
        return self.stub.GetEmaneConfig(request)

    def set_emane_config(
        self, session_id: int, config: Dict[str, str]
    ) -> core_pb2.SetEmaneConfigResponse:
        """
        Set session emane configuration.

        :param session_id: session id
        :param config: emane configuration
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetEmaneConfigRequest(session_id=session_id, config=config)
        return self.stub.SetEmaneConfig(request)

    def get_emane_models(self, session_id: int) -> core_pb2.GetEmaneModelsResponse:
        """
        Get session emane models.

        :param session_id: session id
        :return: response with a list of emane models
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelsRequest(session_id=session_id)
        return self.stub.GetEmaneModels(request)

    def get_emane_model_config(
        self, session_id: int, node_id: int, model: str, interface_id: int = -1
    ) -> core_pb2.GetEmaneModelConfigResponse:
        """
        Get emane model configuration for a node or a node's interface.

        :param session_id: session id
        :param node_id: node id
        :param model: emane model name
        :param interface_id: node interface id
        :return: response with a list of configuration groups
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelConfigRequest(
            session_id=session_id, node_id=node_id, model=model, interface=interface_id
        )
        return self.stub.GetEmaneModelConfig(request)

    def set_emane_model_config(
        self,
        session_id: int,
        node_id: int,
        model: str,
        config: Dict[str, str],
        interface_id: int = -1,
    ) -> core_pb2.SetEmaneModelConfigResponse:
        """
        Set emane model configuration for a node or a node's interface.

        :param session_id: session id
        :param node_id: node id
        :param model: emane model name
        :param config: emane model configuration
        :param interface_id: node interface id
        :return: response with result of success or failure
        :raises grpc.RpcError: when session doesn't exist
        """
        model_config = core_pb2.EmaneModelConfig(
            node_id=node_id, model=model, config=config, interface_id=interface_id
        )
        request = core_pb2.SetEmaneModelConfigRequest(
            session_id=session_id, emane_model_config=model_config
        )
        return self.stub.SetEmaneModelConfig(request)

    def get_emane_model_configs(
        self, session_id: int
    ) -> core_pb2.GetEmaneModelConfigsResponse:
        """
        Get all emane model configurations for a session.

        :param session_id: session id
        :return: response with a dictionary of node/interface ids to configurations
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelConfigsRequest(session_id=session_id)
        return self.stub.GetEmaneModelConfigs(request)

    def save_xml(self, session_id: int, file_path: str) -> core_pb2.SaveXmlResponse:
        """
        Save the current scenario to an XML file.

        :param session_id: session id
        :param file_path: local path to save scenario XML file to
        :return: nothing
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
        self, session_id: int, nem_one: int, nem_two: int, linked: bool
    ) -> core_pb2.EmaneLinkResponse:
        """
        Helps broadcast wireless link/unlink between EMANE nodes.

        :param session_id: session id
        :param nem_one:
        :param nem_two:
        :param linked: True to link, False to unlink
        :return: core_pb2.EmaneLinkResponse
        """
        request = core_pb2.EmaneLinkRequest(
            session_id=session_id, nem_one=nem_one, nem_two=nem_two, linked=linked
        )
        return self.stub.EmaneLink(request)

    def get_interfaces(self) -> core_pb2.GetInterfacesResponse:
        """
        Retrieves a list of interfaces available on the host machine that are not
        a part of a CORE session.

        :return: core_pb2.GetInterfacesResponse
        """
        request = core_pb2.GetInterfacesRequest()
        return self.stub.GetInterfaces(request)

    def get_config_services(self) -> GetConfigServicesResponse:
        request = GetConfigServicesRequest()
        return self.stub.GetConfigServices(request)

    def get_config_service_defaults(
        self, name: str
    ) -> GetConfigServiceDefaultsResponse:
        request = GetConfigServiceDefaultsRequest(name=name)
        return self.stub.GetConfigServiceDefaults(request)

    def get_node_config_service(
        self, session_id: int, node_id: int, name: str
    ) -> GetNodeConfigServiceResponse:
        request = GetNodeConfigServiceRequest(
            session_id=session_id, node_id=node_id, name=name
        )
        return self.stub.GetNodeConfigService(request)

    def get_node_config_services(
        self, session_id: int, node_id: int
    ) -> GetNodeConfigServicesResponse:
        request = GetNodeConfigServicesRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetNodeConfigServices(request)

    def set_node_config_service(
        self, session_id: int, node_id: int, name: str, config: Dict[str, str]
    ) -> SetNodeConfigServiceResponse:
        request = SetNodeConfigServiceRequest(
            session_id=session_id, node_id=node_id, name=name, config=config
        )
        return self.stub.SetNodeConfigService(request)

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
        Makes a context manager based connection to the server, will close after context ends.

        :return: nothing
        """
        try:
            self.connect()
            yield
        finally:
            self.close()
