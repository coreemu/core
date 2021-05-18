"""
emane.py: definition of an Emane class for implementing configuration control of an EMANE emulation.
"""

import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Type

from core import utils
from core.config import ConfigGroup, Configuration
from core.emane import emanemanifest
from core.emane.emanemodel import EmaneModel
from core.emane.linkmonitor import EmaneLinkMonitor
from core.emane.modelmanager import EmaneModelManager
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData
from core.emulator.enumerations import (
    ConfigDataTypes,
    LinkTypes,
    MessageFlags,
    RegisterTlvs,
)
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNetworkBase, CoreNode, CoreNodeBase, NodeBase
from core.nodes.interface import CoreInterface, TunTap
from core.xml import emanexml

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

try:
    from emane.events import EventService, PathlossEvent
    from emane.events import LocationEvent
    from emane.events.eventserviceexception import EventServiceException
except ImportError:
    try:
        from emanesh.events import EventService
        from emanesh.events import LocationEvent
        from emanesh.events.eventserviceexception import EventServiceException
    except ImportError:
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


@dataclass
class StartData:
    node: CoreNodeBase
    ifaces: List[CoreInterface] = field(default_factory=list)


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
        self.emane_config: EmaneGlobalModel = EmaneGlobalModel(session)
        self.config: Dict[str, str] = self.emane_config.default_values()
        self.node_configs: Dict[int, Dict[str, Dict[str, str]]] = {}
        self.node_models: Dict[int, str] = {}

        # link  monitor
        self.link_monitor: EmaneLinkMonitor = EmaneLinkMonitor(self)

        self.service: Optional[EventService] = None
        self.eventchannel: Optional[Tuple[str, int, str]] = None
        self.event_device: Optional[str] = None

    def next_nem_id(self, iface: CoreInterface) -> int:
        nem_id = int(self.config["nem_id_start"])
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
            self.config = self.emane_config.default_values()
            self.node_configs.clear()
            self.node_models.clear()
        else:
            self.node_configs.get(node_id, {}).clear()
            self.node_models.pop(node_id, None)

    def deleteeventservice(self) -> None:
        if self.service:
            for fd in self.service._readFd, self.service._writeFd:
                if fd >= 0:
                    os.close(fd)
            for f in self.service._socket, self.service._socketOTA:
                if f:
                    f.close()
        self.service = None
        self.event_device = None

    def initeventservice(self, filename: str = None, shutdown: bool = False) -> None:
        """
        Re-initialize the EMANE Event service.
        The multicast group and/or port may be configured.
        """
        self.deleteeventservice()
        if shutdown:
            return

        # Get the control network to be used for events
        group, port = self.config["eventservicegroup"].split(":")
        self.event_device = self.config["eventservicedevice"]
        eventnetidx = self.session.get_control_net_index(self.event_device)
        if eventnetidx < 0:
            logger.error(
                "invalid emane event service device provided: %s", self.event_device
            )
            return

        # make sure the event control network is in place
        eventnet = self.session.add_remove_control_net(
            net_index=eventnetidx, remove=False, conf_required=False
        )
        if eventnet is not None:
            # direct EMANE events towards control net bridge
            self.event_device = eventnet.brname
        self.eventchannel = (group, int(port), self.event_device)

        # disabled otachannel for event service
        # only needed for e.g. antennaprofile events xmit by models
        logger.info("using %s for event service traffic", self.event_device)
        try:
            self.service = EventService(eventchannel=self.eventchannel, otachannel=None)
        except EventServiceException:
            logger.exception("error instantiating emane EventService")

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

        # control network bridge required for EMANE 0.9.2
        # - needs to exist when eventservice binds to it (initeventservice)
        otadev = self.config["otamanagerdevice"]
        netidx = self.session.get_control_net_index(otadev)
        logger.debug("emane ota manager device: index(%s) otadev(%s)", netidx, otadev)
        if netidx < 0:
            logger.error(
                "EMANE cannot start, check core config. invalid OTA device provided: %s",
                otadev,
            )
            return EmaneState.NOT_READY

        self.session.add_remove_control_net(
            net_index=netidx, remove=False, conf_required=False
        )
        eventdev = self.config["eventservicedevice"]
        logger.debug("emane event service device: eventdev(%s)", eventdev)
        if eventdev != otadev:
            netidx = self.session.get_control_net_index(eventdev)
            logger.debug("emane event service device index: %s", netidx)
            if netidx < 0:
                logger.error(
                    "emane cannot start due to invalid event service device: %s",
                    eventdev,
                )
                return EmaneState.NOT_READY

            self.session.add_remove_control_net(
                net_index=netidx, remove=False, conf_required=False
            )
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
        self.starteventmonitor()
        self.buildeventservicexml()
        with self._emane_node_lock:
            logger.info("emane building xmls...")
            start_data = self.get_start_data()
            for data in start_data:
                self.start_node(data)
        if self.links_enabled():
            self.link_monitor.start()
        return EmaneState.SUCCESS

    def get_start_data(self) -> List[StartData]:
        node_map = {}
        for node_id in sorted(self._emane_nets):
            emane_net = self._emane_nets[node_id]
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
                start_node = node_map.setdefault(iface.node, StartData(iface.node))
                start_node.ifaces.append(iface)
        start_nodes = sorted(node_map.values(), key=lambda x: x.node.id)
        for start_node in start_nodes:
            start_node.ifaces = sorted(start_node.ifaces, key=lambda x: x.node_id)
        return start_nodes

    def start_node(self, data: StartData) -> None:
        node = data.node
        control_net = self.session.add_remove_control_net(
            0, remove=False, conf_required=False
        )
        if isinstance(node, CoreNode):
            # setup ota device
            otagroup, _otaport = self.config["otamanagergroup"].split(":")
            otadev = self.config["otamanagerdevice"]
            otanetidx = self.session.get_control_net_index(otadev)
            eventgroup, _eventport = self.config["eventservicegroup"].split(":")
            eventdev = self.config["eventservicedevice"]
            eventservicenetidx = self.session.get_control_net_index(eventdev)
            # control network not yet started here
            self.session.add_remove_control_iface(
                node, 0, remove=False, conf_required=False
            )
            if otanetidx > 0:
                logger.info("adding ota device ctrl%d", otanetidx)
                self.session.add_remove_control_iface(
                    node, otanetidx, remove=False, conf_required=False
                )
            if eventservicenetidx >= 0:
                logger.info("adding event service device ctrl%d", eventservicenetidx)
                self.session.add_remove_control_iface(
                    node, eventservicenetidx, remove=False, conf_required=False
                )
            # multicast route is needed for OTA data
            logger.info("OTA GROUP(%s) OTA DEV(%s)", otagroup, otadev)
            node.node_net_client.create_route(otagroup, otadev)
            # multicast route is also needed for event data if on control network
            if eventservicenetidx >= 0 and eventgroup != otagroup:
                node.node_net_client.create_route(eventgroup, eventdev)
        # builds xmls and start emane daemons
        for iface in data.ifaces:
            emanexml.build_platform_xml(self, control_net, node, iface)
            self.start_daemon(node, iface)
            self.install_iface(iface)

    def get_iface(self, nem_id: int) -> Optional[CoreInterface]:
        return self.nems_to_ifaces.get(nem_id)

    def get_nem_id(self, iface: CoreInterface) -> Optional[int]:
        return self.ifaces_to_nems.get(iface)

    def get_nem_port(self, iface: CoreInterface) -> int:
        nem_id = self.get_nem_id(iface)
        return int(f"47{nem_id:03}")

    def write_nem(self, iface: CoreInterface, nem_id: int) -> None:
        path = self.session.directory / "emane_nems"
        try:
            with path.open("a") as f:
                f.write(f"{iface.node.name} {iface.name} {nem_id}\n")
        except IOError:
            logger.exception("error writing to emane nem file")

    def links_enabled(self) -> bool:
        return self.config["link_enabled"] == "1"

    def poststartup(self) -> None:
        """
        Retransmit location events now that all NEMs are active.
        """
        if not self.genlocationevents():
            return
        with self._emane_node_lock:
            for node_id in sorted(self._emane_nets):
                emane_net = self._emane_nets[node_id]
                logger.debug(
                    "post startup for emane node: %s - %s", emane_net.id, emane_net.name
                )
                emane_net.model.post_startup()
                for iface in emane_net.get_ifaces():
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
            # shutdown interfaces and stop daemons
            kill_emaned = "killall -q emane"
            start_data = self.get_start_data()
            for data in start_data:
                node = data.node
                if not node.up:
                    continue
                for iface in data.ifaces:
                    if isinstance(node, CoreNode):
                        iface.shutdown()
                    iface.poshook = None
                if isinstance(node, CoreNode):
                    node.cmd(kill_emaned, wait=False)
                else:
                    node.host_cmd(kill_emaned, wait=False)
            self.stopeventmonitor()

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

    def buildeventservicexml(self) -> None:
        """
        Build the libemaneeventservice.xml file if event service options
        were changed in the global config.
        """
        need_xml = False
        default_values = self.emane_config.default_values()
        for name in ["eventservicegroup", "eventservicedevice"]:
            a = default_values[name]
            b = self.config[name]
            if a != b:
                need_xml = True
        if not need_xml:
            # reset to using default config
            self.initeventservice()
            return
        try:
            group, port = self.config["eventservicegroup"].split(":")
        except ValueError:
            logger.exception("invalid eventservicegroup in EMANE config")
            return
        dev = self.config["eventservicedevice"]
        emanexml.create_event_service_xml(group, port, dev, self.session.directory)
        self.session.distributed.execute(
            lambda x: emanexml.create_event_service_xml(
                group, port, dev, self.session.directory, x
            )
        )

    def start_daemon(self, node: CoreNodeBase, iface: CoreInterface) -> None:
        """
        Start one EMANE daemon per node having a radio.
        Add a control network even if the user has not configured one.
        """
        logger.info("starting emane daemons...")
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
            logger.info("node(%s) emane daemon running: %s", node.name, args)
        else:
            log_file = self.session.directory / f"{iface.name}-emane.log"
            platform_xml = self.session.directory / emanexml.platform_file_name(iface)
            args = f"{emanecmd} -f {log_file} {platform_xml}"
            node.host_cmd(args, cwd=self.session.directory)
            logger.info("node(%s) host emane daemon running: %s", node.name, args)

    def install_iface(self, iface: CoreInterface) -> None:
        emane_net = iface.net
        if not isinstance(emane_net, EmaneNet):
            raise CoreError(
                f"emane interface not connected to emane net: {emane_net.name}"
            )
        config = self.get_iface_config(emane_net, iface)
        external = config.get("external", "0")
        if isinstance(iface, TunTap) and external == "0":
            iface.set_ips()
        # at this point we register location handlers for generating
        # EMANE location events
        if self.genlocationevents():
            iface.poshook = emane_net.setnemposition
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

    def starteventmonitor(self) -> None:
        """
        Start monitoring EMANE location events if configured to do so.
        """
        logger.info("emane start event monitor")
        if not self.doeventmonitor():
            return
        if self.service is None:
            logger.error(
                "Warning: EMANE events will not be generated "
                "because the emaneeventservice\n binding was "
                "unable to load "
                "(install the python-emaneeventservice bindings)"
            )
            return
        self.doeventloop = True
        self.eventmonthread = threading.Thread(
            target=self.eventmonitorloop, daemon=True
        )
        self.eventmonthread.start()

    def stopeventmonitor(self) -> None:
        """
        Stop monitoring EMANE location events.
        """
        self.doeventloop = False
        if self.service is not None:
            self.service.breakloop()
            # reset the service, otherwise nextEvent won"t work
            self.initeventservice(shutdown=True)

        if self.eventmonthread is not None:
            self.eventmonthread.join()
            self.eventmonthread = None

    def eventmonitorloop(self) -> None:
        """
        Thread target that monitors EMANE location events.
        """
        if self.service is None:
            return
        logger.info(
            "subscribing to EMANE location events. (%s)",
            threading.currentThread().getName(),
        )
        while self.doeventloop is True:
            _uuid, _seq, events = self.service.nextEvent()

            # this occurs with 0.9.1 event service
            if not self.doeventloop:
                break

            for event in events:
                nem, eid, data = event
                if eid == LocationEvent.IDENTIFIER:
                    self.handlelocationevent(nem, eid, data)

        logger.info(
            "unsubscribing from EMANE location events. (%s)",
            threading.currentThread().getName(),
        )

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
        self.service.publish(nem1, event)
        self.service.publish(nem2, event)


