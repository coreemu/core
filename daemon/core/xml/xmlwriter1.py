import collections
import os
from xml.dom.minidom import Document

import pwd

from core import coreobj
from core import logger
from core.enumerations import EventTypes
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.misc import ipaddress
from core.misc import nodeutils
from core.netns import nodes
from core.xml import xmlutils
from core.xml.xmldeployment import CoreDeploymentWriter


class Alias:
    ID = "COREID"


class MembType:
    INTERFACE = "interface"
    CHANNEL = "channel"
    SWITCH = "switch"
    HUB = "hub"
    TUNNEL = "tunnel"
    NETWORK = "network"


class NodeType:
    ROUTER = "router"
    HOST = "host"
    MDR = "mdr"
    PC = "PC"
    RJ45 = "rj45"
    SWITCH = "lanswitch"
    HUB = "hub"


class DevType:
    HOST = "host"
    ROUTER = "router"
    SWITCH = "switch"
    HUB = "hub"


class NetType:
    WIRELESS = "wireless"
    ETHERNET = "ethernet"
    PTP_WIRED = "point-to-point-wired"
    PTP_WIRELESS = "point-to-point-wireless"


"""
A link endpoint in CORE
net: the network that the endpoint belongs to
netif: the network interface at this end
id: the identifier for the endpoint
l2devport: if the other end is a layer 2 device, this is the assigned port in that device
params: link/interface parameters
"""
Endpoint = collections.namedtuple('Endpoint',
                                  ['net', 'netif', 'type', 'id', 'l2devport', 'params'])


class CoreDocumentWriter1(Document):
    """
    Utility class for writing a CoreSession to XML in the NMF scenPlan schema. The init
    method builds an xml.dom.minidom.Document, and the writexml() method saves the XML file.
    """

    def __init__(self, session):
        """
        Create an empty Scenario XML Document, then populate it with
        objects from the given session.
        """
        Document.__init__(self)
        logger.debug('Exporting to NMF XML version 1.0')
        with session._objects_lock:
            self.scenarioPlan = ScenarioPlan(self, session)
            if session.state == EventTypes.RUNTIME_STATE.value:
                deployment = CoreDeploymentWriter(self, self.scenarioPlan, session)
                deployment.add_deployment()
                self.scenarioPlan.setAttribute('deployed', 'true')

    def writexml(self, filename):
        """
        Commit to file
        """
        logger.info("saving session XML file %s", filename)
        f = open(filename, "w")
        Document.writexml(self, writer=f, indent="", addindent="  ", newl="\n", encoding="UTF-8")
        f.close()
        if self.scenarioPlan.coreSession.user is not None:
            uid = pwd.getpwnam(self.scenarioPlan.coreSession.user).pw_uid
            gid = os.stat(self.scenarioPlan.coreSession.session_dir).st_gid
            os.chown(filename, uid, gid)


class XmlElement(object):
    """
    The base class for all XML elements in the scenario plan. Includes
    convenience functions.
    """

    def __init__(self, document, parent, element_type):
        self.document = document
        self.parent = parent
        self.base_element = document.createElement("%s" % element_type)
        if self.parent is not None:
            self.parent.appendChild(self.base_element)

    def createElement(self, element_tag):
        return self.document.createElement(element_tag)

    def getTagName(self):
        return self.base_element.tagName

    def createTextNode(self, node_tag):
        return self.document.createTextNode(node_tag)

    def appendChild(self, child):
        if isinstance(child, XmlElement):
            self.base_element.appendChild(child.base_element)
        else:
            self.base_element.appendChild(child)

    @staticmethod
    def add_parameter(doc, parent, key, value):
        if key and value:
            parm = doc.createElement("parameter")
            parm.setAttribute("name", str(key))
            parm.appendChild(doc.createTextNode(str(value)))
            parent.appendChild(parm)

    def addParameter(self, key, value):
        """
        Add a parameter to the xml element
        """
        self.add_parameter(self.document, self, key, value)

    def setAttribute(self, name, val):
        self.base_element.setAttribute(name, val)

    def getAttribute(self, name):
        return self.base_element.getAttribute(name)


