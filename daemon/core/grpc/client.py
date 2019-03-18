from __future__ import print_function
import logging
import os
import threading
from contextlib import contextmanager

import grpc

import core_pb2
import core_pb2_grpc
from core.emulator.emudata import NodeOptions, IpPrefixes, InterfaceData, LinkOptions
from core.enumerations import NodeTypes, LinkTypes, EventTypes


def update_proto(obj, **kwargs):
    for key in kwargs:
        value = kwargs[key]
        if value is not None:
            logging.info("setting proto key(%s) value(%s)", key, value)
            setattr(obj, key, value)


class CoreApiClient(object):
    def __init__(self, address="localhost:50051"):
        self.address = address
        self.stub = None
        self.channel = None

    def create_session(self):
        return self.stub.CreateSession(core_pb2.CreateSessionRequest())

    def delete_session(self, _id):
        request = core_pb2.DeleteSessionRequest()
        request.id = _id
        return self.stub.DeleteSession(request)

    def get_sessions(self):
        return self.stub.GetSessions(core_pb2.GetSessionsRequest())

    def get_session(self, _id):
        request = core_pb2.GetSessionRequest()
        request.id = _id
        return self.stub.GetSession(request)

    def get_session_options(self, _id):
        request = core_pb2.GetSessionOptionsRequest()
        request.id = _id
        return self.stub.GetSessionOptions(request)

    def set_session_options(self, _id, config):
        request = core_pb2.SetSessionOptionsRequest()
        request.id = _id
        request.config.update(config)
        return self.stub.SetSessionOptions(request)

    def get_session_location(self, _id):
        request = core_pb2.GetSessionLocationRequest()
        request.id = _id
        return self.stub.GetSessionLocation(request)

    def set_session_location(self, _id, x=None, y=None, z=None, lat=None, lon=None, alt=None, scale=None):
        request = core_pb2.SetSessionLocationRequest()
        request.id = _id
        update_proto(request.position, x=x, y=y, z=z, lat=lat, lon=lon, alt=alt)
        update_proto(request, scale=scale)
        return self.stub.SetSessionLocation(request)

    def set_session_state(self, _id, state):
        request = core_pb2.SetSessionStateRequest()
        request.id = _id
        request.state = state.value
        return self.stub.SetSessionState(request)

    def node_events(self, _id, handler):
        request = core_pb2.NodeEventsRequest()
        request.id = _id

        def listen():
            for event in self.stub.NodeEvents(request):
                handler(event)

        thread = threading.Thread(target=listen)
        thread.daemon = True
        thread.start()

    def session_events(self, _id, handler):
        request = core_pb2.SessionEventsRequest()
        request.id = _id

        def listen():
            for event in self.stub.SessionEvents(request):
                handler(event)

        thread = threading.Thread(target=listen)
        thread.daemon = True
        thread.start()

    def config_events(self, _id, handler):
        request = core_pb2.ConfigEventsRequest()
        request.id = _id

        def listen():
            for event in self.stub.ConfigEvents(request):
                handler(event)

        thread = threading.Thread(target=listen)
        thread.daemon = True
        thread.start()

    def exception_events(self, _id, handler):
        request = core_pb2.ExceptionEventsRequest()
        request.id = _id

        def listen():
            for event in self.stub.ExceptionEvents(request):
                handler(event)

        thread = threading.Thread(target=listen)
        thread.daemon = True
        thread.start()

    def file_events(self, _id, handler):
        request = core_pb2.FileEventsRequest()
        request.id = _id

        def listen():
            for event in self.stub.FileEvents(request):
                handler(event)

        thread = threading.Thread(target=listen)
        thread.daemon = True
        thread.start()

    def create_node(self, session, _type=NodeTypes.DEFAULT, _id=None, node_options=None, emane=None):
        if not node_options:
            node_options = NodeOptions()

        request = core_pb2.CreateNodeRequest()
        request.session = session
        request.type = _type.value
        update_proto(
            request,
            id=_id,
            name=node_options.name,
            model=node_options.model,
            icon=node_options.icon,
            opaque=node_options.opaque,
            emane=emane
        )
        update_proto(
            request.position,
            x=node_options.x,
            y=node_options.y,
            lat=node_options.lat,
            lon=node_options.lon,
            alt=node_options.alt
        )
        request.services.extend(node_options.services)
        return self.stub.CreateNode(request)

    def get_node(self, session, _id):
        request = core_pb2.GetNodeRequest()
        request.session = session
        request.id = _id
        return self.stub.GetNode(request)

    def edit_node(self, session, _id, node_options):
        request = core_pb2.EditNodeRequest()
        request.session = session
        request.id = _id
        update_proto(
            request.position,
            x=node_options.x,
            y=node_options.y,
            lat=node_options.lat,
            lon=node_options.lon,
            alt=node_options.alt
        )
        return self.stub.EditNode(request)

    def delete_node(self, session, _id):
        request = core_pb2.DeleteNodeRequest()
        request.session = session
        request.id = _id
        return self.stub.DeleteNode(request)

    def get_node_links(self, session, _id):
        request = core_pb2.GetNodeLinksRequest()
        request.session = session
        request.id = _id
        return self.stub.GetNodeLinks(request)

    def create_link(self, session, node_one, node_two, interface_one=None, interface_two=None, link_options=None):
        request = core_pb2.CreateLinkRequest()
        request.session = session
        update_proto(
            request.link,
            node_one=node_one,
            node_two=node_two,
            type=LinkTypes.WIRED.value
        )

        if interface_one is not None:
            update_proto(
                request.link.interface_one,
                id=interface_one.id,
                name=interface_one.name,
                mac=interface_one.mac,
                ip4=interface_one.ip4,
                ip4mask=interface_one.ip4_mask,
                ip6=interface_one.ip6,
                ip6mask=interface_one.ip6_mask
            )

        if interface_two is not None:
            update_proto(
                request.link.interface_two,
                id=interface_two.id,
                name=interface_two.name,
                mac=interface_two.mac,
                ip4=interface_two.ip4,
                ip4mask=interface_two.ip4_mask,
                ip6=interface_two.ip6,
                ip6mask=interface_two.ip6_mask
            )

        if link_options is not None:
            update_proto(
                request.link.options,
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

        return self.stub.CreateLink(request)

    def edit_link(self, session, node_one, node_two, link_options, interface_one=None, interface_two=None):
        request = core_pb2.EditLinkRequest()
        request.session = session
        request.node_one = node_one
        request.node_two = node_two
        update_proto(
            request,
            interface_one=interface_one,
            interface_two=interface_two
        )
        update_proto(
            request.options,
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
        return self.stub.EditLink(request)

    def delete_link(self, session, node_one, node_two, interface_one=None, interface_two=None):
        request = core_pb2.DeleteLinkRequest()
        request.session = session
        request.node_one = node_one
        request.node_two = node_two
        update_proto(
            request,
            interface_one=interface_one,
            interface_two=interface_two
        )
        return self.stub.DeleteLink(request)

    def get_hooks(self, session):
        request = core_pb2.GetHooksRequest()
        request.session = session
        return self.stub.GetHooks(request)

    def add_hook(self, session, state, file_name, file_data):
        request = core_pb2.AddHookRequest()
        request.session = session
        request.hook.state = state.value
        request.hook.file = file_name
        request.hook.data = file_data
        return self.stub.AddHook(request)

    def get_mobility_configs(self, session):
        request = core_pb2.GetMobilityConfigsRequest()
        request.session = session
        return self.stub.GetMobilityConfigs(request)

    def get_mobility_config(self, session, _id):
        request = core_pb2.GetMobilityConfigRequest()
        request.session = session
        request.id = _id
        return self.stub.GetMobilityConfig(request)

    def set_mobility_config(self, session, _id, config):
        request = core_pb2.SetMobilityConfigRequest()
        request.session = session
        request.id = _id
        request.config.update(config)
        return self.stub.SetMobilityConfig(request)

    def mobility_action(self, session, _id, action):
        request = core_pb2.MobilityActionRequest()
        request.session = session
        request.id = _id
        request.action = action
        return self.stub.MobilityAction(request)

    def get_services(self):
        request = core_pb2.GetServicesRequest()
        return self.stub.GetServices(request)

    def get_service_defaults(self, session):
        request = core_pb2.GetServiceDefaultsRequest()
        request.session = session
        return self.stub.GetServiceDefaults(request)

    def set_service_defaults(self, session, service_defaults):
        request = core_pb2.SetServiceDefaultsRequest()
        request.session = session
        for node_type in service_defaults:
            services = service_defaults[node_type]
            service_defaults_proto = request.defaults.add()
            service_defaults_proto.node_type = node_type
            service_defaults_proto.services.extend(services)

        return self.stub.SetServiceDefaults(request)

    def get_node_service(self, session, _id, service):
        request = core_pb2.GetNodeServiceRequest()
        request.session = session
        request.id = _id
        request.service = service
        return self.stub.GetNodeService(request)

    def get_node_service_file(self, session, _id, service, file_name):
        request = core_pb2.GetNodeServiceFileRequest()
        request.session = session
        request.id = _id
        request.service = service
        request.file = file_name
        return self.stub.GetNodeServiceFile(request)

    def set_node_service(self, session, _id, service, startup, validate, shutdown):
        request = core_pb2.SetNodeServiceRequest()
        request.session = session
        request.id = _id
        request.service = service
        request.startup.extend(startup)
        request.validate.extend(validate)
        request.shutdown.extend(shutdown)
        return self.stub.SetNodeService(request)

    def set_node_service_file(self, session, _id, service, file_name, data):
        request = core_pb2.SetNodeServiceFileRequest()
        request.session = session
        request.id = _id
        request.service = service
        request.file = file_name
        request.data = data
        return self.stub.SetNodeServiceFile(request)

    def service_action(self, session, _id, service, action):
        request = core_pb2.ServiceActionRequest()
        request.session = session
        request.id = _id
        request.service = service
        request.action = action
        return self.stub.ServiceAction(request)

    def get_wlan_config(self, session, _id):
        request = core_pb2.GetWlanConfigRequest()
        request.session = session
        request.id = _id
        return self.stub.GetWlanConfig(request)

    def set_wlan_config(self, session, _id, config):
        request = core_pb2.SetWlanConfigRequest()
        request.session = session
        request.id = _id
        request.config.update(config)
        return self.stub.SetWlanConfig(request)

    def get_emane_config(self, session):
        request = core_pb2.GetEmaneConfigRequest()
        request.session = session
        return self.stub.GetEmaneConfig(request)

    def set_emane_config(self, session, config):
        request = core_pb2.SetEmaneConfigRequest()
        request.session = session
        request.config.update(config)
        return self.stub.SetEmaneConfig(request)

    def get_emane_models(self, session):
        request = core_pb2.GetEmaneModelsRequest()
        request.session = session
        return self.stub.GetEmaneModels(request)

    def get_emane_model_config(self, session, _id, model, interface_id=None):
        request = core_pb2.GetEmaneModelConfigRequest()
        request.session = session
        if interface_id is not None:
            _id = _id * 1000 + interface_id
        request.id = _id
        request.model = model
        return self.stub.GetEmaneModelConfig(request)

    def set_emane_model_config(self, session, _id, model, config, interface_id=None):
        request = core_pb2.SetEmaneModelConfigRequest()
        request.session = session
        if interface_id is not None:
            _id = _id * 1000 + interface_id
        request.id = _id
        request.model = model
        request.config.update(config)
        return self.stub.SetEmaneModelConfig(request)

    def get_emane_model_configs(self, session):
        request = core_pb2.GetEmaneModelConfigsRequest()
        request.session = session
        return self.stub.GetEmaneModelConfigs(request)

    def save_xml(self, session, file_path):
        request = core_pb2.SaveXmlRequest()
        request.session = session
        response = self.stub.SaveXml(request)
        with open(file_path, "wb") as xml_file:
            xml_file.write(response.data)

    def open_xml(self, file_path):
        with open(file_path, "rb") as xml_file:
            data = xml_file.read()

        request = core_pb2.OpenXmlRequest()
        request.data = data
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

    client = CoreApiClient()
    with client.context_connect():
        if os.path.exists(xml_file_name):
            response = client.open_xml(xml_file_name)
            print("open xml: {}".format(response))

        print("services: {}".format(client.get_services()))

        # create session
        session_data = client.create_session()
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
        response = client.create_node(session_data.id, _type=NodeTypes.SWITCH)
        print("created switch: {}".format(response))
        switch_id = response.id

        # ip generator for example
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

        for i in xrange(2):
            response = client.create_node(session_data.id)
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
            print("created link: {}".format(client.create_link(session_data.id, node_id, switch_id, interface_one)))
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
    logging.basicConfig()
    main()
