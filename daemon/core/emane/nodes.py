"""
nodes.py: definition of an EmaneNode class for implementing configuration
control of an EMANE emulation. An EmaneNode has several attached NEMs that
share the same MAC+PHY model.
"""

import logging

from core.emulator.enumerations import LinkTypes, NodeTypes, RegisterTlvs
from core.nodes.base import CoreNetworkBase

try:
    from emane.events import LocationEvent
except ImportError:
    try:
        from emanesh.events import LocationEvent
    except ImportError:
        logging.debug("compatible emane python bindings not installed")


class EmaneNet(CoreNetworkBase):
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

    def __init__(self, session, _id=None, name=None, start=True):
        super(EmaneNode, self).__init__(session, _id, name, start)
        self.conf = ""
        self.up = False
        self.nemidmap = {}
        self.model = None
        self.mobility = None

    def linkconfig(
        self,
        netif,
        bw=None,
        delay=None,
        loss=None,
        duplicate=None,
        jitter=None,
        netif2=None,
    ):
        """
        The CommEffect model supports link configuration.
        """
        if not self.model:
            return
        return self.model.linkconfig(
            netif=netif,
            bw=bw,
            delay=delay,
            loss=loss,
            duplicate=duplicate,
            jitter=jitter,
            netif2=netif2,
        )

    def config(self, conf):
        self.conf = conf

    def shutdown(self):
        pass

    def link(self, netif1, netif2):
        pass

    def unlink(self, netif1, netif2):
        pass

    def updatemodel(self, config):
        if not self.model:
            raise ValueError("no model set to update for node(%s)", self.id)
        logging.info(
            "node(%s) updating model(%s): %s", self.id, self.model.name, config
        )
        self.model.set_configs(config, node_id=self.id)

    def setmodel(self, model, config):
        """
        set the EmaneModel associated with this node
        """
        logging.info("adding model: %s", model.name)
        if model.config_type == RegisterTlvs.WIRELESS.value:
            # EmaneModel really uses values from ConfigurableManager
            #  when buildnemxml() is called, not during init()
            self.model = model(session=self.session, _id=self.id)
            self.model.update_config(config)
        elif model.config_type == RegisterTlvs.MOBILITY.value:
            self.mobility = model(session=self.session, _id=self.id)
            self.mobility.update_config(config)

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
        return sorted(self._netif.values(), key=lambda ifc: ifc.node.id)

    def installnetifs(self):
        """
        Install TAP devices into their namespaces. This is done after
        EMANE daemons have been started, because that is their only chance
        to bind to the TAPs.
        """
        if (
            self.session.emane.genlocationevents()
            and self.session.emane.service is None
        ):
            warntxt = "unable to publish EMANE events because the eventservice "
            warntxt += "Python bindings failed to load"
            logging.error(warntxt)

        for netif in self.netifs():
            external = self.session.emane.get_config(
                "external", self.id, self.model.name
            )
            if external == "0":
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
            logging.info("position service not available")
            return
        nemid = self.getnemid(netif)
        ifname = netif.localname
        if nemid is None:
            logging.info("nemid for %s is unknown", ifname)
            return
        lat, lon, alt = self.session.location.getgeo(x, y, z)
        logging.info(
            "setnemposition %s (%s) x,y,z=(%d,%d,%s)(%.6f,%.6f,%.6f)",
            ifname,
            nemid,
            x,
            y,
            z,
            lat,
            lon,
            alt,
        )
        event = LocationEvent()

        # altitude must be an integer or warning is printed
        # unused: yaw, pitch, roll, azimuth, elevation, velocity
        alt = int(round(alt))
        event.append(nemid, latitude=lat, longitude=lon, altitude=alt)
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
            logging.info("position service not available")
            return

        event = LocationEvent()
        i = 0
        for netif in moved_netifs:
            nemid = self.getnemid(netif)
            ifname = netif.localname
            if nemid is None:
                logging.info("nemid for %s is unknown" % ifname)
                continue
            x, y, z = netif.node.getposition()
            lat, lon, alt = self.session.location.getgeo(x, y, z)
            logging.info(
                "setnempositions %d %s (%s) x,y,z=(%d,%d,%s)(%.6f,%.6f,%.6f)",
                i,
                ifname,
                nemid,
                x,
                y,
                z,
                lat,
                lon,
                alt,
            )
            # altitude must be an integer or warning is printed
            alt = int(round(alt))
            event.append(nemid, latitude=lat, longitude=lon, altitude=alt)
            i += 1

        self.session.emane.service.publish(0, event)