class NamedXmlElement(XmlElement):
    """
    The base class for all "named" xml elements. Named elements are
    xml elements in the scenario plan that have an id and a name attribute.
    """

    def __init__(self, scen_plan, parent, element_type, element_name):
        XmlElement.__init__(self, scen_plan.document, parent, element_type)

        self.scenPlan = scen_plan
        self.coreSession = scen_plan.coreSession

        element_path = ''
        self.id = None
        if self.parent is not None and isinstance(self.parent, XmlElement) and self.parent.getTagName() != "scenario":
            element_path = "%s/" % self.parent.getAttribute("id")

        self.id = "%s%s" % (element_path, element_name)
        self.setAttribute("name", element_name)
        self.setAttribute("id", self.id)

    def addPoint(self, core_object):
        """
        Add position to an object
        """
        (x, y, z) = core_object.position.get()
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

    def createAlias(self, domain, value_str):
        """
        Create an alias element for CORE specific information
        """
        a = self.createElement("alias")
        a.setAttribute("domain", "%s" % domain)
        a.appendChild(self.createTextNode(value_str))
        return a


class ScenarioPlan(XmlElement):
    """
    Container class for ScenarioPlan.
    """

    def __init__(self, document, session):
        XmlElement.__init__(self, document, parent=document, element_type='scenario')

        self.coreSession = session

        self.setAttribute('version', '1.0')
        self.setAttribute("name", "%s" % session.name)

        self.setAttribute('xmlns', 'nmfPlan')
        self.setAttribute('xmlns:CORE', 'coreSpecific')
        self.setAttribute('compiled', 'true')

        self.all_channel_members = {}
        self.last_network_id = 0
        self.addNetworks()
        self.addDevices()
        self.addDefaultServices()
        self.addSessionConfiguration()

    def addNetworks(self):
        """
        Add networks in the session to the scenPlan.
        """
        for net in self.coreSession.objects.itervalues():
            if not isinstance(net, coreobj.PyCoreNet):
                continue

            if nodeutils.is_node(net, NodeTypes.CONTROL_NET):
                continue

            # Do not add switches and hubs that belong to another network
            if nodeutils.is_node(net, (NodeTypes.SWITCH, NodeTypes.HUB)):
                if in_other_network(net):
                    continue

            try:
                NetworkElement(self, self, net)
            except:
                logger.exception("error adding node")
                if hasattr(net, "name") and net.name:
                    logger.warn('Unsupported net name: %s, class: %s, type: %s',
                                net.name, net.__class__.__name__, net.type)
                else:
                    logger.warn('Unsupported net class: %s', net.__class__.__name__)

    def addDevices(self):
        """
        Add device elements to the scenario plan.
        """
        for node in self.coreSession.objects.itervalues():
            if not isinstance(node, nodes.PyCoreNode):
                continue

            try:
                DeviceElement(self, self, node)
            except:
                logger.exception("error adding device")
                if hasattr(node, "name") and node.name:
                    logger.warn('Unsupported device name: %s, class: %s, type: %s',
                                node.name, node.__class__.__name__, node.type)
                else:
                    logger.warn('Unsupported device: %s', node.__class__.__name__)

    def addDefaultServices(self):
        """
        Add default services and node types to the ServicePlan.
        """
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
        """
        Add CORE-specific session configuration XML elements.
        """
        config = self.createElement("CORE:sessionconfig")

        # origin: geolocation of cartesian coordinate 0,0,0
        refgeo = self.coreSession.location.refgeo
        origin = self.createElement("origin")
        attrs = ("lat", "lon", "alt")
        have_origin = False
        for i in xrange(3):
            if refgeo[i] is not None:
                origin.setAttribute(attrs[i], str(refgeo[i]))
                have_origin = True
        if have_origin:
            if self.coreSession.location.refscale != 1.0:  # 100 pixels = refscale m
                origin.setAttribute("scale100", str(self.coreSession.location.refscale))
            if self.coreSession.location.refxyz != (0.0, 0.0, 0.0):
                pt = self.createElement("point")
                origin.appendChild(pt)
                x, y, z = self.coreSession.location.refxyz
                coordstxt = "%s,%s" % (x, y)
                if z:
                    coordstxt += ",%s" % z
                coords = self.createTextNode(coordstxt)
                pt.appendChild(coords)
            config.appendChild(origin)

        # options
        options = self.createElement("options")
        options_config = self.coreSession.options.get_configs()
        for _id, default_value in self.coreSession.options.default_values().iteritems():
            value = options_config[_id]
            if value != default_value:
                XmlElement.add_parameter(self.document, options, _id, value)

        if options.hasChildNodes():
            config.appendChild(options)

        # hook scripts
        hooks = self.createElement("hooks")
        for state in sorted(self.coreSession._hooks.keys()):
            for filename, data in self.coreSession._hooks[state]:
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
        for k, v in self.coreSession.metadata.get_configs().iteritems():
            XmlElement.add_parameter(self.document, meta, k, v)
        if meta.hasChildNodes():
            config.appendChild(meta)

        if config.hasChildNodes():
            self.appendChild(config)


