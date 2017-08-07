from xml.dom.minidom import Node

from core import logger
from core.netns import nodes


def add_elements_from_list(dom, parent, iterable, name, attr_name):
    """
    XML helper to iterate through a list and add items to parent using tags
    of the given name and the item value as an attribute named attr_name.
    Example: addelementsfromlist(dom, parent, ('a','b','c'), "letter", "value")
    <parent>
      <letter value="a"/>
      <letter value="b"/>
      <letter value="c"/>
    </parent>
    """
    for item in iterable:
        element = dom.createElement(name)
        element.setAttribute(attr_name, item)
        parent.appendChild(element)


def add_text_elements_from_list(dom, parent, iterable, name, attrs):
    """
    XML helper to iterate through a list and add items to parent using tags
    of the given name, attributes specified in the attrs tuple, and having the
    text of the item within the tags.
    Example: addtextelementsfromlist(dom, parent, ('a','b','c'), "letter",
                                     (('show','True'),))
    <parent>
      <letter show="True">a</letter>
      <letter show="True">b</letter>
      <letter show="True">c</letter>
    </parent>
    """
    for item in iterable:
        element = dom.createElement(name)
        for k, v in attrs:
            element.setAttribute(k, v)
        parent.appendChild(element)
        txt = dom.createTextNode(item)
        element.appendChild(txt)


def add_text_elements_from_tuples(dom, parent, iterable, attrs=()):
    """
    XML helper to iterate through a list of tuples and add items to
    parent using tags named for the first tuple element,
    attributes specified in the attrs tuple, and having the
    text of second tuple element.
    Example: addtextelementsfromtuples(dom, parent,
                 (('first','a'),('second','b'),('third','c')),
                 (('show','True'),))
    <parent>
      <first show="True">a</first>
      <second show="True">b</second>
      <third show="True">c</third>
    </parent>
    """
    for name, value in iterable:
        element = dom.createElement(name)
        for k, v in attrs:
            element.setAttribute(k, v)
        parent.appendChild(element)
        txt = dom.createTextNode(value)
        element.appendChild(txt)


def get_text_elements_to_list(parent):
    """
    XML helper to parse child text nodes from the given parent and return
    a list of (key, value) tuples.
    """
    r = []
    for n in parent.childNodes:
        if n.nodeType != Node.ELEMENT_NODE:
            continue
        k = str(n.nodeName)
        v = ''  # sometimes want None here?
        for c in n.childNodes:
            if c.nodeType != Node.TEXT_NODE:
                continue
            v = str(c.nodeValue)
            break
        r.append((k, v))
    return r


def add_param_to_parent(dom, parent, name, value):
    """
    XML helper to add a <param name="name" value="value"/> tag to the parent
    element, when value is not None.
    """
    if value is None:
        return None
    p = dom.createElement("param")
    parent.appendChild(p)
    p.setAttribute("name", name)
    p.setAttribute("value", "%s" % value)
    return p


def add_text_param_to_parent(dom, parent, name, value):
    """
    XML helper to add a <param name="name">value</param> tag to the parent
    element, when value is not None.
    """
    if value is None:
        return None
    p = dom.createElement("param")
    parent.appendChild(p)
    p.setAttribute("name", name)
    txt = dom.createTextNode(value)
    p.appendChild(txt)
    return p


def add_param_list_to_parent(dom, parent, name, values):
    """
    XML helper to return a parameter list and optionally add it to the
    parent element:
    <paramlist name="name">
       <item value="123">
       <item value="456">
    </paramlist>
    """
    if values is None:
        return None
    p = dom.createElement("paramlist")
    if parent:
        parent.appendChild(p)
    p.setAttribute("name", name)
    for v in values:
        item = dom.createElement("item")
        item.setAttribute("value", str(v))
        p.appendChild(item)
    return p


def get_one_element(dom, name):
    e = dom.getElementsByTagName(name)
    if len(e) == 0:
        return None
    return e[0]


def iter_descendants(dom, max_depth=0):
    """
    Iterate over all descendant element nodes in breadth first order.
    Only consider nodes up to max_depth deep when max_depth is greater
    than zero.
    """
    nodes = [dom]
    depth = 0
    current_depth_nodes = 1
    next_depth_nodes = 0
    while nodes:
        n = nodes.pop(0)
        for child in n.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                yield child
                nodes.append(child)
                next_depth_nodes += 1
        current_depth_nodes -= 1
        if current_depth_nodes == 0:
            depth += 1
            if max_depth > 0 and depth == max_depth:
                return
            current_depth_nodes = next_depth_nodes
            next_depth_nodes = 0


