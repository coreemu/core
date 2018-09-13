import os
import tempfile
from functools import wraps
from threading import Lock

from bottle import HTTPError
from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request
from flask import send_file
from flask_socketio import SocketIO
from flask_socketio import emit

import core_utils
import mobility_routes
from core import logger
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import InterfaceData
from core.emulator.emudata import LinkOptions
from core.emulator.emudata import NodeOptions
from core.enumerations import EventTypes
from core.enumerations import LinkTypes
from core.enumerations import NodeTypes
from core.misc import nodeutils
from core.misc.ipaddress import Ipv4Prefix, Ipv6Prefix
from core.mobility import BasicRangeModel
from core.service import ServiceManager

CORE_LOCK = Lock()
coreemu = CoreEmu()

app = Flask(__name__)
socketio = SocketIO(app)
app.config["SECRET_KEY"] = "core"

mobility_routes.coreemu = coreemu
app.register_blueprint(mobility_routes.mobility_api, url_prefix="/sessions/<int:session_id>")


def synchronized(function):
    global CORE_LOCK

    @wraps(function)
    def wrapper(*args, **kwargs):
        with CORE_LOCK:
            return function(*args, **kwargs)

    return wrapper


def link_data_str(link, key):
    value = link.get(key)
    if value:
        link[key] = str(value)


def convert_value(value):
    if value is None:
        return value
    else:
        return str(value)


def convert_link(session, link_data):
    interface_one = None
    interface_two = None

    if link_data.interface1_id is not None:
        node = session.get_object(link_data.node1_id)
        interface = node.netif(link_data.interface1_id)
        interface_one = {
            "id": link_data.interface1_id,
            "name": interface.name,
            "mac": convert_value(link_data.interface1_mac),
            "ip4": convert_value(link_data.interface1_ip4),
            "ip4mask": link_data.interface1_ip4_mask,
            "ip6": convert_value(link_data.interface1_ip6),
            "ip6mask": link_data.interface1_ip6_mask,
        }

    if link_data.interface2_id is not None:
        node = session.get_object(link_data.node2_id)
        interface = node.netif(link_data.interface2_id)
        interface_two = {
            "id": link_data.interface2_id,
            "name": interface.name,
            "mac": convert_value(link_data.interface2_mac),
            "ip4": convert_value(link_data.interface2_ip4),
            "ip4mask": link_data.interface2_ip4_mask,
            "ip6": convert_value(link_data.interface2_ip6),
            "ip6mask": link_data.interface2_ip6_mask,
        }

    return {
        "node_one": link_data.node1_id,
        "node_two": link_data.node2_id,
        "type": link_data.link_type,
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
    }


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


@socketio.on("connect")
def websocket_connect():
    emit("info", {"message": "You are connected!"})


@socketio.on("disconnect")
def websocket_disconnect():
    logger.info("websocket client disconnected")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ips", methods=["POST"])
def get_ips():
    data = request.get_json() or {}
    node_id = data["id"]
    node_id = int(node_id)

    ip4_prefix = data.get("ip4")
    ip6_prefix = data.get("ip6")

    ip4_prefixes = Ipv4Prefix(ip4_prefix)
    ip6_prefixes = Ipv6Prefix(ip6_prefix)

    return jsonify(
        ip4=str(ip4_prefixes.addr(node_id)),
        ip4mask=ip4_prefixes.prefixlen,
        ip6=str(ip6_prefixes.addr(node_id)),
        ip6mask=ip6_prefixes.prefixlen
    )


@app.route("/sessions/<int:session_id>/xml")
def save_xml(session_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    _, temp_path = tempfile.mkstemp()
    session.save_xml(temp_path, "1.0")
    return send_file(
        temp_path,
        as_attachment=True,
        attachment_filename="session-%s.xml" % session_id
    )


@app.route("/sessions/xml", methods=["POST"])
def open_xml():
    session = coreemu.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE)

    logger.info("open xml: %s", request.files)
    _, temp_path = tempfile.mkstemp()
    session_file = request.files['session']
    session_file.save(temp_path)

    try:
        session.open_xml(temp_path, start=True)
        return jsonify(id=session.session_id)
    except:
        logger.exception("error opening session file")
        coreemu.delete_session(session.session_id)
        return jsonify(error="error opening session file"), 404


