#
# CORE
# Copyright (c)2011-2015 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# Created on Dec 18, 2014
#
# @author: santiago
#

import os
import pwd
import collections
from core.netns import nodes
from core.api import coreapi
from core.misc.ipaddr import *

from xml.dom.minidom import Document
from xmlutils import *
from xmldeployment import CoreDeploymentWriter

def enum(**enums):
    return type('Enum', (), enums)

class Attrib(object):
    ''' scenario plan attribute constants
    '''
    NetType = enum(WIRELESS = 'wireless', ETHERNET = 'ethernet',
                   PTP_WIRED = 'point-to-point-wired',
                   PTP_WIRELESS = 'point-to-point-wireless')
    MembType = enum(INTERFACE = 'interface', CHANNEL = 'channel',
                    SWITCH = 'switch', HUB = 'hub', TUNNEL = 'tunnel',
                    NETWORK = "network")
    DevType = enum(HOST = 'host', ROUTER = 'router', SWITCH = 'switch',
                   HUB = 'hub')
    NodeType = enum(ROUTER = 'router', HOST = 'host', MDR = 'mdr',
                    PC = 'PC', RJ45 = 'rj45')
    Alias = enum(ID = "COREID")

''' A link endpoint in CORE
net: the network that the endpoint belongs to
netif: the network interface at this end
id: the identifier for the endpoint
l2devport: if the other end is a layer 2 device, this is the assigned port in that device
params: link/interface parameters
'''
Endpoint = collections.namedtuple('Endpoint',
                                  ['net', 'netif', 'type', 'id', 'l2devport', 'params'])



class CoreDocumentWriter1(Document):
    ''' Utility class for writing a CoreSession to XML in the NMF scenPlan schema. The init
    method builds an xml.dom.minidom.Document, and the writexml() method saves the XML file.
    '''

    def __init__(self, session):
        ''' Create an empty Scenario XML Document, then populate it with
        objects from the given session.
        '''
        Document.__init__(self)
        session.info('Exporting to NMF XML version 1.0')
        with session._objslock:
            self.scenarioPlan = ScenarioPlan(self, session)
            if session.getstate() == coreapi.CORE_EVENT_RUNTIME_STATE:
                deployment = CoreDeploymentWriter(self, self.scenarioPlan,
                                                  session)
                deployment.add_deployment()
                self.scenarioPlan.setAttribute('deployed', 'true')

    def writexml(self, filename):
        ''' Commit to file
        '''
        self.scenarioPlan.coreSession.info("saving session XML file %s" % filename)
        f = open(filename, "w")
        Document.writexml(self, writer=f, indent="", addindent="  ", newl="\n", \
                          encoding="UTF-8")
        f.close()
        if self.scenarioPlan.coreSession.user is not None:
            uid = pwd.getpwnam(self.scenarioPlan.coreSession.user).pw_uid
            gid = os.stat(self.scenarioPlan.coreSession.sessiondir).st_gid
            os.chown(filename, uid, gid)


class XmlElement(object):
    ''' The base class for all XML elements in the scenario plan. Includes
    convenience functions.
    '''
    def __init__(self, document, parent, elementType):
        self.document = document
        self.parent = parent
        self.baseEle = document.createElement("%s" % elementType)
        if self.parent is not None:
            self.parent.appendChild(self.baseEle)

    def createElement(self, elementTag):
        return self.document.createElement(elementTag)

    def getTagName(self):
        return self.baseEle.tagName

    def createTextNode(self, nodeTag):
        return self.document.createTextNode(nodeTag)

    def appendChild(self, child):
        if isinstance(child, XmlElement):
            self.baseEle.appendChild(child.baseEle)
        else:
            self.baseEle.appendChild(child)

    @staticmethod
    def add_parameter(doc, parent, key, value):
        if key and value:
            parm = doc.createElement("parameter")
            parm.setAttribute("name", str(key))
            parm.appendChild(doc.createTextNode(str(value)))
            parent.appendChild(parm)

    def addParameter(self, key, value):
        '''
        Add a parameter to the xml element
        '''
        self.add_parameter(self.document, self, key, value)

    def setAttribute(self, name, val):
        self.baseEle.setAttribute(name, val)

    def getAttribute(self, name):
        return self.baseEle.getAttribute(name)


