"""
Serves as a global point for storing and retrieving node types needed during simulation.
"""

import pprint

from core.misc import log

logger = log.get_logger(__name__)

_NODE_MAP = None


def _convert_map(x, y):
    x[y[0].name] = y[1]
    return x


def set_node_map(node_map):
    global _NODE_MAP
    print_map = reduce(lambda x, y: _convert_map(x, y), node_map.items(), {})
    logger.info("setting node class map: \n%s", pprint.pformat(print_map, indent=4))
    _NODE_MAP = node_map


def get_node_class(node_type):
    global _NODE_MAP
    return _NODE_MAP[node_type]


def is_node(obj, node_types):
    type_classes = []
    if isinstance(node_types, (tuple, list)):
        for node_type in node_types:
            type_class = get_node_class(node_type)
            type_classes.append(type_class)
    else:
        type_class = get_node_class(node_types)
        type_classes.append(type_class)

    return isinstance(obj, tuple(type_classes))
