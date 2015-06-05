#
# CORE
# Copyright (c)2011-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#

from core.netns import nodes
from xml.dom.minidom import parse
from xmlutils import *

class CoreDocumentParser0(object):
    def __init__(self, session, filename, options):
        self.session = session
        self.verbose = self.session.getcfgitembool('verbose', False)
        self.filename = filename
        if 'dom' in options:
            # this prevents parsing twice when detecting file versions
            self.dom = options['dom']
        else:
            self.dom = parse(filename)
        self.start = options['start']
        self.nodecls = options['nodecls']

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
