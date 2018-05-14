import os
from functools import wraps
from threading import Lock

from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request
from flask_socketio import SocketIO
from flask_socketio import emit

from core import logger
from core.data import ConfigData
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import InterfaceData
from core.emulator.emudata import LinkOptions
from core.emulator.emudata import NodeOptions
from core.enumerations import EventTypes
from core.enumerations import LinkTypes
from core.enumerations import NodeTypes
from core.misc import nodeutils
from core.misc.ipaddress import Ipv4Prefix, Ipv6Prefix

CORE_LOCK = Lock()

app = Flask(__name__)
app.config["SECRET_KEY"] = "core"
socketio = SocketIO(app)

coreemu = CoreEmu()


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


@socketio.on("connect")
def websocket_connect():
    emit("info", {"message": "You are connected!"})
    socketio.emit("node", {
        "id": 1,
        "x": 100,
        "y": 101
    })
    socketio.emit("node", {
        "id": 1,
        "x": 100,
        "y": 150
    })


@socketio.on("disconnect")
def websocket_disconnect():
    logger.info("websocket client disconnected")


@app.route("/")
def home():
    return render_template('index.html')


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
    session.set_state(EventTypes.CONFIGURATION_STATE)
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


@app.route("/sessions/<int:session_id>")
def get_session(session_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    nodes = []
    for node in session.objects.itervalues():
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
            "url": "/sessions/%s/nodes/%s" % (session_id, node.objid)
        })

    return jsonify(
        state=session.state,
        nodes=nodes
    )


@app.route("/sessions/<int:session_id>/nodes", methods=["POST"])
@synchronized
def create_node(session_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

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
    node_options.set_position(data.get("x"), data.get("y"))
    node_options.set_location(data.get("lat"), data.get("lon"), data.get("alt"))
    node = session.add_node(_type=node_type, _id=node_id, node_options=node_options)
    return jsonify(
        id=node.objid,
        url="/sessions/%s/nodes/%s" % (session_id, node.objid)
    ), 201


@app.route("/sessions/<int:session_id>/nodes/<node_id>", methods=["PUT"])
@synchronized
def edit_node(session_id, node_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    if node_id.isdigit():
        node_id = int(node_id)
    node = session.objects.get(node_id)
    if not node:
        return jsonify(error="node does not exist"), 404

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
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    if node_id.isdigit():
        node_id = int(node_id)
    node = session.objects.get(node_id)
    if not node:
        return jsonify(error="node does not exist"), 404

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

    return jsonify(
        name=node.name,
        type=nodeutils.get_node_type(node.__class__).value,
        model=node.type,
        interfaces=interfaces,
        linksurl="/sessions/%s/nodes/%s/links" % (session_id, node.objid)
    )


@app.route("/sessions/<int:session_id>/nodes/<node_id>", methods=["DELETE"])
@synchronized
def delete_node(session_id, node_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    if node_id.isdigit():
        node_id = int(node_id)
    node = session.objects.get(node_id)
    if not node:
        return jsonify(error="node does not exist"), 404

    result = session.delete_node(node_id)
    if result:
        return jsonify()
    else:
        return jsonify(error="failure to delete node"), 404


@app.route("/sessions/<int:session_id>/nodes/<node_id>/services")
def node_services(session_id, node_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    config_data = ConfigData(
        node=node_id,
        object="services",
        type=1,
    )
    logger.debug("configuration message for %s node %s", config_data.object, config_data.node)

    # dispatch to any registered callback for this object type
    replies = session.config_object(config_data)
    if len(replies) != 1:
        return jsonify(error="failure getting node services"), 404

    service_data = replies[0]
    names = service_data.captions.split("|")
    services = {}
    for group in service_data.groups.split("|"):
        group = group.split(":")
        group_name = group[0]
        group_start, group_stop = [int(x) for x in group[1].split("-")]
        group_start -= 1
        services[group_name] = names[group_start:group_stop]

    return jsonify(services)


@app.route("/sessions/<int:session_id>/state", methods=["PUT"])
@synchronized
def set_session_state(session_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

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
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    data = request.get_json()

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
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

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
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    data = request.get_json()
    node_one = data.get("node_one")
    node_two = data.get("node_two")
    interface_one = data.get("interface_one")
    interface_two = data.get("interface_two")
    session.delete_link(node_one, node_two, interface_one, interface_two)
    return jsonify()


@app.route("/sessions/<int:session_id>/nodes/<node_id>/links")
def get_node_links(session_id, node_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        return jsonify(error="session does not exist"), 404

    if node_id.isdigit():
        node_id = int(node_id)
    node = session.objects.get(node_id)
    if not node:
        return jsonify(error="node does not exist"), 404

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


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", debug=True)
