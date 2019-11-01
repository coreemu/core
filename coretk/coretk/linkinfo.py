"""
Link information, such as IPv4, IPv6 and throughput drawn in the canvas
"""
import logging
import math

WIRELESS_DEF = ["mdr", "wlan"]


class LinkInfo:
    def __init__(self, canvas, edge, ip4_src, ip6_src, ip4_dst, ip6_dst):
        """
        create an instance of LinkInfo object
        :param coretk.graph.Graph canvas: canvas object
        :param coretk.graph.CanvasEdge edge: canvas edge onject
        :param ip4_src:
        :param ip6_src:
        :param ip4_dst:
        :param ip6_dst:
        """
        self.canvas = canvas
        self.edge = edge
        # self.edge_id = edge.id
        self.radius = 37
        self.core_grpc = self.canvas.core_grpc

        self.ip4_address_1 = ip4_src
        self.ip6_address_1 = ip6_src
        self.ip4_address_2 = ip4_dst
        self.ip6_address_2 = ip6_dst
        self.id1 = self.create_edge_src_info()
        self.id2 = self.create_edge_dst_info()

    def slope_src_dst(self):
        """
        calculate slope of the line connecting source node to destination node
        :rtype: float
        :return: slope of line
        """
        x1, y1, x2, y2 = self.canvas.coords(self.edge.id)
        if x2 - x1 == 0:
            return 9999.0
        else:
            return (y2 - y1) / (x2 - x1)

    def create_edge_src_info(self):
        """
        draw the ip address for source node

        :return: nothing
        """
        x1, y1, x2, _ = self.canvas.coords(self.edge.id)
        m = self.slope_src_dst()
        distance = math.cos(math.atan(m)) * self.radius
        if x1 > x2:
            distance = -distance
        # id1 = self.canvas.create_text(x1, y1, text=self.ip4_address_1)
        id1 = self.canvas.create_text(
            x1 + distance, y1 + distance * m, text=self.ip4_address_1, tags="linkinfo"
        )
        return id1

    def create_edge_dst_info(self):
        """
        draw the ip address for destination node

        :return: nothing
        """
        x1, _, x2, y2 = self.canvas.coords(self.edge.id)
        m = self.slope_src_dst()
        distance = math.cos(math.atan(m)) * self.radius
        if x1 > x2:
            distance = -distance
        # id2 = self.canvas.create_text(x2, y2, text=self.ip4_address_2)
        id2 = self.canvas.create_text(
            x2 - distance, y2 - distance * m, text=self.ip4_address_2, tags="linkinfo"
        )
        return id2

    def recalculate_info(self):
        """
        move the node info when the canvas node move

        :return: nothing
        """
        x1, y1, x2, y2 = self.canvas.coords(self.edge.id)
        m = self.slope_src_dst()
        distance = math.cos(math.atan(m)) * self.radius
        if x1 > x2:
            distance = -distance
        new_x1 = x1 + distance
        new_y1 = y1 + distance * m
        new_x2 = x2 - distance
        new_y2 = y2 - distance * m
        self.canvas.coords(self.id1, new_x1, new_y1)
        self.canvas.coords(self.id2, new_x2, new_y2)

    # def link_througput(self):
    #     x1, y1, x2, y2 = self.canvas.coords(self.edge.id)
    #     x = (x1 + x2) / 2
    #     y = (y1 + y2) / 2
    #     tid = self.canvas.create_text(x, y, text="place text here")
    #     return tid


class Throughput:
    def __init__(self, canvas, core_grpc):
        """
        create an instance of Throughput object
        :param coretk.app.Application app: application
        """
        self.canvas = canvas
        self.core_grpc = core_grpc
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
            # token = self.grpc_manager.node_id_and_interface_to_edge_token[nid, iid]
            token = self.core_grpc.manager.core_mapping.get_token_from_node_and_interface(
                nid, iid
            )
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
