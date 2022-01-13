"""
Implements configuration and control of an EMANE emulation.
"""

import logging
import os
import threading
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Type, Union

from core import utils
from core.emane.emanemodel import EmaneModel
from core.emane.linkmonitor import EmaneLinkMonitor
from core.emane.modelmanager import EmaneModelManager
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData
from core.emulator.enumerations import LinkTypes, MessageFlags, RegisterTlvs
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNetworkBase, CoreNode, NodeBase
from core.nodes.interface import CoreInterface, TunTap
from core.xml import emanexml

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

try:
    from emane.events import EventService, PathlossEvent, CommEffectEvent, LocationEvent
    from emane.events.eventserviceexception import EventServiceException
except ImportError:
    try:
        from emanesh.events import (
            EventService,
            PathlossEvent,
            CommEffectEvent,
            LocationEvent,
        )
        from emanesh.events.eventserviceexception import EventServiceException
    except ImportError:
        CommEffectEvent = None
        EventService = None
        LocationEvent = None
        PathlossEvent = None
        EventServiceException = None
        logger.debug("compatible emane python bindings not installed")

DEFAULT_EMANE_PREFIX = "/usr"
DEFAULT_DEV = "ctrl0"
DEFAULT_LOG_LEVEL: int = 3


class EmaneState(Enum):
    SUCCESS = 0
    NOT_NEEDED = 1
    NOT_READY = 2


class EmaneEventService:
    def __init__(
        self, manager: "EmaneManager", device: str, group: str, port: int
    ) -> None:
        self.manager: "EmaneManager" = manager
        self.device: str = device
        self.group: str = group
        self.port: int = port
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        logger.info("starting emane event service %s %s:%s", device, group, port)
        self.events: EventService = EventService(
            eventchannel=(group, port, device), otachannel=None
        )

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self) -> None:
        """
        Run and monitor events.
        """
        logger.info("subscribing to emane location events")
        while self.running:
            _uuid, _seq, events = self.events.nextEvent()
            # this occurs with 0.9.1 event service
            if not self.running:
                break
            for event in events:
                nem, eid, data = event
                if eid == LocationEvent.IDENTIFIER:
                    self.manager.handlelocationevent(nem, eid, data)
        logger.info("unsubscribing from emane location events")

    def stop(self) -> None:
        """
        Stop service and monitoring events.
        """
        self.events.breakloop()
        self.running = False
        if self.thread:
            self.thread.join()
            self.thread = None
        for fd in self.events._readFd, self.events._writeFd:
            if fd >= 0:
                os.close(fd)
        for f in self.events._socket, self.events._socketOTA:
            if f:
                f.close()


