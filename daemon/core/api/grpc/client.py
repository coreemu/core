"""
gRpc client for interfacing with CORE, when gRPC mode is enabled.
"""

from __future__ import print_function

import logging
import threading
from contextlib import contextmanager

import grpc

from core.api.grpc import core_pb2, core_pb2_grpc
from core.nodes.ipaddress import Ipv4Prefix, Ipv6Prefix, MacAddress


class InterfaceHelper:
    """
    Convenience class to help generate IP4 and IP6 addresses for gRPC clients.
    """

    def __init__(self, ip4_prefix=None, ip6_prefix=None):
        """
        Creates an InterfaceHelper object.

        :param str ip4_prefix: ip4 prefix to use for generation
        :param str ip6_prefix: ip6 prefix to use for generation
        :raises ValueError: when both ip4 and ip6 prefixes have not been provided
        """
        if not ip4_prefix and not ip6_prefix:
            raise ValueError("ip4 or ip6 must be provided")

        self.ip4 = None
        if ip4_prefix:
            self.ip4 = Ipv4Prefix(ip4_prefix)
        self.ip6 = None
        if ip6_prefix:
            self.ip6 = Ipv6Prefix(ip6_prefix)

    def ip4_address(self, node_id):
        """
        Convenience method to return the IP4 address for a node.

        :param int node_id: node id to get IP4 address for
        :return: IP4 address or None
        :rtype: str
        """
        if not self.ip4:
            raise ValueError("ip4 prefixes have not been set")
        return str(self.ip4.addr(node_id))

    def ip6_address(self, node_id):
        """
        Convenience method to return the IP6 address for a node.

        :param int node_id: node id to get IP6 address for
        :return: IP4 address or None
        :rtype: str
        """
        if not self.ip6:
            raise ValueError("ip6 prefixes have not been set")
        return str(self.ip6.addr(node_id))

    def create_interface(self, node_id, interface_id, name=None, mac=None):
        """
        Creates interface data for linking nodes, using the nodes unique id for generation, along with a random
        mac address, unless provided.

        :param int node_id: node id to create interface for
        :param int interface_id: interface id for interface
        :param str name: name to set for interface, default is eth{id}
        :param str mac: mac address to use for this interface, default is random generation
        :return: new interface data for the provided node
        :rtype: core_pb2.Interface
        """
        # generate ip4 data
        ip4 = None
        ip4_mask = None
        if self.ip4:
            ip4 = str(self.ip4.addr(node_id))
            ip4_mask = self.ip4.prefixlen

        # generate ip6 data
        ip6 = None
        ip6_mask = None
        if self.ip6:
            ip6 = str(self.ip6.addr(node_id))
            ip6_mask = self.ip6.prefixlen

        # random mac
        if not mac:
            mac = MacAddress.random()

        return core_pb2.Interface(
            id=interface_id,
            name=name,
            ip4=ip4,
            ip4mask=ip4_mask,
            ip6=ip6,
            ip6mask=ip6_mask,
            mac=str(mac),
        )


def stream_listener(stream, handler):
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