class NamedXmlElement(XmlElement):
    ''' The base class for all "named" xml elements. Named elements are
    xml elements in the scenario plan that have an id and a name attribute.
    '''
    def __init__(self, scenPlan, parent, elementType, elementName):
        XmlElement.__init__(self, scenPlan.document, parent, elementType)

        self.scenPlan = scenPlan
        self.coreSession = scenPlan.coreSession

        elementPath = ''
        self.id=None
        if self.parent is not None and isinstance(self.parent, XmlElement) and self.parent.getTagName() != "scenario":
            elementPath="%s/" % self.parent.getAttribute("id")

        self.id = "%s%s" % (elementPath,elementName)
        self.setAttribute("name", elementName)
        self.setAttribute("id", self.id)


    def addPoint(self, coreObj):
        ''' Add position to an object
        '''
        (x,y,z) = coreObj.position.get()
        if x is None or y is None:
            return
        lat, lon, alt = self.coreSession.location.getgeo(x, y, z)

        pt = self.createElement("point")
        pt.setAttribute("type", "gps")
        pt.setAttribute("lat", "%s" % lat)
        pt.setAttribute("lon", "%s" % lon)
        if z:
            pt.setAttribute("z", "%s" % alt)
        self.appendChild(pt)

    def createAlias(self, domain, valueStr):
        ''' Create an alias element for CORE specific information
        '''
        a = self.createElement("alias")
        a.setAttribute("domain", "%s" % domain)
        a.appendChild(self.createTextNode(valueStr))
        return a





class ScenarioPlan(XmlElement):
    ''' Container class for ScenarioPlan.
    '''
    def __init__(self, document, session):
        XmlElement.__init__(self, document, parent=document, elementType='scenario')

        self.coreSession = session

        self.setAttribute('version', '1.0')
        self.setAttribute("name", "%s" % session.name)

        self.setAttribute('xmlns', 'nmfPlan')
        self.setAttribute('xmlns:CORE', 'coreSpecific')
        self.setAttribute('compiled', 'true')

        self.allChannelMembers = dict()
        self.lastNetIdx = 0
        self.addNetworks()
        self.addDevices()

        # XXX Do we need these?
        #self.session.emane.setup() # not during runtime?
        #self.addorigin()

        self.addDefaultServices()

        self.addSessionConfiguration()



    def addNetworks(self):
        ''' Add networks in the session to the scenPlan.
        '''
        for net in self.coreSession.objs():
            if not isinstance(net, nodes.PyCoreNet):
                continue

            if isinstance(net, nodes.CtrlNet):
                continue

            # Do not add switches and hubs that belong to another network
            if isinstance(net, (nodes.SwitchNode, nodes.HubNode)):
                if inOtherNetwork(net):
                    continue

            try:
                NetworkElement(self, self, net)
            except:
                if hasattr(net, "name") and net.name:
                    self.coreSession.warn('Unsupported net: %s' % net.name)
                else:
                    self.coreSession.warn('Unsupported net: %s' % net.__class__.__name__)
                

    def addDevices(self):
        ''' Add device elements to the scenario plan.
        '''
        for node in self.coreSession.objs():
            if not isinstance(node, (nodes.PyCoreNode)):
                continue
            try:
                DeviceElement(self, self, node)
            except:
                if hasattr(node, "name") and node.name:
                    self.coreSession.warn('Unsupported device: %s' % node.name)
                else:
                    self.coreSession.warn('Unsupported device: %s' % node.__class__.__name__)


    def addDefaultServices(self):
        ''' Add default services and node types to the ServicePlan.
        '''
        defaultservices = self.createElement("CORE:defaultservices")
        for type in self.coreSession.services.defaultservices:
            defaults = self.coreSession.services.getdefaultservices(type)
            spn = self.createElement("device")
            spn.setAttribute("type", type)
            defaultservices.appendChild(spn)
            for svc in defaults:
                s = self.createElement("service")
                spn.appendChild(s)
                s.setAttribute("name", str(svc._name))
        if defaultservices.hasChildNodes():
            self.appendChild(defaultservices)

    def addSessionConfiguration(self):
        ''' Add CORE-specific session configuration XML elements.
        '''
        config = self.createElement("CORE:sessionconfig")

        # origin: geolocation of cartesian coordinate 0,0,0
        refgeo = self.coreSession.location.refgeo
        origin = self.createElement("origin")
        attrs = ("lat","lon","alt")
        have_origin = False
        for i in xrange(3):
            if refgeo[i] is not None:
                origin.setAttribute(attrs[i], str(refgeo[i]))
                have_origin = True
        if have_origin:
            if self.coreSession.location.refscale != 1.0: # 100 pixels = refscale m
                origin.setAttribute("scale100", str(self.coreSession.location.refscale))
            if self.coreSession.location.refxyz != (0.0, 0.0, 0.0):
                pt = self.createElement("point")
                origin.appendChild(pt)
                x,y,z = self.coreSession.location.refxyz
                coordstxt = "%s,%s" % (x,y)
                if z:
                    coordstxt += ",%s" % z
                coords = self.createTextNode(coordstxt)
                pt.appendChild(coords)
            config.appendChild(origin)


        # options
        options = self.createElement("options")
        defaults = self.coreSession.options.getdefaultvalues()
        for i, (k, v) in enumerate(self.coreSession.options.getkeyvaluelist()):
            if str(v) != str(defaults[i]):
                XmlElement.add_parameter(self.document, options, k, v)
        if options.hasChildNodes():
            config.appendChild(options)

        # hook scripts
        hooks = self.createElement("hooks")
        for state in sorted(self.coreSession._hooks.keys()):
            for (filename, data) in self.coreSession._hooks[state]:
                hook = self.createElement("hook")
                hook.setAttribute("name", filename)
                hook.setAttribute("state", str(state))
                txt = self.createTextNode(data)
                hook.appendChild(txt)
                hooks.appendChild(hook)
        if hooks.hasChildNodes():
            config.appendChild(hooks)

        # metadata
        meta = self.createElement("metadata")
        for (k, v) in self.coreSession.metadata.items():
            XmlElement.add_parameter(self.document, meta, k, v)
        if meta.hasChildNodes():
            config.appendChild(meta)

        if config.hasChildNodes():
            self.appendChild(config)


