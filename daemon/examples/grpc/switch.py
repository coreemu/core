import logging
from builtins import range

from core.api.grpc import client, core_pb2


def log_event(event):
    logging.info("event: %s", event)


def main():
    core = client.CoreGrpcClient()

    with core.context_connect():
        # create session
        response = core.create_session()
        logging.info("created session: %s", response)

        # handle events session may broadcast
        session_id = response.session_id
        core.events(session_id, log_event)

        # change session state
        response = core.set_session_state(session_id, core_pb2.SessionState.CONFIGURATION)
        logging.info("set session state: %s", response)

        # create switch node
        switch = core_pb2.Node(type=core_pb2.NodeType.SWITCH)
        response = core.add_node(session_id, switch)
        logging.info("created switch: %s", response)
        switch_id = response.node_id

        # helper to create interfaces
        interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")

        for i in range(2):
            # create node
            position = core_pb2.Position(x=50 + 50 * i, y=50)
            node = core_pb2.Node(position=position)
            response = core.add_node(session_id, node)
            logging.info("created node: %s", response)
            node_id = response.node_id

            # create link
            interface_one = interface_helper.create_interface(node_id, 0)
            response = core.add_link(session_id, node_id, switch_id, interface_one)
            logging.info("created link: %s", response)

        # change session state
        response = core.set_session_state(session_id, core_pb2.SessionState.INSTANTIATION)
        logging.info("set session state: %s", response)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
