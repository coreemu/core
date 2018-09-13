from flask import jsonify
from flask import request
from flask.blueprints import Blueprint

import core_utils
from core.mobility import BasicRangeModel

coreemu = None

api = Blueprint("wlan_api", __name__)


@api.route("/sessions/<int:session_id>/nodes/<node_id>/wlan")
def get_wlan_config(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    config = session.mobility.get_model_config(node_id, BasicRangeModel.name)
    return jsonify(config)


@api.route("/sessions/<int:session_id>/nodes/<node_id>/wlan", methods=["PUT"])
def set_wlan_config(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    config = request.get_json() or {}
    session.mobility.set_model_config(node_id, BasicRangeModel.name, config)
    return jsonify()
