"""
wireless node configuration for all the wireless node
"""
from collections import OrderedDict

from core.api.grpc import core_pb2


class WlanNodeConfig:
    def __init__(self):
        # maps node id to wlan configuration
        self.configurations = {}

    def set_default_config(self, node_type, node_id):
        if node_type == core_pb2.NodeType.WIRELESS_LAN:
            config = OrderedDict()
            config["range"] = "275"
            config["bandwidth"] = "54000000"
            config["jitter"] = "0"
            config["delay"] = "20000"
            config["error"] = "0"
            self.configurations[node_id] = config

    def set_custom_config(self, node_id, range, bandwidth, jitter, delay, error):
        self.configurations[node_id]["range"] = range
        self.configurations[node_id]["bandwidth"] = bandwidth
        self.configurations[node_id]["jitter"] = jitter
        self.configurations[node_id]["delay"] = delay
        self.configurations[node_id]["error"] = error

    def delete_node_config(self, node_id):
        """
        not implemented
        :param node_id:
        :return:
        """
        return
