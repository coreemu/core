import argparse
import logging

from core.api.grpc import client
from core.api.grpc.core_pb2 import Node, NodeType, Position, SessionState


def log_event(event):
    logging.info("event: %s", event)


def main(args):
    core = client.CoreGrpcClient()

    with core.context_connect():
        # create session
        response = core.create_session()
        session_id = response.session_id
        logging.info("created session: %s", response)

        # add distributed server
        server_name = "core2"
        response = core.add_session_server(session_id, server_name, args.server)
        logging.info("added session server: %s", response)

        # handle events session may broadcast
        core.events(session_id, log_event)

        # change session state
        response = core.set_session_state(session_id, SessionState.CONFIGURATION)
        logging.info("set session state: %s", response)

        # create switch node
        switch = Node(type=NodeType.SWITCH)
        response = core.add_node(session_id, switch)
        logging.info("created switch: %s", response)
        switch_id = response.node_id

        # helper to create interfaces
        interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")

        # create node one
        position = Position(x=100, y=50)
        node = Node(position=position)
        response = core.add_node(session_id, node)
        logging.info("created node one: %s", response)
        node1_id = response.node_id

        # create link
        interface1 = interface_helper.create_interface(node1_id, 0)
        response = core.add_link(session_id, node1_id, switch_id, interface1)
        logging.info("created link from node one to switch: %s", response)

        # create node two
        position = Position(x=200, y=50)
        node = Node(position=position, server=server_name)
        response = core.add_node(session_id, node)
        logging.info("created node two: %s", response)
        node2_id = response.node_id

        # create link
        interface1 = interface_helper.create_interface(node2_id, 0)
        response = core.add_link(session_id, node2_id, switch_id, interface1)
        logging.info("created link from node two to switch: %s", response)

        # change session state
        response = core.set_session_state(session_id, SessionState.INSTANTIATION)
        logging.info("set session state: %s", response)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Run distributed_switch example")
    parser.add_argument(
        "-a",
        "--address",
        help="local address that distributed servers will use for gre tunneling",
    )
    parser.add_argument(
        "-s", "--server", help="distributed server to use for creating nodes"
    )
    args = parser.parse_args()
    main(args)
