import os

from flask import jsonify
from flask import request
from flask.blueprints import Blueprint

import core_utils
import websocket_routes
from core.enumerations import EventTypes, NodeTypes
from core.misc import nodeutils

coreemu = None

api = Blueprint("session_api", __name__)


@api.route("/sessions")
def get_sessions():
    sessions = []
    for session in coreemu.sessions.itervalues():
        sessions.append({
            "id": session.session_id,
            "state": session.state,
            "nodes": session.get_node_count()
        })
    return jsonify(sessions=sessions)


@api.route("/sessions", methods=["POST"])
@core_utils.synchronized
def create_session():
    session = coreemu.create_session()
    session.set_state(EventTypes.DEFINITION_STATE)

    # set session location
    session.location.setrefgeo(47.57917, -122.13232, 2.0)
    session.location.refscale = 150.0

    # add handlers
    session.event_handlers.append(websocket_routes.broadcast_event)
    session.node_handlers.append(websocket_routes.broadcast_node)
    session.config_handlers.append(websocket_routes.broadcast_config)
    session.link_handlers.append(websocket_routes.broadcast_link)
    session.exception_handlers.append(websocket_routes.broadcast_exception)
    session.file_handlers.append(websocket_routes.broadtcast_file)

    response_data = jsonify(
        id=session.session_id,
        state=session.state,
        url="/sessions/%s" % session.session_id
    )
    return response_data, 201


@api.route("/sessions/<int:session_id>", methods=["DELETE"])
@core_utils.synchronized
def delete_session(session_id):
    result = coreemu.delete_session(session_id)
    if result:
        return jsonify()
    else:
        return jsonify(error="session does not exist"), 404


@api.route("/sessions/<int:session_id>/options")
def get_session_options(session_id):
    session = core_utils.get_session(coreemu, session_id)
    config = session.options.get_configs()

    config_options = []
    for configuration in session.options.configurations():
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


@api.route("/sessions/<int:session_id>/options", methods=["PUT"])
@core_utils.synchronized
def set_session_options(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    values = data["values"]
    config = {x["name"]: x["value"] for x in values}
    session.options.set_configs(config)
    return jsonify()


@api.route("/sessions/<int:session_id>")
def get_session(session_id):
    session = core_utils.get_session(coreemu, session_id)

    nodes = []
    links = []
    for node in session.objects.itervalues():
        if not isinstance(node.objid, int):
            continue

        emane_model = None
        if nodeutils.is_node(node, NodeTypes.EMANE):
            emane_model = node.model.name

        services = [x.name for x in getattr(node, "services", [])]
        nodes.append({
            "id": node.objid,
            "name": node.name,
            "type": nodeutils.get_node_type(node.__class__).value,
            "model": getattr(node, "type", None),
            "position": {
                "x": node.position.x,
                "y": node.position.y,
                "z": node.position.z
            },
            "services": services,
            "emane": emane_model,
            "url": "/sessions/%s/nodes/%s" % (session_id, node.objid)
        })

        links_data = node.all_link_data(0)
        for link_data in links_data:
            link = core_utils.convert_link(session, link_data)
            links.append(link)

    return jsonify(
        state=session.state,
        nodes=nodes,
        links=links
    )


@api.route("/sessions/<int:session_id>/state", methods=["PUT"])
@core_utils.synchronized
def set_session_state(session_id):
    session = core_utils.get_session(coreemu, session_id)

    data = request.get_json()
    try:
        state = EventTypes(data["state"])
        session.set_state(state)

        if state == EventTypes.INSTANTIATION_STATE:
            # create session directory if it does not exist
            if not os.path.exists(session.session_dir):
                os.mkdir(session.session_dir)
            session.instantiate()
        elif state == EventTypes.SHUTDOWN_STATE:
            session.shutdown()
        elif state == EventTypes.DATACOLLECT_STATE:
            session.data_collect()
        elif state == EventTypes.DEFINITION_STATE:
            session.clear()

        return jsonify()
    except KeyError:
        return jsonify(error="invalid state"), 404
