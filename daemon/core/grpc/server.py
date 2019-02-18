from concurrent import futures
import time
import logging

import grpc

import core_pb2
import core_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


class CoreApiServer(core_pb2_grpc.CoreApiServicer):

    def GetSessions(self, request, context):
        response = core_pb2.SessionsResponse()
        session = response.sessions.add()
        session.id = 1
        return response


def main():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    core_pb2_grpc.add_CoreApiServicer_to_server(CoreApiServer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()

    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    logging.basicConfig()
    main()