class NetworkElement(NamedXmlElement):
    def __init__(self, scenPlan, parent, netObj):
        ''' Add one PyCoreNet object as one network XML element.
        '''
        elementName = self.getNetworkName(scenPlan, netObj)
        NamedXmlElement.__init__(self, scenPlan, parent, "network", elementName)

        self.scenPlan = scenPlan

        self.addPoint(netObj)

        netType = None
        if isinstance(netObj, (nodes.WlanNode, nodes.EmaneNode)):
            netType = Attrib.NetType.WIRELESS
        elif isinstance(netObj, (nodes.SwitchNode, nodes.HubNode,
                                 nodes.PtpNet, nodes.TunnelNode)):
            netType = Attrib.NetType.ETHERNET
        else:
            netType ="%s" % netObj.__class__.__name__

        typeEle = self.createElement("type")
        typeEle.appendChild(self.createTextNode(netType))
        self.appendChild(typeEle)

        # Gather all endpoints belonging to this network
        self.endpoints = getEndpoints(netObj)

        # Special case for a network of switches and hubs
        createAlias = True
        self.l2devices = []
        if isinstance(netObj, (nodes.SwitchNode, nodes.HubNode)):
            createAlias = False
            self.appendChild(typeEle)
            self.addL2Devices(netObj)

        if createAlias:
            a = self.createAlias(Attrib.Alias.ID, "%d" % int(netObj.objid))
            self.appendChild(a)

        # XXXX TODO: Move this to  channel?
        # key used with tunnel node
        if hasattr(netObj, 'grekey') and netObj.grekey is not None:
            a = self.createAlias("COREGREKEY", "%s" % netObj.grekey)
            self.appendChild(a)

        self.addNetMembers(netObj)
        self.addChannels(netObj)

        presentationEle = self.createElement("CORE:presentation")
        addPresentationEle = False
        if netObj.icon and not netObj.icon.isspace():
            presentationEle.setAttribute("icon", netObj.icon)
            addPresentationEle = True
        if netObj.canvas:
            presentationEle.setAttribute("canvas", str(netObj.canvas))
            addPresentationEle = True
        if addPresentationEle:
            self.appendChild(presentationEle)

    def getNetworkName(self, scenPlan, netObj):
        ''' Determine the name to use for this network element
        '''
        if isinstance(netObj, (nodes.PtpNet, nodes.TunnelNode)):
            name = "net%s" % scenPlan.lastNetIdx
            scenPlan.lastNetIdx += 1
        elif netObj.name:
            name = str(netObj.name) # could use net.brname for bridges?
        elif isinstance(netObj, (nodes.SwitchNode, nodes.HubNode)):
            name = "lan%s" % netObj.objid
        else:
            name = ''
        return name


    def addL2Devices(self, netObj):
        ''' Add switches and hubs
        '''

        # Add the netObj as a device
        self.l2devices.append(DeviceElement(self.scenPlan, self, netObj))

        # Add downstream switches/hubs
        l2devs = []
        neweps = []
        for ep in self.endpoints:
            if ep.type and ep.net.objid != netObj.objid:
                l2s, eps = getDowmstreamL2Devices(ep.net)
                l2devs.extend(l2s)
                neweps.extend(eps)

        for l2dev in l2devs:
            self.l2devices.append(DeviceElement(self.scenPlan, self, l2dev))

        self.endpoints.extend(neweps)

    # XXX: Optimize later
    def addNetMembers(self, netObj):
        ''' Add members to a network XML element.
        '''

        for ep in self.endpoints:
            if ep.type:
                MemberElement(self.scenPlan, self, referencedType=ep.type, referencedId=ep.id)

                if ep.l2devport:
                    MemberElement(self.scenPlan,
                                  self,
                                  referencedType=Attrib.MembType.INTERFACE,
                                  referencedId="%s/%s" % (self.id,ep.l2devport))

        # XXX Revisit this
        # Create implied members given the network type
        if isinstance(netObj, nodes.TunnelNode):
            MemberElement(self.scenPlan,
                          self,
                          referencedType=Attrib.MembType.TUNNEL,
                          referencedId="%s/%s" % (netObj.name, netObj.name))

    # XXX: Optimize later
    def addChannels(self, netObj):
        ''' Add channels to a network XML element
        '''

        if isinstance(netObj, (nodes.WlanNode, nodes.EmaneNode)):
            modelconfigs = netObj.session.mobility.getmodels(netObj)
            modelconfigs += netObj.session.emane.getmodels(netObj)
            chan = None
            for (model, conf) in modelconfigs:
                # Handle mobility parameters below
                if model._type == coreapi.CORE_TLV_REG_MOBILITY:
                    continue

                # Create the channel
                if chan is None:
                    name = "wireless"
                    chan = ChannelElement(self.scenPlan, self, netObj,
                                          channelType=model._name,
                                          channelName=name,
                                          channelDomain="CORE")

                # Add wireless model parameters
                for i, key in enumerate(model.getnames()):
                    value = conf[i]
                    if value is not None:
                        chan.addParameter(key, model.valueof(key, conf))

            for (model, conf) in modelconfigs:
                if model._type == coreapi.CORE_TLV_REG_MOBILITY:
                    # Add wireless mobility parameters
                    mobility = XmlElement(self.scenPlan, chan, "CORE:mobility")
                    # Add a type child
                    typeEle = self.createElement("type")
                    typeEle.appendChild(self.createTextNode(model._name))
                    mobility.appendChild(typeEle)
                    for i, key in enumerate(model.getnames()):
                        value = conf[i]
                        if value is not None:
                            mobility.addParameter(key, value)

            # Add members to the channel
            if chan is not None:
                chan.addChannelMembers(self.endpoints)
                self.appendChild(chan.baseEle)
        elif isinstance(netObj, nodes.PtpNet) :
            if len(self.endpoints) < 2:
                if len(self.endpoints) == 1:
                    self.coreSession.warn('Pt2Pt network with only 1 endpoint: %s' % self.endpoints[0].id)
                else:
                    self.coreSession.warn('Pt2Pt network with no endpoints encountered in %s' % netObj.name)
                return
            name = "chan%d" % (0)
            chan = ChannelElement(self.scenPlan, self, netObj,
                                  channelType=Attrib.NetType.ETHERNET,
                                  channelName=name)

            # Add interface parameters
            if self.endpoints[0].params != self.endpoints[1].params:
                self.coreSession.warn('Pt2Pt Endpoint  parameters do not match in %s' % netObj.name)
            for key, value in self.endpoints[0].params:
                # XXX lifted from original addnetem function. revisit this.
                # default netem parameters are 0 or None
                if value is None or value == 0:
                    continue
                if key == "has_netem" or key == "has_tbf":
                    continue
                chan.addParameter(key, value)

            # Add members to the channel
            chan.addChannelMembers(self.endpoints)
            self.appendChild(chan)

        elif isinstance(netObj, (nodes.SwitchNode,
                              nodes.HubNode, nodes.TunnelNode)):
            cidx=0
            channels = []
            for ep in self.endpoints:
                # Create one channel member per ep
                if ep.type:
                    name = "chan%d" % (cidx)
                    chan = ChannelElement(self.scenPlan, self, netObj,
                                          channelType=Attrib.NetType.ETHERNET,
                                          channelName=name)

                    # Add interface parameters
                    for key, value in ep.params:
                        # XXX lifted from original addnetem function. revisit this.
                        # default netem parameters are 0 or None
                        if value is None or value == 0:
                            continue
                        if key == "has_netem" or key == "has_tbf":
                            continue
                        chan.addParameter(key, value)

                    # Add members to the channel
                    chan.addChannelMembers(ep)
                    channels.append(chan)
                    cidx += 1

            for chan in channels:
                self.appendChild(chan)




