"""
Incorporate grpc into python tkinter GUI
"""
import logging

from core.api.grpc import client, core_pb2


class CoreGrpc:
    def __init__(self):
        """
        Create a CoreGrpc instance
        """
        self.core = client.CoreGrpcClient()
        self.session_id = None
        self.set_up()

    def log_event(self, event):
        logging.info("event: %s", event)

    def set_up(self):
        """
        Create session, handle events session may broadcast, change session state

        :return: nothing
        """
        self.core.connect()
        # create session
        response = self.core.create_session()
        logging.info("created session: %s", response)

        # handle events session may broadcast
        self.session_id = response.session_id
        self.core.events(self.session_id, self.log_event)

        # change session state
        response = self.core.set_session_state(
            self.session_id, core_pb2.SessionState.CONFIGURATION
        )
        logging.info("set session state: %s", response)

    def get_session_id(self):
        return self.session_id

    # TODO add checkings to the function
    def add_node(self, x, y, node_name):
        link_layer_nodes = ["switch", "hub", "wlan", "rj45", "tunnel"]
        network_layer_nodes = ["default"]
        node = None
        if node_name in link_layer_nodes:
            if node_name == "switch":
                node = core_pb2.Node(type=core_pb2.NodeType.SWITCH)
            elif node_name == "hub":
                node = core_pb2.Node(type=core_pb2.NodeType.HUB)
            elif node_name == "wlan":
                node = core_pb2.Node(type=core_pb2.NodeType.WIRELESS_LAN)
            elif node_name == "rj45":
                node = core_pb2.Node(type=core_pb2.NodeType.RJ45)
            elif node_name == "tunnel":
                node = core_pb2.Node(type=core_pb2.NodeType.TUNNEL)

        elif node_name in network_layer_nodes:
            position = core_pb2.Position(x=x, y=y)
            node = core_pb2.Node(position=position)
        else:
            return
        response = self.core.add_node(self.session_id, node)
        logging.info("created %s: %s", node_name, response)
        return response.node_id

    def edit_node(self, session_id, node_id, x, y):
        position = core_pb2.Position(x=x, y=y)
        response = self.core.edit_node(session_id, node_id, position)
        logging.info("updated node id %s: %s", node_id, response)

    def close(self):
        """
        Clean ups when done using grpc

        :return: nothing
        """
        logging.debug("Close grpc")
        self.core.close()
