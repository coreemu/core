import logging

from core.api.grpc import client, core_pb2


def log_event(event):
    logging.info("event: %s", event)


def main():
    core = client.CoreGrpcClient()

    with core.context_connect():
        # create session
        response = core.create_session()
        session_id = response.session_id
        logging.info("created session: %s", response)

        # create nodes for session
        nodes = []
        position = core_pb2.Position(x=50, y=100)
        switch = core_pb2.Node(id=1, type=core_pb2.NodeType.SWITCH, position=position)
        nodes.append(switch)
        for i in range(2, 50):
            position = core_pb2.Position(x=50 + 50 * i, y=50)
            node = core_pb2.Node(id=i, position=position, model="PC")
            nodes.append(node)

        # create links
        interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")
        links = []
        for node in nodes:
            interface_one = interface_helper.create_interface(node.id, 0)
            link = core_pb2.Link(
                type=core_pb2.LinkType.WIRED,
                node_one_id=node.id,
                node_two_id=switch.id,
                interface_one=interface_one,
            )
            links.append(link)

        # start session
        response = core.start_session(session_id, nodes, links)
        logging.info("started session: %s", response)

        input("press enter to shutdown session")

        response = core.stop_session(session_id)
        logging.info("stop sessionL %s", response)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