class DeviceElement(NamedXmlElement):
    ''' A device element in the scenario plan.
    '''
    def __init__(self, scenPlan, parent, devObj):
        ''' Add a PyCoreNode object as a device element.
        '''

        devType = None
        coreDevType = None
        if hasattr(devObj, "type") and devObj.type:
            coreDevType = devObj.type
            if devObj.type == Attrib.NodeType.ROUTER:
                devType = Attrib.DevType.ROUTER
            elif devObj.type == Attrib.NodeType.MDR:
                devType = Attrib.DevType.ROUTER
            elif devObj.type == Attrib.NodeType.HOST:
                devType = Attrib.DevType.HOST
            elif devObj.type == Attrib.NodeType.PC:
                devType = Attrib.DevType.HOST
            elif devObj.type == Attrib.NodeType.RJ45:
                devType = Attrib.DevType.HOST
                nodeId = "EMULATOR-HOST"
            else:
                # Default custom types (defined in ~/.core/nodes.conf) to HOST
                devType = Attrib.DevType.HOST

        if devType is None:
            if isinstance(devObj, nodes.HubNode):
                devType = Attrib.DevType.HUB
            elif isinstance(devObj, nodes.SwitchNode):
                devType = Attrib.DevType.SWITCH

        if devType is None:
            raise Exception
                

        NamedXmlElement.__init__(self, scenPlan, parent, devType, devObj.name)

        if coreDevType is not None:
            typeEle = self.createElement("type")
            typeEle.setAttribute("domain", "CORE")
            typeEle.appendChild(self.createTextNode("%s" % coreDevType))
            self.appendChild(typeEle)

        self.interfaces = []
        self.addInterfaces(devObj)
        alias = self.createAlias(Attrib.Alias.ID, "%s" % devObj.objid)
        self.appendChild(alias)
        self.addPoint(devObj)
        self.addServices(devObj)


        presentationEle = self.createElement("CORE:presentation")
        addPresentationEle = False
        if devObj.icon and not devObj.icon.isspace():
            presentationEle.setAttribute("icon", devObj.icon)
            addPresentationEle = True
        if devObj.canvas:
            presentationEle.setAttribute("canvas", str(devObj.canvas))
            addPresentationEle = True
        if addPresentationEle:
            self.appendChild(presentationEle)

    def addInterfaces(self, devObj):
        ''' Add interfaces to a device element.
        '''
        idx=0
        for ifcObj in devObj.netifs(sort=True):
            if ifcObj.net and isinstance(ifcObj.net, nodes.CtrlNet):
                continue
            if isinstance(devObj, nodes.PyCoreNode):
                ifcEle = InterfaceElement(self.scenPlan, self, devObj, ifcObj)
            else: # isinstance(node, (nodes.HubNode nodes.SwitchNode)):
                ifcEle = InterfaceElement(self.scenPlan, self, devObj, ifcObj, idx)
            idx += 1

            netmodel = None
            if ifcObj.net:
                if hasattr(ifcObj.net, "model"):
                    netmodel = ifcObj.net.model
            if ifcObj.mtu and ifcObj.mtu != 1500:
                ifcEle.setAttribute("mtu", "%s" % ifcObj.mtu)

            # The interfaces returned for Switches and Hubs are the interfaces of the nodes connected to them.
            # The addresses are for those interfaces. Don't include them here.
            if isinstance(devObj, nodes.PyCoreNode):
                # could use ifcObj.params, transport_type
                ifcEle.addAddresses(ifcObj)
                # per-interface models
                # XXX Remove???
                if netmodel and netmodel._name[:6] == "emane_":
                    cfg = self.coreSession.emane.getifcconfig(devObj.objid, netmodel._name,
                                                              None, ifcObj)
                    if cfg:
                        ifcEle.addModels(((netmodel, cfg),) )

            self.interfaces.append(ifcEle)


    def addServices(self, devObj):
        ''' Add services and their customizations to the ServicePlan.
        '''
        if not hasattr(devObj, "services") :
            return

        if len(devObj.services) == 0:
            return

        defaults = self.coreSession.services.getdefaultservices(devObj.type)
        if devObj.services == defaults:
            return
        spn = self.createElement("CORE:services")
        spn.setAttribute("name", devObj.name)
        self.appendChild(spn)

        for svc in devObj.services:
            s = self.createElement("service")
            spn.appendChild(s)
            s.setAttribute("name", str(svc._name))
            s.setAttribute("startup_idx", str(svc._startindex))
            if svc._starttime != "":
                s.setAttribute("start_time", str(svc._starttime))
            # only record service names if not a customized service
            if not svc._custom:
                continue
            s.setAttribute("custom", str(svc._custom))
            addelementsfromlist(self, s, svc._dirs, "directory", "name")

            for fn in svc._configs:
                if len(fn) == 0:
                    continue
                f = self.createElement("file")
                f.setAttribute("name", fn)
                # all file names are added to determine when a file has been deleted
                s.appendChild(f)
                data = self.coreSession.services.getservicefiledata(svc, fn)
                if data is None:
                    # this includes only customized file contents and skips
                    # the auto-generated files
                    continue
                txt = self.createTextNode("\n" + data)
                f.appendChild(txt)

            addtextelementsfromlist(self, s, svc._startup, "command",
                                    (("type","start"),))
            addtextelementsfromlist(self, s, svc._shutdown, "command",
                                    (("type","stop"),))
            addtextelementsfromlist(self, s, svc._validate, "command",
                                    (("type","validate"),))