@app.route("/services")
def get_services():
    groups = {}
    for service in ServiceManager.services.itervalues():
        service_group = groups.setdefault(service.group, [])
        service_group.append(service.name)

    return jsonify(groups=groups)


@app.route("/sessions")
def get_sessions():
    sessions = []
    for session in coreemu.sessions.itervalues():
        sessions.append({
            "id": session.session_id,
            "state": session.state,
            "nodes": session.get_node_count()
        })
    return jsonify(sessions=sessions)


@app.route("/sessions", methods=["POST"])
@synchronized
def create_session():
    session = coreemu.create_session()
    session.set_state(EventTypes.DEFINITION_STATE)

    # set session location
    session.location.setrefgeo(47.57917, -122.13232, 2.0)
    session.location.refscale = 150.0

    # add handlers
    session.event_handlers.append(broadcast_event)
    session.node_handlers.append(broadcast_node)

    response_data = jsonify(
        id=session.session_id,
        state=session.state,
        url="/sessions/%s" % session.session_id
    )
    return response_data, 201


@app.route("/sessions/<int:session_id>", methods=["DELETE"])
@synchronized
def delete_session(session_id):
    result = coreemu.delete_session(session_id)
    if result:
        return jsonify()
    else:
        return jsonify(error="session does not exist"), 404


@app.route("/sessions/<int:session_id>/options")
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