class NetworkElement(NamedXmlElement):
    def __init__(self, scen_plan, parent, network_object):
        """
        Add one PyCoreNet object as one network XML element.
        """
        element_name = self.getNetworkName(scen_plan, network_object)
        NamedXmlElement.__init__(self, scen_plan, parent, "network", element_name)

        self.scenPlan = scen_plan

        self.addPoint(network_object)

        network_type = None
        if nodeutils.is_node(network_object, (NodeTypes.WIRELESS_LAN, NodeTypes.EMANE)):
            network_type = NetType.WIRELESS
        elif nodeutils.is_node(network_object, (NodeTypes.SWITCH, NodeTypes.HUB,
                                                NodeTypes.PEER_TO_PEER, NodeTypes.TUNNEL)):
            network_type = NetType.ETHERNET
        else:
            network_type = "%s" % network_object.__class__.__name__

        type_element = self.createElement("type")
        type_element.appendChild(self.createTextNode(network_type))
        self.appendChild(type_element)

        # Gather all endpoints belonging to this network
        self.endpoints = get_endpoints(network_object)

        # Special case for a network of switches and hubs
        create_alias = True
        self.l2devices = []
        if nodeutils.is_node(network_object, (NodeTypes.SWITCH, NodeTypes.HUB)):
            create_alias = False
            self.appendChild(type_element)
            self.addL2Devices(network_object)

        if create_alias:
            a = self.createAlias(Alias.ID, "%d" % int(network_object.objid))
            self.appendChild(a)

        # XXXX TODO: Move this to  channel?
        # key used with tunnel node
        if hasattr(network_object, 'grekey') and network_object.grekey is not None:
            a = self.createAlias("COREGREKEY", "%s" % network_object.grekey)
            self.appendChild(a)

        self.addNetMembers(network_object)
        self.addChannels(network_object)

        presentation_element = self.createElement("CORE:presentation")
        add_presentation_element = False
        if network_object.icon and not network_object.icon.isspace():
            presentation_element.setAttribute("icon", network_object.icon)
            add_presentation_element = True
        if network_object.canvas:
            presentation_element.setAttribute("canvas", str(network_object.canvas))
            add_presentation_element = True
        if add_presentation_element:
            self.appendChild(presentation_element)

    def getNetworkName(self, scenario_plan, network_object):
        """
        Determine the name to use for this network element

        :param ScenarioPlan scenario_plan:
        :param network_object:
        :return:
        """
        if nodeutils.is_node(network_object, (NodeTypes.PEER_TO_PEER, NodeTypes.TUNNEL)):
            name = "net%s" % scenario_plan.last_network_id
            scenario_plan.last_network_id += 1
        elif network_object.name:
            name = str(network_object.name)  # could use net.brname for bridges?
        elif nodeutils.is_node(network_object, (NodeTypes.SWITCH, NodeTypes.HUB)):
            name = "lan%s" % network_object.objid
        else:
            name = ''
        return name

    def addL2Devices(self, network_object):
        """
        Add switches and hubs
        """

        # Add the netObj as a device
        self.l2devices.append(DeviceElement(self.scenPlan, self, network_object))

        # Add downstream switches/hubs
        l2devs = []
        neweps = []
        for ep in self.endpoints:
            if ep.type and ep.net.objid != network_object.objid:
                l2s, eps = get_dowmstream_l2_devices(ep.net)
                l2devs.extend(l2s)
                neweps.extend(eps)

        for l2dev in l2devs:
            self.l2devices.append(DeviceElement(self.scenPlan, self, l2dev))

        self.endpoints.extend(neweps)

    # XXX: Optimize later
    def addNetMembers(self, network_object):
        """
        Add members to a network XML element.
        """

        for ep in self.endpoints:
            if ep.type:
                MemberElement(self.scenPlan, self, referenced_type=ep.type, referenced_id=ep.id)

                if ep.l2devport:
                    MemberElement(self.scenPlan,
                                  self,
                                  referenced_type=MembType.INTERFACE,
                                  referenced_id="%s/%s" % (self.id, ep.l2devport))

        # XXX Revisit this
        # Create implied members given the network type
        if nodeutils.is_node(network_object, NodeTypes.TUNNEL):
            MemberElement(self.scenPlan, self, referenced_type=MembType.TUNNEL,
                          referenced_id="%s/%s" % (network_object.name, network_object.name))

    # XXX: Optimize later
    def addChannels(self, network_object):
        """
        Add channels to a network XML element
        """

        if nodeutils.is_node(network_object, (NodeTypes.WIRELESS_LAN, NodeTypes.EMANE)):
            modelconfigs = network_object.session.mobility.getmodels(network_object)
            modelconfigs += network_object.session.emane.getmodels(network_object)
            chan = None

            for model, conf in modelconfigs:
                # Handle mobility parameters below
                if model.config_type == RegisterTlvs.MOBILITY.value:
                    continue

                # Create the channel
                if chan is None:
                    name = "wireless"
                    chan = ChannelElement(self.scenPlan, self, network_object,
                                          channel_type=model.name,
                                          channel_name=name,
                                          channel_domain="CORE")

                # Add wireless model parameters
                for key, value in conf.iteritems():
                    if value is not None:
                        chan.addParameter(key, value)

            for model, conf in modelconfigs:
                if model.config_type == RegisterTlvs.MOBILITY.value:
                    # Add wireless mobility parameters
                    mobility = XmlElement(self.scenPlan, chan, "CORE:mobility")
                    # Add a type child
                    type_element = self.createElement("type")
                    type_element.appendChild(self.createTextNode(model.name))
                    mobility.appendChild(type_element)

                    for key, value in conf.iteritems():
                        if value is not None:
                            mobility.addParameter(key, value)

            # Add members to the channel
            if chan is not None:
                chan.addChannelMembers(self.endpoints)
                self.appendChild(chan.base_element)
        elif nodeutils.is_node(network_object, NodeTypes.PEER_TO_PEER):
            if len(self.endpoints) < 2:
                if len(self.endpoints) == 1:
                    logger.warn('Pt2Pt network with only 1 endpoint: %s', self.endpoints[0].id)
                else:
                    logger.warn('Pt2Pt network with no endpoints encountered in %s', network_object.name)
                return
            name = "chan%d" % (0)
            chan = ChannelElement(self.scenPlan, self, network_object,
                                  channel_type=NetType.ETHERNET,
                                  channel_name=name)

            # Add interface parameters
            if self.endpoints[0].params != self.endpoints[1].params:
                logger.warn('Pt2Pt Endpoint  parameters do not match in %s', network_object.name)
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

        elif nodeutils.is_node(network_object, (NodeTypes.SWITCH, NodeTypes.HUB, NodeTypes.TUNNEL)):
            cidx = 0
            channels = []
            for ep in self.endpoints:
                # Create one channel member per ep
                if ep.type:
                    name = "chan%d" % cidx
                    chan = ChannelElement(self.scenPlan, self, network_object, channel_type=NetType.ETHERNET,
                                          channel_name=name)

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
    """
    A device element in the scenario plan.
    """

    def __init__(self, scen_plan, parent, device_object):
        """
        Add a PyCoreNode object as a device element.
        """

        device_type = None
        core_device_type = None
        if hasattr(device_object, "type") and device_object.type:
            core_device_type = device_object.type
            if device_object.type in [NodeType.ROUTER, NodeType.MDR]:
                device_type = DevType.ROUTER
            elif device_object.type == NodeType.HUB:
                device_type = DevType.HUB
            elif device_object.type == NodeType.SWITCH:
                device_type = DevType.SWITCH
            # includes known node types (HOST, PC, RJ45)
            # Default custom types (defined in ~/.core/nodes.conf) to HOST
            else:
                device_type = DevType.HOST

        if device_type is None:
            raise ValueError("unknown device type: %s" % core_device_type)

        NamedXmlElement.__init__(self, scen_plan, parent, device_type, device_object.name)

        if core_device_type is not None:
            type_element = self.createElement("type")
            type_element.setAttribute("domain", "CORE")
            type_element.appendChild(self.createTextNode("%s" % core_device_type))
            self.appendChild(type_element)

        self.interfaces = []
        self.addInterfaces(device_object)
        alias = self.createAlias(Alias.ID, "%s" % device_object.objid)
        self.appendChild(alias)
        self.addPoint(device_object)
        self.addServices(device_object)

        presentation_element = self.createElement("CORE:presentation")
        add_presentation_element = False
        if device_object.icon and not device_object.icon.isspace():
            presentation_element.setAttribute("icon", device_object.icon)
            add_presentation_element = True
        if device_object.canvas:
            presentation_element.setAttribute("canvas", str(device_object.canvas))
            add_presentation_element = True
        if add_presentation_element:
            self.appendChild(presentation_element)

    def addInterfaces(self, device_object):
        """
        Add interfaces to a device element.
        """
        idx = 0
        for interface_object in device_object.netifs(sort=True):
            if interface_object.net and nodeutils.is_node(interface_object.net, NodeTypes.CONTROL_NET):
                continue
            if isinstance(device_object, nodes.PyCoreNode):
                interface_element = InterfaceElement(self.scenPlan, self, device_object, interface_object)
            else:  # isinstance(node, (nodes.HubNode nodes.SwitchNode)):
                interface_element = InterfaceElement(self.scenPlan, self, device_object, interface_object, idx)
            idx += 1

            netmodel = None
            if interface_object.net:
                if hasattr(interface_object.net, "model"):
                    netmodel = interface_object.net.model
            if interface_object.mtu and interface_object.mtu != 1500:
                interface_element.setAttribute("mtu", "%s" % interface_object.mtu)

            # The interfaces returned for Switches and Hubs are the interfaces of the nodes connected to them.
            # The addresses are for those interfaces. Don't include them here.
            if isinstance(device_object, nodes.PyCoreNode):
                # could use ifcObj.params, transport_type
                interface_element.addAddresses(interface_object)
                # per-interface models
                # XXX Remove???
                if netmodel and netmodel.name[:6] == "emane_":
                    cfg = netmodel.getifcconfig(device_object.objid, interface_object)
                    if cfg:
                        interface_element.addModels(((netmodel, cfg),))

            self.interfaces.append(interface_element)

    def addServices(self, device_object):
        """
        Add services and their customizations to the ServicePlan.
        """
        if not hasattr(device_object, "services"):
            return

        if len(device_object.services) == 0:
            return

        defaults = self.coreSession.services.getdefaultservices(device_object.type)
        if device_object.services == defaults:
            return
        spn = self.createElement("CORE:services")
        spn.setAttribute("name", device_object.name)
        self.appendChild(spn)

        for svc in device_object.services:
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
            xmlutils.add_elements_from_list(self, s, svc._dirs, "directory", "name")

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

            xmlutils.add_text_elements_from_list(self, s, svc._startup, "command",
                                                 (("type", "start"),))
            xmlutils.add_text_elements_from_list(self, s, svc._shutdown, "command",
                                                 (("type", "stop"),))
            xmlutils.add_text_elements_from_list(self, s, svc._validate, "command",
                                                 (("type", "validate"),))


