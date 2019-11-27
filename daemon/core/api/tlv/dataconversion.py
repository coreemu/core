"""
Converts CORE data objects into legacy API messages.
"""

from core.api.tlv import coreapi, structutils
from core.emulator.enumerations import ConfigTlvs, NodeTlvs


def convert_node(node_data):
    """
    Convenience method for converting NodeData to a packed TLV message.

    :param core.emulator.data.NodeData node_data: node data to convert
    :return: packed node message
    """
    tlv_data = structutils.pack_values(
        coreapi.CoreNodeTlv,
        [
            (NodeTlvs.NUMBER, node_data.id),
            (NodeTlvs.TYPE, node_data.node_type),
            (NodeTlvs.NAME, node_data.name),
            (NodeTlvs.IP_ADDRESS, node_data.ip_address),
            (NodeTlvs.MAC_ADDRESS, node_data.mac_address),
            (NodeTlvs.IP6_ADDRESS, node_data.ip6_address),
            (NodeTlvs.MODEL, node_data.model),
            (NodeTlvs.EMULATION_ID, node_data.emulation_id),
            (NodeTlvs.EMULATION_SERVER, node_data.server),
            (NodeTlvs.SESSION, node_data.session),
            (NodeTlvs.X_POSITION, int(node_data.x_position)),
            (NodeTlvs.Y_POSITION, int(node_data.y_position)),
            (NodeTlvs.CANVAS, node_data.canvas),
            (NodeTlvs.NETWORK_ID, node_data.network_id),
            (NodeTlvs.SERVICES, node_data.services),
            (NodeTlvs.LATITUDE, node_data.latitude),
            (NodeTlvs.LONGITUDE, node_data.longitude),
            (NodeTlvs.ALTITUDE, node_data.altitude),
            (NodeTlvs.ICON, node_data.icon),
            (NodeTlvs.OPAQUE, node_data.opaque),
        ],
    )
    return coreapi.CoreNodeMessage.pack(node_data.message_type, tlv_data)


def convert_config(config_data):
    """
    Convenience method for converting ConfigData to a packed TLV message.

    :param core.emulator.data.ConfigData config_data: config data to convert
    :return: packed message
    """
    tlv_data = structutils.pack_values(
        coreapi.CoreConfigTlv,
        [
            (ConfigTlvs.NODE, config_data.node),
            (ConfigTlvs.OBJECT, config_data.object),
            (ConfigTlvs.TYPE, config_data.type),
            (ConfigTlvs.DATA_TYPES, config_data.data_types),
            (ConfigTlvs.VALUES, config_data.data_values),
            (ConfigTlvs.CAPTIONS, config_data.captions),
            (ConfigTlvs.BITMAP, config_data.bitmap),
            (ConfigTlvs.POSSIBLE_VALUES, config_data.possible_values),
            (ConfigTlvs.GROUPS, config_data.groups),
            (ConfigTlvs.SESSION, config_data.session),
            (ConfigTlvs.INTERFACE_NUMBER, config_data.interface_number),
            (ConfigTlvs.NETWORK_ID, config_data.network_id),
            (ConfigTlvs.OPAQUE, config_data.opaque),
        ],
    )
    return coreapi.CoreConfMessage.pack(config_data.message_type, tlv_data)
