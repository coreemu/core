"""
emane.py: definition of an Emane class for implementing configuration control of an EMANE emulation.
"""

import os
import threading

from core import CoreCommandError
from core import constants
from core import logger
from core.api import coreapi
from core.api import dataconversion
from core.conf import ConfigGroup
from core.conf import ConfigShim
from core.conf import Configuration
from core.conf import ModelManager
from core.emane import emanemanifest
from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.emanemodel import EmaneModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.rfpipe import EmaneRfPipeModel
from core.emane.tdma import EmaneTdmaModel
from core.enumerations import ConfigDataTypes
from core.enumerations import ConfigFlags
from core.enumerations import ConfigTlvs
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.misc import nodeutils
from core.misc import utils
from core.xml import emanexml

try:
    from emane.events import EventService
    from emane.events import LocationEvent
    from emane.events.eventserviceexception import EventServiceException
except ImportError:
    try:
        from emanesh.events import EventService
        from emanesh.events import LocationEvent
        from emanesh.events.eventserviceexception import EventServiceException
    except ImportError:
        logger.warn("compatible emane python bindings not installed")

EMANE_MODELS = [
    EmaneRfPipeModel,
    EmaneIeee80211abgModel,
    EmaneCommEffectModel,
    EmaneBypassModel,
    EmaneTdmaModel
]