class ChannelElement(NamedXmlElement):
    ''' A channel element in the scenario plan
    '''
    def __init__(self, scenPlan, parent, netObj, channelType, channelName, channelDomain=None):
        NamedXmlElement.__init__(self, scenPlan, parent, "channel", channelName)
        '''
        Create a channel element and append a member child referencing this channel element
        in the parent element.
        '''
        # Create a member element for this channel in the parent
        MemberElement(self.scenPlan,
                      parent,
                      referencedType=Attrib.MembType.CHANNEL,
                      referencedId=self.id)

        # Add a type child
        typeEle = self.createElement("type")
        if channelDomain is not None:
            typeEle.setAttribute("domain", "%s" % channelDomain)
        typeEle.appendChild(self.createTextNode(channelType))
        self.appendChild(typeEle)


    def addChannelMembers(self, endpoints):
        '''
        Add network channel members referencing interfaces in the channel
        '''
        if isinstance(endpoints, list):
            # A list of endpoints is given. Create one channel member per endpoint
            idx = 0
            for ep in endpoints:
                self.addChannelMember(ep.type, ep.id, idx)
                idx += 1
        else:
            # A single endpoint is given. Create one channel member for the endpoint,
            # and if the endpoint is associated with a Layer 2 device port, add the
            # port as a second member
            ep = endpoints
            self.addChannelMember(ep.type, ep.id, 0)
            if ep.l2devport is not None:
                memId = "%s/%s" % (self.parent.getAttribute("id"), ep.l2devport)
                self.addChannelMember(ep.type, memId, 1)


    def addChannelMember(self, memIfcType, memIfcId, memIdx):
        '''
        add a member to a given channel
        '''

        m = MemberElement(self.scenPlan,
                          self,
                          referencedType=memIfcType,
                          referencedId=memIfcId,
                          index=memIdx)
        self.scenPlan.allChannelMembers[memIfcId] = m



