from flask import jsonify
from flask import request
from flask.blueprints import Blueprint

import core_utils
from core import logger
from core.emulator.emudata import LinkOptions, InterfaceData
from core.enumerations import LinkTypes

coreemu = None

api = Blueprint("links_api", __name__)


@api.route("/sessions/<int:session_id>/links", methods=["POST"])
@core_utils.synchronized
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


@api.route("/sessions/<int:session_id>/links", methods=["PUT"])
@core_utils.synchronized
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


@api.route("/sessions/<int:session_id>/links", methods=["DELETE"])
@core_utils.synchronized
def delete_link(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json()
    node_one = data.get("node_one")
    node_two = data.get("node_two")
    interface_one = data.get("interface_one")
    interface_two = data.get("interface_two")
    session.delete_link(node_one, node_two, interface_one, interface_two)
    return jsonify()
