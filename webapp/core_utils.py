import os
from functools import wraps
from threading import Lock

from bottle import abort

save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
CORE_LOCK = Lock()


def synchronized(function):
    global CORE_LOCK

    @wraps(function)
    def wrapper(*args, **kwargs):
        with CORE_LOCK:
            return function(*args, **kwargs)

    return wrapper


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


def link_data_str(link, key):
    value = link.get(key)
    if value is not None:
        link[key] = str(value)


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
