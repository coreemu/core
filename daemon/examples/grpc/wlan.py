"""
Example using gRPC API to create a simple wlan network.
"""

import logging

from core.api.grpc import client
from core.api.grpc.core_pb2 import Node, NodeType, Position, SessionState


def log_event(event):
    logging.info("event: %s", event)


def main():
    # helper to create interface addresses
    interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/24")

    # create grpc client and start connection context, which auto closes connection
    core = client.CoreGrpcClient()
    with core.context_connect():
        # create session
        response = core.create_session()
        logging.info("created session: %s", response)

        # handle events session may broadcast
        session_id = response.session_id
        core.events(session_id, log_event)

        # change session state to configuration so that nodes get started when added
        response = core.set_session_state(session_id, SessionState.CONFIGURATION)
        logging.info("set session state: %s", response)

        # create wlan node
        position = Position(x=200, y=200)
        wlan = Node(type=NodeType.WIRELESS_LAN, position=position)
        response = core.add_node(session_id, wlan)
        logging.info("created wlan: %s", response)
        wlan_id = response.node_id

        # change/configure wlan if desired
        # NOTE: error = loss, and named this way for legacy purposes for now
        config = {
            "bandwidth": "54000000",
            "range": "500",
            "jitter": "0",
            "delay": "5000",
            "error": "0",
        }
        response = core.set_wlan_config(session_id, wlan_id, config)
        logging.info("set wlan config: %s", response)

        # create node one
        position = Position(x=100, y=100)
        node1 = Node(type=NodeType.DEFAULT, position=position)
        response = core.add_node(session_id, node1)
        logging.info("created node: %s", response)
        node1_id = response.node_id

        # create node two
        position = Position(x=300, y=100)
        node2 = Node(type=NodeType.DEFAULT, position=position)
        response = core.add_node(session_id, node2)
        logging.info("created node: %s", response)
        node2_id = response.node_id

        # links nodes to switch
        interface1 = interface_helper.create_interface(node1_id, 0)
        response = core.add_link(session_id, node1_id, wlan_id, interface1)
        logging.info("created link: %s", response)
        interface1 = interface_helper.create_interface(node2_id, 0)
        response = core.add_link(session_id, node2_id, wlan_id, interface1)
        logging.info("created link: %s", response)

        # change session state
        response = core.set_session_state(session_id, SessionState.INSTANTIATION)
        logging.info("set session state: %s", response)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