def start_streamer(stream, handler):
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

    def __init__(self, address="localhost:50051"):
        """
        Creates a CoreGrpcClient instance.

        :param str address: grpc server address to connect to
        """
        self.address = address
        self.stub = None
        self.channel = None

    def start_session(
        self,
        session_id,
        nodes,
        links,
        location=None,
        hooks=None,
        emane_config=None,
        emane_model_configs=None,
        wlan_configs=None,
        mobility_configs=None,
        service_configs=None,
        service_file_configs=None,
    ):
        """
        Start a session.

        :param int session_id: id of session
        :param list nodes: list of nodes to create
        :param list links: list of links to create
        :param core_pb2.SessionLocation location: location to set
        :param list[core_pb2.Hook] hooks: session hooks to set
        :param dict emane_config: emane configuration to set
        :param list emane_model_configs: node emane model configurations
        :param list wlan_configs: node wlan configurations
        :param list mobility_configs: node mobility configurations
        :param list service_configs: node service configurations
        :param list service_file_configs: node service file configurations
        :return: start session response
        :rtype: core_pb2.StartSessionResponse
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
        )
        return self.stub.StartSession(request)

    def stop_session(self, session_id):
        """
        Stop a running session.

        :param int session_id: id of session
        :return: stop session response
        :rtype: core_pb2.StopSessionResponse
        """
        request = core_pb2.StopSessionRequest(session_id=session_id)
        return self.stub.StopSession(request)

    def create_session(self, session_id=None):
        """
        Create a session.

        :param int session_id: id for session, default is None and one will be created for you
        :return: response with created session id
        :rtype: core_pb2.CreateSessionResponse
        """
        request = core_pb2.CreateSessionRequest(session_id=session_id)
        return self.stub.CreateSession(request)

    def delete_session(self, session_id):
        """
        Delete a session.

        :param int session_id: id of session
        :return: response with result of deletion success or failure
        :rtype: core_pb2.DeleteSessionResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteSessionRequest(session_id=session_id)
        return self.stub.DeleteSession(request)

    def get_sessions(self):
        """
        Retrieves all currently known sessions.

        :return: response with a list of currently known session, their state and number of nodes
        :rtype: core_pb2.GetSessionsResponse
        """
        return self.stub.GetSessions(core_pb2.GetSessionsRequest())

    def get_session(self, session_id):
        """
        Retrieve a session.

        :param int session_id: id of session
        :return: response with sessions state, nodes, and links
        :rtype: core_pb2.GetSessionResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionRequest(session_id=session_id)
        return self.stub.GetSession(request)

    def get_session_options(self, session_id):
        """
        Retrieve session options as a dict with id mapping.

        :param int session_id: id of session
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetSessionOptionsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionOptionsRequest(session_id=session_id)
        return self.stub.GetSessionOptions(request)

    def set_session_options(self, session_id, config):
        """
        Set options for a session.

        :param int session_id: id of session
        :param dict[str, str] config: configuration values to set
        :return: response with result of success or failure
        :rtype: core_pb2.SetSessionOptionsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionOptionsRequest(
            session_id=session_id, config=config
        )
        return self.stub.SetSessionOptions(request)

    def get_session_metadata(self, session_id):
        """
        Retrieve session metadata as a dict with id mapping.

        :param int session_id: id of session
        :return: response with metadata dict
        :rtype: core_pb2.GetSessionMetadataResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionMetadataRequest(session_id=session_id)
        return self.stub.GetSessionMetadata(request)

    def set_session_metadata(self, session_id, config):
        """
        Set metadata for a session.

        :param int session_id: id of session
        :param dict[str, str] config: configuration values to set
        :return: response with result of success or failure
        :rtype: core_pb2.SetSessionMetadataResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionMetadataRequest(
            session_id=session_id, config=config
        )
        return self.stub.SetSessionMetadata(request)

    def get_session_location(self, session_id):
        """
        Get session location.

        :param int session_id: id of session
        :return: response with session position reference and scale
        :rtype: core_pb2.GetSessionLocationResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionLocationRequest(session_id=session_id)
        return self.stub.GetSessionLocation(request)

    def set_session_location(
        self,
        session_id,
        x=None,
        y=None,
        z=None,
        lat=None,
        lon=None,
        alt=None,
        scale=None,
    ):
        """
        Set session location.

        :param int session_id: id of session
        :param float x: x position
        :param float y: y position
        :param float z: z position
        :param float lat: latitude position
        :param float lon: longitude  position
        :param float alt: altitude position
        :param float scale: geo scale
        :return: response with result of success or failure
        :rtype: core_pb2.SetSessionLocationResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        location = core_pb2.SessionLocation(
            x=x, y=y, z=z, lat=lat, lon=lon, alt=alt, scale=scale
        )
        request = core_pb2.SetSessionLocationRequest(
            session_id=session_id, location=location
        )
        return self.stub.SetSessionLocation(request)

    def set_session_state(self, session_id, state):
        """
        Set session state.

        :param int session_id: id of session
        :param core_pb2.SessionState state: session state to transition to
        :return: response with result of success or failure
        :rtype: core_pb2.SetSessionStateResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionStateRequest(session_id=session_id, state=state)
        return self.stub.SetSessionState(request)

    def add_session_server(self, session_id, name, host):
        """
        Add distributed session server.

        :param int session_id: id of session
        :param str name: name of server to add
        :param str host: host address to connect to
        :return: response with result of success or failure
        :rtype: core_pb2.AddSessionServerResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.AddSessionServerRequest(
            session_id=session_id, name=name, host=host
        )
        return self.stub.AddSessionServer(request)

    def events(self, session_id, handler):
        """
        Listen for session events.

        :param int session_id: id of session
        :param handler: handler for every event
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.EventsRequest(session_id=session_id)
        stream = self.stub.Events(request)
        start_streamer(stream, handler)

    def throughputs(self, handler):
        """
        Listen for throughput events with information for interfaces and bridges.

        :param handler: handler for every event
        :return: nothing
        """
        request = core_pb2.ThroughputsRequest()
        stream = self.stub.Throughputs(request)
        start_streamer(stream, handler)

    def add_node(self, session_id, node):
        """
        Add node to session.

        :param int session_id: session id
        :param core_pb2.Node node: node to add
        :return: response with node id
        :rtype: core_pb2.AddNodeResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.AddNodeRequest(session_id=session_id, node=node)
        return self.stub.AddNode(request)

    def get_node(self, session_id, node_id):
        """
        Get node details.

        :param int session_id: session id
        :param int node_id: node id
        :return: response with node details
        :rtype: core_pb2.GetNodeResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetNode(request)

    def edit_node(self, session_id, node_id, position, icon=None, source=None):
        """
        Edit a node, currently only changes position.

        :param int session_id: session id
        :param int node_id: node id
        :param core_pb2.Position position: position to set node to
        :param str icon: path to icon for gui to use for node
        :param str source: application source editing node
        :return: response with result of success or failure
        :rtype: core_pb2.EditNodeResponse
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

    def delete_node(self, session_id, node_id):
        """
        Delete node from session.

        :param int session_id: session id
        :param int node_id: node id
        :return: response with result of success or failure
        :rtype: core_pb2.DeleteNodeResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteNodeRequest(session_id=session_id, node_id=node_id)
        return self.stub.DeleteNode(request)

    def node_command(self, session_id, node_id, command):
        """
        Send command to a node and get the output.

        :param int session_id: session id
        :param int node_id: node id
        :return: response with command combined stdout/stderr
        :rtype: core_pb2.NodeCommandResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.NodeCommandRequest(
            session_id=session_id, node_id=node_id, command=command
        )
        return self.stub.NodeCommand(request)

    def get_node_terminal(self, session_id, node_id):
        """
        Retrieve terminal command string for launching a local terminal.

        :param int session_id: session id
        :param int node_id: node id
        :return: response with a node terminal command
        :rtype: core_pb2.GetNodeTerminalResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeTerminalRequest(
            session_id=session_id, node_id=node_id
        )
        return self.stub.GetNodeTerminal(request)

    def get_node_links(self, session_id, node_id):
        """
        Get current links for a node.

        :param int session_id: session id
        :param int node_id: node id
        :return: response with a list of links
        :rtype: core_pb2.GetNodeLinksResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeLinksRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetNodeLinks(request)

    def add_link(
        self,
        session_id,
        node_one_id,
        node_two_id,
        interface_one=None,
        interface_two=None,
        options=None,
    ):
        """
        Add a link between nodes.

        :param int session_id: session id
        :param int node_one_id: node one id
        :param int node_two_id: node two id
        :param core_pb2.Interface interface_one: node one interface data
        :param core_pb2.Interface interface_two: node two interface data
        :param core_pb2.LinkOptions options: options for link (jitter, bandwidth, etc)
        :return: response with result of success or failure
        :rtype: core_pb2.AddLinkResponse
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
        session_id,
        node_one_id,
        node_two_id,
        options,
        interface_one_id=None,
        interface_two_id=None,
    ):
        """
        Edit a link between nodes.

        :param int session_id: session id
        :param int node_one_id: node one id
        :param int node_two_id: node two id
        :param core_pb2.LinkOptions options: options for link (jitter, bandwidth, etc)
        :param int interface_one_id: node one interface id
        :param int interface_two_id: node two interface id
        :return: response with result of success or failure
        :rtype: core_pb2.EditLinkResponse
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
        session_id,
        node_one_id,
        node_two_id,
        interface_one_id=None,
        interface_two_id=None,
    ):
        """
        Delete a link between nodes.

        :param int session_id: session id
        :param int node_one_id: node one id
        :param int node_two_id: node two id
        :param int interface_one_id: node one interface id
        :param int interface_two_id: node two interface id
        :return: response with result of success or failure
        :rtype: core_pb2.DeleteLinkResponse
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

    def get_hooks(self, session_id):
        """
        Get all hook scripts.

        :param int session_id: session id
        :return: response with a list of hooks
        :rtype: core_pb2.GetHooksResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetHooksRequest(session_id=session_id)
        return self.stub.GetHooks(request)

    def add_hook(self, session_id, state, file_name, file_data):
        """
        Add hook scripts.

        :param int session_id: session id
        :param core_pb2.SessionState state: state to trigger hook
        :param str file_name: name of file for hook script
        :param bytes file_data: hook script contents
        :return: response with result of success or failure
        :rtype: core_pb2.AddHookResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        hook = core_pb2.Hook(state=state, file=file_name, data=file_data)
        request = core_pb2.AddHookRequest(session_id=session_id, hook=hook)
        return self.stub.AddHook(request)

    def get_mobility_configs(self, session_id):
        """
        Get all mobility configurations.

        :param int session_id: session id
        :return: response with a dict of node ids to mobility configurations
        :rtype: core_pb2.GetMobilityConfigsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetMobilityConfigsRequest(session_id=session_id)
        return self.stub.GetMobilityConfigs(request)

    def get_mobility_config(self, session_id, node_id):
        """
        Get mobility configuration for a node.

        :param int session_id: session id
        :param int node_id: node id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetMobilityConfigResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetMobilityConfigRequest(
            session_id=session_id, node_id=node_id
        )
        return self.stub.GetMobilityConfig(request)

    def set_mobility_config(self, session_id, node_id, config):
        """
        Set mobility configuration for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param dict[str, str] config: mobility configuration
        :return: response with result of success or failure
        :rtype: core_pb2.SetMobilityConfigResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        mobility_config = core_pb2.MobilityConfig(node_id=node_id, config=config)
        request = core_pb2.SetMobilityConfigRequest(
            session_id=session_id, mobility_config=mobility_config
        )
        return self.stub.SetMobilityConfig(request)

    def mobility_action(self, session_id, node_id, action):
        """
        Send a mobility action for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param core_pb2.ServiceAction action: action to take
        :return: response with result of success or failure
        :rtype: core_pb2.MobilityActionResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.MobilityActionRequest(
            session_id=session_id, node_id=node_id, action=action
        )
        return self.stub.MobilityAction(request)

    def get_services(self):
        """
        Get all currently loaded services.

        :return: response with a list of services
        :rtype: core_pb2.GetServicesResponse
        """
        request = core_pb2.GetServicesRequest()
        return self.stub.GetServices(request)

    def get_service_defaults(self, session_id):
        """
        Get default services for different default node models.

        :param int session_id: session id
        :return: response with a dict of node model to a list of services
        :rtype: core_pb2.GetServiceDefaultsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetServiceDefaultsRequest(session_id=session_id)
        return self.stub.GetServiceDefaults(request)

    def set_service_defaults(self, session_id, service_defaults):
        """
        Set default services for node models.

        :param int session_id: session id
        :param dict service_defaults: node models to lists of services
        :return: response with result of success or failure
        :rtype: core_pb2.SetServiceDefaultsResponse
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

    def get_node_service(self, session_id, node_id, service):
        """
        Get service data for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param str service: service name
        :return: response with node service data
        :rtype: core_pb2.GetNodeServiceResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeServiceRequest(
            session_id=session_id, node_id=node_id, service=service
        )
        return self.stub.GetNodeService(request)

    def get_node_service_file(self, session_id, node_id, service, file_name):
        """
        Get a service file for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param str service: service name
        :param str file_name: file name to get data for
        :return: response with file data
        :rtype: core_pb2.GetNodeServiceFileResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeServiceFileRequest(
            session_id=session_id, node_id=node_id, service=service, file=file_name
        )
        return self.stub.GetNodeServiceFile(request)

    def set_node_service(
        self, session_id, node_id, service, startup, validate, shutdown
    ):
        """
        Set service data for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param str service: service name
        :param list startup: startup commands
        :param list validate: validation commands
        :param list shutdown: shutdown commands
        :return: response with result of success or failure
        :rtype: core_pb2.SetNodeServiceResponse
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

    def set_node_service_file(self, session_id, node_id, service, file_name, data):
        """
        Set a service file for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param str service: service name
        :param str file_name: file name to save
        :param bytes data: data to save for file
        :return: response with result of success or failure
        :rtype: core_pb2.SetNodeServiceFileResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        config = core_pb2.ServiceFileConfig(
            node_id=node_id, service=service, file=file_name, data=data
        )
        request = core_pb2.SetNodeServiceFileRequest(
            session_id=session_id, config=config
        )
        return self.stub.SetNodeServiceFile(request)

    def service_action(self, session_id, node_id, service, action):
        """
        Send an action to a service for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param str service: service name
        :param core_pb2.ServiceAction action: action for service (start, stop, restart, validate)
        :return: response with result of success or failure
        :rtype: core_pb2.ServiceActionResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.ServiceActionRequest(
            session_id=session_id, node_id=node_id, service=service, action=action
        )
        return self.stub.ServiceAction(request)

    def get_wlan_config(self, session_id, node_id):
        """
        Get wlan configuration for a node.

        :param int session_id: session id
        :param int node_id: node id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetWlanConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetWlanConfigRequest(session_id=session_id, node_id=node_id)
        return self.stub.GetWlanConfig(request)

    def set_wlan_config(self, session_id, node_id, config):
        """
        Set wlan configuration for a node.

        :param int session_id: session id
        :param int node_id: node id
        :param dict[str, str] config: wlan configuration
        :return: response with result of success or failure
        :rtype: core_pb2.SetWlanConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        wlan_config = core_pb2.WlanConfig(node_id=node_id, config=config)
        request = core_pb2.SetWlanConfigRequest(
            session_id=session_id, wlan_config=wlan_config
        )
        return self.stub.SetWlanConfig(request)

    def get_emane_config(self, session_id):
        """
        Get session emane configuration.

        :param int session_id: session id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetEmaneConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneConfigRequest(session_id=session_id)
        return self.stub.GetEmaneConfig(request)

    def set_emane_config(self, session_id, config):
        """
        Set session emane configuration.

        :param int session_id: session id
        :param dict[str, str] config: emane configuration
        :return: response with result of success or failure
        :rtype: core_pb2.SetEmaneConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetEmaneConfigRequest(session_id=session_id, config=config)
        return self.stub.SetEmaneConfig(request)

    def get_emane_models(self, session_id):
        """
        Get session emane models.

        :param int session_id: session id
        :return: response with a list of emane models
        :rtype: core_pb2.GetEmaneModelsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelsRequest(session_id=session_id)
        return self.stub.GetEmaneModels(request)

    def get_emane_model_config(self, session_id, node_id, model, interface_id=-1):
        """
        Get emane model configuration for a node or a node's interface.

        :param int session_id: session id
        :param int node_id: node id
        :param str model: emane model name
        :param int interface_id: node interface id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetEmaneModelConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelConfigRequest(
            session_id=session_id, node_id=node_id, model=model, interface=interface_id
        )
        return self.stub.GetEmaneModelConfig(request)

    def set_emane_model_config(
        self, session_id, node_id, model, config, interface_id=-1
    ):
        """
        Set emane model configuration for a node or a node's interface.

        :param int session_id: session id
        :param int node_id: node id
        :param str model: emane model name
        :param dict[str, str] config: emane model configuration
        :param int interface_id: node interface id
        :return: response with result of success or failure
        :rtype: core_pb2.SetEmaneModelConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        model_config = core_pb2.EmaneModelConfig(
            node_id=node_id, model=model, config=config, interface_id=interface_id
        )
        request = core_pb2.SetEmaneModelConfigRequest(
            session_id=session_id, emane_model_config=model_config
        )
        return self.stub.SetEmaneModelConfig(request)

    def get_emane_model_configs(self, session_id):
        """
        Get all emane model configurations for a session.

        :param int session_id: session id
        :return: response with a dictionary of node/interface ids to configurations
        :rtype: core_pb2.GetEmaneModelConfigsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelConfigsRequest(session_id=session_id)
        return self.stub.GetEmaneModelConfigs(request)

    def save_xml(self, session_id, file_path):
        """
        Save the current scenario to an XML file.

        :param int session_id: session id
        :param str file_path: local path to save scenario XML file to
        :return: nothing
        """
        request = core_pb2.SaveXmlRequest(session_id=session_id)
        response = self.stub.SaveXml(request)
        with open(file_path, "w") as xml_file:
            xml_file.write(response.data)

    def open_xml(self, file_path, start=False):
        """
        Load a local scenario XML file to open as a new session.

        :param str file_path: path of scenario XML file
        :param bool start: True to start session, False otherwise
        :return: response with opened session id
        :rtype: core_pb2.OpenXmlResponse
        """
        with open(file_path, "r") as xml_file:
            data = xml_file.read()
        request = core_pb2.OpenXmlRequest(data=data, start=start, file=file_path)
        return self.stub.OpenXml(request)

    def emane_link(self, session_id, nem_one, nem_two, linked):
        """
        Helps broadcast wireless link/unlink between EMANE nodes.

        :param int session_id: session id
        :param int nem_one:
        :param int nem_two:
        :param bool linked: True to link, False to unlink
        :return: core_pb2.EmaneLinkResponse
        """
        request = core_pb2.EmaneLinkRequest(
            session_id=session_id, nem_one=nem_one, nem_two=nem_two, linked=linked
        )
        return self.stub.EmaneLink(request)

    def connect(self):
        """
        Open connection to server, must be closed manually.

        :return: nothing
        """
        self.channel = grpc.insecure_channel(self.address)
        self.stub = core_pb2_grpc.CoreApiStub(self.channel)

    def close(self):
        """
        Close currently opened server channel connection.

        :return: nothing
        """
        if self.channel:
            self.channel.close()
            self.channel = None

    @contextmanager
    def context_connect(self):
        """
        Makes a context manager based connection to the server, will close after context ends.

        :return: nothing
        """
        try:
            self.connect()
            yield
        finally:
            self.close()
