import argparse
import logging

from core.api.grpc import client
from core.api.grpc.wrappers import NodeType, Position, Server


def log_event(event):
    logging.info("event: %s", event)


def main(args):
    # helper to create interfaces
    interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")

    # create grpc client and connect
    core = client.CoreGrpcClient()
    core.connect()

    # create session
    session = core.create_session()

    # add distributed server
    server = Server(name="core2", host=args.server)
    session.servers.append(server)

    # handle events session may broadcast
    core.events(session.id, log_event)

    # create switch node
    position = Position(x=150, y=100)
    switch = session.add_node(1, _type=NodeType.SWITCH, position=position)
    position = Position(x=100, y=50)
    node1 = session.add_node(2, position=position)
    position = Position(x=200, y=50)
    node2 = session.add_node(3, position=position, server=server.name)

    # create links
    iface1 = interface_helper.create_iface(node1.id, 0)
    session.add_link(node1=node1, node2=switch, iface1=iface1)
    iface1 = interface_helper.create_iface(node2.id, 0)
    session.add_link(node1=node2, node2=switch, iface1=iface1)

    # start session
    core.start_session(session)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Run distributed_switch example")
    parser.add_argument(
        "-a",
        "--address",
        required=True,
        help="local address that distributed servers will use for gre tunneling",
    )
    parser.add_argument(
        "-s",
        "--server",
        required=True,
        help="distributed server to use for creating nodes",
    )
    args = parser.parse_args()
    main(args)