class InterfaceElement(NamedXmlElement):
    '''
    A network interface element
    '''
    def __init__(self, scenPlan, parent, devObj, ifcObj, ifcIdx=None):
        '''
        Create a network interface element with references to channel that this
        interface is used.
        '''
        elementName=None
        if ifcIdx is not None:
            elementName = "e%d" % ifcIdx
        else:
            elementName = ifcObj.name
        NamedXmlElement.__init__(self, scenPlan, parent, "interface", elementName)
        self.ifcObj = ifcObj
        self.addChannelReference()

    def addChannelReference(self):
        '''
        Add a reference to the channel that uses this interface
        '''
        try:
            cm = self.scenPlan.allChannelMembers[self.id]
            if cm is not None:
                ch = cm.baseEle.parentNode
                if ch is not None:
                    net = ch.parentNode
                    if net is not None:
                        MemberElement(self.scenPlan,
                                      self,
                                      referencedType=Attrib.MembType.CHANNEL,
                                      referencedId=ch.getAttribute("id"),
                                      index=int(cm.getAttribute("index")))
                        MemberElement(self.scenPlan,
                                      self,
                                      referencedType=Attrib.MembType.NETWORK,
                                      referencedId=net.getAttribute("id"))
        except KeyError:
            pass # Not an error. This occurs when an interface belongs to a switch or a hub within a network and the channel is yet to be defined


    def addAddresses(self, ifcObj):
        '''
        Add MAC and IP addresses to interface XML elements.
        '''
        if ifcObj.hwaddr:
            h = self.createElement("address")
            self.appendChild(h)
            h.setAttribute("type", "mac")
            htxt = self.createTextNode("%s" % ifcObj.hwaddr)
            h.appendChild(htxt)
        for addr in ifcObj.addrlist:
            a = self.createElement("address")
            self.appendChild(a)
            (ip, sep, mask)  = addr.partition('/')
            # mask = int(mask) XXX?
            if isIPv4Address(ip):
                a.setAttribute("type", "IPv4")
            else:
                a.setAttribute("type", "IPv6")

            # a.setAttribute("type", )
            atxt = self.createTextNode("%s" % addr)
            a.appendChild(atxt)


    # XXX Remove?
    def addModels(self, configs):
        '''
        Add models from a list of model-class, config values tuples.
        '''
        for (m, conf) in configs:
            modelEle = self.createElement("model")
            modelEle.setAttribute("name", m._name)
            typeStr = "wireless"
            if m._type == coreapi.CORE_TLV_REG_MOBILITY:
                typeStr = "mobility"
            modelEle.setAttribute("type", typeStr)
            for i, k in enumerate(m.getnames()):
                key = self.createElement(k)
                value = conf[i]
                if value is None:
                    value = ""
                key.appendChild(self.createTextNode("%s" % value))
                modelEle.appendChild(key)
            self.appendChild(modelEle)