class ChannelElement(NamedXmlElement):
    """
    A channel element in the scenario plan
    """

    def __init__(self, scen_plan, parent, network_object, channel_type, channel_name, channel_domain=None):
        NamedXmlElement.__init__(self, scen_plan, parent, "channel", channel_name)
        '''
        Create a channel element and append a member child referencing this channel element
        in the parent element.
        '''
        # Create a member element for this channel in the parent
        MemberElement(self.scenPlan, parent, referenced_type=MembType.CHANNEL, referenced_id=self.id)

        # Add a type child
        type_element = self.createElement("type")
        if channel_domain is not None:
            type_element.setAttribute("domain", "%s" % channel_domain)
        type_element.appendChild(self.createTextNode(channel_type))
        self.appendChild(type_element)

    def addChannelMembers(self, endpoints):
        """
        Add network channel members referencing interfaces in the channel
        """
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
                member_id = "%s/%s" % (self.parent.getAttribute("id"), ep.l2devport)
                self.addChannelMember(ep.type, member_id, 1)

    def addChannelMember(self, member_interface_type, member_interface_id, member_index):
        """
        add a member to a given channel
        """

        m = MemberElement(self.scenPlan,
                          self,
                          referenced_type=member_interface_type,
                          referenced_id=member_interface_id,
                          index=member_index)
        self.scenPlan.all_channel_members[member_interface_id] = m


