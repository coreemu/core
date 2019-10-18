"""
Link information, such as IPv4, IPv6 and throughput drawn in the canvas
"""
import math


class LinkInfo:
    def __init__(self, canvas, edge, ip4_src, ip6_src, ip4_dst, ip6_dst):
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
        x1, y1, x2, y2 = self.canvas.coords(self.edge.id)
        if x2 - x1 == 0:
            return 9999
        else:
            return (y2 - y1) / (x2 - x1)

    def create_edge_src_info(self):
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
    def __init__(self, canvas, grpc):
        self.canvas = canvas
        self.core_grpc = grpc
        self.grpc_manager = canvas.grpc_manager

        # edge canvas id mapped to throughput value
        self.tracker = {}

        # map an edge canvas id to a throughput canvas id
        self.map = {}

    def load_throughput_info(self, interface_throughputs):
        """
        load all interface throughouts from an event

        :param repeated core_bp2.InterfaceThroughputinterface_throughputs: interface throughputs
        :return: nothing
        """
        for t in interface_throughputs:
            nid = t.node_id
            iid = t.interface_id
            tp = t.throughput
            # token = self.grpc_manager.node_id_and_interface_to_edge_token[nid, iid]
            token = self.grpc_manager.core_mapping.get_token_from_node_and_interface(
                nid, iid
            )
            edge_id = self.canvas.edges[token].id
            if edge_id not in self.tracker:
                self.tracker[edge_id] = tp
            else:
                temp = self.tracker[edge_id]
                self.tracker[edge_id] = (temp + tp) / 2

    def draw_throughputs(self):
        for edge_id in self.tracker:
            x1, y1, x2, y2 = self.canvas.coords(edge_id)
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2
            if edge_id not in self.map:
                tp_id = self.canvas.create_text(
                    x, y, text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id])
                )
                self.map[edge_id] = tp_id
            else:
                self.canvas.itemconfig(
                    self.map[edge_id],
                    text="{0:.3f} kbps".format(0.001 * self.tracker[edge_id]),
                )

    def process_grpc_throughput_event(self, interface_throughputs):
        self.load_throughput_info(interface_throughputs)
        self.draw_throughputs()

    def update_throughtput_location(self, edge):
        tp_id = self.map[edge.id]
        x1, y1 = self.canvas.coords(edge.src)
        x2, y2 = self.canvas.coords(edge.dst)
        x = (x1 + x2) / 2
        y = (y1 + y2) / 2
        self.canvas.coords(tp_id, x, y)
