import logging
from builtins import range

from core.api.grpc import client, core_pb2


def log_event(event):
    logging.info("event: %s", event)


def main():
    core = client.CoreGrpcClient()

    with core.context_connect():
        # create session
        session = core.create_session()
        logging.info("created session: %s", session)

        # handle events session may broadcast
        core.exception_events(session.id, log_event)
        core.node_events(session.id, log_event)
        core.session_events(session.id, log_event)
        core.link_events(session.id, log_event)
        core.file_events(session.id, log_event)
        core.config_events(session.id, log_event)

        # change session state
        response = core.set_session_state(session.id, core_pb2.STATE_CONFIGURATION)
        logging.info("set session state: %s", response)

        # create switch node
        switch = core_pb2.Node(type=core_pb2.NODE_SWITCH)
        response = core.add_node(session.id, switch)
        logging.info("created switch: %s", response)
        switch_id = response.id

        # helper to create interfaces
        interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")

        for i in range(2):
            # create node
            position = core_pb2.Position(x=50 + 50 * i, y=50)
            node = core_pb2.Node(position=position)
            response = core.add_node(session.id, node)
            logging.info("created node: %s", response)
            node_id = response.id

            # create link
            interface_one = interface_helper.create_interface(node_id, 0)
            response = core.add_link(session.id, node_id, switch_id, interface_one)
            logging.info("created link: %s", response)

        # change session state
        response = core.set_session_state(session.id, core_pb2.STATE_INSTANTIATION)
        logging.info("set session state: %s", response)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