class InterfaceElement(NamedXmlElement):
    """
    A network interface element
    """

    def __init__(self, scen_plan, parent, device_object, interface_object, interface_index=None):
        """
        Create a network interface element with references to channel that this
        interface is used.
        """
        element_name = None
        if interface_index is not None:
            element_name = "e%d" % interface_index
        else:
            element_name = interface_object.name
        NamedXmlElement.__init__(self, scen_plan, parent, "interface", element_name)
        self.ifcObj = interface_object
        self.addChannelReference()

    def addChannelReference(self):
        """
        Add a reference to the channel that uses this interface
        """
        # cm is None when an interface belongs to a switch
        #  or a hub within a network and the channel is yet to be defined
        cm = self.scenPlan.all_channel_members.get(self.id)
        if cm is not None:
            ch = cm.base_element.parentNode
            if ch is not None:
                net = ch.parentNode
                if net is not None:
                    MemberElement(self.scenPlan,
                                  self,
                                  referenced_type=MembType.CHANNEL,
                                  referenced_id=ch.getAttribute("id"),
                                  index=int(cm.getAttribute("index")))
                    MemberElement(self.scenPlan,
                                  self,
                                  referenced_type=MembType.NETWORK,
                                  referenced_id=net.getAttribute("id"))

    def addAddresses(self, interface_object):
        """
        Add MAC and IP addresses to interface XML elements.
        """
        if interface_object.hwaddr:
            h = self.createElement("address")
            self.appendChild(h)
            h.setAttribute("type", "mac")
            htxt = self.createTextNode("%s" % interface_object.hwaddr)
            h.appendChild(htxt)
        for addr in interface_object.addrlist:
            a = self.createElement("address")
            self.appendChild(a)
            (ip, sep, mask) = addr.partition('/')
            # mask = int(mask) XXX?
            if ipaddress.is_ipv4_address(ip):
                a.setAttribute("type", "IPv4")
            else:
                a.setAttribute("type", "IPv6")

            # a.setAttribute("type", )
            atxt = self.createTextNode("%s" % addr)
            a.appendChild(atxt)

    # XXX Remove?
    def addModels(self, configs):
        """
        Add models from a list of model-class, config values tuples.
        """
        for m, conf in configs:
            node_element = self.createElement("model")
            node_element.setAttribute("name", m.name)
            type_string = "wireless"
            if m.config_type == RegisterTlvs.MOBILITY.value:
                type_string = "mobility"
            node_element.setAttribute("type", type_string)
            for i, k in enumerate(m.getnames()):
                key = self.createElement(k)
                value = conf[i]
                if value is None:
                    value = ""
                key.appendChild(self.createTextNode("%s" % value))
                node_element.appendChild(key)
            self.appendChild(node_element)


