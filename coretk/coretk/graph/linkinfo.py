"""
Link information, such as IPv4, IPv6 and throughput drawn in the canvas
"""
import tkinter as tk
from tkinter import font

from core.api.grpc import core_pb2
from coretk.graph import tags

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
            x1,
            y1,
            text=label_one,
            justify=tk.CENTER,
            font=self.font,
            tags=tags.LINK_INFO,
        )
        self.id2 = self.canvas.create_text(
            x2,
            y2,
            text=label_two,
            justify=tk.CENTER,
            font=self.font,
            tags=tags.LINK_INFO,
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
        # map edge canvas id to token
        self.edge_id_to_token = {}

    def load_throughput_info(self, interface_throughputs):
        """
        load all interface throughouts from an event

        :param repeated core_bp2.InterfaceThroughputinterface_throughputs: interface
            throughputs
        :return: nothing
        """
        for throughput in interface_throughputs:
            nid = throughput.node_id
            iid = throughput.interface_id
            tp = throughput.throughput
            token = self.core.interface_to_edge.get((nid, iid))
            if token:
                edge = self.canvas.edges.get(token)
                if edge:
                    edge_id = edge.id
                    self.edge_id_to_token[edge_id] = token
                    if edge_id not in self.tracker:
                        self.tracker[edge_id] = tp
                    else:
                        temp = self.tracker[edge_id]
                        self.tracker[edge_id] = (temp + tp) / 2
                else:
                    self.core.interface_to_edge.pop((nid, iid), None)

    def edge_is_wired(self, token):
        """
        determine whether link is a WIRED link

        :param token:
        :return:
        """
        canvas_edge = self.canvas.edges[token]
        canvas_src_id = canvas_edge.src
        canvas_dst_id = canvas_edge.dst
        src = self.canvas.nodes[canvas_src_id].core_node
        dst = self.canvas.nodes[canvas_dst_id].core_node
        return not (
            src.type == core_pb2.NodeType.WIRELESS_LAN
            and dst.model == "mdr"
            or src.model == "mdr"
            and dst.type == core_pb2.NodeType.WIRELESS_LAN
        )

    def draw_wired_throughput(self, edge_id):

        x0, y0, x1, y1 = self.canvas.coords(edge_id)
        x = (x0 + x1) / 2
        y = (y0 + y1) / 2
        if edge_id not in self.map:
            tpid = self.canvas.create_text(
                x,
                y,
                tags="throughput",
                font=("Arial", 8),
                text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id]),
            )
            self.map[edge_id] = tpid
        else:
            tpid = self.map[edge_id]
            self.canvas.coords(tpid, x, y)
            self.canvas.itemconfig(
                tpid, text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id])
            )

    def draw_wireless_throughput(self, edge_id):
        token = self.edge_id_to_token[edge_id]
        canvas_edge = self.canvas.edges[token]
        canvas_src_id = canvas_edge.src
        canvas_dst_id = canvas_edge.dst
        src_node = self.canvas.nodes[canvas_src_id]
        dst_node = self.canvas.nodes[canvas_dst_id]

        not_wlan = (
            dst_node
            if src_node.core_node.type == core_pb2.NodeType.WIRELESS_LAN
            else src_node
        )

        x, y = self.canvas.coords(not_wlan.id)
        if edge_id not in self.map:
            tp_id = self.canvas.create_text(
                x + 50,
                y + 25,
                font=("Arial", 8),
                tags="throughput",
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

    def process_grpc_throughput_event(self, interface_throughputs):
        self.load_throughput_info(interface_throughputs)
        self.draw_throughputs()

    def move(self, edge):
        tpid = self.map.get(edge.id)
        if tpid:
            if self.edge_is_wired(edge.token):
                x0, y0, x1, y1 = self.canvas.coords(edge.id)
                self.canvas.coords(tpid, (x0 + x1) / 2, (y0 + y1) / 2)
            else:
                if (
                    self.canvas.nodes[edge.src].core_node.type
                    == core_pb2.NodeType.WIRELESS_LAN
                ):
                    x, y = self.canvas.coords(edge.dst)
                    self.canvas.coords(tpid, x + 50, y + 20)
                else:
                    x, y = self.canvas.coords(edge.src)
                    self.canvas.coords(tpid, x + 50, y + 25)

    def delete(self, edge):
        tpid = self.map.get(edge.id)
        if tpid:
            eid = edge.id
            self.canvas.delete(tpid)
            self.tracker.pop(eid)
            self.map.pop(eid)
            self.edge_id_to_token.pop(eid)
