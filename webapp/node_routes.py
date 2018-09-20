from flask import jsonify
from flask import request
from flask.blueprints import Blueprint

import core_utils
from core import logger
from core.emulator.emudata import NodeOptions
from core.enumerations import NodeTypes
from core.misc import nodeutils

coreemu = None

api = Blueprint("nodes_api", __name__)


@api.route("/sessions/<int:session_id>/nodes", methods=["POST"])
@core_utils.synchronized
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


@api.route("/sessions/<int:session_id>/nodes/<node_id>", methods=["PUT"])
@core_utils.synchronized
def edit_node(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)

    data = request.get_json() or {}

    node_options = NodeOptions()
    node_position = data.get("position", {})
    x = node_position.get("x")
    y = node_position.get("y")
    node_options.set_position(x, y)
    lat = data.get("lat")
    lon = data.get("lon")
    alt = data.get("alt")
    node_options.set_location(lat, lon, alt)
    logger.debug("updating node(%s) - pos(%s, %s) geo(%s, %s, %s)", node_id, x, y, lat, lon, alt)

    result = session.update_node(node_id, node_options)
    if result:
        return jsonify()
    else:
        return jsonify(error="error during node edit"), 404


@api.route("/sessions/<int:session_id>/nodes/<node_id>")
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


@api.route("/sessions/<int:session_id>/nodes/<node_id>/terminal")
def node_terminal(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)
    terminal_command = node.termcmdstring("/bin/bash")
    return jsonify(terminal_command)


@api.route("/sessions/<int:session_id>/nodes/<node_id>", methods=["DELETE"])
@core_utils.synchronized
def delete_node(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node_id = core_utils.get_node_id(node_id)
    result = session.delete_node(node_id)
    if result:
        return jsonify()
    else:
        return jsonify(error="failure to delete node"), 404


@api.route("/sessions/<int:session_id>/nodes/<node_id>/links")
def get_node_links(session_id, node_id):
    session = core_utils.get_session(coreemu, session_id)
    node = core_utils.get_node(session, node_id)

    links_data = node.all_link_data(0)
    links = []
    for link_data in links_data:
        link = link_data._asdict()
        del link["message_type"]
        core_utils.link_data_str(link, "interface1_ip4")
        core_utils.link_data_str(link, "interface1_ip6")
        core_utils.link_data_str(link, "interface1_mac")
        core_utils.link_data_str(link, "interface2_ip4")
        core_utils.link_data_str(link, "interface2_ip6")
        core_utils.link_data_str(link, "interface2_mac")
        links.append(link)

    return jsonify(links=links)
