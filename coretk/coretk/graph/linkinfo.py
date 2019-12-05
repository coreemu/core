"""
Link information, such as IPv4, IPv6 and throughput drawn in the canvas
"""
import logging
import tkinter as tk
from tkinter import font

TEXT_DISTANCE = 0.30


class LinkInfo:
    def __init__(self, canvas, edge, link):
        """
        create an instance of LinkInfo object
        :param coretk.graph.Graph canvas: canvas object
        :param coretk.graph.CanvasEdge edge: canvas edge onject
        :param link: core link to draw info for
        """
        self.canvas = canvas
        self.edge = edge
        self.link = link
        self.id1 = None
        self.id2 = None
        self.font = font.Font(size=8)
        self.draw_labels()

    def get_coordinates(self):
        x1, y1, x2, y2 = self.canvas.coords(self.edge.id)
        v1 = x2 - x1
        v2 = y2 - y1
        ux = TEXT_DISTANCE * v1
        uy = TEXT_DISTANCE * v2
        x1 = x1 + ux
        y1 = y1 + uy
        x2 = x2 - ux
        y2 = y2 - uy
        return x1, y1, x2, y2

    def draw_labels(self):
        x1, y1, x2, y2 = self.get_coordinates()
        label_one = None
        if self.link.HasField("interface_one"):
            label_one = (
                f"{self.link.interface_one.ip4}/{self.link.interface_one.ip4mask}\n"
                f"{self.link.interface_one.ip6}/{self.link.interface_one.ip6mask}\n"
            )
        label_two = None
        if self.link.HasField("interface_two"):
            label_two = (
                f"{self.link.interface_two.ip4}/{self.link.interface_two.ip4mask}\n"
                f"{self.link.interface_two.ip6}/{self.link.interface_two.ip6mask}\n"
            )
        self.id1 = self.canvas.create_text(
            x1, y1, text=label_one, justify=tk.CENTER, font=self.font, tags="linkinfo"
        )
        self.id2 = self.canvas.create_text(
            x2, y2, text=label_two, justify=tk.CENTER, font=self.font, tags="linkinfo"
        )

    def recalculate_info(self):
        """
        move the node info when the canvas node move

        :return: nothing
        """
        x1, y1, x2, y2 = self.get_coordinates()
        self.canvas.coords(self.id1, x1, y1)
        self.canvas.coords(self.id2, x2, y2)


class Throughput:
    def __init__(self, canvas, core):
        self.canvas = canvas
        self.core = core
        # edge canvas id mapped to throughput value
        self.tracker = {}
        # map an edge canvas id to a throughput canvas id
        self.map = {}
        self.edge_id_to_token = {}

    def load_throughput_info(self, interface_throughputs):
        """
        load all interface throughouts from an event

        :param repeated core_bp2.InterfaceThroughputinterface_throughputs: interface
            throughputs
        :return: nothing
        """
        for t in interface_throughputs:
            nid = t.node_id
            iid = t.interface_id
            tp = t.throughput
            token = self.core.interface_to_edge[(nid, iid)]
            print(token)
            edge_id = self.canvas.edges[token].id

            self.edge_id_to_token[edge_id] = token

            if edge_id not in self.tracker:
                self.tracker[edge_id] = tp
            else:
                temp = self.tracker[edge_id]
                self.tracker[edge_id] = (temp + tp) / 2

    def edge_is_wired(self, token):
        """
        determine whether link is a WIRED link

        :param token:
        :return:
        """
        canvas_edge = self.canvas.edges[token]
        canvas_src_id = canvas_edge.src
        canvas_dst_id = canvas_edge.dst
        src_node = self.canvas.nodes[canvas_src_id]
        dst_node = self.canvas.nodes[canvas_dst_id]

        if src_node.node_type == "wlan":
            if dst_node.node_type == "mdr":
                return False
            else:
                logging.debug("linkinfo.py is_wired WARNING wlan only connected to mdr")
                return True
        if dst_node.node_type == "wlan":
            if src_node.node_type == "mdr":
                return False
            else:
                logging.debug("linkinfo.py is_wired WARNING wlan only connected to mdr")
                return True
        return True

    def draw_wired_throughput(self, edge_id):

        x1, y1, x2, y2 = self.canvas.coords(edge_id)
        x = (x1 + x2) / 2
        y = (y1 + y2) / 2

        if edge_id not in self.map:
            tp_id = self.canvas.create_text(
                x, y, text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id])
            )
            self.map[edge_id] = tp_id

        # redraw throughput
        else:
            self.canvas.itemconfig(
                self.map[edge_id],
                text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id]),
            )

    def draw_wireless_throughput(self, edge_id):
        token = self.edge_id_to_token[edge_id]
        canvas_edge = self.canvas.edges[token]
        canvas_src_id = canvas_edge.src
        canvas_dst_id = canvas_edge.dst
        src_node = self.canvas.nodes[canvas_src_id]
        dst_node = self.canvas.nodes[canvas_dst_id]

        # non_wlan_node = None
        if src_node.node_type == "wlan":
            non_wlan_node = dst_node
        else:
            non_wlan_node = src_node

        x, y = self.canvas.coords(non_wlan_node.id)
        if edge_id not in self.map:
            tp_id = self.canvas.create_text(
                x + 50,
                y + 25,
                text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id]),
            )
            self.map[edge_id] = tp_id

        # redraw throughput
        else:
            self.canvas.itemconfig(
                self.map[edge_id],
                text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id]),
            )

    def draw_throughputs(self):
        for edge_id in self.tracker:
            if self.edge_is_wired(self.edge_id_to_token[edge_id]):
                self.draw_wired_throughput(edge_id)
            else:
                self.draw_wireless_throughput(edge_id)
                # draw wireless throughput

            # x1, y1, x2, y2 = self.canvas.coords(edge_id)
            # x = (x1 + x2) / 2
            # y = (y1 + y2) / 2
            #
            # print(self.is_wired(self.edge_id_to_token[edge_id]))
            # # new throughput
            # if edge_id not in self.map:
            #     tp_id = self.canvas.create_text(
            #         x, y, text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id])
            #     )
            #     self.map[edge_id] = tp_id
            #
            # # redraw throughput
            # else:
            #     self.canvas.itemconfig(
            #         self.map[edge_id],
            #         text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id]),
            #     )

    def process_grpc_throughput_event(self, interface_throughputs):
        self.load_throughput_info(interface_throughputs)
        self.draw_throughputs()

    def update_throughtput_location(self, edge):
        tp_id = self.map[edge.id]
        if self.edge_is_wired(self.edge_id_to_token[edge.id]):
            x1, y1 = self.canvas.coords(edge.src)
            x2, y2 = self.canvas.coords(edge.dst)
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2
            self.canvas.coords(tp_id, x, y)
        else:
            if self.canvas.nodes[edge.src].node_type == "wlan":
                x, y = self.canvas.coords(edge.dst)
                self.canvas.coords(tp_id, x + 50, y + 20)
            else:
                x, y = self.canvas.coords(edge.src)
                self.canvas.coords(tp_id, x + 50, y + 25)