@app.route("/sessions/<int:session_id>/options", methods=["PUT"])
@synchronized
def set_session_options(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    values = data["values"]
    config = {x["name"]: x["value"] for x in values}
    session.options.set_configs(config)
    return jsonify()


@app.route("/sessions/<int:session_id>")
def get_session(session_id):
    session = core_utils.get_session(coreemu, session_id)

    nodes = []
    links = []
    for node in session.objects.itervalues():
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
            link = convert_link(session, link_data)
            links.append(link)

    return jsonify(
        state=session.state,
        nodes=nodes,
        links=links
    )


@app.route("/sessions/<int:session_id>/hooks", methods=["POST"])
def add_hook(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    state = data["state"]
    file_name = data["file"]
    file_data = data["data"]
    session.add_hook(state, file_name, None, file_data)
    return jsonify()


@app.route("/sessions/<int:session_id>/hooks")
def get_hooks(session_id):
    session = core_utils.get_session(coreemu, session_id)

    hooks = []
    for state, state_hooks in session._hooks.iteritems():
        for file_name, file_data in state_hooks:
            hooks.append({
                "state": state,
                "file": file_name,
                "data": file_data
            })

    return jsonify(hooks=hooks)


@app.route("/sessions/<int:session_id>/nodes/<node_id>/wlan")
def get_wlan_config(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    config = session.mobility.get_model_config(node_id, BasicRangeModel.name)
    return jsonify(config)


@app.route("/sessions/<int:session_id>/nodes/<node_id>/wlan", methods=["PUT"])
def set_wlan_config(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    config = request.get_json() or {}
    session.mobility.set_model_config(node_id, BasicRangeModel.name, config)
    return jsonify()


@app.route("/sessions/<int:session_id>/emane/config", methods=["PUT"])
@synchronized
def set_emane_config(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    values = data["values"]
    config = {x["name"]: x["value"] for x in values}
    session.emane.set_configs(config)
    return jsonify()


@app.route("/sessions/<int:session_id>/emane/model/config", methods=["PUT"])
@synchronized
def set_emane_model_config(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    model_name = data["name"]
    node_id = data.get("node")
    values = data["values"]
    config = {x["name"]: x["value"] for x in values}
    session.emane.set_model_config(node_id, model_name, config)
    return jsonify()


@app.route("/sessions/<int:session_id>/emane/config")
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


@app.route("/sessions/<int:session_id>/emane/model/config")
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


@app.route("/sessions/<int:session_id>/emane/models")
def get_emane_models(session_id):
    session = core_utils.get_session(coreemu, session_id)

    models = []
    for model in session.emane.models.keys():
        if len(model.split("_")) != 2:
            continue
        models.append(model)

    return jsonify(models=models)


@app.route("/sessions/<int:session_id>/nodes", methods=["POST"])
@synchronized
def create_node(session_id):
    session = core_utils.get_session(coreemu, session_id)

    data = request.get_json() or {}
    node_id = data.get("id")
    node_type = data.get("type", NodeTypes.DEFAULT.value)
    node_type = NodeTypes(node_type)
    logger.info("creating node: %s - %s", node_type.name, data)

    node_options = NodeOptions(
        name=data.get("name"),
        model=data.get("model")
    )
    node_options.icon = data.get("icon")
    node_options.opaque = data.get("opaque")
    node_options.services = data.get("services", [])
    position = data.get("position")
    node_options.set_position(position.get("x"), position.get("y"))
    node_options.set_location(data.get("lat"), data.get("lon"), data.get("alt"))
    node = session.add_node(_type=node_type, _id=node_id, node_options=node_options)

    # configure emane if provided
    emane_model = data.get("emane")
    if emane_model:
        session.emane.set_model_config(node_id, emane_model)

    return jsonify(
        id=node.objid,
        url="/sessions/%s/nodes/%s" % (session_id, node.objid)
    ), 201


@app.route("/sessions/<int:session_id>/nodes/<node_id>", methods=["PUT"])
@synchronized
def edit_node(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)

    data = request.get_json() or {}

    node_options = NodeOptions()
    x = data.get("x")
    y = data.get("y")
    node_options.set_position(x, y)
    lat = data.get("lat")
    lon = data.get("lon")
    alt = data.get("alt")
    node_options.set_location(lat, lon, alt)

    result = session.update_node(node_id, node_options)
    if result:
        return jsonify()
    else:
        return jsonify(error="error during node edit"), 404


@app.route("/sessions/<int:session_id>/nodes/<node_id>")
def get_node(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)

    interfaces = []
    for interface_id, interface in node._netif.iteritems():
        net_id = None
        if interface.net:
            net_id = interface.net.objid

        interfaces.append({
            "id": interface_id,
            "netid": net_id,
            "name": interface.name,
            "mac": str(interface.hwaddr),
            "mtu": interface.mtu,
            "flowid": interface.flow_id
        })

    services = [x.name for x in getattr(node, "services", [])]

    emane_model = None
    if nodeutils.is_node(node, NodeTypes.EMANE):
        emane_model = node.model.name

    return jsonify(
        name=node.name,
        type=nodeutils.get_node_type(node.__class__).value,
        services=services,
        emane=emane_model,
        model=node.type,
        interfaces=interfaces,
        linksurl="/sessions/%s/nodes/%s/links" % (session_id, node.objid)
    )


@app.route("/sessions/<int:session_id>/nodes/<node_id>/terminal")
def node_terminal(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)
    terminal_command = node.termcmdstring("/bin/bash")
    return jsonify(terminal_command)


@app.route("/sessions/<int:session_id>/nodes/<node_id>", methods=["DELETE"])
@synchronized
def delete_node(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    result = session.delete_node(node_id)
    if result:
        return jsonify()
    else:
        return jsonify(error="failure to delete node"), 404


# TODO: this should just be a general service query
@app.route("/sessions/<int:session_id>/nodes/<node_id>/services")
def get_node_services(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)

    services = {}
    for service in ServiceManager.services.itervalues():
        service_group = services.setdefault(service.group, [])
        service_group.append(service.name)

    return jsonify(services)


@app.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>")
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


@app.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>", methods=["PUT"])
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


@app.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service_name>/file")
def get_node_service_file(session_id, node_id, service_name):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)

    # get custom service file or default
    service_file = request.args["file"]
    file_data = session.services.get_service_file(node, service_name, service_file)
    return jsonify(file_data.data)


@app.route("/sessions/<int:session_id>/nodes/<node_id>/services/<service>/file", methods=["PUT"])
def set_node_service_file(session_id, node_id, service):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)

    data = request.get_json() or {}
    file_name = data["name"]
    data = data["data"]
    session.services.set_service_file(node_id, service, file_name, data)
    return jsonify()


@app.route("/sessions/<int:session_id>/state", methods=["PUT"])
@synchronized
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


@app.route("/sessions/<int:session_id>/links", methods=["POST"])
@synchronized
def add_link(session_id):
    session = core_utils.get_session(coreemu, session_id)

    data = request.get_json()
    logger.info("adding link: %s", data)

    node_one = data.get("node_one")
    node_two = data.get("node_two")

    interface_one = None
    interface_one_data = data.get("interface_one")
    if interface_one_data:
        interface_one = InterfaceData(
            _id=interface_one_data.get("id"),
            name=interface_one_data.get("name"),
            mac=interface_one_data.get("mac"),
            ip4=interface_one_data.get("ip4"),
            ip4_mask=interface_one_data.get("ip4mask"),
            ip6=interface_one_data.get("ip6"),
            ip6_mask=interface_one_data.get("ip6mask"),
        )

    interface_two = None
    interface_two_data = data.get("interface_two")
    if interface_two_data:
        interface_two = InterfaceData(
            _id=interface_two_data.get("id"),
            name=interface_two_data.get("name"),
            mac=interface_two_data.get("mac"),
            ip4=interface_two_data.get("ip4"),
            ip4_mask=interface_two_data.get("ip4mask"),
            ip6=interface_two_data.get("ip6"),
            ip6_mask=interface_two_data.get("ip6mask"),
        )

    link_type = None
    link_type_value = data.get("type")
    if link_type_value is not None:
        link_type = LinkTypes(link_type_value)

    options_data = data.get("options")
    link_options = LinkOptions(_type=link_type)
    if options_data:
        link_options.delay = options_data.get("delay")
        link_options.bandwidth = options_data.get("bandwidth")
        link_options.session = options_data.get("session")
        link_options.per = options_data.get("per")
        link_options.dup = options_data.get("dup")
        link_options.jitter = options_data.get("jitter")
        link_options.mer = options_data.get("mer")
        link_options.burst = options_data.get("burst")
        link_options.mburst = options_data.get("mburst")
        link_options.unidirectional = options_data.get("unidirectional")
        link_options.key = options_data.get("key")
        link_options.opaque = options_data.get("opaque")

    session.add_link(node_one, node_two, interface_one, interface_two, link_options=link_options)
    return jsonify(), 201


@app.route("/sessions/<int:session_id>/links", methods=["PUT"])
@synchronized
def edit_link(session_id):
    session = core_utils.get_session(coreemu, session_id)

    data = request.get_json()

    node_one = data.get("node_one")
    node_two = data.get("node_two")
    interface_one = data.get("interface_one")
    interface_two = data.get("interface_two")

    options_data = data.get("options")
    link_options = LinkOptions()
    if options_data:
        link_options.delay = options_data.get("delay")
        link_options.bandwidth = options_data.get("bandwidth")
        link_options.session = options_data.get("session")
        link_options.per = options_data.get("per")
        link_options.dup = options_data.get("dup")
        link_options.jitter = options_data.get("jitter")
        link_options.mer = options_data.get("mer")
        link_options.burst = options_data.get("burst")
        link_options.mburst = options_data.get("mburst")
        link_options.unidirectional = options_data.get("unidirectional")
        link_options.key = options_data.get("key")
        link_options.opaque = options_data.get("opaque")

    session.update_link(node_one, node_two, link_options, interface_one, interface_two)
    return jsonify(), 201


@app.route("/sessions/<int:session_id>/links", methods=["DELETE"])
@synchronized
def delete_link(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json()
    node_one = data.get("node_one")
    node_two = data.get("node_two")
    interface_one = data.get("interface_one")
    interface_two = data.get("interface_two")
    session.delete_link(node_one, node_two, interface_one, interface_two)
    return jsonify()


@app.route("/sessions/<int:session_id>/nodes/<node_id>/links")
def get_node_links(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)

    links_data = node.all_link_data(0)
    links = []
    for link_data in links_data:
        link = link_data._asdict()
        del link["message_type"]
        link_data_str(link, "interface1_ip4")
        link_data_str(link, "interface1_ip6")
        link_data_str(link, "interface1_mac")
        link_data_str(link, "interface2_ip4")
        link_data_str(link, "interface2_ip6")
        link_data_str(link, "interface2_mac")
        links.append(link)

    return jsonify(links=links)


@app.errorhandler(HTTPError)
def handle_error(e):
    return jsonify(message=e.body, status=e.status_code), e.status_code


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", debug=True)
