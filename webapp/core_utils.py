from bottle import abort


def get_session(coreemu, session_id):
    session = coreemu.sessions.get(session_id)
    if not session:
        abort(404, "session does not exist")
    return session


def get_node(session, node_id):
    if node_id.isdigit():
        node_id = int(node_id)
    node = session.objects.get(node_id)
    if not node:
        abort(404, "node does not exist")
    return node


def get_node_id(node_id):
    if node_id.isdigit():
        node_id = int(node_id)
    return node_id