class EmaneManager(ModelManager):
    """
    EMANE controller object. Lives in a Session instance and is used for
    building EMANE config files from all of the EmaneNode objects in this
    emulation, and for controlling the EMANE daemons.
    """
    name = "emane"
    config_type = RegisterTlvs.EMULATION_SERVER.value
    SUCCESS, NOT_NEEDED, NOT_READY = (0, 1, 2)
    EVENTCFGVAR = "LIBEMANEEVENTSERVICECONFIG"
    DEFAULT_LOG_LEVEL = 3

    def __init__(self, session):
        """
        Creates a Emane instance.

        :param core.session.Session session: session this manager is tied to
        :return: nothing
        """
        super(EmaneManager, self).__init__()
        self.session = session
        self._emane_nodes = {}
        self._emane_node_lock = threading.Lock()
        self._ifccounts = {}
        self._ifccountslock = threading.Lock()
        # port numbers are allocated from these counters
        self.platformport = self.session.options.get_config_int("emane_platform_port", 8100)
        self.transformport = self.session.options.get_config_int("emane_transform_port", 8200)
        self.doeventloop = False
        self.eventmonthread = None

        # model for global EMANE configuration options
        self.emane_config = EmaneGlobalModel(session)
        self.set_configs(self.emane_config.default_values())

        session.broker.handlers.add(self.handledistributed)
        self.service = None
        self.event_device = None
        self.emane_check()

    def getifcconfig(self, node_id, interface, model_name):
        """
        Retrieve interface configuration or node configuration if not provided.

        :param int node_id: node id
        :param interface: node interface
        :param str model_name: model to get configuration for
        :return: node/interface model configuration
        :rtype: dict
        """
        # use the network-wide config values or interface(NEM)-specific values?
        if interface is None:
            return self.get_configs(node_id=node_id, config_type=model_name)
        else:
            # don"t use default values when interface config is the same as net
            # note here that using ifc.node.objid as key allows for only one type
            # of each model per node;
            # TODO: use both node and interface as key

            # Adamson change: first check for iface config keyed by "node:ifc.name"
            # (so that nodes w/ multiple interfaces of same conftype can have
            #  different configs for each separate interface)
            key = 1000 * interface.node.objid
            if interface.netindex is not None:
                key += interface.netindex

            # try retrieve interface specific configuration, avoid getting defaults
            config = {}
            if self.has_configs(key):
                config = self.get_configs(key)

            # otherwise retrieve the interfaces node configuration, avoid using defaults
            if not config and self.has_configs(interface.node.objid):
                config = self.get_configs(node_id=interface.node.objid, config_type=model_name)

            if not config and interface.transport_type == "raw":
                # with EMANE 0.9.2+, we need an extra NEM XML from
                # model.buildnemxmlfiles(), so defaults are returned here
                config = self.get_configs(node_id=node_id, config_type=model_name)

            return config

    def config_reset(self, node_id=None):
        super(EmaneManager, self).config_reset(node_id)
        self.set_configs(self.emane_config.default_values())

    def emane_check(self):
        """
        Check if emane is installed and load models.

        :return: nothing
        """
        try:
            # check for emane
            emane_version = utils.check_cmd(["emane", "--version"])
            logger.info("using EMANE: %s", emane_version)

            # load default emane models
            self.load_models(EMANE_MODELS)

            # load custom models
            custom_models_path = self.session.options.get_config("emane_models_dir")
            if custom_models_path:
                emane_models = utils.load_classes(custom_models_path, EmaneModel)
                self.load_models(emane_models)
        except CoreCommandError:
            logger.info("emane is not installed")

    def deleteeventservice(self):
        if self.service:
            for fd in self.service._readFd, self.service._writeFd:
                if fd >= 0:
                    os.close(fd)
            for f in self.service._socket, self.service._socketOTA:
                if f:
                    f.close()
        self.service = None
        self.event_device = None

    def initeventservice(self, filename=None, shutdown=False):
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
            logger.error("invalid emane event service device provided: %s", self.event_device)
            return False

        # make sure the event control network is in place
        eventnet = self.session.add_remove_control_net(net_index=eventnetidx, remove=False, conf_required=False)
        if eventnet is not None:
            # direct EMANE events towards control net bridge
            self.event_device = eventnet.brname
        eventchannel = (group, int(port), self.event_device)

        # disabled otachannel for event service
        # only needed for e.g. antennaprofile events xmit by models
        logger.info("using %s for event service traffic", self.event_device)
        try:
            self.service = EventService(eventchannel=eventchannel, otachannel=None)
        except EventServiceException:
            logger.exception("error instantiating emane EventService")

        return True

    def load_models(self, emane_models):
        """
        load EMANE models and make them available.
        """
        for emane_model in emane_models:
            logger.info("loading emane model: %s", emane_model.__name__)
            self.models[emane_model.name] = emane_model

    def add_node(self, emane_node):
        """
        Add a new EmaneNode object to this Emane controller object

        :param core.emane.nodes.EmaneNode emane_node: emane node to add
        :return: nothing
        """
        with self._emane_node_lock:
            if emane_node.objid in self._emane_nodes:
                raise KeyError("non-unique EMANE object id %s for %s" % (emane_node.objid, emane_node))
            self._emane_nodes[emane_node.objid] = emane_node

    def getnodes(self):
        """
        Return a set of CoreNodes that are linked to an EmaneNode,
        e.g. containers having one or more radio interfaces.
        """
        # assumes self._objslock already held
        nodes = set()
        for emane_node in self._emane_nodes.values():
            for netif in emane_node.netifs():
                nodes.add(netif.node)
        return nodes

    def setup(self):
        """
        Populate self._objs with EmaneNodes; perform distributed setup;
        associate models with EmaneNodes from self.config. Returns
        Emane.(SUCCESS, NOT_NEEDED, NOT_READY) in order to delay session
        instantiation.
        """
        logger.debug("emane setup")

        # TODO: drive this from the session object
        with self.session._objects_lock:
            for node in self.session.objects.itervalues():
                if nodeutils.is_node(node, NodeTypes.EMANE):
                    logger.debug("adding emane node: id(%s) name(%s)", node.objid, node.name)
                    self.add_node(node)

            if not self._emane_nodes:
                logger.debug("no emane nodes in session")
                return EmaneManager.NOT_NEEDED

        # control network bridge required for EMANE 0.9.2
        # - needs to be configured before checkdistributed() for distributed
        # - needs to exist when eventservice binds to it (initeventservice)
        if self.session.master:
            otadev = self.get_config("otamanagerdevice")
            netidx = self.session.get_control_net_index(otadev)
            logger.debug("emane ota manager device: index(%s) otadev(%s)", netidx, otadev)
            if netidx < 0:
                logger.error("EMANE cannot start, check core config. invalid OTA device provided: %s", otadev)
                return EmaneManager.NOT_READY

            ctrlnet = self.session.add_remove_control_net(net_index=netidx, remove=False, conf_required=False)
            self.distributedctrlnet(ctrlnet)
            eventdev = self.get_config("eventservicedevice")
            logger.debug("emane event service device: eventdev(%s)", eventdev)
            if eventdev != otadev:
                netidx = self.session.get_control_net_index(eventdev)
                logger.debug("emane event service device index: %s", netidx)
                if netidx < 0:
                    logger.error("EMANE cannot start, check core config. invalid event service device: %s", eventdev)
                    return EmaneManager.NOT_READY

                ctrlnet = self.session.add_remove_control_net(net_index=netidx, remove=False, conf_required=False)
                self.distributedctrlnet(ctrlnet)

        if self.checkdistributed():
            # we are slave, but haven't received a platformid yet
            platform_id_start = "platform_id_start"
            default_values = self.emane_config.default_values()
            value = self.get_config(platform_id_start)
            if value == default_values[platform_id_start]:
                return EmaneManager.NOT_READY

        self.check_node_models()
        return EmaneManager.SUCCESS

    def startup(self):
        """
        After all the EmaneNode objects have been added, build XML files
        and start the daemons. Returns Emane.(SUCCESS, NOT_NEEDED, or
        NOT_READY) which is used to delay session instantiation.
        """
        self.reset()
        r = self.setup()

        # NOT_NEEDED or NOT_READY
        if r != EmaneManager.SUCCESS:
            return r

        nems = []
        with self._emane_node_lock:
            self.buildxml()
            self.initeventservice()
            self.starteventmonitor()

            if self.numnems() > 0:
                self.startdaemons()
                self.installnetifs(do_netns=False)

            for emane_node in self._emane_nodes.itervalues():
                for netif in emane_node.netifs():
                    nems.append((netif.node.name, netif.name, emane_node.getnemid(netif)))

        if nems:
            emane_nems_filename = os.path.join(self.session.session_dir, "emane_nems")
            try:
                with open(emane_nems_filename, "w") as f:
                    for nodename, ifname, nemid in nems:
                        f.write("%s %s %s\n" % (nodename, ifname, nemid))
            except IOError:
                logger.exception("Error writing EMANE NEMs file: %s")

        return EmaneManager.SUCCESS

    def poststartup(self):
        """
        Retransmit location events now that all NEMs are active.
        """
        if not self.genlocationevents():
            return

        with self._emane_node_lock:
            for key in sorted(self._emane_nodes.keys()):
                emane_node = self._emane_nodes[key]
                logger.debug("post startup for emane node: %s - %s", emane_node.objid, emane_node.name)
                emane_node.model.post_startup()
                for netif in emane_node.netifs():
                    x, y, z = netif.node.position.get()
                    emane_node.setnemposition(netif, x, y, z)

    def reset(self):
        """
        remove all EmaneNode objects from the dictionary,
        reset port numbers and nem id counters
        """
        with self._emane_node_lock:
            self._emane_nodes.clear()

        # don't clear self._ifccounts here; NEM counts are needed for buildxml
        self.platformport = self.session.options.get_config_int("emane_platform_port", 8100)
        self.transformport = self.session.options.get_config_int("emane_transform_port", 8200)

    def shutdown(self):
        """
        stop all EMANE daemons
        """
        with self._ifccountslock:
            self._ifccounts.clear()

        with self._emane_node_lock:
            if not self._emane_nodes:
                return
            logger.info("stopping EMANE daemons.")
            self.deinstallnetifs()
            self.stopdaemons()
            self.stopeventmonitor()

    def handledistributed(self, message):
        """
        Broker handler for processing CORE API messages as they are
        received. This is used to snoop the Link add messages to get NEM
        counts of NEMs that exist on other servers.
        """
        if message.message_type == MessageTypes.LINK.value and message.flags & MessageFlags.ADD.value:
            nn = message.node_numbers()
            # first node is always link layer node in Link add message
            if nn[0] in self.session.broker.network_nodes:
                serverlist = self.session.broker.getserversbynode(nn[1])
                for server in serverlist:
                    with self._ifccountslock:
                        if server not in self._ifccounts:
                            self._ifccounts[server] = 1
                        else:
                            self._ifccounts[server] += 1

    def checkdistributed(self):
        """
        Check for EMANE nodes that exist on multiple emulation servers and
        coordinate the NEM id and port number space.
        If we are the master EMANE node, return False so initialization will
        proceed as normal; otherwise slaves return True here and
        initialization is deferred.
        """
        # check with the session if we are the "master" Emane object?
        master = False

        with self._emane_node_lock:
            if self._emane_nodes:
                master = self.session.master
                logger.info("emane check distributed as master: %s.", master)

        # we are not the master Emane object, wait for nem id and ports
        if not master:
            return True

        nemcount = 0
        with self._emane_node_lock:
            for key in self._emane_nodes:
                emane_node = self._emane_nodes[key]
                nemcount += emane_node.numnetif()

            nemid = int(self.get_config("nem_id_start"))
            nemid += nemcount

            platformid = int(self.get_config("platform_id_start"))

            # build an ordered list of servers so platform ID is deterministic
            servers = []
            for key in sorted(self._emane_nodes):
                for server in self.session.broker.getserversbynode(key):
                    if server not in servers:
                        servers.append(server)

        servers.sort(key=lambda x: x.name)
        for server in servers:
            if server.name == "localhost":
                continue

            if server.sock is None:
                continue

            platformid += 1
            typeflags = ConfigFlags.UPDATE.value
            self.set_config("platform_id_start", str(platformid))
            self.set_config("nem_id_start", str(nemid))
            config_data = ConfigShim.config_data(0, None, typeflags, self.emane_config, self.get_configs())
            message = dataconversion.convert_config(config_data)
            server.sock.send(message)
            # increment nemid for next server by number of interfaces
            with self._ifccountslock:
                if server in self._ifccounts:
                    nemid += self._ifccounts[server]

        return False

    def buildxml(self):
        """
        Build XML files required to run EMANE on each node.
        NEMs run inside containers using the control network for passing
        events and data.
        """
        # assume self._objslock is already held here
        logger.info("emane building xml...")
        # on master, control network bridge added earlier in startup()
        ctrlnet = self.session.add_remove_control_net(net_index=0, remove=False, conf_required=False)
        self.buildplatformxml(ctrlnet)
        self.buildnemxml()
        self.buildeventservicexml()

    # TODO: remove need for tlv messaging
    def distributedctrlnet(self, ctrlnet):
        """
        Distributed EMANE requires multiple control network prefixes to
        be configured. This generates configuration for slave control nets
        using the default list of prefixes.
        """
        session = self.session
        # slave server
        if not session.master:
            return

        servers = session.broker.getservernames()
        # not distributed
        if len(servers) < 2:
            return

        prefix = session.options.get_config("controlnet")
        prefixes = prefix.split()
        # normal Config messaging will distribute controlnets
        if len(prefixes) >= len(servers):
            return

        # this generates a config message having controlnet prefix assignments
        logger.info("Setting up default controlnet prefixes for distributed (%d configured)" % len(prefixes))
        prefixes = ctrlnet.DEFAULT_PREFIX_LIST[0]
        vals = 'controlnet="%s"' % prefixes
        tlvdata = ""
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.OBJECT.value, "session")
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.TYPE.value, 0)
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.VALUES.value, vals)
        rawmsg = coreapi.CoreConfMessage.pack(0, tlvdata)
        msghdr = rawmsg[:coreapi.CoreMessage.header_len]
        msg = coreapi.CoreConfMessage(flags=0, hdr=msghdr, data=rawmsg[coreapi.CoreMessage.header_len:])
        self.session.broker.handle_message(msg)

    def check_node_models(self):
        """
        Associate EmaneModel classes with EmaneNode nodes. The model
        configurations are stored in self.configs.
        """
        for node_id in self._emane_nodes:
            emane_node = self._emane_nodes[node_id]
            logger.debug("checking emane model for node: %s", node_id)

            # skip nodes that already have a model set
            if emane_node.model:
                logger.debug("node(%s) already has model(%s)", emane_node.objid, emane_node.model.name)
                continue

            # set model configured for node, due to legacy messaging configuration before nodes exist
            model_name = self.node_models.get(node_id)
            if not model_name:
                logger.error("emane node(%s) has no node model", node_id)
                raise ValueError("emane node has no model set")

            config = self.get_model_config(node_id=node_id, model_name=model_name)
            logger.debug("setting emane model(%s) config(%s)", model_name, config)
            model_class = self.models[model_name]
            emane_node.setmodel(model_class, config)

    def nemlookup(self, nemid):
        """
        Look for the given numerical NEM ID and return the first matching
        EmaneNode and NEM interface.
        """
        emane_node = None
        netif = None

        for node_id in self._emane_nodes:
            emane_node = self._emane_nodes[node_id]
            netif = emane_node.getnemnetif(nemid)
            if netif is not None:
                break
            else:
                emane_node = None

        return emane_node, netif

    def numnems(self):
        """
        Return the number of NEMs emulated locally.
        """
        count = 0
        for emane_node in self._emane_nodes.itervalues():
            count += len(emane_node.netifs())
        return count

    def buildplatformxml(self, ctrlnet):
        """
        Build a platform.xml file now that all nodes are configured.
        """
        nemid = int(self.get_config("nem_id_start"))

        # assume self._objslock is already held here
        for key in sorted(self._emane_nodes.keys()):
            emane_node = self._emane_nodes[key]
            nemid = emanexml.build_node_platform_xml(self, ctrlnet, emane_node, nemid)

    def buildnemxml(self):
        """
        Builds the xxxnem.xml, xxxmac.xml, and xxxphy.xml files which
        are defined on a per-EmaneNode basis.
        """
        for key in sorted(self._emane_nodes.keys()):
            emane_node = self._emane_nodes[key]
            emanexml.build_xml_files(self, emane_node)

    def buildtransportxml(self):
        """
        Calls emanegentransportxml using a platform.xml file to build the transportdaemon*.xml.
        """
        utils.check_cmd(["emanegentransportxml", "platform.xml"], cwd=self.session.session_dir)

    def buildeventservicexml(self):
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
            logger.exception("invalid eventservicegroup in EMANE config")
            return

        dev = self.get_config("eventservicedevice")

        emanexml.create_event_service_xml(group, port, dev, self.session.session_dir)

    def startdaemons(self):
        """
        Start one EMANE daemon per node having a radio.
        Add a control network even if the user has not configured one.
        """
        logger.info("starting emane daemons...")
        loglevel = str(EmaneManager.DEFAULT_LOG_LEVEL)
        cfgloglevel = self.session.options.get_config_int("emane_log_level")
        realtime = self.session.options.get_config_bool("emane_realtime", default=True)
        if cfgloglevel:
            logger.info("setting user-defined EMANE log level: %d", cfgloglevel)
            loglevel = str(cfgloglevel)

        emanecmd = ["emane", "-d", "-l", loglevel]
        if realtime:
            emanecmd += "-r",

        otagroup, otaport = self.get_config("otamanagergroup").split(":")
        otadev = self.get_config("otamanagerdevice")
        otanetidx = self.session.get_control_net_index(otadev)

        eventgroup, eventport = self.get_config("eventservicegroup").split(":")
        eventdev = self.get_config("eventservicedevice")
        eventservicenetidx = self.session.get_control_net_index(eventdev)

        run_emane_on_host = False
        for node in self.getnodes():
            if hasattr(node, "transport_type") and node.transport_type == "raw":
                run_emane_on_host = True
                continue
            path = self.session.session_dir
            n = node.objid

            # control network not yet started here
            self.session.add_remove_control_interface(node, 0, remove=False, conf_required=False)

            if otanetidx > 0:
                logger.info("adding ota device ctrl%d", otanetidx)
                self.session.add_remove_control_interface(node, otanetidx, remove=False, conf_required=False)

            if eventservicenetidx >= 0:
                logger.info("adding event service device ctrl%d", eventservicenetidx)
                self.session.add_remove_control_interface(node, eventservicenetidx, remove=False, conf_required=False)

            # multicast route is needed for OTA data
            args = [constants.IP_BIN, "route", "add", otagroup, "dev", otadev]
            node.check_cmd(args)

            # multicast route is also needed for event data if on control network
            if eventservicenetidx >= 0 and eventgroup != otagroup:
                args = [constants.IP_BIN, "route", "add", eventgroup, "dev", eventdev]
                node.check_cmd(args)

            # start emane
            args = emanecmd + ["-f", os.path.join(path, "emane%d.log" % n), os.path.join(path, "platform%d.xml" % n)]
            output = node.check_cmd(args)
            logger.info("node(%s) emane daemon running: %s", node.name, args)
            logger.info("node(%s) emane daemon output: %s", node.name, output)

        if not run_emane_on_host:
            return

        path = self.session.session_dir
        emanecmd += ["-f", os.path.join(path, "emane.log")]
        args = emanecmd + [os.path.join(path, "platform.xml")]
        utils.check_cmd(args, cwd=path)
        logger.info("host emane daemon running: %s", args)

    def stopdaemons(self):
        """
        Kill the appropriate EMANE daemons.
        """
        # TODO: we may want to improve this if we had the PIDs from the specific EMANE daemons that we"ve started
        args = ["killall", "-q", "emane"]
        stop_emane_on_host = False
        for node in self.getnodes():
            if hasattr(node, "transport_type") and node.transport_type == "raw":
                stop_emane_on_host = True
                continue

            if node.up:
                node.cmd(args, wait=False)
                # TODO: RJ45 node

        if stop_emane_on_host:
            try:
                utils.check_cmd(args)
                utils.check_cmd(["killall", "-q", "emanetransportd"])
            except CoreCommandError:
                logger.exception("error shutting down emane daemons")

    def installnetifs(self, do_netns=True):
        """
        Install TUN/TAP virtual interfaces into their proper namespaces
        now that the EMANE daemons are running.
        """
        for key in sorted(self._emane_nodes.keys()):
            emane_node = self._emane_nodes[key]
            logger.info("emane install netifs for node: %d", key)
            emane_node.installnetifs(do_netns)

    def deinstallnetifs(self):
        """
        Uninstall TUN/TAP virtual interfaces.
        """
        for key in sorted(self._emane_nodes.keys()):
            emane_node = self._emane_nodes[key]
            emane_node.deinstallnetifs()

    def doeventmonitor(self):
        """
        Returns boolean whether or not EMANE events will be monitored.
        """
        # this support must be explicitly turned on; by default, CORE will
        # generate the EMANE events when nodes are moved
        return self.session.options.get_config_bool("emane_event_monitor")

    def genlocationevents(self):
        """
        Returns boolean whether or not EMANE events will be generated.
        """
        # By default, CORE generates EMANE location events when nodes
        # are moved; this can be explicitly disabled in core.conf
        tmp = self.session.options.get_config_bool("emane_event_generate")
        if tmp is None:
            tmp = not self.doeventmonitor()
        return tmp

    def starteventmonitor(self):
        """
        Start monitoring EMANE location events if configured to do so.
        """
        logger.info("emane start event monitor")
        if not self.doeventmonitor():
            return

        if self.service is None:
            logger.error("Warning: EMANE events will not be generated "
                         "because the emaneeventservice\n binding was "
                         "unable to load "
                         "(install the python-emaneeventservice bindings)")
            return
        self.doeventloop = True
        self.eventmonthread = threading.Thread(target=self.eventmonitorloop)
        self.eventmonthread.daemon = True
        self.eventmonthread.start()

    def stopeventmonitor(self):
        """
        Stop monitoring EMANE location events.
        """
        self.doeventloop = False
        if self.service is not None:
            self.service.breakloop()
            # reset the service, otherwise nextEvent won"t work
            self.initeventservice(shutdown=True)

        if self.eventmonthread is not None:
            # TODO: fix this
            self.eventmonthread._Thread__stop()
            self.eventmonthread.join()
            self.eventmonthread = None

    def eventmonitorloop(self):
        """
        Thread target that monitors EMANE location events.
        """
        if self.service is None:
            return
        logger.info("subscribing to EMANE location events. (%s)", threading.currentThread().getName())
        while self.doeventloop is True:
            uuid, seq, events = self.service.nextEvent()

            # this occurs with 0.9.1 event service
            if not self.doeventloop:
                break

            for event in events:
                nem, eid, data = event
                if eid == LocationEvent.IDENTIFIER:
                    self.handlelocationevent(nem, eid, data)

        logger.info("unsubscribing from EMANE location events. (%s)", threading.currentThread().getName())

    def handlelocationevent(self, rxnemid, eid, data):
        """
        Handle an EMANE location event.
        """
        events = LocationEvent()
        events.restore(data)
        for event in events:
            txnemid, attrs = event
            if "latitude" not in attrs or "longitude" not in attrs or "altitude" not in attrs:
                logger.warn("dropped invalid location event")
                continue

            # yaw,pitch,roll,azimuth,elevation,velocity are unhandled
            lat = attrs["latitude"]
            long = attrs["longitude"]
            alt = attrs["altitude"]
            self.handlelocationeventtoxyz(txnemid, lat, long, alt)

    def handlelocationeventtoxyz(self, nemid, lat, lon, alt):
        """
        Convert the (NEM ID, lat, long, alt) from a received location event
        into a node and x,y,z coordinate values, sending a Node Message.
        Returns True if successfully parsed and a Node Message was sent.
        """
        # convert nemid to node number
        emanenode, netif = self.nemlookup(nemid)
        if netif is None:
            logger.info("location event for unknown NEM %s", nemid)
            return False

        n = netif.node.objid
        # convert from lat/long/alt to x,y,z coordinates
        x, y, z = self.session.location.getxyz(lat, lon, alt)
        x = int(x)
        y = int(y)
        z = int(z)
        logger.info("location event NEM %s (%s, %s, %s) -> (%s, %s, %s)", nemid, lat, lon, alt, x, y, z)
        xbit_check = x.bit_length() > 16 or x < 0
        ybit_check = y.bit_length() > 16 or y < 0
        zbit_check = z.bit_length() > 16 or z < 0
        if any([xbit_check, ybit_check, zbit_check]):
            logger.error("Unable to build node location message, received lat/long/alt exceeds coordinate "
                         "space: NEM %s (%d, %d, %d)", nemid, x, y, z)
            return False

        # generate a node message for this location update
        try:
            node = self.session.get_object(n)
        except KeyError:
            logger.exception("location event NEM %s has no corresponding node %s" % (nemid, n))
            return False

        # don"t use node.setposition(x,y,z) which generates an event
        node.position.set(x, y, z)
        node_data = node.data(message_type=0, lat=lat, lon=lon, alt=alt)
        self.session.broadcast_node(node_data)
        return True

    def emanerunning(self, node):
        """
        Return True if an EMANE process associated with the given node is running, False otherwise.
        """
        args = ["pkill", "-0", "-x", "emane"]
        status = node.cmd(args)
        return status == 0


