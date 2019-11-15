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
        src_node_type = self.canvas.nodes[src_id].core_node.type
        dst_node_type = self.canvas.nodes[dst_id].core_node.type
        is_src_wlan = src_node_type == core_pb2.NodeType.WIRELESS_LAN
        is_dst_wlan = dst_node_type == core_pb2.NodeType.WIRELESS_LAN
        if is_src_wlan or is_dst_wlan:
            self.canvas.itemconfig(edge.id, state=tk.HIDDEN)
            edge.wired = False
            if edge.token not in self.canvas.edges:
                if is_src_wlan and is_dst_wlan:
                    self.canvas.nodes[src_id].antenna_draw.add_antenna()
                elif is_src_wlan:
                    self.canvas.nodes[dst_id].antenna_draw.add_antenna()
                else:
                    self.canvas.nodes[src_id].antenna_draw.add_antenna()
            edge.wired = True

    def redraw_antenna(self, link, node_one, node_two):
        is_node_one_wlan = node_one.core_node.type == core_pb2.NodeType.WIRELESS_LAN
        is_node_two_wlan = node_two.core_node.type == core_pb2.NodeType.WIRELESS_LAN
        if link.type == core_pb2.LinkType.WIRELESS:
            if is_node_one_wlan and is_node_two_wlan:
                node_one.antenna_draw.add_antenna()
            elif is_node_one_wlan and not is_node_two_wlan:
                node_two.antenna_draw.add_antenna()
            elif not is_node_one_wlan and is_node_two_wlan:
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
        self.image = Images.get(ImageEnum.ANTENNA, 32)

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
                    image=self.image,
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
