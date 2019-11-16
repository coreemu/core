"""
canvas graph action
"""
from core.api.grpc import core_pb2
from coretk.dialogs.emaneconfig import EmaneConfiguration
from coretk.dialogs.nodeconfig import NodeConfigDialog
from coretk.dialogs.wlanconfig import WlanConfigDialog


class CanvasAction:
    def __init__(self, master, canvas):
        self.master = master
        self.canvas = canvas
        self.node_to_show_config = None

    def display_configuration(self, canvas_node):
        node_type = canvas_node.core_node.type
        self.node_to_show_config = canvas_node
        if node_type == core_pb2.NodeType.DEFAULT:
            self.display_node_configuration()
        elif node_type == core_pb2.NodeType.WIRELESS_LAN:
            self.display_wlan_configuration(canvas_node)
        elif node_type == core_pb2.NodeType.EMANE:
            self.display_emane_configuration()

    def display_node_configuration(self):
        dialog = NodeConfigDialog(self.master, self.master, self.node_to_show_config)
        dialog.show()
        self.node_to_show_config = None

    def display_wlan_configuration(self, canvas_node):
        wlan_config = self.master.core.wlanconfig_management.configurations[
            canvas_node.core_id
        ]
        dialog = WlanConfigDialog(
            self.master, self.master, self.node_to_show_config, wlan_config
        )
        dialog.show()
        self.node_to_show_config = None

    def display_emane_configuration(self):
        app = self.canvas.core.app
        dialog = EmaneConfiguration(self.master, app, self.node_to_show_config)
        dialog.show()
