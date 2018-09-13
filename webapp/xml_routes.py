import tempfile

from flask import jsonify
from flask import request
from flask import send_file
from flask.blueprints import Blueprint

from core import logger
from core.enumerations import EventTypes

coreemu = None

api = Blueprint("xml_api", __name__)


@api.route("/sessions/<int:session_id>/xml")
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


@api.route("/sessions/xml", methods=["POST"])
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
