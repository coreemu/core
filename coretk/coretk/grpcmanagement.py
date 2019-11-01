"""
Manage useful informations about the nodes, edges and configuration
that can be useful for grpc, acts like a session class
"""
import logging

from core.api.grpc import core_pb2
from coretk.coretocanvas import CoreToCanvasMapping
from coretk.interface import Interface, InterfaceManager
from coretk.wlannodeconfig import WlanNodeConfig

link_layer_nodes = ["switch", "hub", "wlan", "rj45", "tunnel"]
network_layer_nodes = ["router", "host", "PC", "mdr", "prouter", "OVS"]


class Node:
    def __init__(self, session_id, node_id, node_type, model, x, y, name):
        """
        Create an instance of a node

        :param int session_id: session id
        :param int node_id: node id
        :param core_pb2.NodeType node_type: node type
        :param int x: x coordinate
        :param int y: coordinate
        :param str name: node name
        """
        self.session_id = session_id
        self.node_id = node_id
        self.type = node_type
        self.x = x
        self.y = y
        self.model = model
        self.name = name
        self.interfaces = []


class Edge:
    def __init__(self, session_id, node_id_1, node_type_1, node_id_2, node_type_2):
        """
        Create an instance of an edge
        :param int session_id: session id
        :param int node_id_1: node 1 id
        :param int node_type_1: node 1 type
        :param core_pb2.NodeType node_id_2: node 2 id
        :param core_pb2.NodeType node_type_2: node 2 type
        """
        self.session_id = session_id
        self.id1 = node_id_1
        self.id2 = node_id_2
        self.type1 = node_type_1
        self.type2 = node_type_2
        self.interface_1 = None
        self.interface_2 = None