class EmaneGlobalModel:
    """
    Global EMANE configuration options.
    """

    name: str = "emane"
    bitmap: Optional[str] = None

    def __init__(self, session: "Session") -> None:
        self.session: "Session" = session
        self.core_config: List[Configuration] = [
            Configuration(
                id="platform_id_start",
                type=ConfigDataTypes.INT32,
                default="1",
                label="Starting Platform ID",
            ),
            Configuration(
                id="nem_id_start",
                type=ConfigDataTypes.INT32,
                default="1",
                label="Starting NEM ID",
            ),
            Configuration(
                id="link_enabled",
                type=ConfigDataTypes.BOOL,
                default="1",
                label="Enable Links?",
            ),
            Configuration(
                id="loss_threshold",
                type=ConfigDataTypes.INT32,
                default="30",
                label="Link Loss Threshold (%)",
            ),
            Configuration(
                id="link_interval",
                type=ConfigDataTypes.INT32,
                default="1",
                label="Link Check Interval (sec)",
            ),
            Configuration(
                id="link_timeout",
                type=ConfigDataTypes.INT32,
                default="4",
                label="Link Timeout (sec)",
            ),
        ]
        self.emulator_config = None
        self.parse_config()

    def parse_config(self) -> None:
        emane_prefix = self.session.options.get_config(
            "emane_prefix", default=DEFAULT_EMANE_PREFIX
        )
        emane_prefix = Path(emane_prefix)
        emulator_xml = emane_prefix / "share/emane/manifest/nemmanager.xml"
        emulator_defaults = {
            "eventservicedevice": DEFAULT_DEV,
            "eventservicegroup": "224.1.2.8:45703",
            "otamanagerdevice": DEFAULT_DEV,
            "otamanagergroup": "224.1.2.8:45702",
        }
        self.emulator_config = emanemanifest.parse(emulator_xml, emulator_defaults)

    def configurations(self) -> List[Configuration]:
        return self.emulator_config + self.core_config

    def config_groups(self) -> List[ConfigGroup]:
        emulator_len = len(self.emulator_config)
        config_len = len(self.configurations())
        return [
            ConfigGroup("Platform Attributes", 1, emulator_len),
            ConfigGroup("CORE Configuration", emulator_len + 1, config_len),
        ]

    def default_values(self) -> Dict[str, str]:
        return OrderedDict(
            [(config.id, config.default) for config in self.configurations()]
        )
