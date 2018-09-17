from flask_socketio import SocketIO

import core_utils
from core import logger

socketio = None


def register(app):
    global socketio
    socketio = SocketIO(app)

    @socketio.on("connect")
    def websocket_connect():
        logger.info("websocket client connected")

    @socketio.on("disconnect")
    def websocket_disconnect():
        logger.info("websocket client disconnected")


def broadtcast_file(file_data):
    socketio.emit("file", {
        "message_type": file_data.message_type,
        "node": file_data.node,
        "name": file_data.name,
        "mode": file_data.mode,
        "number": file_data.number,
        "type": file_data.type,
        "source": file_data.source,
        "session": file_data.session,
        "data": file_data.data,
        "compressed_data": file_data.compressed_data
    })


def broadcast_exception(exception_data):
    socketio.emit("exception", {
        "node": exception_data.node,
        "session": exception_data.session,
        "level": exception_data.level,
        "source": exception_data.source,
        "date": exception_data.date,
        "text": exception_data.text,
        "opaque": exception_data.opaque
    })


def broadcast_link(link_data):
    logger.info("broadcasting link")
    interface_one = None
    if link_data.interface1_id is not None:
        interface_one = {
            "id": link_data.interface1_id,
            "name": link_data.interface1_name,
            "mac": core_utils.convert_value(link_data.interface1_mac),
            "ip4": core_utils.convert_value(link_data.interface1_ip4),
            "ip4mask": link_data.interface1_ip4_mask,
            "ip6": core_utils.convert_value(link_data.interface1_ip6),
            "ip6mask": link_data.interface1_ip6_mask,
        }

    interface_two = None
    if link_data.interface2_id is not None:
        interface_two = {
            "id": link_data.interface2_id,
            "name": link_data.interface2_name,
            "mac": core_utils.convert_value(link_data.interface2_mac),
            "ip4": core_utils.convert_value(link_data.interface2_ip4),
            "ip4mask": link_data.interface2_ip4_mask,
            "ip6": core_utils.convert_value(link_data.interface2_ip6),
            "ip6mask": link_data.interface2_ip6_mask,
        }

    socketio.emit("link", {
        "message_type": link_data.message_type,
        "type": link_data.link_type,
        "node_one": link_data.node1_id,
        "node_two": link_data.node2_id,
        "interface_one": interface_one,
        "interface_two": interface_two,
        "options": {
            "opaque": link_data.opaque,
            "jitter": link_data.jitter,
            "key": link_data.key,
            "mburst": link_data.mburst,
            "mer": link_data.mer,
            "per": link_data.per,
            "bandwidth": link_data.bandwidth,
            "burst": link_data.burst,
            "delay": link_data.delay,
            "dup": link_data.dup,
            "unidirectional": link_data.unidirectional
        }
    })


def broadcast_config(config_data):
    socketio.emit("config", {
        "message_type": config_data.message_type,
        "node": config_data.node,
        "object": config_data.object,
        "type": config_data.type,
        "data_types": config_data.data_types,
        "data_values": config_data.data_values,
        "captions": config_data.captions,
        "bitmap": config_data.bitmap,
        "possible_values": config_data.possible_values,
        "groups": config_data.groups,
        "session": config_data.session,
        "interface_number": config_data.interface_number,
        "network_id": config_data.network_id,
        "opaque": config_data.opaque
    })


def broadcast_event(event):
    socketio.emit("event", {
        "node": event.node,
        "event_type": event.event_type,
        "name": event.name,
        "data": event.data,
        "time": event.time,
        "session": event.session
    })


def broadcast_node(node):
    socketio.emit("node", {
        "id": node.id,
        "name": node.name,
        "model": node.model,
        "position": {
            "x": node.x_position,
            "y": node.y_position,
        },
        "services": node.services.split("|"),
    })
