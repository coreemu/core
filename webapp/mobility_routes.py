from flask import Blueprint
from flask import jsonify
from flask import request

from core.mobility import Ns2ScriptedMobility

api = Blueprint("mobility_api", __name__)

coreemu = None


@api.route("/sessions/<int:session_id>/nodes/<node_id>/mobility", methods=["POST"])
def set_mobility_config(session_id, node_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    if node_id.isdigit():
        node_id = int(node_id)

    data = request.get_json() or {}

    session.mobility.set_model_config(node_id, Ns2ScriptedMobility.name, data)

    return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/mobility")
def get_mobility_config(session_id, node_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    if node_id.isdigit():
        node_id = int(node_id)

    config = session.mobility.get_model_config(node_id, Ns2ScriptedMobility.name)

    return jsonify(config)


@api.route("/sessions/<int:session_id>/nodes/<node_id>/mobility/<action>", methods=["PUT"])
def mobility_action(session_id, node_id, action):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    if node_id.isdigit():
        node_id = int(node_id)
    node = session.objects.get(node_id)
    if not node:
        return jsonify(error="node does not exist"), 404

    if action == "start":
        node.mobility.start()
    elif action == "pause":
        node.mobility.pause()
    elif action == "stop":
        node.mobility.stop(move_initial=True)
    else:
        return jsonify(error="invalid mobility action: %s" % action), 404

    return jsonify()
