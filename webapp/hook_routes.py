from flask import jsonify
from flask import request
from flask.blueprints import Blueprint

import core_utils

coreemu = None

api = Blueprint("hooks_api", __name__)


@api.route("/sessions/<int:session_id>/hooks", methods=["POST"])
def add_hook(session_id):
    session = core_utils.get_session(coreemu, session_id)
    data = request.get_json() or {}
    state = data["state"]
    file_name = data["file"]
    file_data = data["data"]
    session.add_hook(state, file_name, None, file_data)
    return jsonify()


@api.route("/sessions/<int:session_id>/hooks")
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
