"""
Manage useful informations about the nodes, edges and configuration
that can be useful for grpc, acts like a session class
"""
import logging

from core.api.grpc import core_pb2

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


class GrpcManager:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.id = 1
        # A list of id for re-use, keep in increasing order
        self.reusable = []

        self.preexisting = []

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
        create_node = Node(session_id, self.get_id(), node_type, node_model, x, y, name)
        self.nodes[canvas_id] = create_node
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

        :param core_pb2.Node core_node: core node grpc message
        :param coretk.graph.CanvasNode canvas_node: canvas node
        :param int session_id: session id
        :return: nothing
        """
        core_id = core_node.id
        if core_id >= self.id:
            self.id = core_id + 1
        self.preexisting.append(core_id)
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

    def update_reusable_id(self):
        """
        Update available id for reuse

        :return: nothing
        """
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
            self.reuseable.append(canvas_id)
            self.reuseable.sort()
        except KeyError:
            logging.error("grpcmanagement.py INVALID NODE CANVAS ID")

    def add_edge(self, session_id, token, canvas_id_1, canvas_id_2):
        if canvas_id_1 in self.nodes and canvas_id_2 in self.nodes:
            edge = Edge(
                session_id,
                self.nodes[canvas_id_1].node_id,
                self.nodes[canvas_id_1].type,
                self.nodes[canvas_id_2].node_id,
                self.nodes[canvas_id_2].type,
            )
            self.edges[token] = edge
            logging.debug("Adding edge to grpc manager...")
        else:
            logging.error("grpcmanagement.py INVALID CANVAS NODE ID")