class MemberElement(XmlElement):
    """
    Member elements are references to other elements in the network plan elements of the scenario.
    They are used in networks to reference channels, in channels to reference interfaces,
    and in interfaces to reference networks/channels. Member elements provided allow bi-directional
    traversal of network plan components.
    """

    def __init__(self, scene_plan, parent, referenced_type, referenced_id, index=None):
        """
        Create a member element
        """
        XmlElement.__init__(self, scene_plan.document, parent, "member")
        self.setAttribute("type", "%s" % referenced_type)
        # See'Understanding the Network Modeling Framework document'
        if index is not None:
            self.setAttribute("index", "%d" % index)
        self.appendChild(self.createTextNode("%s" % referenced_id))


#
# =======================================================================================
#                                        Helpers
# =======================================================================================

def get_endpoint(network_object, interface_object):
    """
    Create an Endpoint object given the network and the interface of interest
    """
    ep = None
    l2devport = None

    # skip if either are none
    if not network_object or not interface_object:
        return ep

    # if ifcObj references an interface of a node and is part of this network
    if interface_object.net.objid == network_object.objid and hasattr(interface_object,
                                                                      'node') and interface_object.node:
        params = interface_object.getparams()
        if nodeutils.is_node(interface_object.net, (NodeTypes.HUB, NodeTypes.SWITCH)):
            l2devport = "%s/e%d" % (interface_object.net.name, interface_object.net.getifindex(interface_object))
        ep = Endpoint(network_object,
                      interface_object,
                      type=MembType.INTERFACE,
                      id="%s/%s" % (interface_object.node.name, interface_object.name),
                      l2devport=l2devport,
                      params=params)

    # else if ifcObj references another node and is connected to this network
    elif hasattr(interface_object, "othernet"):
        if interface_object.othernet.objid == network_object.objid:
            # #hack used for upstream parameters for link between switches
            # #(see LxBrNet.linknet())
            interface_object.swapparams('_params_up')
            params = interface_object.getparams()
            interface_object.swapparams('_params_up')
            owner = interface_object.net
            l2devport = "%s/e%d" % (
                interface_object.othernet.name, interface_object.othernet.getifindex(interface_object))

            # Create the endpoint.
            # XXX the interface index might not match what is shown in the gui. For switches and hubs,
            # The gui assigns its index but doesn't pass it to the daemon and vice versa.
            # The gui stores it's index in the IMN file, which it reads and writes without daemon intervention.
            # Fix this!
            ep = Endpoint(owner,
                          interface_object,
                          type=MembType.INTERFACE,
                          id="%s/%s/e%d" % (network_object.name, owner.name, owner.getifindex(interface_object)),
                          l2devport=l2devport,
                          params=params)
        # else this node has an interface that belongs to another network
        # i.e. a switch/hub interface connected to another switch/hub and CORE has the other switch/hub
        # as the containing network
        else:
            ep = Endpoint(network_object, interface_object, type=None, id=None, l2devport=None, params=None)

    return ep


