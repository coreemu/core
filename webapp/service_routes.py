from flask import jsonify
from flask import request
from flask.blueprints import Blueprint

import core_utils
from core import logger
from core.service import ServiceManager

coreemu = None

api = Blueprint("service_api", __name__)


@api.route("/services")
def get_services():
    groups = {}
    for service in ServiceManager.services.itervalues():
        service_group = groups.setdefault(service.group, [])
        service_group.append(service.name)

    return jsonify(groups=groups)


@api.route("/sessions/<int:session_id>/services/default")
def get_session_service_defaults(session_id):
    session = core_utils.get_session(coreemu, session_id)
    return jsonify(defaults=session.services.default_services)


@api.route("/sessions/<int:session_id>/services/default", methods=["POST"])
def set_session_service_defaults(session_id):
    data = request.get_json() or {}
    session = core_utils.get_session(coreemu, session_id)
    session.services.default_services.clear()
    session.services.default_services.update(data)
    logger.info("default services: %s", session.services.default_services)
    return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>")
def get_node_service(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)

    service = session.services.get_service(node_id, service_name, default_service=True)
    service_config = {
        "executables": service.executables,
        "dependencies": service.dependencies,
        "dirs": service.dirs,
        "configs": service.configs,
        "startup": service.startup,
        "validate": service.validate,
        "validation_mode": service.validation_mode.name,
        "validation_timer": service.validation_timer,
        "shutdown": service.shutdown,
        "meta": service.meta,
    }
    return jsonify(service_config)


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>", methods=["PUT"])
def set_node_service(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)

    data = request.get_json() or {}

    logger.info("setting custom service node(%s) service(%s)", node_id, service_name)
    # guarantee custom service exists
    session.services.set_service(node_id, service_name)
    service = session.services.get_service(node_id, service_name)
    service.startup = tuple(data["startup"])
    logger.info("custom startup: %s", service.startup)
    service.validate = tuple(data["validate"])
    logger.info("custom validate: %s", service.validate)
    service.shutdown = tuple(data["shutdown"])
    logger.info("custom shutdown: %s", service.shutdown)
    return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>/file")
def get_node_service_file(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)

    # get custom service file or default
    service_file = request.args["file"]
    file_data = session.services.get_service_file(node, service_name, service_file)
    return jsonify(file_data.data)


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service>/file", methods=["PUT"])
def set_node_service_file(session_id, node_id, service):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)

    data = request.get_json() or {}
    file_name = data["name"]
    data = data["data"]
    session.services.set_service_file(node_id, service, file_name, data)
    return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>/start", methods=["PUT"])
def start_node_service(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)
    status = -1
    for service in node.services:
        if service.name == service_name:
            status = session.services.startup_service(node, service, wait=True)
            break

    if status:
        return jsonify(), 400
    else:
        return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>/stop", methods=["PUT"])
def stop_node_service(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)
    status = -1
    for service in node.services:
        if service.name == service_name:
            status = session.services.stop_service(node, service)
            break

    if status:
        return jsonify(), 400
    else:
        return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>/restart", methods=["PUT"])
def restart_node_service(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)
    status = -1
    for service in node.services:
        if service.name == service_name:
            status = session.services.stop_service(node, service)
            if not status:
                status = session.services.startup_service(node, service, wait=True)
            break

    if status:
        return jsonify(), 400
    else:
        return jsonify()


@api.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>/validate", methods=["PUT"])
def validate_node_service(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)
    status = -1
    for service in node.services:
        if service.name == service_name:
            status = session.services.validate_service(node, service)
            break

    if status:
        return jsonify(), 400
    else:
        return jsonify()
