"""
Some graph helper functions
"""
import logging
import tkinter as tk

from coretk.images import ImageEnum, Images
from coretk.nodeutils import NodeUtils

CANVAS_COMPONENT_TAGS = [
    "edge",
    "node",
    "nodename",
    "wallpaper",
    "linkinfo",
    "antenna",
    "wireless",
    "selectednodes",
    "shape",
    "shapetext",
]


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
        is_src_wireless = NodeUtils.is_wireless_node(src_node_type)
        is_dst_wireless = NodeUtils.is_wireless_node(dst_node_type)
        if is_src_wireless or is_dst_wireless:
            self.canvas.itemconfig(edge.id, state=tk.HIDDEN)
            edge.wired = False
            if edge.token not in self.canvas.edges:
                if is_src_wireless and is_dst_wireless:
                    self.canvas.nodes[src_id].antenna_draw.add_antenna()
                elif is_src_wireless:
                    self.canvas.nodes[dst_id].antenna_draw.add_antenna()
                else:
                    self.canvas.nodes[src_id].antenna_draw.add_antenna()
            edge.wired = True

    def redraw_antenna(self, node_one, node_two):
        is_node_one_wireless = NodeUtils.is_wireless_node(node_one.core_node.type)
        is_node_two_wireless = NodeUtils.is_wireless_node(node_two.core_node.type)
        if is_node_one_wireless or is_node_two_wireless:
            if is_node_one_wireless and not is_node_two_wireless:
                node_two.antenna_draw.add_antenna()
            elif not is_node_one_wireless and is_node_two_wireless:
                node_one.antenna_draw.add_antenna()
            else:
                logging.error("bad link between two wireless nodes")

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
            aid = self.canvas.create_image(
                x - 16 + self.offset,
                y - 23,
                anchor=tk.CENTER,
                image=self.image,
                tags="antenna",
            )
            # self.canvas.tag_raise("antenna")
            self.antennas.append(aid)
            self.quantity = self.quantity + 1
            self.offset = self.offset + 8

    def delete_antenna(self):
        """
        delete one antenna

        :return: nothing
        """
        if len(self.antennas) > 0:
            self.canvas.delete(self.antennas.pop())
        self.quantity -= 1
        self.offset -= 8

    def delete_antennas(self):
        """
        delete all antennas

        :return: nothing
        """
        for aid in self.antennas:
            self.canvas.delete(aid)
        self.antennas.clear()
        self.quantity = 0
        self.offset = 0

    def update_antennas_position(self, offset_x, offset_y):
        """
        redraw antennas of a node according to the new node position

        :return: nothing
        """
        for i in self.antennas:
            self.canvas.move(i, offset_x, offset_y)
