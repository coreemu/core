"""
Converts CORE data objects into legacy API messages.
"""

from core import logger
from core.api import coreapi
from core.enumerations import NodeTlvs
from core.misc import structutils


def convert_node(node_data):
    """
    Callback to handle an node broadcast out from a session.

    :param core.data.NodeData node_data: node data to handle
    :return: packed node message
    """
    logger.debug("converting node data to message: %s", node_data)

    tlv_data = structutils.pack_values(coreapi.CoreNodeTlv, [
        (NodeTlvs.NUMBER, node_data.id),
        (NodeTlvs.TYPE, node_data.node_type),
        (NodeTlvs.NAME, node_data.name),
        (NodeTlvs.IP_ADDRESS, node_data.ip_address),
        (NodeTlvs.MAC_ADDRESS, node_data.mac_address),
        (NodeTlvs.IP6_ADDRESS, node_data.ip6_address),
        (NodeTlvs.MODEL, node_data.model),
        (NodeTlvs.EMULATION_ID, node_data.emulation_id),
        (NodeTlvs.EMULATION_SERVER, node_data.emulation_server),
        (NodeTlvs.SESSION, node_data.session),
        (NodeTlvs.X_POSITION, node_data.x_position),
        (NodeTlvs.Y_POSITION, node_data.y_position),
        (NodeTlvs.CANVAS, node_data.canvas),
        (NodeTlvs.NETWORK_ID, node_data.network_id),
        (NodeTlvs.SERVICES, node_data.services),
        (NodeTlvs.LATITUDE, node_data.latitude),
        (NodeTlvs.LONGITUDE, node_data.longitude),
        (NodeTlvs.ALTITUDE, node_data.altitude),
        (NodeTlvs.ICON, node_data.icon),
        (NodeTlvs.OPAQUE, node_data.opaque)
    ])

    return coreapi.CoreNodeMessage.pack(node_data.message_type, tlv_data)