class EmaneGlobalModel(EmaneModel):
    """
    Global EMANE configuration options.
    """

    _DEFAULT_DEV = "ctrl0"

    name = "emane"

    emulator_xml = "/usr/share/emane/manifest/nemmanager.xml"
    emulator_defaults = {
        "eventservicedevice": _DEFAULT_DEV,
        "eventservicegroup": "224.1.2.8:45703",
        "otamanagerdevice": _DEFAULT_DEV,
        "otamanagergroup": "224.1.2.8:45702"
    }
    emulator_config = emanemanifest.parse(emulator_xml, emulator_defaults)
    emulator_config.insert(
        0,
        Configuration(_id="platform_id_start", _type=ConfigDataTypes.INT32, default="1",
                      label="Starting Platform ID (core)")
    )

    nem_config = [
        Configuration(_id="nem_id_start", _type=ConfigDataTypes.INT32, default="1",
                      label="Starting NEM ID (core)")
    ]

    @classmethod
    def configurations(cls):
        return cls.emulator_config + cls.nem_config

    @classmethod
    def config_groups(cls):
        emulator_len = len(cls.emulator_config)
        config_len = len(cls.configurations())
        return [
            ConfigGroup("Platform Attributes", 1, emulator_len),
            ConfigGroup("NEM Parameters", emulator_len + 1, config_len)
        ]

    def __init__(self, session, object_id=None):
        super(EmaneGlobalModel, self).__init__(session, object_id)

    def build_xml_files(self, config, interface=None):
        raise NotImplementedError