class MemberElement(XmlElement):
    '''
    Member elements are references to other elements in the network plan elements of the scenario.
    They are used in networks to reference channels, in channels to reference interfaces,
    and in interfaces to reference networks/channels. Member elements provided allow bi-directional
    traversal of network plan components.
    '''
    def __init__(self, scenPlan, parent, referencedType, referencedId, index=None):
        '''
        Create a member element
        '''
        XmlElement.__init__(self, scenPlan.document, parent, "member")
        self.setAttribute("type", "%s" % referencedType)
        # See'Understanding the Network Modeling Framework document'
        if index is not None:
            self.setAttribute("index", "%d" % index)
        self.appendChild(self.createTextNode("%s" % referencedId))


#
# =======================================================================================
#                                        Helpers
# =======================================================================================
def getEndpoint(netObj, ifcObj):
    '''
    Create an Endpoint object given the network and the interface of interest
    '''
    ep = None
    l2devport=None

    # if ifcObj references an interface of a node and is part of this network
    if ifcObj.net.objid == netObj.objid and hasattr(ifcObj,'node') and ifcObj.node:
        params = ifcObj.getparams()
        if isinstance(ifcObj.net, (nodes.HubNode, nodes.SwitchNode)):
            l2devport="%s/e%d" % (ifcObj.net.name, ifcObj.net.getifindex(ifcObj))
        ep = Endpoint(netObj,
                      ifcObj,
                      type = Attrib.MembType.INTERFACE,
                      id="%s/%s" % (ifcObj.node.name, ifcObj.name),
                      l2devport=l2devport,
                      params=params)

    # else if ifcObj references another node and is connected to this network
    elif hasattr(ifcObj,"othernet"):
        if ifcObj.othernet.objid == netObj.objid:
            # #hack used for upstream parameters for link between switches
            # #(see LxBrNet.linknet())
            ifcObj.swapparams('_params_up')
            params = ifcObj.getparams()
            ifcObj.swapparams('_params_up')
            owner = ifcObj.net
            l2devport="%s/e%d" % (ifcObj.othernet.name, ifcObj.othernet.getifindex(ifcObj))

            # Create the endpoint.
            # XXX the interface index might not match what is shown in the gui. For switches and hubs,
            # The gui assigns its index but doesn't pass it to the daemon and vice versa.
            # The gui stores it's index in the IMN file, which it reads and writes without daemon intervention.
            # Fix this!
            ep = Endpoint(owner,
                          ifcObj,
                          type = Attrib.MembType.INTERFACE,
                          id="%s/%s/e%d" % (netObj.name, owner.name, owner.getifindex(ifcObj)),
                          l2devport=l2devport,
                          params=params)
        # else this node has an interface that belongs to another network
        # i.e. a switch/hub interface connected to another switch/hub and CORE has the other switch/hub
        # as the containing network
        else :
            ep = Endpoint(netObj, ifcObj,type=None, id=None, l2devport=None, params=None)


    return ep

