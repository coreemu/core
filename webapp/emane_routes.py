from flask import jsonify
from flask import request
from flask.blueprints import Blueprint

import core_utils

coreemu = None

api = Blueprint("emane_api", __name__)


@api.route("/sessions/<int:session_id>/emane/config", methods=["PUT"])
def set_emane_config(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    values = data["values"]
    config = {x["name"]: x["value"] for x in values}
    session.emane.set_configs(config)
    return jsonify()


@api.route("/sessions/<int:session_id>/emane/model/config", methods=["PUT"])
def set_emane_model_config(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    model_name = data["name"]
    node_id = data["node"]
    values = data["values"]
    config = {x["name"]: x["value"] for x in values}
    session.emane.set_model_config(node_id, model_name, config)
    return jsonify()


@api.route("/sessions/<int:session_id>/emane/model/configs")
def get_emane_model_configs(session_id):
    session = core_utils.get_session(coreemu, session_id)
    response = {}
    for node_id, model_config in session.emane.node_configurations.iteritems():
        if node_id == -1:
            continue

        for model_name in model_config.iterkeys():
            model = session.emane.models[model_name]
            config = session.emane.get_model_config(node_id, model_name)
            config_groups = core_utils.get_config_groups(model, config)
            node_configurations = response.setdefault(node_id, {})
            node_configurations[model_name] = config_groups
    return jsonify(configurations=response)


@api.route("/sessions/<int:session_id>/emane/config")
def get_emane_config(session_id):
    session = core_utils.get_session(coreemu, session_id)
    config = session.emane.get_configs()
    response = core_utils.get_config_groups(session.emane.emane_config, config)
    return jsonify(groups=response)


@api.route("/sessions/<int:session_id>/emane/model/config")
def get_emane_model_config(session_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(request.args["node"])
    model_name = request.args["name"]
    model = session.emane.models[model_name]
    config = session.emane.get_model_config(node_id, model_name)
    response = core_utils.get_config_groups(model, config)
    return jsonify(groups=response)


@api.route("/sessions/<int:session_id>/emane/models")
def get_emane_models(session_id):
    session = core_utils.get_session(coreemu, session_id)

    models = []
    for model in session.emane.models.keys():
        if len(model.split("_")) != 2:
            continue
        models.append(model)

    return jsonify(models=models)
