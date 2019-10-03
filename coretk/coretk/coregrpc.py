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
        self.interface_helper = None

    def log_event(self, event):
        logging.info("event: %s", event)

    def redraw_canvas(self):
        return

    def create_new_session(self):
        """
        Create a new session

        :return: nothing
        """
        response = self.core.create_session()
        logging.info("created session: %s", response)

        # handle events session may broadcast
        self.session_id = response.session_id
        self.core.events(self.session_id, self.log_event)

    def query_existing_sessions(self, sessions):
        """
        Query for existing sessions and prompt to join one

        :param repeated core_pb2.SessionSummary sessions: summaries of all the existing sessions

        :return: nothing
        """
        for session in sessions:
            logging.info("Session id: %s, Session state: %s", session.id, session.state)
        logging.info("Input a session you want to enter from the keyboard:")
        usr_input = int(input())
        if usr_input == 0:
            self.create_new_session()
        else:
            response = self.core.get_session(usr_input)
            self.session_id = usr_input
            # self.core.events(self.session_id, self.log_event)
            logging.info("Entering session_id %s.... Result: %s", usr_input, response)

    def set_up(self):
        """
        Query sessions, if there exist any, promt whether to join one

        :return: nothing
        """
        self.core.connect()

        response = self.core.get_sessions()
        logging.info("all sessions: %s", response)

        # if there are no sessions, create a new session, else join a session
        sessions = response.sessions

        if len(sessions) == 0:
            self.create_new_session()
        else:
            # self.create_new_session()
            self.query_existing_sessions(sessions)

    def set_configuration_state(self):
        response = self.core.set_session_state(
            self.session_id, core_pb2.SessionState.CONFIGURATION
        )
        logging.info("set session state: %s", response)

    def set_instantiate_state(self):
        response = self.core.set_session_state(
            self.session_id, core_pb2.SessionState.INSTANTIATION
        )
        logging.info("set session state: %s", response)

    def get_session_id(self):
        return self.session_id

    def add_node(self, node_type, model, x, y, name):
        logging.info("ADD NODE %s", name)
        position = core_pb2.Position(x=x, y=y)
        node = core_pb2.Node(type=node_type, position=position, model=model, image=name)
        response = self.core.add_node(self.session_id, node)
        logging.info("created node: %s", response)
        return response.node_id

    def edit_node(self, session_id, node_id, x, y):
        position = core_pb2.Position(x=x, y=y)
        response = self.core.edit_node(session_id, node_id, position)
        logging.info("updated node id %s: %s", node_id, response)

    # def create_interface_helper(self):
    #     self.interface_helper = self.core.InterfaceHelper(ip4_prefix="10.83.0.0/16")

    # TODO case for other core_pb2.NodeType
    def add_link(self, id1, id2, type1, type2):
        """
        Grpc client request add link

        :param int session_id: session id
        :param int id1: node 1 core id
        :param core_pb2.NodeType type1: node 1 core node type
        :param int id2: node 2 core id
        :param core_pb2.NodeType type2: node 2 core node type
        :return: nothing
        """
        if not self.interface_helper:
            logging.debug("INTERFACE HELPER NOT CREATED YET, CREATING ONE...")
            self.interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")

        interface1 = None
        interface2 = None
        if type1 == core_pb2.NodeType.DEFAULT:
            interface1 = self.interface_helper.create_interface(id1, 0)
        if type2 == core_pb2.NodeType.DEFAULT:
            interface2 = self.interface_helper.create_interface(id2, 0)
        response = self.core.add_link(self.session_id, id1, id2, interface1, interface2)
        logging.info("created link: %s", response)

    def close(self):
        """
        Clean ups when done using grpc

        :return: nothing
        """
        logging.debug("Close grpc")
        self.core.close()
