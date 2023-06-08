import time

from core.api.grpc import client
from core.api.grpc.wrappers import Position


def main():
    # create grpc client and connect
    core = client.CoreGrpcClient("172.16.0.254:50051")
    core.connect()

    # get session
    sessions = core.get_sessions()

    print("sessions=", sessions)
    for i in range(300):
        position = Position(x=100, y=100 + i)
        core.move_node(sessions[0].id, 2, position=position)
        time.sleep(1)
    print("press enter to quit")
    input()


if __name__ == "__main__":
    main()
