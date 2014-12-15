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
    
def gettextchild(dom):
    # this could be improved to skip XML comments
    child = dom.firstChild
    if child is not None and child.nodeType == Node.TEXT_NODE:
        return str(child.nodeValue)
    return None
    
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