def getEndpoints(netObj):
    '''
    Gather all endpoints of the given network
    '''
    # Get all endpoints
    endpoints = []

    # XXX TODO: How to represent physical interfaces.
    #
    # NOTE: The following code works except it would be missing physical (rj45) interfaces from Pt2pt links
    # TODO: Fix data in net.netifs to include Pt2Pt physical interfaces
    #
    # Iterate through all the nodes in the scenario, then iterate through all the interface for each node,
    # and check if the interface is connected to this network.

    for ifcObj in netObj.netifs(sort=True):
        try:
            ep = getEndpoint(netObj, ifcObj)
            if ep is not None:
                endpoints.append(ep)
        except Exception:
            pass
    return endpoints

def getDowmstreamL2Devices(netObj):
    '''
    Helper function for getting a list of all downstream layer 2 devices from the given netObj
    '''
    l2devObjs = [netObj]
    allendpoints = []
    myendpoints = getEndpoints(netObj)
    allendpoints.extend(myendpoints)
    for ep in myendpoints:
        if ep.type and ep.net.objid != netObj.objid:
            l2s, eps = getDowmstreamL2Devices(ep.net)
            l2devObjs.extend(l2s)
            allendpoints.extend(eps)

    return l2devObjs, allendpoints



def getAllNetworkInterfaces(session):
    '''
    Gather all network interfacecs in the session
    '''
    netifs = []
    for node in session.objs():
        for netif in node.netifs(sort=True):
            if netif not in netifs:
                netifs.append(netif)
    return netifs

def inOtherNetwork(netObj):
    '''
    Determine if CORE considers a given network object to be part of another network.
    Note: CORE considers layer 2 devices to be their own networks. However, if a l2 device
    is connected to another device, it is possible that one of its ports belong to the other
    l2 device's network (thus, "othernet").
    '''
    for netif in netObj.netifs(sort=True):
        if hasattr(netif,"othernet"):
            if netif.othernet.objid != netObj.objid:
                return True
    return False
