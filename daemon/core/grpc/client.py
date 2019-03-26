"""
gRpc client for interfacing with CORE, when gRPC mode is enabled.
"""

from __future__ import print_function

import logging
import os
import threading
from contextlib import contextmanager

import grpc

from core.emulator.emudata import NodeOptions, IpPrefixes, InterfaceData, LinkOptions
from core.enumerations import NodeTypes, LinkTypes, EventTypes
from core.grpc import core_pb2
from core.grpc import core_pb2_grpc


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

        :param int _id: id for session, defaults to None will be created for you
        :return: response with created session id
        :rtype: core_pb2.CreateSessionResponse
        """
        request = core_pb2.CreateSessionRequest(id=_id)
        return self.stub.CreateSession(request)

    def delete_session(self, _id):
        """
        Delete a session.

        :param int _id: id of session to delete
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

        :param int _id: id of session to get data for
        :return: response with sessions state, nodes, and links
        :rtype: core_pb2.GetSessionResponse
        :raises grpc.RpcError: when session doesn't exist
        """
        request = core_pb2.GetSessionRequest(id=_id)
        return self.stub.GetSession(request)

    def get_session_options(self, _id):
        request = core_pb2.GetSessionOptionsRequest(id=_id)
        return self.stub.GetSessionOptions(request)

    def set_session_options(self, _id, config):
        request = core_pb2.SetSessionOptionsRequest(id=_id, config=config)
        return self.stub.SetSessionOptions(request)

    def get_session_location(self, _id):
        request = core_pb2.GetSessionLocationRequest(id=_id)
        return self.stub.GetSessionLocation(request)

    def set_session_location(self, _id, x=None, y=None, z=None, lat=None, lon=None, alt=None, scale=None):
        position = core_pb2.Position(x=x, y=y, z=z, lat=lat, lon=lon, alt=alt)
        request = core_pb2.SetSessionLocationRequest(id=_id, position=position, scale=scale)
        return self.stub.SetSessionLocation(request)

    def set_session_state(self, _id, state):
        request = core_pb2.SetSessionStateRequest(id=_id, state=state.value)
        return self.stub.SetSessionState(request)

    def node_events(self, _id, handler):
        request = core_pb2.NodeEventsRequest(id=_id)
        stream = self.stub.NodeEvents(request)
        start_streamer(stream, handler)

    def link_events(self, _id, handler):
        request = core_pb2.LinkEventsRequest(id=_id)
        stream = self.stub.LinkEvents(request)
        start_streamer(stream, handler)

    def session_events(self, _id, handler):
        request = core_pb2.SessionEventsRequest(id=_id)
        stream = self.stub.SessionEvents(request)
        start_streamer(stream, handler)

    def config_events(self, _id, handler):
        request = core_pb2.ConfigEventsRequest(id=_id)
        stream = self.stub.ConfigEvents(request)
        start_streamer(stream, handler)

    def exception_events(self, _id, handler):
        request = core_pb2.ExceptionEventsRequest(id=_id)
        stream = self.stub.ExceptionEvents(request)
        start_streamer(stream, handler)

    def file_events(self, _id, handler):
        request = core_pb2.FileEventsRequest(id=_id)
        stream = self.stub.FileEvents(request)
        start_streamer(stream, handler)

    def add_node(self, session, _type=NodeTypes.DEFAULT, _id=None, node_options=None, emane=None):
        if not node_options:
            node_options = NodeOptions()
        position = core_pb2.Position(
            x=node_options.x, y=node_options.y,
            lat=node_options.lat, lon=node_options.lon, alt=node_options.alt)
        request = core_pb2.AddNodeRequest(
            session=session, type=_type.value, name=node_options.name,
            model=node_options.model, icon=node_options.icon, services=node_options.services,
            opaque=node_options.opaque, emane=emane, position=position)
        return self.stub.AddNode(request)

    def get_node(self, session, _id):
        request = core_pb2.GetNodeRequest(session=session, id=_id)
        return self.stub.GetNode(request)

    def edit_node(self, session, _id, node_options):
        position = core_pb2.Position(
            x=node_options.x, y=node_options.y,
            lat=node_options.lat, lon=node_options.lon, alt=node_options.alt)
        request = core_pb2.EditNodeRequest(session=session, id=_id, position=position)
        return self.stub.EditNode(request)

    def delete_node(self, session, _id):
        request = core_pb2.DeleteNodeRequest(session=session, id=_id)
        return self.stub.DeleteNode(request)

    def get_node_links(self, session, _id):
        request = core_pb2.GetNodeLinksRequest(session=session, id=_id)
        return self.stub.GetNodeLinks(request)

    def add_link(self, session, node_one, node_two, interface_one=None, interface_two=None, link_options=None):
        interface_one_proto = None
        if interface_one is not None:
            mac = interface_one.mac
            if mac is not None:
                mac = str(mac)
            interface_one_proto = core_pb2.Interface(
                id=interface_one.id, name=interface_one.name, mac=mac,
                ip4=interface_one.ip4, ip4mask=interface_one.ip4_mask,
                ip6=interface_one.ip6, ip6mask=interface_one.ip6_mask)

        interface_two_proto = None
        if interface_two is not None:
            mac = interface_two.mac
            if mac is not None:
                mac = str(mac)
            interface_two_proto = core_pb2.Interface(
                id=interface_two.id, name=interface_two.name, mac=mac,
                ip4=interface_two.ip4, ip4mask=interface_two.ip4_mask,
                ip6=interface_two.ip6, ip6mask=interface_two.ip6_mask)

        options = None
        if link_options is not None:
            options = core_pb2.LinkOptions(
                delay=link_options.delay,
                bandwidth=link_options.bandwidth,
                per=link_options.per,
                dup=link_options.dup,
                jitter=link_options.jitter,
                mer=link_options.mer,
                burst=link_options.burst,
                mburst=link_options.mburst,
                unidirectional=link_options.unidirectional,
                key=link_options.key,
                opaque=link_options.opaque
            )

        link = core_pb2.Link(
            node_one=node_one, node_two=node_two, type=LinkTypes.WIRED.value,
            interface_one=interface_one_proto, interface_two=interface_two_proto, options=options)
        request = core_pb2.AddLinkRequest(session=session, link=link)
        return self.stub.AddLink(request)

    def edit_link(self, session, node_one, node_two, link_options, interface_one=None, interface_two=None):
        options = core_pb2.LinkOptions(
            delay=link_options.delay,
            bandwidth=link_options.bandwidth,
            per=link_options.per,
            dup=link_options.dup,
            jitter=link_options.jitter,
            mer=link_options.mer,
            burst=link_options.burst,
            mburst=link_options.mburst,
            unidirectional=link_options.unidirectional,
            key=link_options.key,
            opaque=link_options.opaque
        )
        request = core_pb2.EditLinkRequest(
            session=session, node_one=node_one, node_two=node_two, options=options,
            interface_one=interface_one, interface_two=interface_two)
        return self.stub.EditLink(request)

    def delete_link(self, session, node_one, node_two, interface_one=None, interface_two=None):
        request = core_pb2.DeleteLinkRequest(
            session=session, node_one=node_one, node_two=node_two,
            interface_one=interface_one, interface_two=interface_two)
        return self.stub.DeleteLink(request)

    def get_hooks(self, session):
        request = core_pb2.GetHooksRequest(session=session)
        return self.stub.GetHooks(request)

    def add_hook(self, session, state, file_name, file_data):
        hook = core_pb2.Hook(state=state.value, file=file_name, data=file_data)
        request = core_pb2.AddHookRequest(session=session, hook=hook)
        return self.stub.AddHook(request)

    def get_mobility_configs(self, session):
        request = core_pb2.GetMobilityConfigsRequest(session=session)
        return self.stub.GetMobilityConfigs(request)

    def get_mobility_config(self, session, _id):
        request = core_pb2.GetMobilityConfigRequest(session=session, id=_id)
        return self.stub.GetMobilityConfig(request)

    def set_mobility_config(self, session, _id, config):
        request = core_pb2.SetMobilityConfigRequest(session=session, id=_id, config=config)
        return self.stub.SetMobilityConfig(request)

    def mobility_action(self, session, _id, action):
        request = core_pb2.MobilityActionRequest(session=session, id=_id, action=action)
        return self.stub.MobilityAction(request)

    def get_services(self):
        request = core_pb2.GetServicesRequest()
        return self.stub.GetServices(request)

    def get_service_defaults(self, session):
        request = core_pb2.GetServiceDefaultsRequest(session=session)
        return self.stub.GetServiceDefaults(request)

    def set_service_defaults(self, session, service_defaults):
        defaults = []
        for node_type in service_defaults:
            services = service_defaults[node_type]
            default = core_pb2.ServiceDefaults(node_type=node_type, services=services)
            defaults.append(default)
        request = core_pb2.SetServiceDefaultsRequest(session=session, defaults=defaults)
        return self.stub.SetServiceDefaults(request)

    def get_node_service(self, session, _id, service):
        request = core_pb2.GetNodeServiceRequest(session=session, id=_id, service=service)
        return self.stub.GetNodeService(request)

    def get_node_service_file(self, session, _id, service, file_name):
        request = core_pb2.GetNodeServiceFileRequest(session=session, id=_id, service=service, file=file_name)
        return self.stub.GetNodeServiceFile(request)

    def set_node_service(self, session, _id, service, startup, validate, shutdown):
        request = core_pb2.SetNodeServiceRequest(
            session=session, id=_id, service=service, startup=startup, validate=validate, shutdown=shutdown)
        return self.stub.SetNodeService(request)

    def set_node_service_file(self, session, _id, service, file_name, data):
        request = core_pb2.SetNodeServiceFileRequest(
            session=session, id=_id, service=service, file=file_name, data=data)
        return self.stub.SetNodeServiceFile(request)

    def service_action(self, session, _id, service, action):
        request = core_pb2.ServiceActionRequest(session=session, id=_id, service=service, action=action)
        return self.stub.ServiceAction(request)

    def get_wlan_config(self, session, _id):
        request = core_pb2.GetWlanConfigRequest(session=session, id=_id)
        return self.stub.GetWlanConfig(request)

    def set_wlan_config(self, session, _id, config):
        request = core_pb2.SetWlanConfigRequest(session=session, id=_id, config=config)
        return self.stub.SetWlanConfig(request)

    def get_emane_config(self, session):
        request = core_pb2.GetEmaneConfigRequest(session=session)
        return self.stub.GetEmaneConfig(request)

    def set_emane_config(self, session, config):
        request = core_pb2.SetEmaneConfigRequest(session=session, config=config)
        return self.stub.SetEmaneConfig(request)

    def get_emane_models(self, session):
        request = core_pb2.GetEmaneModelsRequest(session=session)
        return self.stub.GetEmaneModels(request)

    def get_emane_model_config(self, session, _id, model, interface_id=None):
        if interface_id is not None:
            _id = _id * 1000 + interface_id
        request = core_pb2.GetEmaneModelConfigRequest(session=session, id=_id, model=model)
        return self.stub.GetEmaneModelConfig(request)

    def set_emane_model_config(self, session, _id, model, config, interface_id=None):
        if interface_id is not None:
            _id = _id * 1000 + interface_id
        request = core_pb2.SetEmaneModelConfigRequest(session=session, id=_id, model=model, config=config)
        return self.stub.SetEmaneModelConfig(request)

    def get_emane_model_configs(self, session):
        request = core_pb2.GetEmaneModelConfigsRequest(session=session)
        return self.stub.GetEmaneModelConfigs(request)

    def save_xml(self, session, file_path):
        request = core_pb2.SaveXmlRequest(session=session)
        response = self.stub.SaveXml(request)
        with open(file_path, "wb") as xml_file:
            xml_file.write(response.data)

    def open_xml(self, file_path):
        with open(file_path, "rb") as xml_file:
            data = xml_file.read()
        request = core_pb2.OpenXmlRequest(data=data)
        return self.stub.OpenXml(request)

    def connect(self):
        self.channel = grpc.insecure_channel(self.address)
        self.stub = core_pb2_grpc.CoreApiStub(self.channel)

    def close(self):
        if self.channel:
            self.channel.close()
            self.channel = None

    @contextmanager
    def context_connect(self):
        try:
            self.connect()
            yield
        finally:
            self.close()


def main():
    xml_file_name = "/tmp/core.xml"

    client = CoreGrpcClient()
    with client.context_connect():
        if os.path.exists(xml_file_name):
            response = client.open_xml(xml_file_name)
            print("open xml: {}".format(response))

        print("services: {}".format(client.get_services()))

        # create session
        session_data = client.create_session()
        client.exception_events(session_data.id, lambda x: print(x))
        client.node_events(session_data.id, lambda x: print(x))
        client.session_events(session_data.id, lambda x: print(x))
        client.link_events(session_data.id, lambda x: print(x))
        client.file_events(session_data.id, lambda x: print(x))
        client.config_events(session_data.id, lambda x: print(x))
        print("created session: {}".format(session_data))
        print("default services: {}".format(client.get_service_defaults(session_data.id)))
        print("emane models: {}".format(client.get_emane_models(session_data.id)))
        print("add hook: {}".format(client.add_hook(session_data.id, EventTypes.RUNTIME_STATE, "test", "echo hello")))
        print("hooks: {}".format(client.get_hooks(session_data.id)))

        response = client.get_sessions()
        print("core client received: {}".format(response))

        print("set emane config: {}".format(client.set_emane_config(session_data.id, {"otamanagerttl": "2"})))
        print("emane config: {}".format(client.get_emane_config(session_data.id)))

        # set session location
        response = client.set_session_location(
            session_data.id,
            x=0, y=0, z=None,
            lat=47.57917, lon=-122.13232, alt=3.0,
            scale=150000.0
        )
        print("set location response: {}".format(response))

        # get options
        print("get options: {}".format(client.get_session_options(session_data.id)))

        # get location
        print("get location: {}".format(client.get_session_location(session_data.id)))

        # change session state
        print("set session state: {}".format(client.set_session_state(session_data.id, EventTypes.CONFIGURATION_STATE)))

        # create switch node
        response = client.add_node(session_data.id, _type=NodeTypes.SWITCH)
        print("created switch: {}".format(response))
        switch_id = response.id

        # ip generator for example
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

        for _ in xrange(2):
            response = client.add_node(session_data.id)
            print("created node: {}".format(response))
            node_id = response.id
            node_options = NodeOptions()
            node_options.x = 5
            node_options.y = 5
            print("edit node: {}".format(client.edit_node(session_data.id, node_id, node_options)))
            print("get node: {}".format(client.get_node(session_data.id, node_id)))
            print("emane model config: {}".format(
                client.get_emane_model_config(session_data.id, node_id, "emane_tdma")))

            print("node service: {}".format(client.get_node_service(session_data.id, node_id, "zebra")))

            # create link
            interface_one = InterfaceData(
                _id=None, name=None, mac=None,
                ip4=str(prefixes.ip4.addr(node_id)), ip4_mask=prefixes.ip4.prefixlen,
                ip6=None, ip6_mask=None
            )
            print("created link: {}".format(client.add_link(session_data.id, node_id, switch_id, interface_one)))
            link_options = LinkOptions()
            link_options.per = 50
            print("edit link: {}".format(client.edit_link(
                session_data.id, node_id, switch_id, link_options, interface_one=0)))

            print("get node links: {}".format(client.get_node_links(session_data.id, node_id)))

        # change session state
        print("set session state: {}".format(client.set_session_state(session_data.id, EventTypes.INSTANTIATION_STATE)))
        # import pdb; pdb.set_trace()

        # get session
        print("get session: {}".format(client.get_session(session_data.id)))

        # save xml
        client.save_xml(session_data.id, xml_file_name)

        # delete session
        print("delete session: {}".format(client.delete_session(session_data.id)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
