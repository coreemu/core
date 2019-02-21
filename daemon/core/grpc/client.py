from __future__ import print_function
import logging
from contextlib import contextmanager

import grpc

import core_pb2
import core_pb2_grpc


class CoreApiClient(object):
    def __init__(self, address="localhost:50051"):
        self.address = address
        self.stub = None

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
        request = core_pb2.SessionLocationRequest()
        request.id = _id
        return self.stub.GetSessionLocation(request)

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
        response = client.get_sessions()
        print("core client received: %s" % response)

        if len(response.sessions) > 0:
            session_data = response.sessions[0]
            session = client.get_session(session_data.id)
            print(session)

            print(client.get_session_options(session_data.id))
            print(client.get_session_location(session_data.id))


if __name__ == "__main__":
    logging.basicConfig()
    main()
