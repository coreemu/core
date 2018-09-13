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
    node_id = data.get("node")
    values = data["values"]
    config = {x["name"]: x["value"] for x in values}
    session.emane.set_model_config(node_id, model_name, config)
    return jsonify()


@api.route("/sessions/<int:session_id>/emane/config")
def get_emane_config(session_id):
    session = core_utils.get_session(coreemu, session_id)

    config = session.emane.get_configs()

    config_options = []
    for configuration in session.emane.emane_config.configurations():
        value = config[configuration.id]
        config_options.append({
            "label": configuration.label,
            "name": configuration.id,
            "value": value,
            "type": configuration.type.value,
            "select": configuration.options
        })

    response = []
    for config_group in session.emane.emane_config.config_groups():
        start = config_group.start - 1
        stop = config_group.stop
        response.append({
            "name": config_group.name,
            "options": config_options[start: stop]
        })

    return jsonify(groups=response)


@api.route("/sessions/<int:session_id>/emane/model/config")
def get_emane_model_config(session_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(request.args.get("node"))

    model_name = request.args["name"]
    model = session.emane.models[model_name]
    config = session.emane.get_model_config(node_id, model_name)

    config_options = []
    for configuration in model.configurations():
        value = config[configuration.id]
        config_options.append({
            "label": configuration.label,
            "name": configuration.id,
            "value": value,
            "type": configuration.type.value,
            "select": configuration.options
        })

    response = []
    for config_group in model.config_groups():
        start = config_group.start - 1
        stop = config_group.stop
        response.append({
            "name": config_group.name,
            "options": config_options[start: stop]
        })

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
