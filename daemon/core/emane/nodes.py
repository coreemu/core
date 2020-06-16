"""
Provides an EMANE network node class, which has several attached NEMs that
share the same MAC+PHY model.
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type

from core.emulator.data import LinkData, LinkOptions
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import (
    LinkTypes,
    MessageFlags,
    NodeTypes,
    RegisterTlvs,
    TransportType,
)
from core.errors import CoreError
from core.nodes.base import CoreNetworkBase
from core.nodes.interface import CoreInterface

if TYPE_CHECKING:
    from core.emane.emanemodel import EmaneModel
    from core.emulator.session import Session
    from core.location.mobility import WirelessModel, WayPointMobility

    OptionalEmaneModel = Optional[EmaneModel]
    WirelessModelType = Type[WirelessModel]

try:
    from emane.events import LocationEvent
except ImportError:
    try:
        from emanesh.events import LocationEvent
    except ImportError:
        LocationEvent = None
        logging.debug("compatible emane python bindings not installed")


class EmaneNet(CoreNetworkBase):
    """
    EMANE node contains NEM configuration and causes connected nodes
    to have TAP interfaces (instead of VEth). These are managed by the
    Emane controller object that exists in a session.
    """

    apitype: NodeTypes = NodeTypes.EMANE
    linktype: LinkTypes = LinkTypes.WIRED
    type: str = "wlan"
    is_emane: bool = True

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: DistributedServer = None,
    ) -> None:
        super().__init__(session, _id, name, server)
        self.conf: str = ""
        self.nemidmap: Dict[CoreInterface, int] = {}
        self.model: "OptionalEmaneModel" = None
        self.mobility: Optional[WayPointMobility] = None

    def linkconfig(
        self, iface: CoreInterface, options: LinkOptions, iface2: CoreInterface = None
    ) -> None:
        """
        The CommEffect model supports link configuration.
        """
        if not self.model:
            return
        self.model.linkconfig(iface, options, iface2)

    def config(self, conf: str) -> None:
        self.conf = conf

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def link(self, iface1: CoreInterface, iface2: CoreInterface) -> None:
        pass

    def unlink(self, iface1: CoreInterface, iface2: CoreInterface) -> None:
        pass

    def linknet(self, net: "CoreNetworkBase") -> CoreInterface:
        raise CoreError("emane networks cannot be linked to other networks")

    def updatemodel(self, config: Dict[str, str]) -> None:
        if not self.model:
            raise CoreError(f"no model set to update for node({self.name})")
        logging.info(
            "node(%s) updating model(%s): %s", self.id, self.model.name, config
        )
        self.model.update_config(config)

    def setmodel(self, model: "WirelessModelType", config: Dict[str, str]) -> None:
        """
        set the EmaneModel associated with this node
        """
        logging.info("adding model: %s", model.name)
        if model.config_type == RegisterTlvs.WIRELESS:
            # EmaneModel really uses values from ConfigurableManager
            #  when buildnemxml() is called, not during init()
            self.model = model(session=self.session, _id=self.id)
            self.model.update_config(config)
        elif model.config_type == RegisterTlvs.MOBILITY:
            self.mobility = model(session=self.session, _id=self.id)
            self.mobility.update_config(config)

    def setnemid(self, iface: CoreInterface, nemid: int) -> None:
        """
        Record an interface to numerical ID mapping. The Emane controller
        object manages and assigns these IDs for all NEMs.
        """
        self.nemidmap[iface] = nemid

    def getnemid(self, iface: CoreInterface) -> Optional[int]:
        """
        Given an interface, return its numerical ID.
        """
        if iface not in self.nemidmap:
            return None
        else:
            return self.nemidmap[iface]

    def get_nem_iface(self, nemid: int) -> Optional[CoreInterface]:
        """
        Given a numerical NEM ID, return its interface. This returns the
        first interface that matches the given NEM ID.
        """
        for iface in self.nemidmap:
            if self.nemidmap[iface] == nemid:
                return iface
        return None

    def install_ifaces(self) -> None:
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

        for iface in self.get_ifaces():
            external = self.session.emane.get_config(
                "external", self.id, self.model.name
            )
            if external == "0":
                iface.setaddrs()

            if not self.session.emane.genlocationevents():
                iface.poshook = None
                continue

            # at this point we register location handlers for generating
            # EMANE location events
            iface.poshook = self.setnemposition
            iface.setposition()

    def deinstall_ifaces(self) -> None:
        """
        Uninstall TAP devices. This invokes their shutdown method for
        any required cleanup; the device may be actually removed when
        emanetransportd terminates.
        """
        for iface in self.get_ifaces():
            if iface.transport_type == TransportType.VIRTUAL:
                iface.shutdown()
            iface.poshook = None

    def _nem_position(
        self, iface: CoreInterface
    ) -> Optional[Tuple[int, float, float, float]]:
        """
        Creates nem position for emane event for a given interface.

        :param iface: interface to get nem emane position for
        :return: nem position tuple, None otherwise
        """
        nemid = self.getnemid(iface)
        ifname = iface.localname
        if nemid is None:
            logging.info("nemid for %s is unknown", ifname)
            return
        node = iface.node
        x, y, z = node.getposition()
        lat, lon, alt = self.session.location.getgeo(x, y, z)
        if node.position.alt is not None:
            alt = node.position.alt
        node.position.set_geo(lon, lat, alt)
        # altitude must be an integer or warning is printed
        alt = int(round(alt))
        return nemid, lon, lat, alt

    def setnemposition(self, iface: CoreInterface) -> None:
        """
        Publish a NEM location change event using the EMANE event service.

        :param iface: interface to set nem position for
        """
        if self.session.emane.service is None:
            logging.info("position service not available")
            return

        position = self._nem_position(iface)
        if position:
            nemid, lon, lat, alt = position
            event = LocationEvent()
            event.append(nemid, latitude=lat, longitude=lon, altitude=alt)
            self.session.emane.service.publish(0, event)

    def setnempositions(self, moved_ifaces: List[CoreInterface]) -> None:
        """
        Several NEMs have moved, from e.g. a WaypointMobilityModel
        calculation. Generate an EMANE Location Event having several
        entries for each interface that has moved.
        """
        if len(moved_ifaces) == 0:
            return

        if self.session.emane.service is None:
            logging.info("position service not available")
            return

        event = LocationEvent()
        for iface in moved_ifaces:
            position = self._nem_position(iface)
            if position:
                nemid, lon, lat, alt = position
                event.append(nemid, latitude=lat, longitude=lon, altitude=alt)
        self.session.emane.service.publish(0, event)

    def all_link_data(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        links = super().all_link_data(flags)
        # gather current emane links
        nem_ids = set(self.nemidmap.values())
        emane_manager = self.session.emane
        emane_links = emane_manager.link_monitor.links
        considered = set()
        for link_key in emane_links:
            considered_key = tuple(sorted(link_key))
            if considered_key in considered:
                continue
            considered.add(considered_key)
            nem1, nem2 = considered_key
            # ignore links not related to this node
            if nem1 not in nem_ids and nem2 not in nem_ids:
                continue
            # ignore incomplete links
            if (nem2, nem1) not in emane_links:
                continue
            link = emane_manager.get_nem_link(nem1, nem2)
            if link:
                links.append(link)
        return links
