#
# CORE
# Copyright (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#

from core.netns import nodes
from xml.dom.minidom import Node

def addelementsfromlist(dom, parent, iterable, name, attr_name):
    ''' XML helper to iterate through a list and add items to parent using tags
    of the given name and the item value as an attribute named attr_name.
    Example: addelementsfromlist(dom, parent, ('a','b','c'), "letter", "value")
    <parent>
      <letter value="a"/>
      <letter value="b"/>
      <letter value="c"/>
    </parent>
    '''
    for item in iterable:
        element = dom.createElement(name)
        element.setAttribute(attr_name, item)
        parent.appendChild(element)

def addtextelementsfromlist(dom, parent, iterable, name, attrs):
    ''' XML helper to iterate through a list and add items to parent using tags
    of the given name, attributes specified in the attrs tuple, and having the
    text of the item within the tags.
    Example: addtextelementsfromlist(dom, parent, ('a','b','c'), "letter",
                                     (('show','True'),))
    <parent>
      <letter show="True">a</letter>
      <letter show="True">b</letter>
      <letter show="True">c</letter>
    </parent>
    '''
    for item in iterable:
        element = dom.createElement(name)
        for k,v in attrs:
            element.setAttribute(k, v)
        parent.appendChild(element)
        txt = dom.createTextNode(item)
        element.appendChild(txt)

def addtextelementsfromtuples(dom, parent, iterable, attrs=()):
    ''' XML helper to iterate through a list of tuples and add items to
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
    '''
    for name, value in iterable:
        element = dom.createElement(name)
        for k,v in attrs:
            element.setAttribute(k, v)
        parent.appendChild(element)
        txt = dom.createTextNode(value)
        element.appendChild(txt)

def gettextelementstolist(parent):
    ''' XML helper to parse child text nodes from the given parent and return
    a list of (key, value) tuples.
    '''
    r = []
    for n in parent.childNodes:
        if n.nodeType != Node.ELEMENT_NODE:
            continue
        k = str(n.nodeName)
        v = '' # sometimes want None here?
        for c in n.childNodes:
            if c.nodeType != Node.TEXT_NODE:
                continue
            v = str(c.nodeValue)
            break
        r.append((k,v))
    return r

def addparamtoparent(dom, parent, name, value):
    ''' XML helper to add a <param name="name" value="value"/> tag to the parent
    element, when value is not None.
    '''
    if value is None:
        return None
    p = dom.createElement("param")
    parent.appendChild(p)
    p.setAttribute("name", name)
    p.setAttribute("value", "%s" % value)
    return p

def addtextparamtoparent(dom, parent, name, value):
    ''' XML helper to add a <param name="name">value</param> tag to the parent
    element, when value is not None.
    '''
    if value is None:
        return None
    p = dom.createElement("param")
    parent.appendChild(p)
    p.setAttribute("name", name)
    txt = dom.createTextNode(value)
    p.appendChild(txt)
    return p

def addparamlisttoparent(dom, parent, name, values):
    ''' XML helper to return a parameter list and optionally add it to the
    parent element:
    <paramlist name="name">
       <item value="123">
       <item value="456">
    </paramlist>
    '''
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

def getoneelement(dom, name):
    e = dom.getElementsByTagName(name)
    if len(e) == 0:
        return None
    return e[0]

def iterDescendants(dom, max_depth = 0):
    '''\
    Iterate over all descendant element nodes in breadth first order.
    Only consider nodes up to max_depth deep when max_depth is greater
    than zero.
    '''
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

def iterMatchingDescendants(dom, matchFunction, max_depth = 0):
    '''\
    Iterate over descendant elements where matchFunction(descendant)
    returns true.  Only consider nodes up to max_depth deep when
    max_depth is greater than zero.
    '''
    for d in iterDescendants(dom, max_depth):
        if matchFunction(d):
            yield d

