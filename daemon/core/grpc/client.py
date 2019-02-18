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


if __name__ == "__main__":
    logging.basicConfig()
    main()
