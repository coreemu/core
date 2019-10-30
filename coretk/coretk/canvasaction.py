"""
canvas graph action
"""

# import tkinter as tk

from core.api.grpc import core_pb2
from coretk.nodeconfigtable import NodeConfig
from coretk.wlanconfiguration import WlanConfiguration

NODE_TO_TYPE = {
    "router": core_pb2.NodeType.DEFAULT,
    "wlan": core_pb2.NodeType.WIRELESS_LAN,
}


class CanvasAction:
    def __init__(self, master, canvas):
        self.master = master

        self.canvas = canvas
        self.node_to_show_config = None

    def display_configuration(self, canvas_node):
        pb_type = NODE_TO_TYPE[canvas_node.node_type]
        self.node_to_show_config = canvas_node
        if pb_type == core_pb2.NodeType.DEFAULT:
            self.display_node_configuration()
        elif pb_type == core_pb2.NodeType.WIRELESS_LAN:
            self.display_wlan_configuration()

    def display_node_configuration(self):
        NodeConfig(self.canvas, self.node_to_show_config)
        self.node_to_show_config = None

    def display_wlan_configuration(self):
        WlanConfiguration(self.canvas, self.node_to_show_config)
        self.node_to_show_config = None
