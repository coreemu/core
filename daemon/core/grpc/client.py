from __future__ import print_function
import logging
from contextlib import contextmanager

import grpc

import core_pb2
import core_pb2_grpc
from core.emulator.emudata import NodeOptions
from core.enumerations import NodeTypes


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

    def set_session_location(self, _id, x=None, y=None , z=None, lat=None, lon=None, alt=None, scale=None):
        request = core_pb2.SetSessionLocationRequest()
        request.id = _id
        update_proto(request.position, x=x, y=y, z=z, lat=lat, lon=lon, alt=alt)
        update_proto(request, scale=scale)
        return self.stub.SetSessionLocation(request)

    def set_session_state(self, _id, state):
        request = core_pb2.SetSessionStateRequest()
        request.id = _id
        request.state = state
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
            print("set session state: %s" % client.set_session_state(session_data.id, core_pb2.INSTANTIATION))

            for i in xrange(2):
                response = client.create_node(session_data.id)
                print("created node: %s" % response)
                node_options = NodeOptions()
                node_options.x = 5
                node_options.y = 5
                print("edit node: %s" % client.edit_node(session_data.id, response.id, node_options))

            # get session
            print("get session: %s" % client.get_session(session_data.id))

            # delete session
            print("delete session: %s" % client.delete_session(session_data.id))


if __name__ == "__main__":
    logging.basicConfig()
    main()
