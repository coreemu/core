"""
Wireless connection handler
"""
from core.api.grpc import core_pb2


class WirelessConnection:
    def __init__(self, canvas, grpc):
        self.canvas = canvas
        self.core_grpc = grpc
        self.core_mapping = grpc.manager.core_mapping
        # map a (node_one_id, node_two_id) to a wlan canvas id
        self.map = {}

    def add_wlan_connection(self, node_one_id, node_two_id):
        canvas_id_one = self.core_mapping.get_canvas_id_from_core_id(node_one_id)
        canvas_id_two = self.core_mapping.get_canvas_id_from_core_id(node_two_id)
        key = tuple(sorted((node_one_id, node_two_id)))

        if key not in self.map:
            x1, y1 = self.canvas.coords(canvas_id_one)
            x2, y2 = self.canvas.coords(canvas_id_two)
            wlan_canvas_id = self.canvas.create_line(
                x1, y1, x2, y2, fill="#009933", tags="wlan", width=1.5
            )
            self.map[key] = wlan_canvas_id
            self.canvas.nodes[canvas_id_one].wlans.append(wlan_canvas_id)
            self.canvas.nodes[canvas_id_two].wlans.append(wlan_canvas_id)

    def delete_wlan_connection(self, node_one_id, node_two_id):
        canvas_id_one = self.core_mapping.get_canvas_id_from_core_id(node_one_id)
        canvas_id_two = self.core_mapping.get_canvas_id_from_core_id(node_two_id)

        key = tuple(sorted((node_one_id, node_two_id)))
        wlan_canvas_id = self.map[key]

        self.canvas.nodes[canvas_id_one].wlans.remove(wlan_canvas_id)
        self.canvas.nodes[canvas_id_two].wlans.remove(wlan_canvas_id)

        self.canvas.delete(wlan_canvas_id)
        self.map.pop(key, None)

    def hangle_link_event(self, link_event):
        if link_event.message_type == core_pb2.MessageType.ADD:
            self.add_wlan_connection(
                link_event.link.node_one_id, link_event.link.node_two_id
            )

        if link_event.message_type == core_pb2.MessageType.DELETE:
            self.delete_wlan_connection(
                link_event.link.node_one_id, link_event.link.node_two_id
            )