def iter_matching_descendants(dom, match_function, max_depth=0):
    """
    Iterate over descendant elements where matchFunction(descendant)
    returns true.  Only consider nodes up to max_depth deep when
    max_depth is greater than zero.
    """
    for d in iter_descendants(dom, max_depth):
        if match_function(d):
            yield d


def iter_descendants_with_name(dom, tag_name, max_depth=0):
    """
    Iterate over descendant elements whose name is contained in
    tagName (or is named tagName if tagName is a string).  Only
    consider nodes up to max_depth deep when max_depth is greater than
    zero.
    """
    if isinstance(tag_name, basestring):
        tag_name = (tag_name,)

    def match(d):
        return d.tagName in tag_name

    return iter_matching_descendants(dom, match, max_depth)


def iter_descendants_with_attribute(dom, tag_name, attr_name, attr_value, max_depth=0):
    """
    Iterate over descendant elements whose name is contained in
    tagName (or is named tagName if tagName is a string) and have an
    attribute named attrName with value attrValue.  Only consider
    nodes up to max_depth deep when max_depth is greater than zero.
    """
    if isinstance(tag_name, basestring):
        tag_name = (tag_name,)

    def match(d):
        return d.tagName in tag_name and \
               d.getAttribute(attr_name) == attr_value

    return iter_matching_descendants(dom, match, max_depth)


def iter_children(dom, node_type):
    """
    Iterate over all child elements of the given type.
    """
    for child in dom.childNodes:
        if child.nodeType == node_type:
            yield child


def get_text_child(dom):
    """
    Return the text node of the given element.
    """
    for child in iter_children(dom, Node.TEXT_NODE):
        return str(child.nodeValue)
    return None


def get_child_text_trim(dom):
    text = get_text_child(dom)
    if text:
        text = text.strip()
    return text


def get_params_set_attrs(dom, param_names, target):
    """
    XML helper to get <param name="name" value="value"/> tags and set
    the attribute in the target object. String type is used. Target object
    attribute is unchanged if the XML attribute is not present.
    """
    params = dom.getElementsByTagName("param")
    for param in params:
        param_name = param.getAttribute("name")
        value = param.getAttribute("value")
        if value is None:
            continue  # never reached?
        if param_name in param_names:
            setattr(target, param_name, str(value))


def xml_type_to_node_class(session, type):
    """
    Helper to convert from a type string to a class name in nodes.*.
    """
    if hasattr(nodes, type):
        # TODO: remove and use a mapping to known nodes
        logger.error("using eval to retrieve node type: %s", type)
        return eval("nodes.%s" % type)
    else:
        return None


def iter_children_with_name(dom, tag_name):
    return iter_descendants_with_name(dom, tag_name, 1)


def iter_children_with_attribute(dom, tag_name, attr_name, attr_value):
    return iter_descendants_with_attribute(dom, tag_name, attr_name, attr_value, 1)


def get_first_child_by_tag_name(dom, tag_name):
    """
    Return the first child element whose name is contained in tagName
    (or is named tagName if tagName is a string).
    """
    for child in iter_children_with_name(dom, tag_name):
        return child
    return None


def get_first_child_text_by_tag_name(dom, tag_name):
    """
    Return the corresponding text of the first child element whose
    name is contained in tagName (or is named tagName if tagName is a
    string).
    """
    child = get_first_child_by_tag_name(dom, tag_name)
    if child:
        return get_text_child(child)
    return None


def get_first_child_text_trim_by_tag_name(dom, tag_name):
    text = get_first_child_text_by_tag_name(dom, tag_name)
    if text:
        text = text.strip()
    return text


def get_first_child_with_attribute(dom, tag_name, attr_name, attr_value):
    """
    Return the first child element whose name is contained in tagName
    (or is named tagName if tagName is a string) that has an attribute
    named attrName with value attrValue.
    """
    for child in \
        iter_children_with_attribute(dom, tag_name, attr_name, attr_value):
        return child
    return None


def get_first_child_text_with_attribute(dom, tag_name, attr_name, attr_value):
    """
    Return the corresponding text of the first child element whose
    name is contained in tagName (or is named tagName if tagName is a
    string) that has an attribute named attrName with value attrValue.
    """
    child = get_first_child_with_attribute(dom, tag_name, attr_name, attr_value)
    if child:
        return get_text_child(child)
    return None


def get_first_child_text_trim_with_attribute(dom, tag_name, attr_name, attr_value):
    text = get_first_child_text_with_attribute(dom, tag_name, attr_name, attr_value)
    if text:
        text = text.strip()
    return text
