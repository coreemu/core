from flask.ext.socketio import SocketIO, emit

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
