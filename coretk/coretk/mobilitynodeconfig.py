"""
mobility configurations for all the nodes
"""

import logging
from collections import OrderedDict

from core.api.grpc import core_pb2


class MobilityNodeConfig:
    def __init__(self):
        self.configurations = {}

    def set_default_configuration(self, node_type, node_id):
        """
        set default mobility configuration for a node

        :param core_pb2.NodeType node_type: protobuf node type
        :param int node_id: node id
        :return: nothing
        """
        if node_type == core_pb2.NodeType.WIRELESS_LAN:
            config = OrderedDict()
            config["autostart"] = ""
            config["file"] = ""
            config["loop"] = "1"
            config["map"] = ""
            config["refresh_ms"] = "50"
            config["script_pause"] = ""
            config["script_start"] = ""
            config["script_stop"] = ""
            self.configurations[node_id] = config

    def set_custom_configuration(
        self,
        node_id,
        file,
        refresh_ms,
        loop,
        autostart,
        node_mapping,
        script_start,
        script_pause,
        script_stop,
    ):
        """
        set custom mobility configuration for a node

        :param int node_id: node id
        :param str file: path to mobility script file
        :param str refresh_ms: refresh time
        :param str loop: loop option
        :param str autostart: auto-start seconds value
        :param str node_mapping: node mapping
        :param str script_start: path to script to run upon start
        :param str script_pause: path to script to run upon pause
        :param str script_stop: path to script to run upon stop
        :return: nothing
        """
        if node_id in self.configurations:
            self.configurations[node_id]["autostart"] = autostart
            self.configurations[node_id]["file"] = file
            self.configurations[node_id]["loop"] = loop
            self.configurations[node_id]["map"] = node_mapping
            self.configurations[node_id]["refresh_ms"] = refresh_ms
            self.configurations[node_id]["script_pause"] = script_pause
            self.configurations[node_id]["script_start"] = script_start
            self.configurations[node_id]["script_stop"] = script_stop
        else:
            logging.error("mobilitynodeconfig.py invalid node_id")
