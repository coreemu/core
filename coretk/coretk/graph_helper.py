"""
Some graph helper functions
"""
import logging
import tkinter as tk

from core.api.grpc import core_pb2
from coretk.images import ImageEnum, Images

CANVAS_COMPONENT_TAGS = ["edge", "node", "nodename", "wallpaper", "linkinfo"]


class GraphHelper:
    def __init__(self, canvas, core):
        """
        create an instance of GraphHelper object
        """
        self.canvas = canvas
        self.core = core

    def delete_canvas_components(self):
        """
        delete the components of the graph leaving only the blank canvas

        :return: nothing
        """
        for tag in CANVAS_COMPONENT_TAGS:
            for i in self.canvas.find_withtag(tag):
                self.canvas.delete(i)

    def draw_wireless_case(self, src_id, dst_id, edge):
        src_node_name = self.canvas.nodes[src_id].node_type
        dst_node_name = self.canvas.nodes[dst_id].node_type

        if src_node_name == "wlan" or dst_node_name == "wlan":
            self.canvas.itemconfig(edge.id, state=tk.HIDDEN)
            edge.wired = False
            if edge.token not in self.canvas.edges:
                if src_node_name == "wlan" and dst_node_name == "wlan":
                    self.canvas.nodes[src_id].antenna_draw.add_antenna()
                elif src_node_name == "wlan":
                    self.canvas.nodes[dst_id].antenna_draw.add_antenna()
                else:
                    self.canvas.nodes[src_id].antenna_draw.add_antenna()

            edge.wired = True

    def redraw_antenna(self, link, node_one, node_two):
        if link.type == core_pb2.LinkType.WIRELESS:
            if node_one.node_type == "wlan" and node_two.node_type == "wlan":
                node_one.antenna_draw.add_antenna()
            elif node_one.node_type == "wlan" and node_two.node_type != "wlan":
                node_two.antenna_draw.add_antenna()
            elif node_one.node_type != "wlan" and node_two.node_type == "wlan":
                node_one.antenna_draw.add_antenna()
            else:
                logging.error(
                    "graph_helper.py WIRELESS link but both nodes are non-wireless node"
                )

    def update_wlan_connection(self, old_x, old_y, new_x, new_y, edge_ids):
        for eid in edge_ids:
            x1, y1, x2, y2 = self.canvas.coords(eid)
            if x1 == old_x and y1 == old_y:
                self.canvas.coords(eid, new_x, new_y, x2, y2)
            else:
                self.canvas.coords(eid, x1, y1, new_x, new_y)


class WlanAntennaManager:
    def __init__(self, canvas, node_id):
        """
        crate an instance for AntennaManager
        """
        self.canvas = canvas
        self.node_id = node_id
        self.quantity = 0
        self._max = 5
        self.antennas = []

        # distance between each antenna
        self.offset = 0

    def add_antenna(self):
        """
        add an antenna to a node

        :return: nothing
        """
        if self.quantity < 5:
            x, y = self.canvas.coords(self.node_id)
            self.antennas.append(
                self.canvas.create_image(
                    x - 16 + self.offset,
                    y - 16,
                    anchor=tk.CENTER,
                    image=Images.get(ImageEnum.ANTENNA),
                    tags="antenna",
                )
            )
            self.quantity = self.quantity + 1
            self.offset = self.offset + 8

    def update_antennas_position(self, offset_x, offset_y):
        """
        redraw antennas of a node according to the new node position

        :return: nothing
        """
        for i in self.antennas:
            self.canvas.move(i, offset_x, offset_y)

    def delete_antenna(self, canvas_id):
        return

    def delete_antennas(self):
        """
        Delete all the antennas of a node

        :return: nothing
        """
        for i in self.antennas:
            self.canvas.delete(i)


# class WlanConnection:
#     def __init__(self, canvas, grpc):
#         """
#         create in
#         :param canvas:
#         """
#         self.canvas = canvas
#         self.core_grpc = grpc
#         self.throughput_on = False
#         self.map_node_link = {}
#         self.links = []
#
#     def wireless_nodes(self):
#         """
#         retrieve all the wireless clouds in the canvas
#
#         :return: list(coretk.graph.CanvasNode)
#         """
#         wireless_nodes = []
#         for n in self.canvas.nodes.values():
#             if n.node_type == "wlan":
#                 wireless_nodes.append(n)
#         return wireless_nodes
#
#     def draw_wireless_link(self, src, dst):
#         """
#         draw a line between 2 nodes that are connected to the same wireless cloud
#
#         :param coretk.graph.CanvasNode src: source node
#         :param coretk.graph.CanvasNode dst: destination node
#         :return: nothing
#         """
#         cid = self.canvas.create_line(src.x_coord, src.y_coord, dst.x_coord, dst.y_coord, tags="wlanconnection")
#         if src.id not in self.map_node_link:
#             self.map_node_link[src.id] = []
#         if dst.id not in self.map_node_link:
#             self.map_node_link[dst.id] = []
#         self.map_node_link[src.id].append(cid)
#         self.map_node_link[dst.id].append(cid)
#         self.links.append(cid)
#
#     def subnet_wireless_connection(self, wlan_node):
#         """
#         retrieve all the non-wireless nodes connected to wireless_node and create line (represent wireless connection) between each pair of nodes
#         :param coretk.grpah.CanvasNode wlan_node: wireless node
#
#         :return: nothing
#         """
#         non_wlan_nodes = []
#         for e in wlan_node.edges:
#             src = self.canvas.nodes[e.src]
#             dst = self.canvas.nodes[e.dst]
#             if src.node_type == "wlan" and dst.node_type != "wlan":
#                 non_wlan_nodes.append(dst)
#             elif src.node_type != "wlan" and dst.node_type == "wlan":
#                 non_wlan_nodes.append(src)
#
#         size = len(non_wlan_nodes)
#         for i in range(size):
#             for j in range(i+1, size):
#                 self.draw_wireless_link(non_wlan_nodes[i], non_wlan_nodes[j])
#
#     def session_wireless_connection(self):
#         """
#         draw all the wireless connection in the canvas
#
#         :return: nothing
#         """
#         wlan_nodes = self.wireless_nodes()
#         for n in wlan_nodes:
#             self.subnet_wireless_connection(n)
#
#     def show_links(self):
#         """
#         show all the links
#         """
#         for l in self.links:
#             self.canvas.itemconfig(l, state=tk.NORMAL)
#
#     def hide_links(self):
#         """
#         hide all the links
#         :return:
#         """
#         for l in self.links:
#             self.canvas.itemconfig(l, state=tk.HIDDEN)