def iterDescendantsWithName(dom, tagName, max_depth = 0):
    '''\
    Iterate over descendant elements whose name is contained in
    tagName (or is named tagName if tagName is a string).  Only
    consider nodes up to max_depth deep when max_depth is greater than
    zero.
    '''
    if isinstance(tagName, basestring):
        tagName = (tagName,)
    def match(d):
        return d.tagName in tagName
    return iterMatchingDescendants(dom, match, max_depth)

def iterDescendantsWithAttribute(dom, tagName, attrName, attrValue,
                                 max_depth = 0):
    '''\
    Iterate over descendant elements whose name is contained in
    tagName (or is named tagName if tagName is a string) and have an
    attribute named attrName with value attrValue.  Only consider
    nodes up to max_depth deep when max_depth is greater than zero.
    '''
    if isinstance(tagName, basestring):
        tagName = (tagName,)
    def match(d):
        return d.tagName in tagName and \
            d.getAttribute(attrName) == attrValue
    return iterMatchingDescendants(dom, match, max_depth)

def iterChildren(dom, nodeType):
    '''\
    Iterate over all child elements of the given type.
    '''
    for child in dom.childNodes:
        if child.nodeType == nodeType:
            yield child

def gettextchild(dom):
    '''\
    Return the text node of the given element.
    '''
    for child in iterChildren(dom, Node.TEXT_NODE):
        return str(child.nodeValue)
    return None

def getChildTextTrim(dom):
    text = gettextchild(dom)
    if text:
        text = text.strip()
    return text

def getparamssetattrs(dom, param_names, target):
    ''' XML helper to get <param name="name" value="value"/> tags and set
    the attribute in the target object. String type is used. Target object
    attribute is unchanged if the XML attribute is not present.
    '''
    params = dom.getElementsByTagName("param")
    for param in params:
        param_name = param.getAttribute("name")
        value = param.getAttribute("value")
        if value is None:
            continue # never reached?
        if param_name in param_names:
            setattr(target, param_name, str(value))

def xmltypetonodeclass(session, type):
    ''' Helper to convert from a type string to a class name in nodes.*.
    '''
    if hasattr(nodes, type):
        return eval("nodes.%s" % type)
    else:
        return None

def iterChildrenWithName(dom, tagName):
    return iterDescendantsWithName(dom, tagName, 1)

def iterChildrenWithAttribute(dom, tagName, attrName, attrValue):
    return iterDescendantsWithAttribute(dom, tagName, attrName, attrValue, 1)

def getFirstChildByTagName(dom, tagName):
    '''\
    Return the first child element whose name is contained in tagName
    (or is named tagName if tagName is a string).
    '''
    for child in iterChildrenWithName(dom, tagName):
        return child
    return None

def getFirstChildTextByTagName(dom, tagName):
    '''\
    Return the corresponding text of the first child element whose
    name is contained in tagName (or is named tagName if tagName is a
    string).
    '''
    child = getFirstChildByTagName(dom, tagName)
    if child:
        return gettextchild(child)
    return None

def getFirstChildTextTrimByTagName(dom, tagName):
    text = getFirstChildTextByTagName(dom, tagName)
    if text:
        text = text.strip()
    return text

def getFirstChildWithAttribute(dom, tagName, attrName, attrValue):
    '''\
    Return the first child element whose name is contained in tagName
    (or is named tagName if tagName is a string) that has an attribute
    named attrName with value attrValue.
    '''
    for child in \
            iterChildrenWithAttribute(dom, tagName, attrName, attrValue):
        return child
    return None

def getFirstChildTextWithAttribute(dom, tagName, attrName, attrValue):
    '''\
    Return the corresponding text of the first child element whose
    name is contained in tagName (or is named tagName if tagName is a
    string) that has an attribute named attrName with value attrValue.
    '''
    child = getFirstChildWithAttribute(dom, tagName, attrName, attrValue)
    if child:
        return gettextchild(child)
    return None

def getFirstChildTextTrimWithAttribute(dom, tagName, attrName, attrValue):
    text = getFirstChildTextWithAttribute(dom, tagName, attrName, attrValue)
    if text:
        text = text.strip()
    return text
