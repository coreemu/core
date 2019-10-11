"""
Incorporate grpc into python tkinter GUI
"""
import logging
import os
import tkinter as tk

from core.api.grpc import client, core_pb2


class CoreGrpc:
    def __init__(self, master):
        """
        Create a CoreGrpc instance
        """
        print("Create grpc instance")
        self.core = client.CoreGrpcClient()
        self.session_id = None
        self.master = master

        # self.set_up()
        self.interface_helper = None

    def log_event(self, event):
        logging.info("event: %s", event)

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

    def _enter_session(self, session_id, dialog):
        """
        enter an existing session

        :return:
        """
        dialog.destroy()
        response = self.core.get_session(session_id)
        self.session_id = session_id
        print("set session id: %s", session_id)
        logging.info("Entering session_id %s.... Result: %s", session_id, response)
        # self.master.canvas.draw_existing_component()

    def _create_session(self, dialog):
        """
        create a new session

        :param tkinter.Toplevel dialog: save core session prompt dialog
        :return: nothing
        """
        dialog.destroy()
        self.create_new_session()

    def query_existing_sessions(self, sessions):
        """
        Query for existing sessions and prompt to join one

        :param repeated core_pb2.SessionSummary sessions: summaries of all the existing sessions

        :return: nothing
        """
        dialog = tk.Toplevel()
        dialog.title("CORE sessions")
        for session in sessions:
            b = tk.Button(
                dialog,
                text="Session " + str(session.id),
                command=lambda sid=session.id: self._enter_session(sid, dialog),
            )
            b.pack(side=tk.TOP)
        b = tk.Button(
            dialog, text="create new", command=lambda: self._create_session(dialog)
        )
        b.pack(side=tk.TOP)
        dialog.update()
        x = (
            self.master.winfo_x()
            + (self.master.winfo_width() - dialog.winfo_width()) / 2
        )
        y = (
            self.master.winfo_y()
            + (self.master.winfo_height() / 2 - dialog.winfo_height()) / 2
        )
        dialog.geometry(f"+{int(x)}+{int(y)}")
        dialog.wait_window()

    def delete_session(self):
        response = self.core.delete_session(self.session_id)
        logging.info("Deleted session result: %s", response)

    def set_up(self):
        """
        Query sessions, if there exist any, prompt whether to join one

        :return: existing sessions
        """
        self.core.connect()

        response = self.core.get_sessions()
        logging.info("all sessions: %s", response)

        # if there are no sessions, create a new session, else join a session
        sessions = response.sessions

        if len(sessions) == 0:
            self.create_new_session()
        else:

            self.query_existing_sessions(sessions)

    def get_session_state(self):
        response = self.core.get_session(self.session_id)
        logging.info("get session: %s", response)
        return response.session.state

    def set_session_state(self, state):
        """
        Set session state

        :param str state: session state to set
        :return: nothing
        """
        response = None
        if state == "configuration":
            response = self.core.set_session_state(
                self.session_id, core_pb2.SessionState.CONFIGURATION
            )
        elif state == "instantiation":
            response = self.core.set_session_state(
                self.session_id, core_pb2.SessionState.INSTANTIATION
            )
        elif state == "datacollect":
            response = self.core.set_session_state(
                self.session_id, core_pb2.SessionState.DATACOLLECT
            )
        elif state == "shutdown":
            response = self.core.set_session_state(
                self.session_id, core_pb2.SessionState.SHUTDOWN
            )
        elif state == "runtime":
            response = self.core.set_session_state(
                self.session_id, core_pb2.SessionState.RUNTIME
            )
        elif state == "definition":
            response = self.core.set_session_state(
                self.session_id, core_pb2.SessionState.DEFINITION
            )
        elif state == "none":
            response = self.core.set_session_state(
                self.session_id, core_pb2.SessionState.NONE
            )
        else:
            logging.error("coregrpc.py: set_session_state: INVALID STATE")

        logging.info("set session state: %s", response)

    def add_node(self, node_type, model, x, y, name, node_id):
        logging.info("coregrpc.py ADD NODE %s", name)
        position = core_pb2.Position(x=x, y=y)
        node = core_pb2.Node(id=node_id, type=node_type, position=position, model=model)
        response = self.core.add_node(self.session_id, node)
        logging.info("created node: %s", response)
        return response.node_id

    def edit_node(self, node_id, x, y):
        position = core_pb2.Position(x=x, y=y)
        response = self.core.edit_node(self.session_id, node_id, position)
        logging.info("updated node id %s: %s", node_id, response)

    def delete_nodes(self):
        for node in self.core.get_session(self.session_id).session.nodes:
            response = self.core.delete_node(self.session_id, node.id)
            logging.info("delete node %s", response)

    def delete_links(self):
        for link in self.core.get_session(self.session_id).session.links:
            response = self.core.delete_link(
                self.session_id,
                link.node_one_id,
                link.node_two_id,
                link.interface_one.id,
                link.interface_two.id,
            )
            logging.info("delete link %s", response)

    def add_link(self, id1, id2, type1, type2, edge):
        """
        Grpc client request add link

        :param int session_id: session id
        :param int id1: node 1 core id
        :param core_pb2.NodeType type1: node 1 core node type
        :param int id2: node 2 core id
        :param core_pb2.NodeType type2: node 2 core node type
        :return: nothing
        """
        if1 = None
        if2 = None
        if type1 == core_pb2.NodeType.DEFAULT:
            interface = edge.interface_1
            if1 = core_pb2.Interface(
                id=interface.id,
                name=interface.name,
                mac=interface.mac,
                ip4=interface.ipv4,
                ip4mask=interface.ip4prefix,
            )
            # if1 = core_pb2.Interface(id=id1, name=edge.interface_1.name, ip4=edge.interface_1.ipv4, ip4mask=edge.interface_1.ip4prefix)
            logging.debug("create interface 1 %s", if1)
            # interface1 = self.interface_helper.create_interface(id1, 0)

        if type2 == core_pb2.NodeType.DEFAULT:
            interface = edge.interface_2
            if2 = core_pb2.Interface(
                id=interface.id,
                name=interface.name,
                mac=interface.mac,
                ip4=interface.ipv4,
                ip4mask=interface.ip4prefix,
            )
            # if2 = core_pb2.Interface(id=id2, name=edge.interface_2.name, ip4=edge.interface_2.ipv4, ip4mask=edge.interface_2.ip4prefix)
            logging.debug("create interface 2: %s", if2)
            # interface2 = self.interface_helper.create_interface(id2, 0)

        # response = self.core.add_link(self.session_id, id1, id2, interface1, interface2)
        response = self.core.add_link(self.session_id, id1, id2, if1, if2)
        logging.info("created link: %s", response)

    def launch_terminal(self, node_id):
        response = self.core.get_node_terminal(self.session_id, node_id)
        logging.info("get terminal %s", response.terminal)
        os.system("xterm -e %s &" % response.terminal)

    def save_xml(self, file_path):
        """
        Save core session as to an xml file

        :param str file_path: file path that user pick
        :return: nothing
        """
        response = self.core.save_xml(self.session_id, file_path)
        logging.info("coregrpc.py save xml %s", response)

    def open_xml(self, file_path):
        """
        Open core xml

        :param str file_path: file to open
        :return: session id
        """
        response = self.core.open_xml(file_path)
        return response.session_id
        # logging.info("coregrpc.py open_xml()", type(response))

    def close(self):
        """
        Clean ups when done using grpc

        :return: nothing
        """
        logging.debug("Close grpc")
        self.core.close()
