"""
emane.py: definition of an Emane class for implementing configuration control of an EMANE emulation.
"""

import logging
import os
import threading
from collections import OrderedDict
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
from core.nodes.base import CoreNode, NodeBase
from core.nodes.interface import CoreInterface
from core.nodes.network import CtrlNet
from core.nodes.physical import Rj45Node
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


class EmaneManager(ModelManager):
    """
    EMANE controller object. Lives in a Session instance and is used for
    building EMANE config files for all EMANE networks in this emulation, and for
    controlling the EMANE daemons.
    """

    name: str = "emane"
    config_type: RegisterTlvs = RegisterTlvs.EMULATION_SERVER
    SUCCESS: int = 0
    NOT_NEEDED: int = 1
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

    def get_iface_config(
        self, node_id: int, iface: CoreInterface, model_name: str
    ) -> Dict[str, str]:
        """
        Retrieve interface configuration or node configuration if not provided.

        :param node_id: node id
        :param iface: node interface
        :param model_name: model to get configuration for
        :return: node/interface model configuration
        """
        # use the network-wide config values or interface(NEM)-specific values?
        if iface is None:
            return self.get_configs(node_id=node_id, config_type=model_name)
        else:
            # don"t use default values when interface config is the same as net
            # note here that using iface.node.id as key allows for only one type
            # of each model per node;
            # TODO: use both node and interface as key

            # Adamson change: first check for iface config keyed by "node:iface.name"
            # (so that nodes w/ multiple interfaces of same conftype can have
            #  different configs for each separate interface)
            key = 1000 * iface.node.id
            if iface.node_id is not None:
                key += iface.node_id

            # try retrieve interface specific configuration, avoid getting defaults
            config = self.get_configs(node_id=key, config_type=model_name)

            # otherwise retrieve the interfaces node configuration, avoid using defaults
            if not config:
                config = self.get_configs(node_id=iface.node.id, config_type=model_name)

            # get non interface config, when none found
            if not config:
                # with EMANE 0.9.2+, we need an extra NEM XML from
                # model.buildnemxmlfiles(), so defaults are returned here
                config = self.get_configs(node_id=node_id, config_type=model_name)

            return config

    def config_reset(self, node_id: int = None) -> None:
        super().config_reset(node_id)
        self.set_configs(self.emane_config.default_values())

    def emane_check(self) -> None:
        """
        Check if emane is installed and load models.

        :return: nothing
        """
        try:
            # check for emane
            args = "emane --version"
            emane_version = utils.cmd(args)
            logging.info("using EMANE: %s", emane_version)
            self.session.distributed.execute(lambda x: x.remote_cmd(args))

            # load default emane models
            self.load_models(EMANE_MODELS)

            # load custom models
            custom_models_path = self.session.options.get_config("emane_models_dir")
            if custom_models_path:
                emane_models = utils.load_classes(custom_models_path, EmaneModel)
                self.load_models(emane_models)
        except CoreCommandError:
            logging.info("emane is not installed")

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
                raise KeyError(
                    f"non-unique EMANE object id {emane_net.id} for {emane_net}"
                )
            self._emane_nets[emane_net.id] = emane_net

    def getnodes(self) -> Set[CoreNode]:
        """
        Return a set of CoreNodes that are linked to an EMANE network,
        e.g. containers having one or more radio interfaces.
        """
        # assumes self._objslock already held
        nodes = set()
        for emane_net in self._emane_nets.values():
            for iface in emane_net.get_ifaces():
                nodes.add(iface.node)
        return nodes

    def setup(self) -> int:
        """
        Setup duties for EMANE manager.

        :return: SUCCESS, NOT_NEEDED, NOT_READY in order to delay session
            instantiation
        """
        logging.debug("emane setup")

        # TODO: drive this from the session object
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
                return EmaneManager.NOT_NEEDED

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
            return EmaneManager.NOT_READY

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
                    "EMANE cannot start, check core config. invalid event service device: %s",
                    eventdev,
                )
                return EmaneManager.NOT_READY

            self.session.add_remove_control_net(
                net_index=netidx, remove=False, conf_required=False
            )

        self.check_node_models()
        return EmaneManager.SUCCESS

    def startup(self) -> int:
        """
        After all the EMANE networks have been added, build XML files
        and start the daemons.

        :return: SUCCESS, NOT_NEEDED, NOT_READY in order to delay session
            instantiation
        """
        self.reset()
        r = self.setup()

        # NOT_NEEDED or NOT_READY
        if r != EmaneManager.SUCCESS:
            return r

        nems = []
        with self._emane_node_lock:
            self.buildxml()
            self.starteventmonitor()

            if self.numnems() > 0:
                self.startdaemons()
                self.install_ifaces()

            for node_id in self._emane_nets:
                emane_node = self._emane_nets[node_id]
                for iface in emane_node.get_ifaces():
                    nems.append(
                        (iface.node.name, iface.name, emane_node.getnemid(iface))
                    )

        if nems:
            emane_nems_filename = os.path.join(self.session.session_dir, "emane_nems")
            try:
                with open(emane_nems_filename, "w") as f:
                    for nodename, ifname, nemid in nems:
                        f.write(f"{nodename} {ifname} {nemid}\n")
            except IOError:
                logging.exception("Error writing EMANE NEMs file: %s")
        if self.links_enabled():
            self.link_monitor.start()
        return EmaneManager.SUCCESS

    def links_enabled(self) -> bool:
        return self.get_config("link_enabled") == "1"

    def poststartup(self) -> None:
        """
        Retransmit location events now that all NEMs are active.
        """
        if not self.genlocationevents():
            return

        with self._emane_node_lock:
            for key in sorted(self._emane_nets.keys()):
                emane_node = self._emane_nets[key]
                logging.debug(
                    "post startup for emane node: %s - %s",
                    emane_node.id,
                    emane_node.name,
                )
                emane_node.model.post_startup()
                for iface in emane_node.get_ifaces():
                    iface.setposition()

    def reset(self) -> None:
        """
        Remove all EMANE networks from the dictionary, reset port numbers and
        nem id counters
        """
        with self._emane_node_lock:
            self._emane_nets.clear()

        self.platformport = self.session.options.get_config_int(
            "emane_platform_port", 8100
        )
        self.transformport = self.session.options.get_config_int(
            "emane_transform_port", 8200
        )

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
            self.deinstall_ifaces()
            self.stopdaemons()
            self.stopeventmonitor()

    def buildxml(self) -> None:
        """
        Build XML files required to run EMANE on each node.
        NEMs run inside containers using the control network for passing
        events and data.
        """
        # assume self._objslock is already held here
        logging.info("emane building xml...")
        # on master, control network bridge added earlier in startup()
        ctrlnet = self.session.add_remove_control_net(
            net_index=0, remove=False, conf_required=False
        )
        self.buildplatformxml(ctrlnet)
        self.buildnemxml()
        self.buildeventservicexml()

    def check_node_models(self) -> None:
        """
        Associate EMANE model classes with EMANE network nodes.
        """
        for node_id in self._emane_nets:
            emane_node = self._emane_nets[node_id]
            logging.debug("checking emane model for node: %s", node_id)

            # skip nodes that already have a model set
            if emane_node.model:
                logging.debug(
                    "node(%s) already has model(%s)",
                    emane_node.id,
                    emane_node.model.name,
                )
                continue

            # set model configured for node, due to legacy messaging configuration before nodes exist
            model_name = self.node_models.get(node_id)
            if not model_name:
                logging.error("emane node(%s) has no node model", node_id)
                raise ValueError("emane node has no model set")

            config = self.get_model_config(node_id=node_id, model_name=model_name)
            logging.debug("setting emane model(%s) config(%s)", model_name, config)
            model_class = self.models[model_name]
            emane_node.setmodel(model_class, config)

    def nemlookup(self, nemid) -> Tuple[Optional[EmaneNet], Optional[CoreInterface]]:
        """
        Look for the given numerical NEM ID and return the first matching
        EMANE network and NEM interface.
        """
        emane_node = None
        iface = None

        for node_id in self._emane_nets:
            emane_node = self._emane_nets[node_id]
            iface = emane_node.get_nem_iface(nemid)
            if iface is not None:
                break
            else:
                emane_node = None

        return emane_node, iface

    def get_nem_link(
        self, nem1: int, nem2: int, flags: MessageFlags = MessageFlags.NONE
    ) -> Optional[LinkData]:
        emane1, iface = self.nemlookup(nem1)
        if not emane1 or not iface:
            logging.error("invalid nem: %s", nem1)
            return None
        node1 = iface.node
        emane2, iface = self.nemlookup(nem2)
        if not emane2 or not iface:
            logging.error("invalid nem: %s", nem2)
            return None
        node2 = iface.node
        color = self.session.get_link_color(emane1.id)
        return LinkData(
            message_type=flags,
            type=LinkTypes.WIRELESS,
            node1_id=node1.id,
            node2_id=node2.id,
            network_id=emane1.id,
            color=color,
        )

    def numnems(self) -> int:
        """
        Return the number of NEMs emulated locally.
        """
        count = 0
        for node_id in self._emane_nets:
            emane_node = self._emane_nets[node_id]
            count += len(emane_node.ifaces)
        return count

    def buildplatformxml(self, ctrlnet: CtrlNet) -> None:
        """
        Build a platform.xml file now that all nodes are configured.
        """
        nemid = int(self.get_config("nem_id_start"))
        platform_xmls = {}

        # assume self._objslock is already held here
        for key in sorted(self._emane_nets.keys()):
            emane_node = self._emane_nets[key]
            nemid = emanexml.build_node_platform_xml(
                self, ctrlnet, emane_node, nemid, platform_xmls
            )

    def buildnemxml(self) -> None:
        """
        Builds the nem, mac, and phy xml files for each EMANE network.
        """
        for key in sorted(self._emane_nets):
            emane_net = self._emane_nets[key]
            emanexml.build_xml_files(self, emane_net)

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

    def startdaemons(self) -> None:
        """
        Start one EMANE daemon per node having a radio.
        Add a control network even if the user has not configured one.
        """
        logging.info("starting emane daemons...")
        loglevel = str(EmaneManager.DEFAULT_LOG_LEVEL)
        cfgloglevel = self.session.options.get_config_int("emane_log_level")
        realtime = self.session.options.get_config_bool("emane_realtime", default=True)
        if cfgloglevel:
            logging.info("setting user-defined EMANE log level: %d", cfgloglevel)
            loglevel = str(cfgloglevel)

        emanecmd = f"emane -d -l {loglevel}"
        if realtime:
            emanecmd += " -r"

        otagroup, _otaport = self.get_config("otamanagergroup").split(":")
        otadev = self.get_config("otamanagerdevice")
        otanetidx = self.session.get_control_net_index(otadev)

        eventgroup, _eventport = self.get_config("eventservicegroup").split(":")
        eventdev = self.get_config("eventservicedevice")
        eventservicenetidx = self.session.get_control_net_index(eventdev)

        run_emane_on_host = False
        for node in self.getnodes():
            if isinstance(node, Rj45Node):
                run_emane_on_host = True
                continue
            path = self.session.session_dir
            n = node.id

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
            node.node_net_client.create_route(otagroup, otadev)

            # multicast route is also needed for event data if on control network
            if eventservicenetidx >= 0 and eventgroup != otagroup:
                node.node_net_client.create_route(eventgroup, eventdev)

            # start emane
            log_file = os.path.join(path, f"emane{n}.log")
            platform_xml = os.path.join(path, f"platform{n}.xml")
            args = f"{emanecmd} -f {log_file} {platform_xml}"
            output = node.cmd(args)
            logging.info("node(%s) emane daemon running: %s", node.name, args)
            logging.debug("node(%s) emane daemon output: %s", node.name, output)

        if not run_emane_on_host:
            return

        path = self.session.session_dir
        log_file = os.path.join(path, "emane.log")
        platform_xml = os.path.join(path, "platform.xml")
        emanecmd += f" -f {log_file} {platform_xml}"
        utils.cmd(emanecmd, cwd=path)
        self.session.distributed.execute(lambda x: x.remote_cmd(emanecmd, cwd=path))
        logging.info("host emane daemon running: %s", emanecmd)

    def stopdaemons(self) -> None:
        """
        Kill the appropriate EMANE daemons.
        """
        # TODO: we may want to improve this if we had the PIDs from the specific EMANE
        #  daemons that we"ve started
        kill_emaned = "killall -q emane"
        kill_transortd = "killall -q emanetransportd"
        stop_emane_on_host = False
        for node in self.getnodes():
            if isinstance(node, Rj45Node):
                stop_emane_on_host = True
                continue

            if node.up:
                node.cmd(kill_emaned, wait=False)
                # TODO: RJ45 node

        if stop_emane_on_host:
            try:
                utils.cmd(kill_emaned)
                utils.cmd(kill_transortd)
                self.session.distributed.execute(lambda x: x.remote_cmd(kill_emaned))
                self.session.distributed.execute(lambda x: x.remote_cmd(kill_transortd))
            except CoreCommandError:
                logging.exception("error shutting down emane daemons")

    def install_ifaces(self) -> None:
        """
        Install TUN/TAP virtual interfaces into their proper namespaces
        now that the EMANE daemons are running.
        """
        for key in sorted(self._emane_nets.keys()):
            node = self._emane_nets[key]
            logging.info("emane install interface for node(%s): %d", node.name, key)
            node.install_ifaces()

    def deinstall_ifaces(self) -> None:
        """
        Uninstall TUN/TAP virtual interfaces.
        """
        for key in sorted(self._emane_nets.keys()):
            emane_node = self._emane_nets[key]
            emane_node.deinstall_ifaces()

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
        _emanenode, iface = self.nemlookup(nemid)
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
