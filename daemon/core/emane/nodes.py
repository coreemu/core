"""
Provides an EMANE network node class, which has several attached NEMs that
share the same MAC+PHY model.
"""

import logging
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Type

from core.emulator.data import InterfaceData, LinkData, LinkOptions
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import EventTypes, MessageFlags, NodeTypes, RegisterTlvs
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNetworkBase, CoreNode
from core.nodes.interface import CoreInterface

logger = logging.getLogger(__name__)

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
        logger.debug("compatible emane python bindings not installed")


class TunTap(CoreInterface):
    """
    TUN/TAP virtual device in TAP mode
    """

    def __init__(
        self,
        _id: int,
        name: str,
        localname: str,
        use_ovs: bool,
        node: CoreNode = None,
        server: "DistributedServer" = None,
    ) -> None:
        super().__init__(_id, name, localname, use_ovs, node=node, server=server)
        self.node: CoreNode = node

    def startup(self) -> None:
        """
        Startup logic for a tunnel tap.

        :return: nothing
        """
        self.up = True

    def shutdown(self) -> None:
        """
        Shutdown functionality for a tunnel tap.

        :return: nothing
        """
        if not self.up:
            return
        self.up = False

    def waitfor(
        self, func: Callable[[], int], attempts: int = 10, maxretrydelay: float = 0.25
    ) -> bool:
        """
        Wait for func() to return zero with exponential backoff.

        :param func: function to wait for a result of zero
        :param attempts: number of attempts to wait for a zero result
        :param maxretrydelay: maximum retry delay
        :return: True if wait succeeded, False otherwise
        """
        delay = 0.01
        result = False
        for i in range(1, attempts + 1):
            r = func()
            if r == 0:
                result = True
                break
            msg = f"attempt {i} failed with nonzero exit status {r}"
            if i < attempts + 1:
                msg += ", retrying..."
                logger.info(msg)
                time.sleep(delay)
                delay += delay
                if delay > maxretrydelay:
                    delay = maxretrydelay
            else:
                msg += ", giving up"
                logger.info(msg)
        return result

    def nodedevexists(self) -> int:
        """
        Checks if device exists.

        :return: 0 if device exists, 1 otherwise
        """
        try:
            self.node.node_net_client.device_show(self.name)
            return 0
        except CoreCommandError:
            return 1

    def waitfordevicenode(self) -> None:
        """
        Check for presence of a node device - tap device may not appear right away waits.

        :return: nothing
        """
        logger.debug("waiting for device node: %s", self.name)
        count = 0
        while True:
            result = self.waitfor(self.nodedevexists)
            if result:
                break
            should_retry = count < 5
            is_emane_running = self.node.session.emane.emanerunning(self.node)
            if all([should_retry, is_emane_running]):
                count += 1
            else:
                raise RuntimeError("node device failed to exist")

    def set_ips(self) -> None:
        """
        Set interface ip addresses.

        :return: nothing
        """
        self.waitfordevicenode()
        for ip in self.ips():
            self.node.node_net_client.create_address(self.name, str(ip))


class EmaneNet(CoreNetworkBase):
    """
    EMANE node contains NEM configuration and causes connected nodes
    to have TAP interfaces (instead of VEth). These are managed by the
    Emane controller object that exists in a session.
    """

    apitype: NodeTypes = NodeTypes.EMANE
    type: str = "wlan"

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: DistributedServer = None,
    ) -> None:
        super().__init__(session, _id, name, server)
        self.conf: str = ""
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

    def startup(self) -> None:
        self.up = True

    def shutdown(self) -> None:
        self.up = False

    def link(self, iface1: CoreInterface, iface2: CoreInterface) -> None:
        pass

    def unlink(self, iface1: CoreInterface, iface2: CoreInterface) -> None:
        pass

    def updatemodel(self, config: Dict[str, str]) -> None:
        """
        Update configuration for the current model.

        :param config: configuration to update model with
        :return: nothing
        """
        if not self.model:
            raise CoreError(f"no model set to update for node({self.name})")
        logger.info("node(%s) updating model(%s): %s", self.id, self.model.name, config)
        self.model.update_config(config)

    def setmodel(self, model: "WirelessModelType", config: Dict[str, str]) -> None:
        """
        set the EmaneModel associated with this node
        """
        if model.config_type == RegisterTlvs.WIRELESS:
            # EmaneModel really uses values from ConfigurableManager
            #  when buildnemxml() is called, not during init()
            self.model = model(session=self.session, _id=self.id)
            self.model.update_config(config)
        elif model.config_type == RegisterTlvs.MOBILITY:
            self.mobility = model(session=self.session, _id=self.id)
            self.mobility.update_config(config)

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        links = []
        emane_manager = self.session.emane
        # gather current emane links
        nem_ids = set()
        for iface in self.get_ifaces():
            nem_id = emane_manager.get_nem_id(iface)
            nem_ids.add(nem_id)
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
            link = emane_manager.get_nem_link(nem1, nem2, flags)
            if link:
                links.append(link)
        return links

    def create_tuntap(self, node: CoreNode, iface_data: InterfaceData) -> CoreInterface:
        """
        Create a tuntap interface for the provided node.

        :param node: node to create tuntap interface for
        :param iface_data: interface data to create interface with
        :return: created tuntap interface
        """
        with node.lock:
            if iface_data.id is not None and iface_data.id in node.ifaces:
                raise CoreError(
                    f"node({self.id}) interface({iface_data.id}) already exists"
                )
            iface_id = (
                iface_data.id if iface_data.id is not None else node.next_iface_id()
            )
            name = iface_data.name if iface_data.name is not None else f"eth{iface_id}"
            session_id = self.session.short_session_id()
            localname = f"tap{node.id}.{iface_id}.{session_id}"
            iface = TunTap(iface_id, name, localname, self.session.use_ovs(), node=node)
            if iface_data.mac:
                iface.set_mac(iface_data.mac)
            for ip in iface_data.get_ips():
                iface.add_ip(ip)
            node.ifaces[iface_id] = iface
            self.attach(iface)
        if self.up:
            iface.startup()
        if self.session.state == EventTypes.RUNTIME_STATE:
            self.session.emane.start_iface(self, iface)
        return iface

    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        raise CoreError(
            f"emane network({self.name}) do not support adopting interfaces"
        )
