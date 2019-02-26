from __future__ import print_function
import logging
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

    def create_session(self):
        return self.stub.CreateSession(core_pb2.CreateSessionRequest())

    def delete_session(self, _id):
        request = core_pb2.DeleteSessionRequest()
        request.id = _id
        return self.stub.DeleteSession(request)

    def get_sessions(self):
        return self.stub.GetSessions(core_pb2.SessionsRequest())

    def get_session(self, _id):
        request = core_pb2.SessionRequest()
        request.id = _id
        return self.stub.GetSession(request)

    def get_session_options(self, _id):
        request = core_pb2.SessionOptionsRequest()
        request.id = _id
        return self.stub.GetSessionOptions(request)

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

    @contextmanager
    def connect(self):
        channel = grpc.insecure_channel(self.address)
        try:
            self.stub = core_pb2_grpc.CoreApiStub(channel)
            yield channel
        finally:
            channel.close()


def main():
    client = CoreApiClient()
    with client.connect():
        # create session
        response = client.create_session()
        print("created session: %s" % response)

        response = client.get_sessions()
        print("core client received: %s" % response)

        if len(response.sessions) > 0:
            session_data = response.sessions[0]

            # set session location
            response = client.set_session_location(
                session_data.id,
                x=0, y=0, z=None,
                lat=47.57917, lon=-122.13232, alt=3.0,
                scale=150000.0
            )
            print("set location response: %s" % response)

            # get options
            print("get options: %s" % client.get_session_options(session_data.id))

            # get location
            print("get location: %s" % client.get_session_location(session_data.id))

            # change session state
            print("set session state: %s" % client.set_session_state(session_data.id, EventTypes.CONFIGURATION_STATE))

            # create switch node
            response = client.create_node(session_data.id, _type=NodeTypes.SWITCH)
            print("created switch: %s" % response)
            switch_id = response.id

            # ip generator for example
            prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

            for i in xrange(2):
                response = client.create_node(session_data.id)
                print("created node: %s" % response)
                node_id = response.id
                node_options = NodeOptions()
                node_options.x = 5
                node_options.y = 5
                print("edit node: %s" % client.edit_node(session_data.id, node_id, node_options))
                print("get node: %s" % client.get_node(session_data.id, node_id))

                # create link
                interface_one = InterfaceData(
                    _id=None, name=None, mac=None,
                    ip4=str(prefixes.ip4.addr(node_id)), ip4_mask=prefixes.ip4.prefixlen,
                    ip6=None, ip6_mask=None
                )
                print("created link: %s" % client.create_link(session_data.id, node_id, switch_id, interface_one))
                link_options = LinkOptions()
                link_options.per = 50
                print("edit link: %s" % client.edit_link(
                    session_data.id, node_id, switch_id, link_options, interface_one=0))

            # change session state
            print("set session state: %s" % client.set_session_state(session_data.id, EventTypes.INSTANTIATION_STATE))

            # get session
            print("get session: %s" % client.get_session(session_data.id))

            # delete session
            print("delete session: %s" % client.delete_session(session_data.id))


if __name__ == "__main__":
    logging.basicConfig()
    main()
