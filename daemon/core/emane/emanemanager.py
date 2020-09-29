"""
emane.py: definition of an Emane class for implementing configuration control of an EMANE emulation.
"""

import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Type

from core import utils
from core.config import ConfigGroup, Configuration, ModelManager
from core.emane import emanemanifest
from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.emanemodel import EmaneModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.linkmonitor import EmaneLinkMonitor
from core.emane.nodes import EmaneNet
from core.emane.rfpipe import EmaneRfPipeModel
from core.emane.tdma import EmaneTdmaModel
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
        logging.debug("compatible emane python bindings not installed")

EMANE_MODELS = [
    EmaneRfPipeModel,
    EmaneIeee80211abgModel,
    EmaneCommEffectModel,
    EmaneBypassModel,
    EmaneTdmaModel,
]
DEFAULT_EMANE_PREFIX = "/usr"
DEFAULT_DEV = "ctrl0"


class EmaneState(Enum):
    SUCCESS = 0
    NOT_NEEDED = 1
    NOT_READY = 2


@dataclass
class StartData:
    node: CoreNodeBase
    ifaces: List[CoreInterface] = field(default_factory=list)


class EmaneManager(ModelManager):
    """
    EMANE controller object. Lives in a Session instance and is used for
    building EMANE config files for all EMANE networks in this emulation, and for
    controlling the EMANE daemons.
    """

    name: str = "emane"
    config_type: RegisterTlvs = RegisterTlvs.EMULATION_SERVER
    NOT_READY: int = 2
    EVENTCFGVAR: str = "LIBEMANEEVENTSERVICECONFIG"
    DEFAULT_LOG_LEVEL: int = 3

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
        self.set_configs(self.emane_config.default_values())

        # link  monitor
        self.link_monitor: EmaneLinkMonitor = EmaneLinkMonitor(self)

        self.service: Optional[EventService] = None
        self.eventchannel: Optional[Tuple[str, int, str]] = None
        self.event_device: Optional[str] = None
        self.emane_check()

    def next_nem_id(self) -> int:
        nem_id = int(self.get_config("nem_id_start"))
        while nem_id in self.nems_to_ifaces:
            nem_id += 1
        return nem_id

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
            config = self.get_configs(node_id=key, config_type=model_name)
        # attempt to retrieve node specific config, when iface config is not present
        if not config:
            config = self.get_configs(node_id=iface.node.id, config_type=model_name)
        # attempt to get emane net specific config, when node config is not present
        if not config:
            # with EMANE 0.9.2+, we need an extra NEM XML from
            # model.buildnemxmlfiles(), so defaults are returned here
            config = self.get_configs(node_id=emane_net.id, config_type=model_name)
        # return default config values, when a config is not present
        if not config:
            config = emane_net.model.default_values()
        return config

    def config_reset(self, node_id: int = None) -> None:
        super().config_reset(node_id)
        self.set_configs(self.emane_config.default_values())

    def emane_check(self) -> None:
        """
        Check if emane is installed and load models.

        :return: nothing
        """
        # check for emane
        path = utils.which("emane", required=False)
        if not path:
            logging.info("emane is not installed")
            return

        # get version
        emane_version = utils.cmd("emane --version")
        logging.info("using emane: %s", emane_version)

        # load default emane models
        self.load_models(EMANE_MODELS)

        # load custom models
        custom_models_path = self.session.options.get_config("emane_models_dir")
        if custom_models_path:
            emane_models = utils.load_classes(custom_models_path, EmaneModel)
            self.load_models(emane_models)

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
        group, port = self.get_config("eventservicegroup").split(":")
        self.event_device = self.get_config("eventservicedevice")
        eventnetidx = self.session.get_control_net_index(self.event_device)
        if eventnetidx < 0:
            logging.error(
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
        logging.info("using %s for event service traffic", self.event_device)
        try:
            self.service = EventService(eventchannel=self.eventchannel, otachannel=None)
        except EventServiceException:
            logging.exception("error instantiating emane EventService")

    def load_models(self, emane_models: List[Type[EmaneModel]]) -> None:
        """
        Load EMANE models and make them available.
        """
        for emane_model in emane_models:
            logging.debug("loading emane model: %s", emane_model.__name__)
            emane_prefix = self.session.options.get_config(
                "emane_prefix", default=DEFAULT_EMANE_PREFIX
            )
            emane_model.load(emane_prefix)
            self.models[emane_model.name] = emane_model

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
        logging.debug("emane setup")
        with self.session.nodes_lock:
            for node_id in self.session.nodes:
                node = self.session.nodes[node_id]
                if isinstance(node, EmaneNet):
                    logging.debug(
                        "adding emane node: id(%s) name(%s)", node.id, node.name
                    )
                    self.add_node(node)
            if not self._emane_nets:
                logging.debug("no emane nodes in session")
                return EmaneState.NOT_NEEDED

        # check if bindings were installed
        if EventService is None:
            raise CoreError("EMANE python bindings are not installed")

        # control network bridge required for EMANE 0.9.2
        # - needs to exist when eventservice binds to it (initeventservice)
        otadev = self.get_config("otamanagerdevice")
        netidx = self.session.get_control_net_index(otadev)
        logging.debug("emane ota manager device: index(%s) otadev(%s)", netidx, otadev)
        if netidx < 0:
            logging.error(
                "EMANE cannot start, check core config. invalid OTA device provided: %s",
                otadev,
            )
            return EmaneState.NOT_READY

        self.session.add_remove_control_net(
            net_index=netidx, remove=False, conf_required=False
        )
        eventdev = self.get_config("eventservicedevice")
        logging.debug("emane event service device: eventdev(%s)", eventdev)
        if eventdev != otadev:
            netidx = self.session.get_control_net_index(eventdev)
            logging.debug("emane event service device index: %s", netidx)
            if netidx < 0:
                logging.error(
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
            logging.info("emane building xmls...")
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
                logging.error("emane net(%s) has no model", emane_net.name)
                continue
            for iface in emane_net.get_ifaces():
                if not iface.node:
                    logging.error(
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
        control_net = self.session.add_remove_control_net(
            0, remove=False, conf_required=False
        )
        emanexml.build_platform_xml(self, control_net, data)
        self.start_daemon(data.node)
        for iface in data.ifaces:
            self.install_iface(iface)

    def set_nem(self, nem_id: int, iface: CoreInterface) -> None:
        if nem_id in self.nems_to_ifaces:
            raise CoreError(f"adding duplicate nem: {nem_id}")
        self.nems_to_ifaces[nem_id] = iface
        self.ifaces_to_nems[iface] = nem_id

    def get_iface(self, nem_id: int) -> Optional[CoreInterface]:
        return self.nems_to_ifaces.get(nem_id)

    def get_nem_id(self, iface: CoreInterface) -> Optional[int]:
        return self.ifaces_to_nems.get(iface)

    def write_nem(self, iface: CoreInterface, nem_id: int) -> None:
        path = os.path.join(self.session.session_dir, "emane_nems")
        try:
            with open(path, "a") as f:
                f.write(f"{iface.node.name} {iface.name} {nem_id}\n")
        except IOError:
            logging.exception("error writing to emane nem file")

    def links_enabled(self) -> bool:
        return self.get_config("link_enabled") == "1"

    def poststartup(self) -> None:
        """
        Retransmit location events now that all NEMs are active.
        """
        if not self.genlocationevents():
            return
        with self._emane_node_lock:
            for node_id in sorted(self._emane_nets):
                emane_net = self._emane_nets[node_id]
                logging.debug(
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
            logging.info("stopping EMANE daemons")
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
            logging.debug("checking emane model for node: %s", node_id)

            # skip nodes that already have a model set
            if emane_net.model:
                logging.debug(
                    "node(%s) already has model(%s)", emane_net.id, emane_net.model.name
                )
                continue

            # set model configured for node, due to legacy messaging configuration
            # before nodes exist
            model_name = self.node_models.get(node_id)
            if not model_name:
                logging.error("emane node(%s) has no node model", node_id)
                raise ValueError("emane node has no model set")

            config = self.get_model_config(node_id=node_id, model_name=model_name)
            logging.debug("setting emane model(%s) config(%s)", model_name, config)
            model_class = self.models[model_name]
            emane_net.setmodel(model_class, config)

    def get_nem_link(
        self, nem1: int, nem2: int, flags: MessageFlags = MessageFlags.NONE
    ) -> Optional[LinkData]:
        iface1 = self.get_iface(nem1)
        if not iface1:
            logging.error("invalid nem: %s", nem1)
            return None
        node1 = iface1.node
        iface2 = self.get_iface(nem2)
        if not iface2:
            logging.error("invalid nem: %s", nem2)
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
            b = self.get_config(name)
            if a != b:
                need_xml = True

        if not need_xml:
            # reset to using default config
            self.initeventservice()
            return

        try:
            group, port = self.get_config("eventservicegroup").split(":")
        except ValueError:
            logging.exception("invalid eventservicegroup in EMANE config")
            return

        dev = self.get_config("eventservicedevice")
        emanexml.create_event_service_xml(group, port, dev, self.session.session_dir)
        self.session.distributed.execute(
            lambda x: emanexml.create_event_service_xml(
                group, port, dev, self.session.session_dir, x
            )
        )

    def start_daemon(self, node: CoreNodeBase) -> None:
        """
        Start one EMANE daemon per node having a radio.
        Add a control network even if the user has not configured one.
        """
        logging.info("starting emane daemons...")
        loglevel = str(EmaneManager.DEFAULT_LOG_LEVEL)
        cfgloglevel = self.session.options.get_config_int("emane_log_level")
        realtime = self.session.options.get_config_bool("emane_realtime", default=True)
        if cfgloglevel:
            logging.info("setting user-defined emane log level: %d", cfgloglevel)
            loglevel = str(cfgloglevel)
        emanecmd = f"emane -d -l {loglevel}"
        if realtime:
            emanecmd += " -r"
        if isinstance(node, CoreNode):
            otagroup, _otaport = self.get_config("otamanagergroup").split(":")
            otadev = self.get_config("otamanagerdevice")
            otanetidx = self.session.get_control_net_index(otadev)
            eventgroup, _eventport = self.get_config("eventservicegroup").split(":")
            eventdev = self.get_config("eventservicedevice")
            eventservicenetidx = self.session.get_control_net_index(eventdev)

            # control network not yet started here
            self.session.add_remove_control_iface(
                node, 0, remove=False, conf_required=False
            )
            if otanetidx > 0:
                logging.info("adding ota device ctrl%d", otanetidx)
                self.session.add_remove_control_iface(
                    node, otanetidx, remove=False, conf_required=False
                )
            if eventservicenetidx >= 0:
                logging.info("adding event service device ctrl%d", eventservicenetidx)
                self.session.add_remove_control_iface(
                    node, eventservicenetidx, remove=False, conf_required=False
                )
            # multicast route is needed for OTA data
            logging.info("OTA GROUP(%s) OTA DEV(%s)", otagroup, otadev)
            node.node_net_client.create_route(otagroup, otadev)
            # multicast route is also needed for event data if on control network
            if eventservicenetidx >= 0 and eventgroup != otagroup:
                node.node_net_client.create_route(eventgroup, eventdev)
            # start emane
            log_file = os.path.join(node.nodedir, f"{node.name}-emane.log")
            platform_xml = os.path.join(node.nodedir, f"{node.name}-platform.xml")
            args = f"{emanecmd} -f {log_file} {platform_xml}"
            node.cmd(args)
            logging.info("node(%s) emane daemon running: %s", node.name, args)
        else:
            path = self.session.session_dir
            log_file = os.path.join(path, f"{node.name}-emane.log")
            platform_xml = os.path.join(path, f"{node.name}-platform.xml")
            emanecmd += f" -f {log_file} {platform_xml}"
            node.host_cmd(emanecmd, cwd=path)
            logging.info("node(%s) host emane daemon running: %s", node.name, emanecmd)

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
        logging.info("emane start event monitor")
        if not self.doeventmonitor():
            return
        if self.service is None:
            logging.error(
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
        logging.info(
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

        logging.info(
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
                logging.warning("dropped invalid location event")
                continue

            # yaw,pitch,roll,azimuth,elevation,velocity are unhandled
            lat = attrs["latitude"]
            lon = attrs["longitude"]
            alt = attrs["altitude"]
            logging.debug("emane location event: %s,%s,%s", lat, lon, alt)
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
            logging.info("location event for unknown NEM %s", nemid)
            return False

        n = iface.node.id
        # convert from lat/long/alt to x,y,z coordinates
        x, y, z = self.session.location.getxyz(lat, lon, alt)
        x = int(x)
        y = int(y)
        z = int(z)
        logging.debug(
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
            logging.error(
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
            logging.exception(
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
                _id="platform_id_start",
                _type=ConfigDataTypes.INT32,
                default="1",
                label="Starting Platform ID",
            ),
            Configuration(
                _id="nem_id_start",
                _type=ConfigDataTypes.INT32,
                default="1",
                label="Starting NEM ID",
            ),
            Configuration(
                _id="link_enabled",
                _type=ConfigDataTypes.BOOL,
                default="1",
                label="Enable Links?",
            ),
            Configuration(
                _id="loss_threshold",
                _type=ConfigDataTypes.INT32,
                default="30",
                label="Link Loss Threshold (%)",
            ),
            Configuration(
                _id="link_interval",
                _type=ConfigDataTypes.INT32,
                default="1",
                label="Link Check Interval (sec)",
            ),
            Configuration(
                _id="link_timeout",
                _type=ConfigDataTypes.INT32,
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
        emulator_xml = os.path.join(emane_prefix, "share/emane/manifest/nemmanager.xml")
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
