#
# CORE
# Copyright (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
Helpers for loading and saving XML files. savesessionxml(session, filename) is
the main public interface here.
'''
import os, pwd
from xml.dom.minidom import parse, Document, Node
from core.netns import nodes
from core.api import coreapi

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

class CoreDocumentParser(object):
    def __init__(self, session, filename, start=False,
                 nodecls=nodes.CoreNode):
        self.session = session
        self.verbose = self.session.getcfgitembool('verbose', False)
        self.filename = filename
        self.dom = parse(filename)
        self.start = start
        self.nodecls = nodecls
        
        #self.scenario = getoneelement(self.dom, "Scenario")
        self.np = getoneelement(self.dom, "NetworkPlan")
        if self.np is None:
            raise ValueError, "missing NetworkPlan!"
        self.mp = getoneelement(self.dom, "MotionPlan")
        self.sp = getoneelement(self.dom, "ServicePlan")
        self.meta = getoneelement(self.dom, "CoreMetaData")
        
        self.coords = self.getmotiondict(self.mp)
        # link parameters parsed in parsenets(), applied in parsenodes()
        self.linkparams = {}
        
        self.parsedefaultservices()
        self.parseorigin()
        self.parsenets()
        self.parsenodes()
        self.parseservices()
        self.parsemeta()

        
    def warn(self, msg):
        if self.session:
            warnstr = "XML parsing '%s':" % (self.filename)
            self.session.warn("%s %s" % (warnstr, msg))
        
    def getmotiondict(self, mp):
        ''' Parse a MotionPlan into a dict with node names for keys and coordinates
        for values.
        '''
        if mp is None:
            return {}
        coords = {}
        for node in mp.getElementsByTagName("Node"):
            nodename = str(node.getAttribute("name"))
            if nodename == '':
                continue
            for m in node.getElementsByTagName("motion"):
                if m.getAttribute("type") != "stationary":
                    continue
                point = m.getElementsByTagName("point")
                if len(point) == 0:
                    continue
                txt = point[0].firstChild
                if txt is None:
                    continue
                xyz = map(int, txt.nodeValue.split(','))
                z = None
                x, y = xyz[0:2]
                if (len(xyz) == 3):
                    z = xyz[2]
                coords[nodename] = (x, y, z)
        return coords

    @staticmethod
    def getcommonattributes(obj):
        ''' Helper to return tuple of attributes common to nodes and nets. 
        '''
        id = int(obj.getAttribute("id"))
        name = str(obj.getAttribute("name"))
        type = str(obj.getAttribute("type"))
        return(id, name, type)
        
    def parsenets(self):
        linkednets = []
        for net in self.np.getElementsByTagName("NetworkDefinition"):
            id, name, type = self.getcommonattributes(net)
            nodecls = xmltypetonodeclass(self.session, type)
            if not nodecls:
                self.warn("skipping unknown network node '%s' type '%s'" % \
                          (name, type))
                continue
            n = self.session.addobj(cls = nodecls, objid = id, name = name,
                                    start = self.start)
            if name in self.coords:
                x, y, z = self.coords[name]
                n.setposition(x, y, z)
            getparamssetattrs(net, ("icon", "canvas", "opaque"), n)
            if hasattr(n, "canvas") and n.canvas is not None:
                n.canvas = int(n.canvas)
            # links between two nets (e.g. switch-switch)
            for ifc in net.getElementsByTagName("interface"):
                netid = str(ifc.getAttribute("net"))
                ifcname = str(ifc.getAttribute("name"))
                linkednets.append((n, netid, ifcname))
            self.parsemodels(net, n)
        # link networks together now that they all have been parsed
        for (n, netid, ifcname) in linkednets:
            try:
                n2 = n.session.objbyname(netid)
            except KeyError:
                n.warn("skipping net %s interface: unknown net %s" % \
                          (n.name, netid))
                continue
            upstream = False
            netif = n.getlinknetif(n2)
            if netif is None:
                netif = n2.linknet(n)
            else:
                netif.swapparams('_params_up')
                upstream = True
            key = (n2.name,  ifcname)
            if key in self.linkparams:
                for (k, v) in self.linkparams[key]:
                    netif.setparam(k, v)
            if upstream:
                netif.swapparams('_params_up')
    
    def parsenodes(self):
        for node in self.np.getElementsByTagName("Node"):
            id, name, type = self.getcommonattributes(node)
            if type == "rj45":
                nodecls = nodes.RJ45Node
            else:
                nodecls = self.nodecls
            n = self.session.addobj(cls = nodecls, objid = id, name = name,
                                    start = self.start)
            if name in self.coords:
                x, y, z = self.coords[name]
                n.setposition(x, y, z)
            n.type = type
            getparamssetattrs(node, ("icon", "canvas", "opaque"), n)
            if hasattr(n, "canvas") and n.canvas is not None:
                n.canvas = int(n.canvas)
            for ifc in node.getElementsByTagName("interface"):
                self.parseinterface(n, ifc)
    
    def parseinterface(self, n, ifc):
        '''  Parse a interface block such as:
        <interface name="eth0" net="37278">
            <address type="mac">00:00:00:aa:00:01</address>
            <address>10.0.0.2/24</address>
            <address>2001::2/64</address>
        </interface>
        '''
        name = str(ifc.getAttribute("name"))
        netid = str(ifc.getAttribute("net"))
        hwaddr = None
        addrlist = []
        try:
            net = n.session.objbyname(netid)
        except KeyError:
            n.warn("skipping node %s interface %s: unknown net %s" % \
                      (n.name, name, netid))
            return
        for addr in ifc.getElementsByTagName("address"):
            addrstr = gettextchild(addr)
            if addrstr is None:
                continue
            if addr.getAttribute("type") == "mac":
                hwaddr = addrstr
            else:
                addrlist.append(addrstr)
        i = n.newnetif(net, addrlist = addrlist, hwaddr = hwaddr,
                       ifindex = None, ifname = name)
        for model in ifc.getElementsByTagName("model"):
            self.parsemodel(model, n, n.objid)
        key = (n.name, name)
        if key in self.linkparams:
            netif = n.netif(i)
            for (k, v) in self.linkparams[key]:
                netif.setparam(k, v)
    
    def parsemodels(self, dom, obj):
        ''' Mobility/wireless model config is stored in a ConfigurableManager's
        config dict.
        '''
        nodenum = int(dom.getAttribute("id"))
        for model in dom.getElementsByTagName("model"):
            self.parsemodel(model, obj, nodenum)
    
    def parsemodel(self, model, obj, nodenum):
        ''' Mobility/wireless model config is stored in a ConfigurableManager's
        config dict.
        '''
        name = model.getAttribute("name")
        if name == '':
            return
        type = model.getAttribute("type")
        # convert child text nodes into key=value pairs
        kvs = gettextelementstolist(model)
            
        mgr = self.session.mobility
        # TODO: the session.confobj() mechanism could be more generic;
        #       it only allows registering Conf Message callbacks, but here
        #       we want access to the ConfigurableManager, not the callback
        if name[:5] == "emane":
            mgr = self.session.emane
        elif name[:5] == "netem":
            mgr = None
            self.parsenetem(model, obj, kvs)

        elif name[:3] == "xen":
            mgr = self.session.xen
        # TODO: assign other config managers here
        if mgr:
            mgr.setconfig_keyvalues(nodenum, name, kvs)
        
    def parsenetem(self, model, obj, kvs):
        ''' Determine interface and invoke setparam() using the parsed
        (key, value) pairs.
        '''
        ifname = model.getAttribute("netif")
        peer = model.getAttribute("peer")
        key = (peer, ifname)
        # nodes and interfaces do not exist yet, at this point of the parsing,
        # save (key, value) pairs for later
        try:
            #kvs = map(lambda(k, v): (int(v)), kvs)
            kvs = map(self.numericvalue, kvs)
        except ValueError:
            self.warn("error parsing link parameters for '%s' on '%s'" % \
                      (ifname, peer))
        self.linkparams[key] = kvs
    
    @staticmethod
    def numericvalue(keyvalue):
        (key, value) = keyvalue
        if '.' in str(value):
            value = float(value)
        else:
            value = int(value)
        return (key, value)

    def parseorigin(self):
        ''' Parse any origin tag from the Mobility Plan and set the CoreLocation
            reference point appropriately.
        '''
        origin = getoneelement(self.mp, "origin")
        if not origin:
            return
        location = self.session.location
        geo = []
        attrs = ("lat","lon","alt")
        for i in xrange(3):
            a = origin.getAttribute(attrs[i])
            if a is not None:
                a = float(a)
            geo.append(a)
        location.setrefgeo(geo[0], geo[1], geo[2])
        scale = origin.getAttribute("scale100")
        if scale is not None:
            location.refscale = float(scale)
        point = getoneelement(origin, "point")
        if point is not None and point.firstChild is not None:
            xyz = point.firstChild.nodeValue.split(',')
            if len(xyz) == 2:
                xyz.append('0.0')
            if len(xyz) == 3:
                xyz = map(lambda(x): float(x), xyz)
                location.refxyz = (xyz[0], xyz[1], xyz[2])
            
    def parsedefaultservices(self):
        ''' Prior to parsing nodes, use session.services manager to store
        default services for node types
        '''
        for node in self.sp.getElementsByTagName("Node"):
            type = node.getAttribute("type")
            if type == '':
                continue # node-specific service config
            services = []
            for service in node.getElementsByTagName("Service"):
                services.append(str(service.getAttribute("name")))
            self.session.services.defaultservices[type] = services
            self.session.info("default services for type %s set to %s" % \
                              (type, services))
        
    def parseservices(self):
        ''' After node objects exist, parse service customizations and add them
        to the nodes.
        '''
        svclists = {}
        # parse services and store configs into session.services.configs
        for node in self.sp.getElementsByTagName("Node"):
            name = node.getAttribute("name")
            if name == '':
                continue # node type without name
            n = self.session.objbyname(name)
            if n is None:
                self.warn("skipping service config for unknown node '%s'" % \
                          name)
                continue
            for service in node.getElementsByTagName("Service"):
                svcname = service.getAttribute("name")
                if self.parseservice(service, n):
                    if n.objid in svclists:
                        svclists[n.objid] += "|" + svcname
                    else:
                        svclists[n.objid] = svcname
        # nodes in NetworkPlan but not in ServicePlan use the 
        # default services for their type
        for node in self.np.getElementsByTagName("Node"):
            id, name, type = self.getcommonattributes(node)
            if id in svclists:
                continue # custom config exists
            else:
                svclists[int(id)] = None # use defaults

        # associate nodes with services
        for objid in sorted(svclists.keys()):
            n = self.session.obj(objid)
            self.session.services.addservicestonode(node=n, nodetype=n.type,
                                                services_str=svclists[objid],
                                                verbose=self.verbose)
                
    def parseservice(self, service, n):
        ''' Use session.services manager to store service customizations before
        they are added to a node.
        '''
        name = service.getAttribute("name")
        svc = self.session.services.getservicebyname(name)
        if svc is None:
            return False
        values = []
        startup_idx = service.getAttribute("startup_idx")
        if startup_idx is not None:
            values.append("startidx=%s" % startup_idx)
        startup_time = service.getAttribute("start_time")
        if startup_time is not None:
            values.append("starttime=%s" % startup_time)
        dirs = []
        for dir in service.getElementsByTagName("Directory"):
            dirname = dir.getAttribute("name")
            dirs.append(dirname)
        if len(dirs):
            values.append("dirs=%s" % dirs)
        
        startup = []
        shutdown = []
        validate = []
        for cmd in service.getElementsByTagName("Command"):
            type = cmd.getAttribute("type")
            cmdstr = gettextchild(cmd)
            if cmdstr is None:
                continue
            if type == "start":
                startup.append(cmdstr)
            elif type == "stop":
                shutdown.append(cmdstr)
            elif type == "validate":
                validate.append(cmdstr)
        if len(startup):
            values.append("cmdup=%s" % startup)
        if len(shutdown):
            values.append("cmddown=%s" % shutdown)
        if len(validate):
            values.append("cmdval=%s" % validate)
            
        files = []
        for file in service.getElementsByTagName("File"):
            filename = file.getAttribute("name")
            files.append(filename)
            data = gettextchild(file)
            typestr = "service:%s:%s" % (name, filename)
            self.session.services.setservicefile(nodenum=n.objid, type=typestr,
                                                 filename=filename,
                                                 srcname=None, data=data)
        if len(files):
            values.append("files=%s" % files)
        if not bool(service.getAttribute("custom")):
            return True
        self.session.services.setcustomservice(n.objid, svc, values)
        return True
    
    def parsehooks(self, hooks):
        ''' Parse hook scripts from XML into session._hooks.
        '''
        for hook in hooks.getElementsByTagName("Hook"):
            filename = hook.getAttribute("name")
            state = hook.getAttribute("state")
            data = gettextchild(hook)
            if data is None:
                data = "" # allow for empty file
            type = "hook:%s" % state
            self.session.sethook(type, filename=filename,
                                 srcname=None, data=data)
        
    def parsemeta(self):
        opt = getoneelement(self.meta, "SessionOptions")
        if opt:
            for param in opt.getElementsByTagName("param"):
                k = str(param.getAttribute("name"))
                v = str(param.getAttribute("value"))
                if v == '':
                    v = gettextchild(param) # allow attribute/text for newlines
                setattr(self.session.options, k, v)
        hooks = getoneelement(self.meta, "Hooks")
        if hooks:
            self.parsehooks(hooks)
        meta = getoneelement(self.meta, "MetaData")
        if meta:
            for param in meta.getElementsByTagName("param"):
                k = str(param.getAttribute("name"))
                v = str(param.getAttribute("value"))
                if v == '':
                    v = gettextchild(param)
                self.session.metadata.additem(k, v)
                

class CoreDocumentWriter(Document):
    ''' Utility class for writing a CoreSession to XML. The init method builds
    an xml.dom.minidom.Document, and the writexml() method saves the XML file.
    '''
    def __init__(self, session):
        ''' Create an empty Scenario XML Document, then populate it with
        objects from the given session.
        '''
        Document.__init__(self)
        self.session = session
        self.scenario = self.createElement("Scenario")
        self.np = self.createElement("NetworkPlan")
        self.mp = self.createElement("MotionPlan")
        self.sp = self.createElement("ServicePlan")
        self.meta = self.createElement("CoreMetaData")

        self.appendChild(self.scenario)
        self.scenario.appendChild(self.np)
        self.scenario.appendChild(self.mp)
        self.scenario.appendChild(self.sp)
        self.scenario.appendChild(self.meta)
        
        self.populatefromsession()

    def populatefromsession(self):
        self.session.emane.setup() # not during runtime?
        self.addorigin()
        self.adddefaultservices()
        self.addnets()
        self.addnodes()
        self.addmetadata()
            
    def writexml(self, filename):
        self.session.info("saving session XML file %s" % filename)
        f = open(filename, "w")
        Document.writexml(self, writer=f, indent="", addindent="  ", newl="\n", \
                          encoding="UTF-8")
        f.close()
        if self.session.user is not None:
            uid = pwd.getpwnam(self.session.user).pw_uid
            gid = os.stat(self.session.sessiondir).st_gid
            os.chown(filename, uid, gid)
            
    def addnets(self):
        ''' Add PyCoreNet objects as NetworkDefinition XML elements.
        '''
        with self.session._objslock:
            for net in self.session.objs():
                if not isinstance(net, nodes.PyCoreNet):
                    continue
                self.addnet(net)

    def addnet(self, net):
        ''' Add one PyCoreNet object as a NetworkDefinition XML element.
        '''
        n = self.createElement("NetworkDefinition")
        self.np.appendChild(n)
        n.setAttribute("name", net.name)
        # could use net.brname
        n.setAttribute("id", "%s" % net.objid)
        n.setAttribute("type", "%s" % net.__class__.__name__)
        self.addnetinterfaces(n, net)
        # key used with tunnel node
        if hasattr(net, 'grekey') and net.grekey is not None:
            n.setAttribute("key", "%s" % net.grekey)
        # link parameters
        for netif in net.netifs(sort=True):
            self.addnetem(n, netif)        
        # wireless/mobility models
        modelconfigs = net.session.mobility.getmodels(net)
        modelconfigs += net.session.emane.getmodels(net)
        self.addmodels(n, modelconfigs)
        self.addposition(net)
        
    def addnetem(self, n, netif):
        ''' Similar to addmodels(); used for writing netem link effects
        parameters. TODO: Interface parameters should be moved to the model
        construct, then this separate method shouldn't be required.
        '''
        params = netif.getparams()
        if len(params) == 0:
            return
        model = self.createElement("model")
        model.setAttribute("name", "netem")
        model.setAttribute("netif", netif.name)
        if hasattr(netif, "node") and netif.node is not None:
            model.setAttribute("peer", netif.node.name)
        # link between switches uses one veth interface
        elif hasattr(netif, "othernet") and netif.othernet is not None:
            if netif.othernet.name == n.getAttribute("name"):
                model.setAttribute("peer", netif.net.name)
            else:
                model.setAttribute("peer", netif.othernet.name)
                model.setAttribute("netif", netif.localname)
            # hack used for upstream parameters for link between switches
            # (see LxBrNet.linknet())
            if netif.othernet.objid == int(n.getAttribute("id")):
                netif.swapparams('_params_up')
                params = netif.getparams()
                netif.swapparams('_params_up')
        has_params = False
        for k, v in params:
            # default netem parameters are 0 or None
            if v is None or v == 0:
                continue
            if k == "has_netem" or k == "has_tbf":
                continue
            key = self.createElement(k)
            key.appendChild(self.createTextNode("%s" % v))
            model.appendChild(key)
            has_params = True
        if has_params:
            n.appendChild(model)
        
    def addmodels(self, n, configs):
        ''' Add models from a list of model-class, config values tuples.
        '''
        for (m, conf) in configs:
            model = self.createElement("model")
            n.appendChild(model)
            model.setAttribute("name", m._name)
            type = "wireless"
            if m._type == coreapi.CORE_TLV_REG_MOBILITY:
                type = "mobility"
            model.setAttribute("type", type)
            for i, k in enumerate(m.getnames()):
                key = self.createElement(k)
                value = conf[i]
                if value is None:
                    value = ""
                key.appendChild(self.createTextNode("%s" % value))
                model.appendChild(key)

    def addnodes(self):
        ''' Add PyCoreNode objects as node XML elements.
        '''
        with self.session._objslock:
            for node in self.session.objs():
                if not isinstance(node, nodes.PyCoreNode):
                    continue
                self.addnode(node)

    def addnode(self, node):
        ''' Add a PyCoreNode object as node XML elements.
        '''
        n = self.createElement("Node")
        self.np.appendChild(n)
        n.setAttribute("name", node.name)
        n.setAttribute("id", "%s" % node.nodeid())
        if node.type:
            n.setAttribute("type", node.type)
        self.addinterfaces(n, node)
        self.addposition(node)
        addparamtoparent(self, n, "icon", node.icon)
        addparamtoparent(self, n, "canvas", node.canvas)
        self.addservices(node)
        
    def addinterfaces(self, n, node):
        ''' Add PyCoreNetIfs to node XML elements.
        '''
        for ifc in node.netifs(sort=True):
            i = self.createElement("interface")
            n.appendChild(i)
            i.setAttribute("name", ifc.name)
            netmodel = None
            if ifc.net:
                i.setAttribute("net", ifc.net.name)
                if hasattr(ifc.net, "model"):
                    netmodel = ifc.net.model
            if ifc.mtu and ifc.mtu != 1500:
                i.setAttribute("mtu", "%s" % ifc.mtu)
            # could use ifc.params, transport_type
            self.addaddresses(i, ifc)
            # per-interface models
            if netmodel and netmodel._name[:6] == "emane_":
                cfg = self.session.emane.getifcconfig(node.objid, netmodel._name,
                                                      None, ifc)
                if cfg:
                    self.addmodels(i, ((netmodel, cfg),) )


    def addnetinterfaces(self, n, net):
        ''' Similar to addinterfaces(), but only adds interface elements to the
        supplied XML node that would not otherwise appear in the Node elements.
        These are any interfaces that link two switches/hubs together.
        '''
        for ifc in net.netifs(sort=True):
            if not hasattr(ifc, "othernet") or not ifc.othernet:
                continue
            i = self.createElement("interface")
            n.appendChild(i)
            if net.objid == ifc.net.objid:
                i.setAttribute("name", ifc.localname)
                i.setAttribute("net", ifc.othernet.name)
            else:
                i.setAttribute("name", ifc.name)
                i.setAttribute("net", ifc.net.name)

    def addposition(self, node):
        ''' Add object coordinates as location XML element.
        '''
        (x,y,z) = node.position.get()
        if x is None or y is None:
            return
        # <Node name="n1">
        mpn = self.createElement("Node")
        mpn.setAttribute("name", node.name)
        self.mp.appendChild(mpn)
        
        #   <motion type="stationary">
        motion = self.createElement("motion")
        motion.setAttribute("type", "stationary")
        mpn.appendChild(motion)
        
        #       <point>$X$,$Y$,$Z$</point>
        pt = self.createElement("point")
        motion.appendChild(pt)
        coordstxt = "%s,%s" % (x,y)
        if z:
            coordstxt += ",%s" % z
        coords = self.createTextNode(coordstxt)
        pt.appendChild(coords)

    def addorigin(self):
        ''' Add origin to Motion Plan using canvas reference point.
            The CoreLocation class maintains this reference point.
        '''
        refgeo = self.session.location.refgeo
        origin = self.createElement("origin")
        attrs = ("lat","lon","alt")
        have_origin = False
        for i in xrange(3):
            if refgeo[i] is not None:
                origin.setAttribute(attrs[i], str(refgeo[i]))
                have_origin = True
        if not have_origin:
            return
        if self.session.location.refscale != 1.0: # 100 pixels = refscale m
            origin.setAttribute("scale100", str(self.session.location.refscale))
        if self.session.location.refxyz != (0.0, 0.0, 0.0):
            pt = self.createElement("point")
            origin.appendChild(pt)
            x,y,z = self.session.location.refxyz
            coordstxt = "%s,%s" % (x,y)
            if z:
                coordstxt += ",%s" % z
            coords = self.createTextNode(coordstxt)
            pt.appendChild(coords)

        self.mp.appendChild(origin)
        
    def adddefaultservices(self):
        ''' Add default services and node types to the ServicePlan.
        '''
        for type in self.session.services.defaultservices:
            defaults = self.session.services.getdefaultservices(type)
            spn = self.createElement("Node")
            spn.setAttribute("type", type)
            self.sp.appendChild(spn)
            for svc in defaults:
                s = self.createElement("Service")
                spn.appendChild(s)
                s.setAttribute("name", str(svc._name))
        
    def addservices(self, node):
        ''' Add services and their customizations to the ServicePlan.
        '''
        if len(node.services) == 0:
            return
        defaults = self.session.services.getdefaultservices(node.type)
        if node.services == defaults:
            return
        spn = self.createElement("Node")
        spn.setAttribute("name", node.name)
        self.sp.appendChild(spn)

        for svc in node.services:
            s = self.createElement("Service")
            spn.appendChild(s)
            s.setAttribute("name", str(svc._name))
            s.setAttribute("startup_idx", str(svc._startindex))
            if svc._starttime != "":
                s.setAttribute("start_time", str(svc._starttime))
            # only record service names if not a customized service
            if not svc._custom:
                continue
            s.setAttribute("custom", str(svc._custom))
            addelementsfromlist(self, s, svc._dirs, "Directory", "name")
            
            for fn in svc._configs:
                if len(fn) == 0:
                    continue
                f = self.createElement("File")
                f.setAttribute("name", fn)
                # all file names are added to determine when a file has been deleted
                s.appendChild(f)
                data = self.session.services.getservicefiledata(svc, fn)
                if data is None:
                    # this includes only customized file contents and skips
                    # the auto-generated files
                    continue
                txt = self.createTextNode(data)
                f.appendChild(txt)
                    
            addtextelementsfromlist(self, s, svc._startup, "Command",
                                    (("type","start"),))
            addtextelementsfromlist(self, s, svc._shutdown, "Command",
                                    (("type","stop"),))
            addtextelementsfromlist(self, s, svc._validate, "Command",
                                    (("type","validate"),))

    def addaddresses(self, i, netif):
        ''' Add MAC and IP addresses to interface XML elements.
        '''
        if netif.hwaddr:
            h = self.createElement("address")
            i.appendChild(h)
            h.setAttribute("type", "mac")
            htxt = self.createTextNode("%s" % netif.hwaddr)
            h.appendChild(htxt)
        for addr in netif.addrlist:
            a = self.createElement("address")
            i.appendChild(a)
            # a.setAttribute("type", )
            atxt = self.createTextNode("%s" % addr)
            a.appendChild(atxt)
            
    def addhooks(self):
        ''' Add hook script XML elements to the metadata tag.
        '''
        hooks = self.createElement("Hooks")
        for state in sorted(self.session._hooks.keys()):
            for (filename, data) in self.session._hooks[state]:
                hook = self.createElement("Hook")
                hook.setAttribute("name", filename)
                hook.setAttribute("state", str(state))
                txt = self.createTextNode(data)
                hook.appendChild(txt)
                hooks.appendChild(hook)
        if hooks.hasChildNodes():
            self.meta.appendChild(hooks)
            
    def addmetadata(self):
        ''' Add CORE-specific session meta-data XML elements.
        '''
        # options
        options = self.createElement("SessionOptions")
        defaults = self.session.options.getdefaultvalues()
        for i, (k, v) in enumerate(self.session.options.getkeyvaluelist()):
            if str(v) != str(defaults[i]):
                addtextparamtoparent(self, options, k, v)
                #addparamtoparent(self, options, k, v)
        if options.hasChildNodes():
            self.meta.appendChild(options)
        # hook scripts
        self.addhooks()
        # meta
        meta = self.createElement("MetaData")
        self.meta.appendChild(meta)
        for (k, v) in self.session.metadata.items():
            addtextparamtoparent(self, meta, k, v)
            #addparamtoparent(self, meta, k, v)

def opensessionxml(session, filename, start=False, nodecls=nodes.CoreNode):
    ''' Import a session from the EmulationScript XML format.
    '''
    doc = CoreDocumentParser(session, filename, start, nodecls)
    if start:
        session.name = os.path.basename(filename)
        session.filename = filename
        session.node_count = str(session.getnodecount())
        session.instantiate()

def savesessionxml(session, filename):
    ''' Export a session to the EmulationScript XML format.
    '''
    doc = CoreDocumentWriter(session)
    doc.writexml(filename)

