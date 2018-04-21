"""
nodes.py: definition of an EmaneNode class for implementing configuration
control of an EMANE emulation. An EmaneNode has several attached NEMs that
share the same MAC+PHY model.
"""

import os

from core import logger
from core.coreobj import PyCoreNet
from core.enumerations import LinkTypes
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs

try:
    from emane.events import LocationEvent
except ImportError:
    try:
        from emanesh.events import LocationEvent
    except ImportError:
        logger.warn("compatible emane python bindings not installed")


class EmaneNet(PyCoreNet):
    """
    EMANE network base class.
    """
    apitype = NodeTypes.EMANE.value
    linktype = LinkTypes.WIRELESS.value
    # icon used
    type = "wlan"


class EmaneNode(EmaneNet):
    """
    EMANE node contains NEM configuration and causes connected nodes
    to have TAP interfaces (instead of VEth). These are managed by the
    Emane controller object that exists in a session.
    """

    def __init__(self, session, objid=None, name=None, start=True):
        PyCoreNet.__init__(self, session, objid, name, start)
        self.conf = ""
        self.up = False
        self.nemidmap = {}
        self.model = None
        self.mobility = None

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None, jitter=None, netif2=None):
        """
        The CommEffect model supports link configuration.
        """
        if not self.model:
            return
        return self.model.linkconfig(netif=netif, bw=bw, delay=delay, loss=loss,
                                     duplicate=duplicate, jitter=jitter, netif2=netif2)

    def config(self, conf):
        self.conf = conf

    def shutdown(self):
        pass

    def link(self, netif1, netif2):
        pass

    def unlink(self, netif1, netif2):
        pass

    def setmodel(self, model, config):
        """
        set the EmaneModel associated with this node
        """
        logger.info("adding model: %s", model.name)
        if model.config_type == RegisterTlvs.WIRELESS.value:
            # EmaneModel really uses values from ConfigurableManager
            #  when buildnemxml() is called, not during init()
            self.model = model(session=self.session, object_id=self.objid)
        elif model.config_type == RegisterTlvs.MOBILITY.value:
            self.mobility = model(session=self.session, object_id=self.objid, values=config)

    def setnemid(self, netif, nemid):
        """
        Record an interface to numerical ID mapping. The Emane controller
        object manages and assigns these IDs for all NEMs.
        """
        self.nemidmap[netif] = nemid

    def getnemid(self, netif):
        """
        Given an interface, return its numerical ID.
        """
        if netif not in self.nemidmap:
            return None
        else:
            return self.nemidmap[netif]

    def getnemnetif(self, nemid):
        """
        Given a numerical NEM ID, return its interface. This returns the
        first interface that matches the given NEM ID.
        """
        for netif in self.nemidmap:
            if self.nemidmap[netif] == nemid:
                return netif
        return None

    def netifs(self, sort=True):
        """
        Retrieve list of linked interfaces sorted by node number.
        """
        return sorted(self._netif.values(), key=lambda ifc: ifc.node.objid)

    def buildplatformxmlentry(self, doc):
        """
        Return a dictionary of XML elements describing the NEMs
        connected to this EmaneNode for inclusion in the platform.xml file.
        """
        ret = {}
        if self.model is None:
            logger.info("warning: EmaneNode %s has no associated model", self.name)
            return ret

        for netif in self.netifs():
            nementry = self.model.build_nem_xml(doc, self, netif)
            trans = self.model.build_transport_xml(doc, self, netif)
            nementry.appendChild(trans)
            ret[netif] = nementry

        return ret

    def build_xml_files(self, emane_manager):
        """
        Let the configured model build the necessary nem, mac, and phy XMLs.

        :param core.emane.emanemanager.EmaneManager emane_manager: core emane manager
        :return: nothing
        """
        if self.model is None:
            return

        # build XML for overall network (EmaneNode) configs
        self.model.build_xml_files(emane_manager, interface=None)

        # build XML for specific interface (NEM) configs
        need_virtual = False
        need_raw = False
        vtype = "virtual"
        rtype = "raw"

        for netif in self.netifs():
            self.model.build_xml_files(emane_manager, netif)
            if "virtual" in netif.transport_type:
                need_virtual = True
                vtype = netif.transport_type
            else:
                need_raw = True
                rtype = netif.transport_type

        # build transport XML files depending on type of interfaces involved
        if need_virtual:
            self.buildtransportxml(emane_manager, vtype)

        if need_raw:
            self.buildtransportxml(emane_manager, rtype)

    def buildtransportxml(self, emane, transport_type):
        """
        Write a transport XML file for the Virtual or Raw Transport.
        """
        transdoc = emane.xmldoc("transport")
        trans = transdoc.getElementsByTagName("transport").pop()
        trans.setAttribute("name", "%s Transport" % transport_type.capitalize())
        trans.setAttribute("library", "trans%s" % transport_type.lower())
        trans.appendChild(emane.xmlparam(transdoc, "bitrate", "0"))

        flowcontrol = False
        names = self.model.getnames()
        values = emane.getconfig(self.objid, self.model.name, self.model.getdefaultvalues())[1]

        if "flowcontrolenable" in names and values:
            i = names.index("flowcontrolenable")
            if self.model.booltooffon(values[i]) == "on":
                flowcontrol = True

        if "virtual" in transport_type.lower():
            if os.path.exists("/dev/net/tun_flowctl"):
                trans.appendChild(emane.xmlparam(transdoc, "devicepath", "/dev/net/tun_flowctl"))
            else:
                trans.appendChild(emane.xmlparam(transdoc, "devicepath", "/dev/net/tun"))
            if flowcontrol:
                trans.appendChild(emane.xmlparam(transdoc, "flowcontrolenable", "on"))

        emane.xmlwrite(transdoc, self.transportxmlname(transport_type.lower()))

    def transportxmlname(self, type):
        """
        Return the string name for the Transport XML file, e.g. 'n3transvirtual.xml'
        """
        return "n%strans%s.xml" % (self.objid, type)

    def installnetifs(self, do_netns=True):
        """
        Install TAP devices into their namespaces. This is done after
        EMANE daemons have been started, because that is their only chance
        to bind to the TAPs.
        """
        if self.session.emane.genlocationevents() and self.session.emane.service is None:
            warntxt = "unable to publish EMANE events because the eventservice "
            warntxt += "Python bindings failed to load"
            logger.error(warntxt)

        for netif in self.netifs():
            if do_netns and "virtual" in netif.transport_type.lower():
                netif.install()
            netif.setaddrs()
            if not self.session.emane.genlocationevents():
                netif.poshook = None
                continue
            # at this point we register location handlers for generating
            # EMANE location events
            netif.poshook = self.setnemposition
            x, y, z = netif.node.position.get()
            self.setnemposition(netif, x, y, z)

    def deinstallnetifs(self):
        """
        Uninstall TAP devices. This invokes their shutdown method for
        any required cleanup; the device may be actually removed when
        emanetransportd terminates.
        """
        for netif in self.netifs():
            if "virtual" in netif.transport_type.lower():
                netif.shutdown()
            netif.poshook = None

    def setnemposition(self, netif, x, y, z):
        """
        Publish a NEM location change event using the EMANE event service.
        """
        if self.session.emane.service is None:
            logger.info("position service not available")
            return
        nemid = self.getnemid(netif)
        ifname = netif.localname
        if nemid is None:
            logger.info("nemid for %s is unknown" % ifname)
            return
        lat, long, alt = self.session.location.getgeo(x, y, z)
        logger.info("setnemposition %s (%s) x,y,z=(%d,%d,%s)(%.6f,%.6f,%.6f)", ifname, nemid, x, y, z, lat, long, alt)
        event = LocationEvent()

        # altitude must be an integer or warning is printed
        # unused: yaw, pitch, roll, azimuth, elevation, velocity
        alt = int(round(alt))
        event.append(nemid, latitude=lat, longitude=long, altitude=alt)
        self.session.emane.service.publish(0, event)

    def setnempositions(self, moved_netifs):
        """
        Several NEMs have moved, from e.g. a WaypointMobilityModel
        calculation. Generate an EMANE Location Event having several
        entries for each netif that has moved.
        """
        if len(moved_netifs) == 0:
            return

        if self.session.emane.service is None:
            logger.info("position service not available")
            return

        event = LocationEvent()
        i = 0
        for netif in moved_netifs:
            nemid = self.getnemid(netif)
            ifname = netif.localname
            if nemid is None:
                logger.info("nemid for %s is unknown" % ifname)
                continue
            x, y, z = netif.node.getposition()
            lat, long, alt = self.session.location.getgeo(x, y, z)
            logger.info("setnempositions %d %s (%s) x,y,z=(%d,%d,%s)(%.6f,%.6f,%.6f)",
                        i, ifname, nemid, x, y, z, lat, long, alt)
            # altitude must be an integer or warning is printed
            alt = int(round(alt))
            event.append(nemid, latitude=lat, longitude=long, altitude=alt)
            i += 1

        self.session.emane.service.publish(0, event)
