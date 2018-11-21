import os

from core.mobility import Ns2ScriptedMobility
from flask import Blueprint
from flask import jsonify
from flask import request

import core_utils

api = Blueprint("mobility_api", __name__)

coreemu = None


@api.route("/sessions/<int:session_id>/mobility/configs")
def get_mobility_configs(session_id):
    session = core_utils.get_session(coreemu, session_id)
    configs = {}
    for node_id, model_config in session.mobility.node_configurations.iteritems():
        if node_id == -1:
            continue

        for model_name in model_config.iterkeys():
            if model_name != Ns2ScriptedMobility.name:
                continue

            config = session.mobility.get_model_config(node_id, model_name)
            configs[node_id] = config
    return jsonify(configurations=configs)


@api.route("/sessions/<int:session_id>/nodes/<node_id>/mobility", methods=["POST"])
def set_mobility_config(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    data = request.get_json() or {}
    data["file"] = os.path.join(core_utils.save_dir, data["file"])
    session.mobility.set_model_config(node_id, Ns2ScriptedMobility.name, data)
    return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/mobility")
def get_mobility_config(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    config = session.mobility.get_model_config(node_id, Ns2ScriptedMobility.name)
    return jsonify(config)


@api.route("/sessions/<int:session_id>/nodes/<node_id>/mobility/<action>", methods=["PUT"])
def mobility_action(session_id, node_id, action):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)

    if action == "start":
        node.mobility.start()
    elif action == "pause":
        node.mobility.pause()
    elif action == "stop":
        node.mobility.stop(move_initial=True)
    else:
        return jsonify(error="invalid mobility action: %s" % action), 404

    return jsonify()
