"""
Serves as a global point for storing and retrieving node types needed during simulation.
"""

from core import logger

_NODE_MAP = None


def _log_map():
    global _NODE_MAP
    for key, value in _NODE_MAP.iteritems():
        name = None
        if value:
            name = value.__name__
        logger.info("node type (%s) - class (%s)", key.name, name)


def _convert_map(x, y):
    """
    Convenience method to create a human readable version of the node map to log.

    :param dict x: dictionary to reduce node items into
    :param tuple y: current node item
    :return:
    """
    x[y[0].name] = y[1]
    return x


def update_node_map(node_map):
    """
    Update the current node map with the provided node map values.


    :param dict node_map: node map to update with
    """
    global _NODE_MAP
    _NODE_MAP.update(node_map)
    _log_map()


def set_node_map(node_map):
    """
    Set the global node map that proides a consistent way to retrieve differently configured nodes.

    :param dict node_map: node map to set to
    :return: nothing
    """
    global _NODE_MAP
    _NODE_MAP = node_map
    _log_map()


def get_node_type(node_class):
    """
    Retrieve the node type given a node class.

    :param class node_class: node class to get type for
    :return: node type
    :rtype: core.enumerations.NodeTypes
    """
    global _NODE_MAP
    node_type_map = {v: k for k, v in _NODE_MAP.iteritems()}
    return node_type_map.get(node_class)


def get_node_class(node_type):
    """
    Retrieve the node class for a given node type.

    :param int node_type: node type to retrieve class for
    :return: node class
    """
    global _NODE_MAP
    return _NODE_MAP[node_type]


def is_node(obj, node_types):
    """
    Validates if an object is one of the provided node types.

    :param obj: object to check type for
    :param int|tuple|list node_types: node type(s) to check against
    :return: True if the object is one of the node types, False otherwise
    :rtype: bool
    """
    type_classes = []
    if isinstance(node_types, (tuple, list)):
        for node_type in node_types:
            type_class = get_node_class(node_type)
            type_classes.append(type_class)
    else:
        type_class = get_node_class(node_types)
        type_classes.append(type_class)

    return isinstance(obj, tuple(type_classes))
