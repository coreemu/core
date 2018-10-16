import os

from flask import Flask
from flask import jsonify
from flask import request
from werkzeug.exceptions import HTTPException

import core_utils
import emane_routes
import hook_routes
import link_routes
import mobility_routes
import node_routes
import service_routes
import session_routes
import websocket_routes
import wlan_routes
import xml_routes
from core.emulator.coreemu import CoreEmu
from core.misc.ipaddress import Ipv4Prefix, Ipv6Prefix

coreemu = CoreEmu()

app = Flask(__name__)
app.config["SECRET_KEY"] = "core"
websocket_routes.register(app)


def register_blueprint(blueprint):
    """
    Register api module and set coreemu object.

    :param module blueprint: module that defines api routes
    :return: nothing
    """
    blueprint.coreemu = coreemu
    app.register_blueprint(blueprint.api)


register_blueprint(emane_routes)
register_blueprint(hook_routes)
register_blueprint(link_routes)
register_blueprint(mobility_routes)
register_blueprint(node_routes)
register_blueprint(service_routes)
register_blueprint(session_routes)
register_blueprint(wlan_routes)
register_blueprint(xml_routes)


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


@app.route("/upload", methods=["POST"])
def upload():
    if not os.path.exists(core_utils.save_dir):
        os.mkdir(core_utils.save_dir, 755)
    upload_file = request.files["file"]
    save_path = os.path.join(core_utils.save_dir, upload_file.filename)
    upload_file.save(save_path)
    return jsonify()


@app.errorhandler(HTTPException)
def handle_error(e):
    return jsonify(message=e.description, status=e.code), e.code


if __name__ == "__main__":
    websocket_routes.socketio.run(app, host="0.0.0.0", debug=True)