class GrpcManager:
    def __init__(self, grpc):
        self.nodes = {}
        self.edges = {}
        self.id = 1
        # A list of id for re-use, keep in increasing order
        self.reusable = []
        self.preexisting = set()
        self.core_grpc = grpc
        # self.update_preexisting_ids()
        # self.core_id_to_canvas_id = {}
        self.interfaces_manager = InterfaceManager()
        # map tuple(core_node_id, interface_id) to and edge
        # self.node_id_and_interface_to_edge_token = {}
        self.core_mapping = CoreToCanvasMapping()
        self.wlanconfig_management = WlanNodeConfig()

    def update_preexisting_ids(self):
        """
        get preexisting node ids
        :return:
        """
        max_id = 0
        client = self.core_grpc.core
        sessions = client.get_sessions().sessions
        for session_summary in sessions:
            session = client.get_session(session_summary.id).session
            for node in session.nodes:
                if node.id > max_id:
                    max_id = node.id
                self.preexisting.append(node.id)
        self.id = max_id + 1
        self.update_reusable_id()

    def peek_id(self):
        """
        Peek the next id to be used

        :return: nothing
        """
        if len(self.reusable) == 0:
            return self.id
        else:
            return self.reusable[0]

    def get_id(self):
        """
        Get the next node id as well as update id status and reusable ids

        :rtype: int
        :return: the next id to be used
        """
        if len(self.reusable) == 0:
            new_id = self.id
            self.id = self.id + 1
            return new_id
        else:
            return self.reusable.pop(0)

    def add_node(self, session_id, canvas_id, x, y, name):
        """
        Add node, with information filled in, to grpc manager

        :param int session_id: session id
        :param int canvas_id: node's canvas id
        :param int x: x coord
        :param int y: y coord
        :param str name: node type
        :return: nothing
        """
        node_type = None
        node_model = None
        if name in link_layer_nodes:
            if name == "switch":
                node_type = core_pb2.NodeType.SWITCH
            elif name == "hub":
                node_type = core_pb2.NodeType.HUB
            elif name == "wlan":
                node_type = core_pb2.NodeType.WIRELESS_LAN
            elif name == "rj45":
                node_type = core_pb2.NodeType.RJ45
            elif name == "tunnel":
                node_type = core_pb2.NodeType.TUNNEL
        elif name in network_layer_nodes:
            node_type = core_pb2.NodeType.DEFAULT
            node_model = name
        else:
            logging.error("grpcmanagemeny.py INVALID node name")
        nid = self.get_id()
        create_node = Node(session_id, nid, node_type, node_model, x, y, name)

        # set default configuration for wireless node
        self.wlanconfig_management.set_default_config(node_type, nid)

        self.nodes[canvas_id] = create_node
        self.core_mapping.map_core_id_to_canvas_id(nid, canvas_id)
        # self.core_id_to_canvas_id[nid] = canvas_id
        logging.debug(
            "Adding node to GrpcManager.. Session id: %s, Coords: (%s, %s), Name: %s",
            session_id,
            x,
            y,
            name,
        )

    def add_preexisting_node(self, canvas_node, session_id, core_node, name):
        """
        Add preexisting nodes to grpc manager

        :param str name: node_type
        :param core_pb2.Node core_node: core node grpc message
        :param coretk.graph.CanvasNode canvas_node: canvas node
        :param int session_id: session id
        :return: nothing
        """

        # update the next available id
        core_id = core_node.id
        if self.id is None or core_id >= self.id:
            self.id = core_id + 1
        self.preexisting.add(core_id)
        n = Node(
            session_id,
            core_id,
            core_node.type,
            core_node.model,
            canvas_node.x_coord,
            canvas_node.y_coord,
            name,
        )
        self.nodes[canvas_node.id] = n

    def update_node_location(self, canvas_id, new_x, new_y):
        """
        update node

        :param int canvas_id: canvas id of that node
        :param int new_x: new x coord
        :param int new_y: new y coord
        :return: nothing
        """
        self.nodes[canvas_id].x = new_x
        self.nodes[canvas_id].y = new_y

    def update_reusable_id(self):
        """
        Update available id for reuse

        :return: nothing
        """
        if len(self.preexisting) > 0:
            for i in range(1, self.id):
                if i not in self.preexisting:
                    self.reusable.append(i)

            self.preexisting.clear()
            logging.debug("Next id: %s, Reusable: %s", self.id, self.reusable)

    def delete_node(self, canvas_id):
        """
        Delete a node from the session

        :param int canvas_id: node's id in the canvas
        :return: thing
        """
        try:
            self.nodes.pop(canvas_id)
            self.reusable.append(canvas_id)
            self.reusable.sort()
        except KeyError:
            logging.error("grpcmanagement.py INVALID NODE CANVAS ID")

    def create_interface(self, edge, src_canvas_id, dst_canvas_id):
        """
        Create the interface for the two end of an edge, add a copy to node's interfaces

        :param coretk.grpcmanagement.Edge edge: edge to add interfaces to
        :param int src_canvas_id: canvas id for the source node
        :param int dst_canvas_id: canvas id for the destination node
        :return: nothing
        """
        src_interface = None
        dst_interface = None
        print("create interface")
        self.interfaces_manager.new_subnet()

        src_node = self.nodes[src_canvas_id]
        if src_node.model in network_layer_nodes:
            ifid = len(src_node.interfaces)
            name = "eth" + str(ifid)
            src_interface = Interface(
                name=name, ifid=ifid, ipv4=str(self.interfaces_manager.get_address())
            )
            self.nodes[src_canvas_id].interfaces.append(src_interface)
            logging.debug(
                "Create source interface 1... IP: %s, name: %s",
                src_interface.ipv4,
                src_interface.name,
            )

        dst_node = self.nodes[dst_canvas_id]
        if dst_node.model in network_layer_nodes:
            ifid = len(dst_node.interfaces)
            name = "eth" + str(ifid)
            dst_interface = Interface(
                name=name, ifid=ifid, ipv4=str(self.interfaces_manager.get_address())
            )
            self.nodes[dst_canvas_id].interfaces.append(dst_interface)
            logging.debug(
                "Create destination interface... IP: %s, name: %s",
                dst_interface.ipv4,
                dst_interface.name,
            )

        edge.interface_1 = src_interface
        edge.interface_2 = dst_interface
        return src_interface, dst_interface

    def add_edge(self, session_id, token, canvas_id_1, canvas_id_2):
        """
        Add an edge to grpc manager

        :param int session_id: core session id
        :param tuple(int, int) token: edge's identification in the canvas
        :param int canvas_id_1: canvas id of source node
        :param int canvas_id_2: canvas_id of destination node

        :return: nothing
        """
        if canvas_id_1 in self.nodes and canvas_id_2 in self.nodes:
            edge = Edge(
                session_id,
                self.nodes[canvas_id_1].node_id,
                self.nodes[canvas_id_1].type,
                self.nodes[canvas_id_2].node_id,
                self.nodes[canvas_id_2].type,
            )
            self.edges[token] = edge
            src_interface, dst_interface = self.create_interface(
                edge, canvas_id_1, canvas_id_2
            )
            node_one_id = self.nodes[canvas_id_1].node_id
            node_two_id = self.nodes[canvas_id_2].node_id

            # provide a way to get an edge from a core node and an interface id
            if src_interface is not None:
                # self.node_id_and_interface_to_edge_token[tuple([node_one_id, src_interface.id])] = token
                self.core_mapping.map_node_and_interface_to_canvas_edge(
                    node_one_id, src_interface.id, token
                )
                logging.debug(
                    "map node id %s, interface_id %s to edge token %s",
                    node_one_id,
                    src_interface.id,
                    token,
                )

            if dst_interface is not None:
                # self.node_id_and_interface_to_edge_token[tuple([node_two_id, dst_interface.id])] = token
                self.core_mapping.map_node_and_interface_to_canvas_edge(
                    node_two_id, dst_interface.id, token
                )
                logging.debug(
                    "map node id %s, interface_id %s to edge token %s",
                    node_two_id,
                    dst_interface.id,
                    token,
                )

            logging.debug("Adding edge to grpc manager...")
        else:
            logging.error("grpcmanagement.py INVALID CANVAS NODE ID")