def get_endpoints(network_object):
    """
    Gather all endpoints of the given network
    """
    # Get all endpoints
    endpoints = []

    # XXX TODO: How to represent physical interfaces.
    #
    # NOTE: The following code works except it would be missing physical (rj45) interfaces from Pt2pt links
    # TODO: Fix data in net.netifs to include Pt2Pt physical interfaces
    #
    # Iterate through all the nodes in the scenario, then iterate through all the interface for each node,
    # and check if the interface is connected to this network.

    for interface_object in network_object.netifs(sort=True):
        try:
            ep = get_endpoint(network_object, interface_object)
            if ep is not None:
                endpoints.append(ep)
        except:
            logger.debug("error geting endpoints, was skipped before")

    return endpoints


def get_dowmstream_l2_devices(network_object):
    """
    Helper function for getting a list of all downstream layer 2 devices from the given netObj
    """
    l2_device_objects = [network_object]
    allendpoints = []
    myendpoints = get_endpoints(network_object)
    allendpoints.extend(myendpoints)
    for ep in myendpoints:
        if ep.type and ep.net.objid != network_object.objid:
            l2s, eps = get_dowmstream_l2_devices(ep.net)
            l2_device_objects.extend(l2s)
            allendpoints.extend(eps)

    return l2_device_objects, allendpoints


def get_all_network_interfaces(session):
    """
    Gather all network interfacecs in the session
    """
    netifs = []
    for node in session.objects.itervalues():
        for netif in node.netifs(sort=True):
            if netif not in netifs:
                netifs.append(netif)
    return netifs


def in_other_network(network_object):
    """
    Determine if CORE considers a given network object to be part of another network.
    Note: CORE considers layer 2 devices to be their own networks. However, if a l2 device
    is connected to another device, it is possible that one of its ports belong to the other
    l2 device's network (thus, "othernet").
    """
    for netif in network_object.netifs(sort=True):
        if hasattr(netif, "othernet"):
            if netif.othernet.objid != network_object.objid:
                return True
    return False