class EmaneManager:
    """
    EMANE controller object. Lives in a Session instance and is used for
    building EMANE config files for all EMANE networks in this emulation, and for
    controlling the EMANE daemons.
    """

    name: str = "emane"
    config_type: RegisterTlvs = RegisterTlvs.EMULATION_SERVER

    def __init__(self, session: "Session") -> None:
        """
        Creates a Emane instance.

        :param session: session this manager is tied to
        :return: nothing
        """
        super().__init__()
        self.session: "Session" = session
        self.nems_to_ifaces: Dict[int, CoreInterface] = {}
        self.ifaces_to_nems: Dict[CoreInterface, int] = {}
        self._emane_nets: Dict[int, EmaneNet] = {}
        self._emane_node_lock: threading.Lock = threading.Lock()
        # port numbers are allocated from these counters
        self.platformport: int = self.session.options.get_config_int(
            "emane_platform_port", 8100
        )
        self.transformport: int = self.session.options.get_config_int(
            "emane_transform_port", 8200
        )
        self.doeventloop: bool = False
        self.eventmonthread: Optional[threading.Thread] = None

        # model for global EMANE configuration options
        self.node_configs: Dict[int, Dict[str, Dict[str, str]]] = {}
        self.node_models: Dict[int, str] = {}

        # link  monitor
        self.link_monitor: EmaneLinkMonitor = EmaneLinkMonitor(self)
        # emane event monitoring
        self.services: Dict[str, EmaneEventService] = {}
        self.nem_service: Dict[int, EmaneEventService] = {}

    def next_nem_id(self, iface: CoreInterface) -> int:
        nem_id = self.session.options.get_config_int("nem_id_start")
        while nem_id in self.nems_to_ifaces:
            nem_id += 1
        self.nems_to_ifaces[nem_id] = iface
        self.ifaces_to_nems[iface] = nem_id
        self.write_nem(iface, nem_id)
        return nem_id

    def get_config(
        self, key: int, model: str, default: bool = True
    ) -> Optional[Dict[str, str]]:
        """
        Get the current or default configuration for an emane model.

        :param key: key to get configuration for
        :param model: emane model to get configuration for
        :param default: True to return default configuration when none exists, False
            otherwise
        :return: emane model configuration
        :raises CoreError: when model does not exist
        """
        model_class = self.get_model(model)
        model_configs = self.node_configs.get(key)
        config = None
        if model_configs:
            config = model_configs.get(model)
        if config is None and default:
            config = model_class.default_values()
        return config

    def set_config(self, key: int, model: str, config: Dict[str, str] = None) -> None:
        """
        Sets and update the provided configuration against the default model
        or currently set emane model configuration.

        :param key: configuration key to set
        :param model: model to set configuration for
        :param config: configuration to update current configuration with
        :return: nothing
        :raises CoreError: when model does not exist
        """
        self.get_model(model)
        model_config = self.get_config(key, model)
        config = config if config else {}
        model_config.update(config)
        model_configs = self.node_configs.setdefault(key, {})
        model_configs[model] = model_config

    def get_model(self, model_name: str) -> Type[EmaneModel]:
        """
        Convenience method for getting globally loaded emane models.

        :param model_name: name of model to retrieve
        :return: emane model class
        :raises CoreError: when model does not exist
        """
        return EmaneModelManager.get(model_name)

    def get_iface_config(
        self, emane_net: EmaneNet, iface: CoreInterface
    ) -> Dict[str, str]:
        """
        Retrieve configuration for a given interface, first checking for interface
        specific config, node specific config, network specific config, and finally
        falling back to the default configuration settings.

        :param emane_net: emane network the interface is connected to
        :param iface: interface running emane
        :return: net, node, or interface model configuration
        """
        model_name = emane_net.model.name
        config = None
        # try to retrieve interface specific configuration
        if iface.node_id is not None:
            key = utils.iface_config_id(iface.node.id, iface.node_id)
            config = self.get_config(key, model_name, default=False)
        # attempt to retrieve node specific config, when iface config is not present
        if not config:
            config = self.get_config(iface.node.id, model_name, default=False)
        # attempt to get emane net specific config, when node config is not present
        if not config:
            # with EMANE 0.9.2+, we need an extra NEM XML from
            # model.buildnemxmlfiles(), so defaults are returned here
            config = self.get_config(emane_net.id, model_name, default=False)
        # return default config values, when a config is not present
        if not config:
            config = emane_net.model.default_values()
        return config

    def config_reset(self, node_id: int = None) -> None:
        if node_id is None:
            self.node_configs.clear()
            self.node_models.clear()
        else:
            self.node_configs.get(node_id, {}).clear()
            self.node_models.pop(node_id, None)

    def add_node(self, emane_net: EmaneNet) -> None:
        """
        Add EMANE network object to this manager.

        :param emane_net: emane node to add
        :return: nothing
        """
        with self._emane_node_lock:
            if emane_net.id in self._emane_nets:
                raise CoreError(
                    f"duplicate emane network({emane_net.id}): {emane_net.name}"
                )
            self._emane_nets[emane_net.id] = emane_net

    def getnodes(self) -> Set[CoreNode]:
        """
        Return a set of CoreNodes that are linked to an EMANE network,
        e.g. containers having one or more radio interfaces.
        """
        nodes = set()
        for emane_net in self._emane_nets.values():
            for iface in emane_net.get_ifaces():
                nodes.add(iface.node)
        return nodes

    def setup(self) -> EmaneState:
        """
        Setup duties for EMANE manager.

        :return: SUCCESS, NOT_NEEDED, NOT_READY in order to delay session
            instantiation
        """
        logger.debug("emane setup")
        with self.session.nodes_lock:
            for node_id in self.session.nodes:
                node = self.session.nodes[node_id]
                if isinstance(node, EmaneNet):
                    logger.debug(
                        "adding emane node: id(%s) name(%s)", node.id, node.name
                    )
                    self.add_node(node)
            if not self._emane_nets:
                logger.debug("no emane nodes in session")
                return EmaneState.NOT_NEEDED
        # check if bindings were installed
        if EventService is None:
            raise CoreError("EMANE python bindings are not installed")
        self.check_node_models()
        return EmaneState.SUCCESS

    def startup(self) -> EmaneState:
        """
        After all the EMANE networks have been added, build XML files
        and start the daemons.

        :return: SUCCESS, NOT_NEEDED, NOT_READY in order to delay session
            instantiation
        """
        self.reset()
        status = self.setup()
        if status != EmaneState.SUCCESS:
            return status
        self.startup_nodes()
        if self.links_enabled():
            self.link_monitor.start()
        return EmaneState.SUCCESS

    def startup_nodes(self) -> None:
        with self._emane_node_lock:
            logger.info("emane building xmls...")
            for emane_net, iface in self.get_ifaces():
                self.start_iface(emane_net, iface)

    def start_iface(self, emane_net: EmaneNet, iface: CoreInterface) -> None:
        nem_id = self.next_nem_id(iface)
        nem_port = self.get_nem_port(iface)
        logger.info(
            "starting emane for node(%s) iface(%s) nem(%s)",
            iface.node.name,
            iface.name,
            nem_id,
        )
        config = self.get_iface_config(emane_net, iface)
        self.setup_control_channels(nem_id, iface, config)
        emanexml.build_platform_xml(nem_id, nem_port, emane_net, iface, config)
        self.start_daemon(iface)
        self.install_iface(iface, config)

    def get_ifaces(self) -> List[Tuple[EmaneNet, CoreInterface]]:
        ifaces = []
        for emane_net in self._emane_nets.values():
            if not emane_net.model:
                logger.error("emane net(%s) has no model", emane_net.name)
                continue
            for iface in emane_net.get_ifaces():
                if not iface.node:
                    logger.error(
                        "emane net(%s) connected interface(%s) missing node",
                        emane_net.name,
                        iface.name,
                    )
                    continue
                ifaces.append((emane_net, iface))
        return sorted(ifaces, key=lambda x: (x[1].node.id, x[1].node_id))

    def setup_control_channels(
        self, nem_id: int, iface: CoreInterface, config: Dict[str, str]
    ) -> None:
        node = iface.node
        # setup ota device
        otagroup, _otaport = config["otamanagergroup"].split(":")
        otadev = config["otamanagerdevice"]
        ota_index = self.session.get_control_net_index(otadev)
        self.session.add_remove_control_net(ota_index, conf_required=False)
        if isinstance(node, CoreNode):
            self.session.add_remove_control_iface(node, ota_index, conf_required=False)
        # setup event device
        eventgroup, eventport = config["eventservicegroup"].split(":")
        eventdev = config["eventservicedevice"]
        event_index = self.session.get_control_net_index(eventdev)
        event_net = self.session.add_remove_control_net(
            event_index, conf_required=False
        )
        if isinstance(node, CoreNode):
            self.session.add_remove_control_iface(
                node, event_index, conf_required=False
            )
        # initialize emane event services
        service = self.services.get(event_net.brname)
        if not service:
            try:
                service = EmaneEventService(
                    self, event_net.brname, eventgroup, int(eventport)
                )
                self.services[event_net.brname] = service
                self.nem_service[nem_id] = service
            except EventServiceException:
                raise CoreError(
                    "failed to start emane event services "
                    f"{event_net.brname} {eventgroup}:{eventport}"
                )
        else:
            self.nem_service[nem_id] = service
        # setup multicast routes as needed
        logger.info(
            "node(%s) interface(%s) ota(%s:%s) event(%s:%s)",
            node.name,
            iface.name,
            otagroup,
            otadev,
            eventgroup,
            eventdev,
        )
        node.node_net_client.create_route(otagroup, otadev)
        if eventgroup != otagroup:
            node.node_net_client.create_route(eventgroup, eventdev)

    def get_iface(self, nem_id: int) -> Optional[CoreInterface]:
        return self.nems_to_ifaces.get(nem_id)

    def get_nem_id(self, iface: CoreInterface) -> Optional[int]:
        return self.ifaces_to_nems.get(iface)

    def get_nem_port(self, iface: CoreInterface) -> int:
        nem_id = self.get_nem_id(iface)
        return int(f"47{nem_id:03}")

    def get_nem_position(
        self, iface: CoreInterface
    ) -> Optional[Tuple[int, float, float, int]]:
        """
        Retrieves nem position for a given interface.

        :param iface: interface to get nem emane position for
        :return: nem position tuple, None otherwise
        """
        nem_id = self.get_nem_id(iface)
        if nem_id is None:
            logger.info("nem for %s is unknown", iface.localname)
            return
        node = iface.node
        x, y, z = node.getposition()
        lat, lon, alt = self.session.location.getgeo(x, y, z)
        if node.position.alt is not None:
            alt = node.position.alt
        node.position.set_geo(lon, lat, alt)
        # altitude must be an integer or warning is printed
        alt = int(round(alt))
        return nem_id, lon, lat, alt

    def set_nem_position(self, iface: CoreInterface) -> None:
        """
        Publish a NEM location change event using the EMANE event service.

        :param iface: interface to set nem position for
        """
        position = self.get_nem_position(iface)
        if position:
            nemid, lon, lat, alt = position
            event = LocationEvent()
            event.append(nemid, latitude=lat, longitude=lon, altitude=alt)
            self.publish_event(nemid, event, send_all=True)

    def set_nem_positions(self, moved_ifaces: List[CoreInterface]) -> None:
        """
        Several NEMs have moved, from e.g. a WaypointMobilityModel
        calculation. Generate an EMANE Location Event having several
        entries for each interface that has moved.
        """
        if not moved_ifaces:
            return
        services = {}
        for iface in moved_ifaces:
            position = self.get_nem_position(iface)
            if not position:
                continue
            nem_id, lon, lat, alt = position
            service = self.nem_service.get(nem_id)
            if not service:
                continue
            event = services.setdefault(service, LocationEvent())
            event.append(nem_id, latitude=lat, longitude=lon, altitude=alt)
        for service, event in services.items():
            service.events.publish(0, event)

    def write_nem(self, iface: CoreInterface, nem_id: int) -> None:
        path = self.session.directory / "emane_nems"
        try:
            with path.open("a") as f:
                f.write(f"{iface.node.name} {iface.name} {nem_id}\n")
        except IOError:
            logger.exception("error writing to emane nem file")

    def links_enabled(self) -> bool:
        return self.session.options.get_config_int("link_enabled") == 1

    def poststartup(self) -> None:
        """
        Retransmit location events now that all NEMs are active.
        """
        events_enabled = self.genlocationevents()
        with self._emane_node_lock:
            for node_id in sorted(self._emane_nets):
                emane_net = self._emane_nets[node_id]
                logger.debug(
                    "post startup for emane node: %s - %s", emane_net.id, emane_net.name
                )
                for iface in emane_net.get_ifaces():
                    emane_net.model.post_startup(iface)
                    if events_enabled:
                        iface.setposition()

    def reset(self) -> None:
        """
        Remove all EMANE networks from the dictionary, reset port numbers and
        nem id counters
        """
        with self._emane_node_lock:
            self._emane_nets.clear()
            self.nems_to_ifaces.clear()
            self.ifaces_to_nems.clear()
            self.nems_to_ifaces.clear()
            self.services.clear()

    def shutdown(self) -> None:
        """
        stop all EMANE daemons
        """
        with self._emane_node_lock:
            if not self._emane_nets:
                return
            logger.info("stopping EMANE daemons")
            if self.links_enabled():
                self.link_monitor.stop()
            # shutdown interfaces
            for _, iface in self.get_ifaces():
                node = iface.node
                if not node.up:
                    continue
                kill_cmd = f'pkill -f "emane.+{iface.name}"'
                if isinstance(node, CoreNode):
                    iface.shutdown()
                    node.cmd(kill_cmd, wait=False)
                else:
                    node.host_cmd(kill_cmd, wait=False)
                iface.poshook = None
            # stop emane event services
            while self.services:
                _, service = self.services.popitem()
                service.stop()
            self.nem_service.clear()

    def check_node_models(self) -> None:
        """
        Associate EMANE model classes with EMANE network nodes.
        """
        for node_id in self._emane_nets:
            emane_net = self._emane_nets[node_id]
            logger.debug("checking emane model for node: %s", node_id)
            # skip nodes that already have a model set
            if emane_net.model:
                logger.debug(
                    "node(%s) already has model(%s)", emane_net.id, emane_net.model.name
                )
                continue
            # set model configured for node, due to legacy messaging configuration
            # before nodes exist
            model_name = self.node_models.get(node_id)
            if not model_name:
                logger.error("emane node(%s) has no node model", node_id)
                raise ValueError("emane node has no model set")

            config = self.get_config(node_id, model_name)
            logger.debug("setting emane model(%s) config(%s)", model_name, config)
            model_class = self.get_model(model_name)
            emane_net.setmodel(model_class, config)

    def get_nem_link(
        self, nem1: int, nem2: int, flags: MessageFlags = MessageFlags.NONE
    ) -> Optional[LinkData]:
        iface1 = self.get_iface(nem1)
        if not iface1:
            logger.error("invalid nem: %s", nem1)
            return None
        node1 = iface1.node
        iface2 = self.get_iface(nem2)
        if not iface2:
            logger.error("invalid nem: %s", nem2)
            return None
        node2 = iface2.node
        if iface1.net != iface2.net:
            return None
        emane_net = iface1.net
        color = self.session.get_link_color(emane_net.id)
        return LinkData(
            message_type=flags,
            type=LinkTypes.WIRELESS,
            node1_id=node1.id,
            node2_id=node2.id,
            network_id=emane_net.id,
            color=color,
        )

    def start_daemon(self, iface: CoreInterface) -> None:
        """
        Start emane daemon for a given nem/interface.

        :param iface: interface to start emane daemon for
        :return: nothing
        """
        node = iface.node
        loglevel = str(DEFAULT_LOG_LEVEL)
        cfgloglevel = self.session.options.get_config_int("emane_log_level")
        realtime = self.session.options.get_config_bool("emane_realtime", default=True)
        if cfgloglevel:
            logger.info("setting user-defined emane log level: %d", cfgloglevel)
            loglevel = str(cfgloglevel)
        emanecmd = f"emane -d -l {loglevel}"
        if realtime:
            emanecmd += " -r"
        if isinstance(node, CoreNode):
            # start emane
            log_file = node.directory / f"{iface.name}-emane.log"
            platform_xml = node.directory / emanexml.platform_file_name(iface)
            args = f"{emanecmd} -f {log_file} {platform_xml}"
            node.cmd(args)
        else:
            log_file = self.session.directory / f"{iface.name}-emane.log"
            platform_xml = self.session.directory / emanexml.platform_file_name(iface)
            args = f"{emanecmd} -f {log_file} {platform_xml}"
            node.host_cmd(args, cwd=self.session.directory)

    def install_iface(self, iface: CoreInterface, config: Dict[str, str]) -> None:
        external = config.get("external", "0")
        if isinstance(iface, TunTap) and external == "0":
            iface.set_ips()
        # at this point we register location handlers for generating
        # EMANE location events
        if self.genlocationevents():
            iface.poshook = self.set_nem_position
            iface.setposition()

    def doeventmonitor(self) -> bool:
        """
        Returns boolean whether or not EMANE events will be monitored.
        """
        # this support must be explicitly turned on; by default, CORE will
        # generate the EMANE events when nodes are moved
        return self.session.options.get_config_bool("emane_event_monitor")

    def genlocationevents(self) -> bool:
        """
        Returns boolean whether or not EMANE events will be generated.
        """
        # By default, CORE generates EMANE location events when nodes
        # are moved; this can be explicitly disabled in core.conf
        tmp = self.session.options.get_config_bool("emane_event_generate")
        if tmp is None:
            tmp = not self.doeventmonitor()
        return tmp

    def handlelocationevent(self, rxnemid: int, eid: int, data: str) -> None:
        """
        Handle an EMANE location event.
        """
        events = LocationEvent()
        events.restore(data)
        for event in events:
            txnemid, attrs = event
            if (
                "latitude" not in attrs
                or "longitude" not in attrs
                or "altitude" not in attrs
            ):
                logger.warning("dropped invalid location event")
                continue
            # yaw,pitch,roll,azimuth,elevation,velocity are unhandled
            lat = attrs["latitude"]
            lon = attrs["longitude"]
            alt = attrs["altitude"]
            logger.debug("emane location event: %s,%s,%s", lat, lon, alt)
            self.handlelocationeventtoxyz(txnemid, lat, lon, alt)

    def handlelocationeventtoxyz(
        self, nemid: int, lat: float, lon: float, alt: float
    ) -> bool:
        """
        Convert the (NEM ID, lat, long, alt) from a received location event
        into a node and x,y,z coordinate values, sending a Node Message.
        Returns True if successfully parsed and a Node Message was sent.
        """
        # convert nemid to node number
        iface = self.get_iface(nemid)
        if iface is None:
            logger.info("location event for unknown NEM %s", nemid)
            return False

        n = iface.node.id
        # convert from lat/long/alt to x,y,z coordinates
        x, y, z = self.session.location.getxyz(lat, lon, alt)
        x = int(x)
        y = int(y)
        z = int(z)
        logger.debug(
            "location event NEM %s (%s, %s, %s) -> (%s, %s, %s)",
            nemid,
            lat,
            lon,
            alt,
            x,
            y,
            z,
        )
        xbit_check = x.bit_length() > 16 or x < 0
        ybit_check = y.bit_length() > 16 or y < 0
        zbit_check = z.bit_length() > 16 or z < 0
        if any([xbit_check, ybit_check, zbit_check]):
            logger.error(
                "Unable to build node location message, received lat/long/alt "
                "exceeds coordinate space: NEM %s (%d, %d, %d)",
                nemid,
                x,
                y,
                z,
            )
            return False

        # generate a node message for this location update
        try:
            node = self.session.get_node(n, NodeBase)
        except CoreError:
            logger.exception(
                "location event NEM %s has no corresponding node %s", nemid, n
            )
            return False

        # don"t use node.setposition(x,y,z) which generates an event
        node.position.set(x, y, z)
        node.position.set_geo(lon, lat, alt)
        self.session.broadcast_node(node)
        return True

    def is_emane_net(self, net: Optional[CoreNetworkBase]) -> bool:
        return isinstance(net, EmaneNet)

    def emanerunning(self, node: CoreNode) -> bool:
        """
        Return True if an EMANE process associated with the given node is running,
        False otherwise.
        """
        args = "pkill -0 -x emane"
        try:
            node.cmd(args)
            result = True
        except CoreCommandError:
            result = False
        return result

    def publish_pathloss(self, nem1: int, nem2: int, rx1: float, rx2: float) -> None:
        """
        Publish pathloss events between provided nems, using provided rx power.
        :param nem1: interface one for pathloss
        :param nem2: interface two for pathloss
        :param rx1: received power from nem2 to nem1
        :param rx2: received power from nem1 to nem2
        :return: nothing
        """
        event = PathlossEvent()
        event.append(nem1, forward=rx1)
        event.append(nem2, forward=rx2)
        self.publish_event(nem1, event)
        self.publish_event(nem2, event)

    def publish_event(
        self,
        nem_id: int,
        event: Union[PathlossEvent, CommEffectEvent, LocationEvent],
        send_all: bool = False,
    ) -> None:
        service = self.nem_service.get(nem_id)
        if not service:
            logger.error("no service to publish event nem(%s)", nem_id)
            return
        if send_all:
            nem_id = 0
        service.events.publish(nem_id, event)
