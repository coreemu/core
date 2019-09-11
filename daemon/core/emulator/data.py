"""
CORE data objects.
"""

import collections

ConfigData = collections.namedtuple(
    "ConfigData",
    [
        "message_type",
        "node",
        "object",
        "type",
        "data_types",
        "data_values",
        "captions",
        "bitmap",
        "possible_values",
        "groups",
        "session",
        "interface_number",
        "network_id",
        "opaque",
    ],
)
ConfigData.__new__.__defaults__ = (None,) * len(ConfigData._fields)

EventData = collections.namedtuple(
    "EventData", ["node", "event_type", "name", "data", "time", "session"]
)
EventData.__new__.__defaults__ = (None,) * len(EventData._fields)

ExceptionData = collections.namedtuple(
    "ExceptionData", ["node", "session", "level", "source", "date", "text", "opaque"]
)
ExceptionData.__new__.__defaults__ = (None,) * len(ExceptionData._fields)

FileData = collections.namedtuple(
    "FileData",
    [
        "message_type",
        "node",
        "name",
        "mode",
        "number",
        "type",
        "source",
        "session",
        "data",
        "compressed_data",
    ],
)
FileData.__new__.__defaults__ = (None,) * len(FileData._fields)

NodeData = collections.namedtuple(
    "NodeData",
    [
        "message_type",
        "id",
        "node_type",
        "name",
        "ip_address",
        "mac_address",
        "ip6_address",
        "model",
        "emulation_id",
        "emulation_server",
        "session",
        "x_position",
        "y_position",
        "canvas",
        "network_id",
        "services",
        "latitude",
        "longitude",
        "altitude",
        "icon",
        "opaque",
    ],
)
NodeData.__new__.__defaults__ = (None,) * len(NodeData._fields)

LinkData = collections.namedtuple(
    "LinkData",
    [
        "message_type",
        "node1_id",
        "node2_id",
        "delay",
        "bandwidth",
        "per",
        "dup",
        "jitter",
        "mer",
        "burst",
        "session",
        "mburst",
        "link_type",
        "gui_attributes",
        "unidirectional",
        "emulation_id",
        "network_id",
        "key",
        "interface1_id",
        "interface1_name",
        "interface1_ip4",
        "interface1_ip4_mask",
        "interface1_mac",
        "interface1_ip6",
        "interface1_ip6_mask",
        "interface2_id",
        "interface2_name",
        "interface2_ip4",
        "interface2_ip4_mask",
        "interface2_mac",
        "interface2_ip6",
        "interface2_ip6_mask",
        "opaque",
    ],
)
LinkData.__new__.__defaults__ = (None,) * len(LinkData._fields)
