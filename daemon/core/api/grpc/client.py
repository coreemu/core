"""
gRpc client for interfacing with CORE, when gRPC mode is enabled.
"""

from __future__ import print_function

import logging
import threading
from contextlib import contextmanager

import grpc

from core.api.grpc import core_pb2
from core.api.grpc import core_pb2_grpc
from core.nodes.ipaddress import Ipv4Prefix, Ipv6Prefix, MacAddress


class InterfaceHelper(object):
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
            mac=str(mac)
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


class CoreGrpcClient(object):
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

    def create_session(self, _id=None):
        """
        Create a session.

        :param int _id: id for session, default is None and one will be created for you
        :return: response with created session id
        :rtype: core_pb2.CreateSessionResponse
        """
        request = core_pb2.CreateSessionRequest(id=_id)
        return self.stub.CreateSession(request)

    def delete_session(self, _id):
        """
        Delete a session.

        :param int _id: id of session
        :return: response with result of deletion success or failure
        :rtype: core_pb2.DeleteSessionResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteSessionRequest(id=_id)
        return self.stub.DeleteSession(request)

    def get_sessions(self):
        """
        Retrieves all currently known sessions.

        :return: response with a list of currently known session, their state and number of nodes
        :rtype: core_pb2.GetSessionsResponse
        """
        return self.stub.GetSessions(core_pb2.GetSessionsRequest())

    def get_session(self, _id):
        """
        Retrieve a session.

        :param int _id: id of session
        :return: response with sessions state, nodes, and links
        :rtype: core_pb2.GetSessionResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionRequest(id=_id)
        return self.stub.GetSession(request)

    def get_session_options(self, _id):
        """
        Retrieve session options.

        :param int _id: id of session
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetSessionOptionsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionOptionsRequest(id=_id)
        return self.stub.GetSessionOptions(request)

    def set_session_options(self, _id, config):
        """
        Set options for a session.

        :param int _id: id of session
        :param dict[str, str] config: configuration values to set
        :return: response with result of success or failure
        :rtype: core_pb2.SetSessionOptionsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionOptionsRequest(id=_id, config=config)
        return self.stub.SetSessionOptions(request)

    def get_session_location(self, _id):
        """
        Get session location.

        :param int _id: id of session
        :return: response with session position reference and scale
        :rtype: core_pb2.GetSessionLocationResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionLocationRequest(id=_id)
        return self.stub.GetSessionLocation(request)

    def set_session_location(self, _id, x=None, y=None, z=None, lat=None, lon=None, alt=None, scale=None):
        """
        Set session location.

        :param int _id: id of session
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
        position = core_pb2.Position(x=x, y=y, z=z, lat=lat, lon=lon, alt=alt)
        request = core_pb2.SetSessionLocationRequest(id=_id, position=position, scale=scale)
        return self.stub.SetSessionLocation(request)

    def set_session_state(self, _id, state):
        """
        Set session state.

        :param int _id: id of session
        :param core_pb2.SessionState state: session state to transition to
        :return: response with result of success or failure
        :rtype: core_pb2.SetSessionStateResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetSessionStateRequest(id=_id, state=state)
        return self.stub.SetSessionState(request)

    def node_events(self, _id, handler):
        """
        Listen for session node events.

        :param int _id: id of session
        :param handler: handler for every event
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.NodeEventsRequest(id=_id)
        stream = self.stub.NodeEvents(request)
        start_streamer(stream, handler)

    def link_events(self, _id, handler):
        """
        Listen for session link events.

        :param int _id: id of session
        :param handler: handler for every event
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.LinkEventsRequest(id=_id)
        stream = self.stub.LinkEvents(request)
        start_streamer(stream, handler)

    def session_events(self, _id, handler):
        """
        Listen for session events.

        :param int _id: id of session
        :param handler: handler for every event
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SessionEventsRequest(id=_id)
        stream = self.stub.SessionEvents(request)
        start_streamer(stream, handler)

    def config_events(self, _id, handler):
        """
        Listen for session config events.

        :param int _id: id of session
        :param handler: handler for every event
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.ConfigEventsRequest(id=_id)
        stream = self.stub.ConfigEvents(request)
        start_streamer(stream, handler)

    def exception_events(self, _id, handler):
        """
        Listen for session exception events.

        :param int _id: id of session
        :param handler: handler for every event
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.ExceptionEventsRequest(id=_id)
        stream = self.stub.ExceptionEvents(request)
        start_streamer(stream, handler)

    def file_events(self, _id, handler):
        """
        Listen for session file events.

        :param int _id: id of session
        :param handler: handler for every event
        :return: nothing
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.FileEventsRequest(id=_id)
        stream = self.stub.FileEvents(request)
        start_streamer(stream, handler)

    def add_node(self, session, node):
        """
        Add node to session.

        :param int session: session id
        :param core_pb2.Node node: node to add
        :return: response with node id
        :rtype: core_pb2.AddNodeResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.AddNodeRequest(session=session, node=node)
        return self.stub.AddNode(request)

    def get_node(self, session, _id):
        """
        Get node details.

        :param int session: session id
        :param int _id: node id
        :return: response with node details
        :rtype: core_pb2.GetNodeResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeRequest(session=session, id=_id)
        return self.stub.GetNode(request)

    def edit_node(self, session, _id, position):
        """
        Edit a node, currently only changes position.

        :param int session: session id
        :param int _id: node id
        :param core_pb2.Position position: position to set node to
        :return: response with result of success or failure
        :rtype: core_pb2.EditNodeResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.EditNodeRequest(session=session, id=_id, position=position)
        return self.stub.EditNode(request)

    def delete_node(self, session, _id):
        """
        Delete node from session.

        :param int session: session id
        :param int _id: node id
        :return: response with result of success or failure
        :rtype: core_pb2.DeleteNodeResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteNodeRequest(session=session, id=_id)
        return self.stub.DeleteNode(request)

    def get_node_links(self, session, _id):
        """
        Get current links for a node.

        :param int session: session id
        :param int _id: node id
        :return: response with a list of links
        :rtype: core_pb2.GetNodeLinksResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeLinksRequest(session=session, id=_id)
        return self.stub.GetNodeLinks(request)

    def add_link(self, session, node_one, node_two, interface_one=None, interface_two=None, options=None):
        """
        Add a link between nodes.

        :param int session: session id
        :param int node_one: node one id
        :param int node_two: node two id
        :param core_pb2.Interface interface_one: node one interface data
        :param core_pb2.Interface interface_two: node two interface data
        :param core_pb2.LinkOptions options: options for link (jitter, bandwidth, etc)
        :return: response with result of success or failure
        :rtype: core_pb2.AddLinkResponse
        :raises grpc.RpcError: when session or one of the nodes don't exist
        """
        link = core_pb2.Link(
            node_one=node_one, node_two=node_two, type=core_pb2.LINK_WIRED,
            interface_one=interface_one, interface_two=interface_two, options=options)
        request = core_pb2.AddLinkRequest(session=session, link=link)
        return self.stub.AddLink(request)

    def edit_link(self, session, node_one, node_two, options, interface_one=None, interface_two=None):
        """
        Edit a link between nodes.

        :param int session: session id
        :param int node_one: node one id
        :param int node_two: node two id
        :param core_pb2.LinkOptions options: options for link (jitter, bandwidth, etc)
        :param int interface_one: node one interface id
        :param int interface_two: node two interface id
        :return: response with result of success or failure
        :rtype: core_pb2.EditLinkResponse
        :raises grpc.RpcError: when session or one of the nodes don't exist
        """
        request = core_pb2.EditLinkRequest(
            session=session, node_one=node_one, node_two=node_two, options=options,
            interface_one=interface_one, interface_two=interface_two)
        return self.stub.EditLink(request)

    def delete_link(self, session, node_one, node_two, interface_one=None, interface_two=None):
        """
        Delete a link between nodes.

        :param int session: session id
        :param int node_one: node one id
        :param int node_two: node two id
        :param int interface_one: node one interface id
        :param int interface_two: node two interface id
        :return: response with result of success or failure
        :rtype: core_pb2.DeleteLinkResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.DeleteLinkRequest(
            session=session, node_one=node_one, node_two=node_two,
            interface_one=interface_one, interface_two=interface_two)
        return self.stub.DeleteLink(request)

    def get_hooks(self, session):
        """
        Get all hook scripts.

        :param int session: session id
        :return: response with a list of hooks
        :rtype: core_pb2.GetHooksResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetHooksRequest(session=session)
        return self.stub.GetHooks(request)

    def add_hook(self, session, state, file_name, file_data):
        """
        Add hook scripts.

        :param int session: session id
        :param core_pb2.SessionState state: state to trigger hook
        :param str file_name: name of file for hook script
        :param bytes file_data: hook script contents
        :return: response with result of success or failure
        :rtype: core_pb2.AddHookResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        hook = core_pb2.Hook(state=state, file=file_name, data=file_data)
        request = core_pb2.AddHookRequest(session=session, hook=hook)
        return self.stub.AddHook(request)

    def get_mobility_configs(self, session):
        """
        Get all mobility configurations.

        :param int session: session id
        :return: response with a dict of node ids to mobility configurations
        :rtype: core_pb2.GetMobilityConfigsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetMobilityConfigsRequest(session=session)
        return self.stub.GetMobilityConfigs(request)

    def get_mobility_config(self, session, _id):
        """
        Get mobility configuration for a node.

        :param int session: session id
        :param int _id: node id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetMobilityConfigResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetMobilityConfigRequest(session=session, id=_id)
        return self.stub.GetMobilityConfig(request)

    def set_mobility_config(self, session, _id, config):
        """
        Set mobility configuration for a node.

        :param int session: session id
        :param int _id: node id
        :param dict[str, str] config: mobility configuration
        :return: response with result of success or failure
        :rtype: core_pb2.SetMobilityConfigResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.SetMobilityConfigRequest(session=session, id=_id, config=config)
        return self.stub.SetMobilityConfig(request)

    def mobility_action(self, session, _id, action):
        """
        Send a mobility action for a node.

        :param int session: session id
        :param int _id: node id
        :param core_pb2.ServiceAction action: action to take
        :return: response with result of success or failure
        :rtype: core_pb2.MobilityActionResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.MobilityActionRequest(session=session, id=_id, action=action)
        return self.stub.MobilityAction(request)

    def get_services(self):
        """
        Get all currently loaded services.

        :return: response with a list of services
        :rtype: core_pb2.GetServicesResponse
        """
        request = core_pb2.GetServicesRequest()
        return self.stub.GetServices(request)

    def get_service_defaults(self, session):
        """
        Get default services for different default node models.

        :param int session: session id
        :return: response with a dict of node model to a list of services
        :rtype: core_pb2.GetServiceDefaultsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetServiceDefaultsRequest(session=session)
        return self.stub.GetServiceDefaults(request)

    def set_service_defaults(self, session, service_defaults):
        """
        Set default services for node models.

        :param int session: session id
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
        request = core_pb2.SetServiceDefaultsRequest(session=session, defaults=defaults)
        return self.stub.SetServiceDefaults(request)

    def get_node_service(self, session, _id, service):
        """
        Get service data for a node.

        :param int session: session id
        :param int _id: node id
        :param str service: service name
        :return: response with node service data
        :rtype: core_pb2.GetNodeServiceResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeServiceRequest(session=session, id=_id, service=service)
        return self.stub.GetNodeService(request)

    def get_node_service_file(self, session, _id, service, file_name):
        """
        Get a service file for a node.

        :param int session: session id
        :param int _id: node id
        :param str service: service name
        :param str file_name: file name to get data for
        :return: response with file data
        :rtype: core_pb2.GetNodeServiceFileResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.GetNodeServiceFileRequest(session=session, id=_id, service=service, file=file_name)
        return self.stub.GetNodeServiceFile(request)

    def set_node_service(self, session, _id, service, startup, validate, shutdown):
        """
        Set service data for a node.

        :param int session: session id
        :param int _id: node id
        :param str service: service name
        :param list startup: startup commands
        :param list validate: validation commands
        :param list shutdown: shutdown commands
        :return: response with result of success or failure
        :rtype: core_pb2.SetNodeServiceResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.SetNodeServiceRequest(
            session=session, id=_id, service=service, startup=startup, validate=validate, shutdown=shutdown)
        return self.stub.SetNodeService(request)

    def set_node_service_file(self, session, _id, service, file_name, data):
        """
        Set a service file for a node.

        :param int session: session id
        :param int _id: node id
        :param str service: service name
        :param str file_name: file name to save
        :param bytes data: data to save for file
        :return: response with result of success or failure
        :rtype: core_pb2.SetNodeServiceFileResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.SetNodeServiceFileRequest(
            session=session, id=_id, service=service, file=file_name, data=data)
        return self.stub.SetNodeServiceFile(request)

    def service_action(self, session, _id, service, action):
        """
        Send an action to a service for a node.

        :param int session: session id
        :param int _id: node id
        :param str service: service name
        :param core_pb2.ServiceAction action: action for service (start, stop, restart, validate)
        :return: response with result of success or failure
        :rtype: core_pb2.ServiceActionResponse
        :raises grpc.RpcError: when session or node doesn't exist
        """
        request = core_pb2.ServiceActionRequest(session=session, id=_id, service=service, action=action)
        return self.stub.ServiceAction(request)

    def get_wlan_config(self, session, _id):
        """
        Get wlan configuration for a node.

        :param int session: session id
        :param int _id: node id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetWlanConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetWlanConfigRequest(session=session, id=_id)
        return self.stub.GetWlanConfig(request)

    def set_wlan_config(self, session, _id, config):
        """
        Set wlan configuration for a node.

        :param int session: session id
        :param int _id: node id
        :param dict[str, str] config: wlan configuration
        :return: response with result of success or failure
        :rtype: core_pb2.SetWlanConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetWlanConfigRequest(session=session, id=_id, config=config)
        return self.stub.SetWlanConfig(request)

    def get_emane_config(self, session):
        """
        Get session emane configuration.

        :param int session: session id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetEmaneConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneConfigRequest(session=session)
        return self.stub.GetEmaneConfig(request)

    def set_emane_config(self, session, config):
        """
        Set session emane configuration.

        :param int session: session id
        :param dict[str, str] config: emane configuration
        :return: response with result of success or failure
        :rtype: core_pb2.SetEmaneConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetEmaneConfigRequest(session=session, config=config)
        return self.stub.SetEmaneConfig(request)

    def get_emane_models(self, session):
        """
        Get session emane models.

        :param int session: session id
        :return: response with a list of emane models
        :rtype: core_pb2.GetEmaneModelsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelsRequest(session=session)
        return self.stub.GetEmaneModels(request)

    def get_emane_model_config(self, session, _id, model, interface_id=-1):
        """
        Get emane model configuration for a node or a node's interface.

        :param int session: session id
        :param int _id: node id
        :param str model: emane model name
        :param int interface_id: node interface id
        :return: response with a list of configuration groups
        :rtype: core_pb2.GetEmaneModelConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelConfigRequest(session=session, id=_id, model=model, interface=interface_id)
        return self.stub.GetEmaneModelConfig(request)

    def set_emane_model_config(self, session, _id, model, config, interface_id=-1):
        """
        Set emane model configuration for a node or a node's interface.

        :param int session: session id
        :param int _id: node id
        :param str model: emane model name
        :param dict[str, str] config: emane model configuration
        :param int interface_id: node interface id
        :return: response with result of success or failure
        :rtype: core_pb2.SetEmaneModelConfigResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.SetEmaneModelConfigRequest(
            session=session, id=_id, model=model, config=config, interface=interface_id)
        return self.stub.SetEmaneModelConfig(request)

    def get_emane_model_configs(self, session):
        """
        Get all emane model configurations for a session.

        :param int session: session id
        :return: response with a dictionary of node/interface ids to configurations
        :rtype: core_pb2.GetEmaneModelConfigsResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetEmaneModelConfigsRequest(session=session)
        return self.stub.GetEmaneModelConfigs(request)

    def save_xml(self, session, file_path):
        """
        Save the current scenario to an XML file.

        :param int session: session id
        :param str file_path: local path to save scenario XML file to
        :return: nothing
        """
        request = core_pb2.SaveXmlRequest(session=session)
        response = self.stub.SaveXml(request)
        with open(file_path, "wb") as xml_file:
            xml_file.write(response.data)

    def open_xml(self, file_path):
        """
        Load a local scenario XML file to open as a new session.

        :param str file_path: path of scenario XML file
        :return: response with opened session id
        :rtype: core_pb2.OpenXmlResponse
        """
        with open(file_path, "rb") as xml_file:
            data = xml_file.read()
        request = core_pb2.OpenXmlRequest(data=data)
        return self.stub.OpenXml(request)

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
