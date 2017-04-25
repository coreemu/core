"""
emane.py: definition of an Emane class for implementing configuration control of an EMANE emulation.
"""

import os
import subprocess
import threading
from xml.dom.minidom import parseString

from core import constants
from core import emane
from core.api import coreapi
from core.conf import ConfigurableManager
from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.emanemodel import EmaneModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.rfpipe import EmaneRfPipeModel
from core.enumerations import ConfigDataTypes, NodeTypes
from core.enumerations import ConfigFlags
from core.enumerations import ConfigTlvs
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.enumerations import RegisterTlvs
from core.misc import log
from core.misc import nodeutils
from core.misc import utils
from core.misc.ipaddress import MacAddress
from core.xml import xmlutils

logger = log.get_logger(__name__)

# EMANE 0.7.4/0.8.1
try:
    import emaneeventservice
    import emaneeventlocation
except ImportError:
    logger.error("error importing emaneeventservice and emaneeventlocation")

# EMANE 0.9.1+
try:
    from emanesh.events import EventService
    from emanesh.events import LocationEvent
except ImportError:
    logger.error("error importing emanesh")

EMANE_MODELS = [
    EmaneRfPipeModel,
    EmaneIeee80211abgModel,
    EmaneCommEffectModel,
    EmaneBypassModel
]


class EmaneManager(ConfigurableManager):
    """
    EMANE controller object. Lives in a Session instance and is used for
    building EMANE config files from all of the EmaneNode objects in this
    emulation, and for controlling the EMANE daemons.
    """
    name = "emane"
    version = None
    versionstr = None
    config_type = RegisterTlvs.EMULATION_SERVER.value
    _hwaddr_prefix = "02:02"
    (SUCCESS, NOT_NEEDED, NOT_READY) = (0, 1, 2)
    EVENTCFGVAR = 'LIBEMANEEVENTSERVICECONFIG'
    DEFAULT_LOG_LEVEL = 3

    def __init__(self, session):
        """
        Creates a Emane instance.

        :param core.session.Session session: session this manager is tied to
        :return: nothing
        """
        ConfigurableManager.__init__(self)
        self.session = session
        self._objs = {}
        self._objslock = threading.Lock()
        self._ifccounts = {}
        self._ifccountslock = threading.Lock()
        # Port numbers are allocated from these counters
        self.platformport = self.session.get_config_item_int('emane_platform_port', 8100)
        self.transformport = self.session.get_config_item_int('emane_transform_port', 8200)
        self.doeventloop = False
        self.eventmonthread = None
        self.logversion()
        # model for global EMANE configuration options
        self.emane_config = EmaneGlobalModel(session, None)
        session.broker.handlers += (self.handledistributed,)
        self.service = None
        self._modelclsmap = {
            self.emane_config.name: self.emane_config
        }
        self.loadmodels()

    def logversion(self):
        """
        Log the installed EMANE version.
        """
        logger.info("using EMANE version: %s", emane.VERSIONSTR)

    def deleteeventservice(self):
        if hasattr(self, 'service'):
            if self.service:
                for fd in self.service._readFd, self.service._writeFd:
                    if fd >= 0:
                        os.close(fd)
                for f in self.service._socket, self.service._socketOTA:
                    if f:
                        f.close()
            del self.service

    def initeventservice(self, filename=None, shutdown=False):
        """
        (Re-)initialize the EMANE Event service.
        The multicast group and/or port may be configured.
        - For versions < 0.9.1 this can be changed via XML config file
          and an environment variable pointing to that file.
        - For version >= 0.9.1 this is passed into the EventService
          constructor.
        """
        self.deleteeventservice()
        self.service = None

        # EMANE 0.9.1+ does not require event service XML config
        if EmaneManager.version >= emane.EMANE091:
            if shutdown:
                return
            # Get the control network to be used for events
            values = self.getconfig(None, "emane",
                                    self.emane_config.getdefaultvalues())[1]
            group, port = self.emane_config.valueof('eventservicegroup', values).split(':')
            eventdev = self.emane_config.valueof('eventservicedevice', values)
            eventnetidx = self.session.get_control_net_index(eventdev)
            if EmaneManager.version > emane.EMANE091:
                if eventnetidx < 0:
                    msg = "Invalid Event Service device provided: %s" % eventdev
                    logger.error(msg)
                    return False

                    # Make sure the event control network is in place
                eventnet = self.session.add_remove_control_net(net_index=eventnetidx,
                                                               remove=False,
                                                               conf_required=False)
                if eventnet is not None:
                    # direct EMANE events towards control net bridge
                    eventdev = eventnet.brname
            eventchannel = (group, int(port), eventdev)

            # disabled otachannel for event service
            # only needed for e.g. antennaprofile events xmit by models
            logger.info("Using %s for event service traffic" % eventdev)
            try:
                self.service = EventService(eventchannel=eventchannel, otachannel=None)
            except:
                logger.exception("error instantiating EventService")

            return True

        tmp = None
        if filename is not None:
            tmp = os.getenv(EmaneManager.EVENTCFGVAR)
            os.environ.update({EmaneManager.EVENTCFGVAR: filename})

        rc = True
        try:
            self.service = emaneeventservice.EventService()
        except:
            self.service = None
            rc = False

        if self.service:
            for f in self.service._readFd, self.service._writeFd, self.service._socket, self.service._socketOTA:
                if f:
                    utils.closeonexec(f)

        if filename is not None:
            os.environ.pop(EmaneManager.EVENTCFGVAR)
            if tmp is not None:
                os.environ.update({EmaneManager.EVENTCFGVAR: tmp})

        return rc

    def loadmodels(self):
        """
        load EMANE models and make them available.
        """
        for emane_model in EMANE_MODELS:
            logger.info("loading emane model: (%s) %s - %s",
                        emane_model, emane_model.name, RegisterTlvs(emane_model.config_type))
            self._modelclsmap[emane_model.name] = emane_model
            self.session.add_config_object(emane_model.name, emane_model.config_type,
                                           emane_model.configure_emane)

    def addobj(self, obj):
        """
        add a new EmaneNode object to this Emane controller object
        """
        self._objslock.acquire()
        if obj.objid in self._objs:
            self._objslock.release()
            raise KeyError("non-unique EMANE object id %s for %s" % (obj.objid, obj))
        self._objs[obj.objid] = obj
        self._objslock.release()

    def getnodes(self):
        """
        Return a set of CoreNodes that are linked to an EmaneNode,
        e.g. containers having one or more radio interfaces.
        """
        # assumes self._objslock already held
        r = set()
        for e in self._objs.values():
            for netif in e.netifs():
                r.add(netif.node)
        return r

    def getmodels(self, n):
        """
        Used with XML export; see ConfigurableManager.getmodels()
        """
        r = ConfigurableManager.getmodels(self, n)
        # EMANE global params are stored with first EMANE node (if non-default
        # values are configured)
        sorted_ids = sorted(self.configs.keys())
        if None in self.configs and len(sorted_ids) > 1 and \
                n.objid == sorted_ids[1]:
            v = self.configs[None]
            for model in v:
                cls = self._modelclsmap[model[0]]
                vals = model[1]
                r.append((cls, vals))
        return r

    def getifcconfig(self, nodenum, conftype, defaultvalues, ifc):
        # use the network-wide config values or interface(NEM)-specific values?
        if ifc is None:
            return self.getconfig(nodenum, conftype, defaultvalues)[1]
        else:
            # don't use default values when interface config is the same as net
            # note here that using ifc.node.objid as key allows for only one type
            # of each model per node; TODO: use both node and interface as key

            # Adamson change: first check for iface config keyed by "node:ifc.name"
            # (so that nodes w/ multiple interfaces of same conftype can have
            #  different configs for each separate interface)
            key = 1000 * ifc.node.objid + ifc.netindex
            values = self.getconfig(key, conftype, None)[1]
            if not values:
                values = self.getconfig(ifc.node.objid, conftype, None)[1]
            if not values and emane.VERSION > emane.EMANE091:
                # with EMANE 0.9.2+, we need an extra NEM XML from
                # model.buildnemxmlfiles(), so defaults are returned here
                if ifc.transport_type == "raw":
                    values = self.getconfig(nodenum, conftype, defaultvalues)[1]
            return values

    def setup(self):
        """
        Populate self._objs with EmaneNodes; perform distributed setup;
        associate models with EmaneNodes from self.config. Returns
        Emane.(SUCCESS, NOT_NEEDED, NOT_READY) in order to delay session
        instantiation.
        """
        with self.session._objects_lock:
            for obj in self.session.objects.itervalues():
                if nodeutils.is_node(obj, NodeTypes.EMANE):
                    self.addobj(obj)
            if len(self._objs) == 0:
                return EmaneManager.NOT_NEEDED
        if emane.VERSION == emane.EMANEUNK:
            raise ValueError, 'EMANE version not properly detected'
        # control network bridge required for EMANE 0.9.2
        # - needs to be configured before checkdistributed() for distributed
        # - needs to exist when eventservice binds to it (initeventservice)
        if emane.VERSION > emane.EMANE091 and self.session.master:
            values = self.getconfig(None, "emane",
                                    self.emane_config.getdefaultvalues())[1]
            otadev = self.emane_config.valueof('otamanagerdevice', values)
            netidx = self.session.get_control_net_index(otadev)
            if netidx < 0:
                msg = "EMANE cannot be started. " \
                      "Invalid OTA device provided: %s. Check core.conf." % otadev
                logger.error(msg)
                return EmaneManager.NOT_READY

            ctrlnet = self.session.add_remove_control_net(net_index=netidx, remove=False, conf_required=False)
            self.distributedctrlnet(ctrlnet)
            eventdev = self.emane_config.valueof('eventservicedevice', values)
            if eventdev != otadev:
                netidx = self.session.get_control_net_index(eventdev)
                if netidx < 0:
                    msg = "EMANE cannot be started." \
                          "Invalid Event Service device provided: %s. Check core.conf." % eventdev
                    logger.error(msg)
                    return EmaneManager.NOT_READY

                ctrlnet = self.session.add_remove_control_net(net_index=netidx, remove=False, conf_required=False)
                self.distributedctrlnet(ctrlnet)

        if self.checkdistributed():
            # we are slave, but haven't received a platformid yet
            cfgval = self.getconfig(None, self.emane_config.name,
                                    self.emane_config.getdefaultvalues())[1]
            i = self.emane_config.getnames().index('platform_id_start')
            if cfgval[i] == self.emane_config.getdefaultvalues()[i]:
                return EmaneManager.NOT_READY
        self.setnodemodels()
        return EmaneManager.SUCCESS

    def startup(self):
        """
        After all the EmaneNode objects have been added, build XML files
        and start the daemons. Returns Emane.(SUCCESS, NOT_NEEDED, or
        NOT_READY) which is used to delay session instantiation.
        """
        self.reset()
        r = self.setup()
        if r != EmaneManager.SUCCESS:
            return r  # NOT_NEEDED or NOT_READY
        if emane.VERSIONSTR == "":
            raise ValueError("EMANE version not properly detected")
        nems = []
        with self._objslock:
            if emane.VERSION < emane.EMANE092:
                self.buildxml()
                self.initeventservice()
                self.starteventmonitor()
                if self.numnems() > 0:
                    # TODO: check and return failure for these methods
                    self.startdaemons()
                    self.installnetifs()
            else:
                self.buildxml2()
                self.initeventservice()
                self.starteventmonitor()
                if self.numnems() > 0:
                    self.startdaemons2()
                    self.installnetifs(do_netns=False)
            for e in self._objs.itervalues():
                for netif in e.netifs():
                    nems.append((netif.node.name, netif.name,
                                 e.getnemid(netif)))
        if nems:
            emane_nems_filename = os.path.join(self.session.session_dir,
                                               'emane_nems')
            try:
                with open(emane_nems_filename, 'w') as f:
                    for nodename, ifname, nemid in nems:
                        f.write('%s %s %s\n' % (nodename, ifname, nemid))
            except IOError:
                logger.exception('Error writing EMANE NEMs file: %s')

        return EmaneManager.SUCCESS

    def poststartup(self):
        """
        Retransmit location events now that all NEMs are active.
        """
        if not self.genlocationevents():
            return
        with self._objslock:
            for n in sorted(self._objs.keys()):
                e = self._objs[n]
                for netif in e.netifs():
                    (x, y, z) = netif.node.position.get()
                    e.setnemposition(netif, x, y, z)

    def reset(self):
        """
        remove all EmaneNode objects from the dictionary,
        reset port numbers and nem id counters
        """
        with self._objslock:
            self._objs.clear()
        # don't clear self._ifccounts here; NEM counts are needed for buildxml
        self.platformport = self.session.get_config_item_int('emane_platform_port', 8100)
        self.transformport = self.session.get_config_item_int('emane_transform_port', 8200)

    def shutdown(self):
        """
        stop all EMANE daemons
        """
        self._ifccountslock.acquire()
        self._ifccounts.clear()
        self._ifccountslock.release()
        self._objslock.acquire()
        if len(self._objs) == 0:
            self._objslock.release()
            return
        logger.info("Stopping EMANE daemons.")
        self.deinstallnetifs()
        self.stopdaemons()
        self.stopeventmonitor()
        self._objslock.release()

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
                    self._ifccountslock.acquire()
                    if server not in self._ifccounts:
                        self._ifccounts[server] = 1
                    else:
                        self._ifccounts[server] += 1
                    self._ifccountslock.release()

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
        self._objslock.acquire()
        if len(self._objs) > 0:
            master = self.session.master
            logger.info("Setup EMANE with master=%s." % master)
        self._objslock.release()

        # we are not the master Emane object, wait for nem id and ports
        if not master:
            return True

        cfgval = self.getconfig(None, self.emane_config.name,
                                self.emane_config.getdefaultvalues())[1]
        values = list(cfgval)

        nemcount = 0
        self._objslock.acquire()
        for n in self._objs:
            emanenode = self._objs[n]
            nemcount += emanenode.numnetif()
        nemid = int(self.emane_config.valueof("nem_id_start", values))
        nemid += nemcount
        platformid = int(self.emane_config.valueof("platform_id_start", values))
        names = list(self.emane_config.getnames())

        # build an ordered list of servers so platform ID is deterministic
        servers = []
        for n in sorted(self._objs):
            for s in self.session.broker.getserversbynode(n):
                if s not in servers:
                    servers.append(s)
        self._objslock.release()

        for server in servers:
            if server == "localhost":
                continue
            (host, port, sock) = self.session.broker.getserver(server)
            if sock is None:
                continue
            platformid += 1
            typeflags = ConfigFlags.UPDATE.value
            values[names.index("platform_id_start")] = str(platformid)
            values[names.index("nem_id_start")] = str(nemid)
            msg = EmaneGlobalModel.config_data(flags=0, node_id=None, type_flags=typeflags, values=values)
            sock.send(msg)
            # increment nemid for next server by number of interfaces
            self._ifccountslock.acquire()
            if server in self._ifccounts:
                nemid += self._ifccounts[server]
            self._ifccountslock.release()

        return False

    def buildxml(self):
        """
        Build all of the XML files required to run EMANE on the host.
        NEMs run in a single host emane process, with TAP devices pushed
        into namespaces.
        """
        # assume self._objslock is already held here
        logger.info("Emane.buildxml()")
        self.buildplatformxml()
        self.buildnemxml()
        self.buildtransportxml()
        self.buildeventservicexml()

    def buildxml2(self):
        """
        Build XML files required to run EMANE on each node.
        NEMs run inside containers using the control network for passing
        events and data.
        """
        # assume self._objslock is already held here
        logger.info("Emane.buildxml2()")
        # on master, control network bridge added earlier in startup()
        ctrlnet = self.session.add_remove_control_net(net_index=0, remove=False, conf_required=False)
        self.buildplatformxml2(ctrlnet)
        self.buildnemxml()
        self.buildeventservicexml()

    def distributedctrlnet(self, ctrlnet):
        """
        Distributed EMANE requires multiple control network prefixes to
        be configured. This generates configuration for slave control nets
        using the default list of prefixes.
        """
        session = self.session
        if not session.master:
            return  # slave server
        servers = session.broker.getserverlist()
        if len(servers) < 2:
            return  # not distributed
        prefix = session.config.get('controlnet')
        prefix = getattr(session.options, 'controlnet', prefix)
        prefixes = prefix.split()
        if len(prefixes) >= len(servers):
            return  # normal Config messaging will distribute controlnets
        # this generates a config message having controlnet prefix assignments
        logger.info("Setting up default controlnet prefixes for distributed (%d configured)" % len(prefixes))
        prefixes = ctrlnet.DEFAULT_PREFIX_LIST[0]
        vals = "controlnet='%s'" % prefixes
        tlvdata = ""
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.OBJECT.value, "session")
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.TYPE.value, 0)
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.VALUES.value, vals)
        rawmsg = coreapi.CoreConfMessage.pack(0, tlvdata)
        msghdr = rawmsg[:coreapi.CoreMessage.header_len]
        msg = coreapi.CoreConfMessage(flags=0, hdr=msghdr, data=rawmsg[coreapi.CoreMessage.header_len:])
        self.session.broker.handle_message(msg)

    def xmldoc(self, doctype):
        """
        Returns an XML xml.minidom.Document with a DOCTYPE tag set to the
        provided doctype string, and an initial element having the same
        name.
        """
        # we hack in the DOCTYPE using the parser
        docstr = """<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE %s SYSTEM "file:///usr/share/emane/dtd/%s.dtd">
        <%s/>""" % (doctype, doctype, doctype)
        # normally this would be: doc = Document()
        return parseString(docstr)

    def xmlparam(self, doc, name, value):
        """
        Convenience function for building a parameter tag of the format:
        <param name="name" value="value" />
        """
        p = doc.createElement("param")
        p.setAttribute("name", name)
        p.setAttribute("value", value)
        return p

    def xmlshimdefinition(self, doc, name):
        """
        Convenience function for building a definition tag of the format:
        <shim definition="name" />
        """
        p = doc.createElement("shim")
        p.setAttribute("definition", name)
        return p

    def xmlwrite(self, doc, filename):
        """
        Write the given XML document to the specified filename.
        """
        pathname = os.path.join(self.session.session_dir, filename)
        f = open(pathname, "w")
        doc.writexml(writer=f, indent="", addindent="  ", newl="\n", encoding="UTF-8")
        f.close()

    def setnodemodels(self):
        """
        Associate EmaneModel classes with EmaneNode nodes. The model
        configurations are stored in self.configs.
        """
        for n in self._objs:
            self.setnodemodel(n)

    def setnodemodel(self, n):
        emanenode = self._objs[n]
        if n not in self.configs:
            return False
        for t, v in self.configs[n]:
            if t is None:
                continue
            if t == self.emane_config.name:
                continue
            # only use the first valid EmaneModel
            # convert model name to class (e.g. emane_rfpipe -> EmaneRfPipe)
            cls = self._modelclsmap[t]
            emanenode.setmodel(cls, v)
            return True
        # no model has been configured for this EmaneNode
        return False

    def nemlookup(self, nemid):
        """
        Look for the given numerical NEM ID and return the first matching
        EmaneNode and NEM interface.
        """
        emanenode = None
        netif = None

        for n in self._objs:
            emanenode = self._objs[n]
            netif = emanenode.getnemnetif(nemid)
            if netif is not None:
                break
            else:
                emanenode = None
        return emanenode, netif

    def numnems(self):
        """
        Return the number of NEMs emulated locally.
        """
        count = 0
        for o in self._objs.values():
            count += len(o.netifs())
        return count

    def buildplatformxml(self):
        """
        Build a platform.xml file now that all nodes are configured.
        """
        values = self.getconfig(None, "emane", self.emane_config.getdefaultvalues())[1]
        doc = self.xmldoc("platform")
        plat = doc.getElementsByTagName("platform").pop()
        if emane.VERSION < emane.EMANE091:
            platformid = self.emane_config.valueof("platform_id_start", values)
            plat.setAttribute("name", "Platform %s" % platformid)
            plat.setAttribute("id", platformid)

        names = list(self.emane_config.getnames())
        platform_names = names[:len(self.emane_config._confmatrix_platform)]
        platform_names.remove('platform_id_start')

        # append all platform options (except starting id) to doc
        map(lambda n: plat.appendChild(self.xmlparam(doc, n, self.emane_config.valueof(n, values))), platform_names)

        nemid = int(self.emane_config.valueof("nem_id_start", values))
        # assume self._objslock is already held here
        for n in sorted(self._objs.keys()):
            emanenode = self._objs[n]
            nems = emanenode.buildplatformxmlentry(doc)
            for netif in sorted(nems, key=lambda n: n.node.objid):
                # set ID, endpoints here
                nementry = nems[netif]
                nementry.setAttribute("id", "%d" % nemid)
                if emane.VERSION < emane.EMANE092:
                    # insert nem options (except nem id) to doc
                    trans_addr = self.emane_config.valueof("transportendpoint", values)
                    nementry.insertBefore(
                        self.xmlparam(doc, "transportendpoint", "%s:%d" % (trans_addr, self.transformport)),
                        nementry.firstChild
                    )
                    platform_addr = self.emane_config.valueof("platformendpoint", values)
                    nementry.insertBefore(
                        self.xmlparam(doc, "platformendpoint", "%s:%d" % (platform_addr, self.platformport)),
                        nementry.firstChild
                    )
                plat.appendChild(nementry)
                emanenode.setnemid(netif, nemid)
                # NOTE: MAC address set before here is incorrect, including the one
                #  sent from the GUI via link message
                # MAC address determined by NEM ID: 02:02:00:00:nn:nn"
                macstr = self._hwaddr_prefix + ":00:00:"
                macstr += "%02X:%02X" % ((nemid >> 8) & 0xFF, nemid & 0xFF)
                netif.sethwaddr(MacAddress.from_string(macstr))
                # increment counters used to manage IDs, endpoint port numbers
                nemid += 1
                self.platformport += 1
                self.transformport += 1
        self.xmlwrite(doc, "platform.xml")

    def newplatformxmldoc(self, values, otadev=None, eventdev=None):
        """
        Start a new platform XML file. Use global EMANE config values
        as keys. Override OTA manager and event service devices if
        specified (in order to support Raw Transport).
        """
        doc = self.xmldoc("platform")
        plat = doc.getElementsByTagName("platform").pop()
        names = list(self.emane_config.getnames())
        platform_names = names[:len(self.emane_config._confmatrix_platform)]
        platform_names.remove('platform_id_start')
        platform_values = list(values)
        if otadev:
            i = platform_names.index('otamanagerdevice')
            platform_values[i] = otadev
        if eventdev:
            i = platform_names.index('eventservicedevice')
            platform_values[i] = eventdev
        # append all platform options (except starting id) to doc
        map(lambda n: plat.appendChild(self.xmlparam(doc, n, self.emane_config.valueof(n, platform_values))),
            platform_names)
        return doc

    def buildplatformxml2(self, ctrlnet):
        """
        Build a platform.xml file now that all nodes are configured.
        """
        values = self.getconfig(None, "emane", self.emane_config.getdefaultvalues())[1]
        nemid = int(self.emane_config.valueof("nem_id_start", values))
        platformxmls = {}

        # assume self._objslock is already held here
        for n in sorted(self._objs.keys()):
            emanenode = self._objs[n]
            nems = emanenode.buildplatformxmlentry(self.xmldoc("platform"))
            for netif in sorted(nems, key=lambda n: n.node.objid):
                nementry = nems[netif]
                nementry.setAttribute("id", "%d" % nemid)
                k = netif.node.objid
                if netif.transport_type == "raw":
                    k = 'host'
                    otadev = ctrlnet.brname
                    eventdev = ctrlnet.brname
                else:
                    otadev = None
                    eventdev = None
                if k not in platformxmls:
                    platformxmls[k] = self.newplatformxmldoc(values, otadev,
                                                             eventdev)
                doc = platformxmls[k]
                plat = doc.getElementsByTagName("platform").pop()
                plat.appendChild(nementry)
                emanenode.setnemid(netif, nemid)
                macstr = self._hwaddr_prefix + ":00:00:"
                macstr += "%02X:%02X" % ((nemid >> 8) & 0xFF, nemid & 0xFF)
                netif.sethwaddr(MacAddress.from_string(macstr))
                nemid += 1
        for k in sorted(platformxmls.keys()):
            if k == 'host':
                self.xmlwrite(platformxmls['host'], "platform.xml")
                continue
            self.xmlwrite(platformxmls[k], "platform%d.xml" % k)

    def buildnemxml(self):
        """
        Builds the xxxnem.xml, xxxmac.xml, and xxxphy.xml files which
        are defined on a per-EmaneNode basis.
        """
        for n in sorted(self._objs.keys()):
            emanenode = self._objs[n]
            emanenode.buildnemxmlfiles(self)

    def appendtransporttonem(self, doc, nem, nodenum, ifc=None):
        """
        Given a nem XML node and EMANE WLAN node number, append
        a <transport/> tag to the NEM definition, required for using
        EMANE's internal transport.
        """
        if emane.VERSION < emane.EMANE092:
            return
        emanenode = self._objs[nodenum]
        transtag = doc.createElement("transport")
        transtypestr = "virtual"
        if ifc and ifc.transport_type == "raw":
            transtypestr = "raw"
        transtag.setAttribute("definition", emanenode.transportxmlname(transtypestr))
        nem.appendChild(transtag)

    def buildtransportxml(self):
        """
        Calls emanegentransportxml using a platform.xml file to build
        the transportdaemon*.xml.
        """
        try:
            subprocess.check_call(["emanegentransportxml", "platform.xml"], cwd=self.session.session_dir)
        except subprocess.CalledProcessError:
            logger.exception("error running emanegentransportxml")

    def buildeventservicexml(self):
        """
        Build the libemaneeventservice.xml file if event service options
        were changed in the global config.
        """
        defaults = self.emane_config.getdefaultvalues()
        values = self.getconfig(None, "emane", self.emane_config.getdefaultvalues())[1]
        need_xml = False
        keys = ('eventservicegroup', 'eventservicedevice')
        for k in keys:
            a = self.emane_config.valueof(k, defaults)
            b = self.emane_config.valueof(k, values)
            if a != b:
                need_xml = True

        if not need_xml:
            # reset to using default config
            self.initeventservice()
            return

        try:
            group, port = self.emane_config.valueof('eventservicegroup', values).split(':')
        except ValueError:
            logger.exception("invalid eventservicegroup in EMANE config")
            return
        dev = self.emane_config.valueof('eventservicedevice', values)

        doc = self.xmldoc("emaneeventmsgsvc")
        es = doc.getElementsByTagName("emaneeventmsgsvc").pop()
        kvs = (('group', group), ('port', port), ('device', dev), ('mcloop', '1'), ('ttl', '32'))
        xmlutils.add_text_elements_from_tuples(doc, es, kvs)
        filename = 'libemaneeventservice.xml'
        self.xmlwrite(doc, filename)
        pathname = os.path.join(self.session.session_dir, filename)
        self.initeventservice(filename=pathname)

    def startdaemons(self):
        """
        Start the appropriate EMANE daemons. The transport daemon will
        bind to the TAP interfaces.
        """
        logger.info("Emane.startdaemons()")
        path = self.session.session_dir
        loglevel = str(EmaneManager.DEFAULT_LOG_LEVEL)
        cfgloglevel = self.session.get_config_item_int("emane_log_level")
        realtime = self.session.get_config_item_bool("emane_realtime", True)
        if cfgloglevel:
            logger.info("setting user-defined EMANE log level: %d" % cfgloglevel)
            loglevel = str(cfgloglevel)
        emanecmd = ["emane", "-d", "--logl", loglevel, "-f", os.path.join(path, "emane.log")]
        if realtime:
            emanecmd += "-r",
        try:
            cmd = emanecmd + [os.path.join(path, "platform.xml")]
            logger.info("Emane.startdaemons() running %s" % str(cmd))
            subprocess.check_call(cmd, cwd=path)
        except subprocess.CalledProcessError:
            logger.exception("error starting emane")

        # start one transport daemon per transportdaemon*.xml file
        transcmd = ["emanetransportd", "-d", "--logl", loglevel, "-f", os.path.join(path, "emanetransportd.log")]
        if realtime:
            transcmd += "-r",
        files = os.listdir(path)
        for file in files:
            if file[-3:] == "xml" and file[:15] == "transportdaemon":
                cmd = transcmd + [os.path.join(path, file)]
                try:
                    logger.info("Emane.startdaemons() running %s" % str(cmd))
                    subprocess.check_call(cmd, cwd=path)
                except subprocess.CalledProcessError:
                    logger.exception("error starting emanetransportd")

    def startdaemons2(self):
        """
        Start one EMANE daemon per node having a radio.
        Add a control network even if the user has not configured one.
        """
        logger.info("Emane.startdaemons()")
        loglevel = str(EmaneManager.DEFAULT_LOG_LEVEL)
        cfgloglevel = self.session.get_config_item_int("emane_log_level")
        realtime = self.session.get_config_item_bool("emane_realtime", True)
        if cfgloglevel:
            logger.info("setting user-defined EMANE log level: %d" % cfgloglevel)
            loglevel = str(cfgloglevel)
        emanecmd = ["emane", "-d", "--logl", loglevel]
        if realtime:
            emanecmd += "-r",

        values = self.getconfig(None, "emane", self.emane_config.getdefaultvalues())[1]
        otagroup, otaport = self.emane_config.valueof('otamanagergroup', values).split(':')
        otadev = self.emane_config.valueof('otamanagerdevice', values)
        otanetidx = self.session.get_control_net_index(otadev)

        eventgroup, eventport = self.emane_config.valueof('eventservicegroup', values).split(':')
        eventdev = self.emane_config.valueof('eventservicedevice', values)
        eventservicenetidx = self.session.get_control_net_index(eventdev)

        run_emane_on_host = False
        for node in self.getnodes():
            if hasattr(node, 'transport_type') and node.transport_type == "raw":
                run_emane_on_host = True
                continue
            path = self.session.session_dir
            n = node.objid

            # control network not yet started here
            self.session.add_remove_control_interface(node, 0, remove=False, conf_required=False)

            if otanetidx > 0:
                logger.info("adding ota device ctrl%d" % otanetidx)
                self.session.add_remove_control_interface(node, otanetidx, remove=False, conf_required=False)

            if eventservicenetidx >= 0:
                logger.info("adding event service device ctrl%d" % eventservicenetidx)
                self.session.add_remove_control_interface(node, eventservicenetidx, remove=False, conf_required=False)

            # multicast route is needed for OTA data
            cmd = [constants.IP_BIN, "route", "add", otagroup, "dev", otadev]
            # rc = node.cmd(cmd, wait=True)
            node.cmd(cmd, wait=True)
            # multicast route is also needed for event data if on control network
            if eventservicenetidx >= 0 and eventgroup != otagroup:
                cmd = [constants.IP_BIN, "route", "add", eventgroup, "dev", eventdev]
                node.cmd(cmd, wait=True)

            try:
                cmd = emanecmd + ["-f", os.path.join(path, "emane%d.log" % n), os.path.join(path, "platform%d.xml" % n)]
                logger.info("Emane.startdaemons2() running %s" % str(cmd))
                status = node.cmd(cmd, wait=True)
                logger.info("Emane.startdaemons2() return code %d" % status)
            except subprocess.CalledProcessError:
                logger.exception("error starting emane")

        if not run_emane_on_host:
            return

        path = self.session.session_dir
        try:
            emanecmd += ["-f", os.path.join(path, "emane.log")]
            cmd = emanecmd + [os.path.join(path, "platform.xml")]
            logger.info("Emane.startdaemons2() running %s" % str(cmd))
            subprocess.check_call(cmd, cwd=path)
        except subprocess.CalledProcessError:
            logger.exception("error starting emane")

    def stopdaemons(self):
        """
        Kill the appropriate EMANE daemons.
        """
        # TODO: we may want to improve this if we had the PIDs from the
        #       specific EMANE daemons that we've started
        cmd = ["killall", "-q", "emane"]
        stop_emane_on_host = False
        if emane.VERSION > emane.EMANE091:
            for node in self.getnodes():
                if hasattr(node, 'transport_type') and \
                        node.transport_type == "raw":
                    stop_emane_on_host = True
                    continue
                if node.up:
                    node.cmd(cmd, wait=False)
                    # TODO: RJ45 node
        else:
            stop_emane_on_host = True
        if stop_emane_on_host:
            subprocess.call(cmd)
            subprocess.call(["killall", "-q", "emanetransportd"])

    def installnetifs(self, do_netns=True):
        """
        Install TUN/TAP virtual interfaces into their proper namespaces
        now that the EMANE daemons are running.
        """
        for n in sorted(self._objs.keys()):
            emanenode = self._objs[n]
            logger.info("Emane.installnetifs() for node %d" % n)
            emanenode.installnetifs(do_netns)

    def deinstallnetifs(self):
        """
        Uninstall TUN/TAP virtual interfaces.
        """
        for n in sorted(self._objs.keys()):
            emanenode = self._objs[n]
            emanenode.deinstallnetifs()

    def configure(self, session, config_data):
        """
        Handle configuration messages for global EMANE config.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        """
        r = self.emane_config.configure_emane(session, config_data)

        # extra logic to start slave Emane object after nemid has been
        # configured from the master
        config_type = config_data.type
        if config_type == ConfigFlags.UPDATE.value and self.session.master is False:
            # instantiation was previously delayed by self.setup()
            # returning Emane.NOT_READY
            self.session.instantiate()

        return r

    def doeventmonitor(self):
        """
        Returns boolean whether or not EMANE events will be monitored.
        """
        # this support must be explicitly turned on; by default, CORE will
        # generate the EMANE events when nodes are moved
        return self.session.get_config_item_bool('emane_event_monitor', False)

    def genlocationevents(self):
        """
        Returns boolean whether or not EMANE events will be generated.
        """
        # By default, CORE generates EMANE location events when nodes
        # are moved; this can be explicitly disabled in core.conf
        tmp = self.session.get_config_item_bool('emane_event_generate')
        if tmp is None:
            tmp = not self.doeventmonitor()
        return tmp

    def starteventmonitor(self):
        """
        Start monitoring EMANE location events if configured to do so.
        """
        logger.info("Emane.starteventmonitor()")
        if not self.doeventmonitor():
            return
        if self.service is None:
            errmsg = "Warning: EMANE events will not be generated " \
                     "because the emaneeventservice\n binding was " \
                     "unable to load " \
                     "(install the python-emaneeventservice bindings)"
            logger.error(errmsg)
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
            # reset the service, otherwise nextEvent won't work
            self.initeventservice(shutdown=True)
        if self.eventmonthread is not None:
            if emane.VERSION >= emane.EMANE091:
                self.eventmonthread._Thread__stop()
            self.eventmonthread.join()
            self.eventmonthread = None

    def eventmonitorloop(self):
        """
        Thread target that monitors EMANE location events.
        """
        if self.service is None:
            return
        logger.info("Subscribing to EMANE location events (not generating them). " \
                    "(%s) " % threading.currentThread().getName())
        while self.doeventloop is True:
            if emane.VERSION >= emane.EMANE091:
                uuid, seq, events = self.service.nextEvent()
                if not self.doeventloop:
                    break  # this occurs with 0.9.1 event service
                for event in events:
                    (nem, eid, data) = event
                    if eid == LocationEvent.IDENTIFIER:
                        self.handlelocationevent2(nem, eid, data)
            else:
                (event, platform, nem, cmp, data) = self.service.nextEvent()
                if event == emaneeventlocation.EVENT_ID:
                    self.handlelocationevent(event, platform, nem, cmp, data)
        logger.info("Unsubscribing from EMANE location events. (%s) " % threading.currentThread().getName())

    def handlelocationevent(self, event, platform, nem, component, data):
        """
        Handle an EMANE location event (EMANE 0.8.1 and earlier).
        """
        event = emaneeventlocation.EventLocation(data)
        entries = event.entries()
        for e in entries.values():
            # yaw,pitch,roll,azimuth,elevation,velocity are unhandled
            (nemid, lat, long, alt) = e[:4]
            self.handlelocationeventtoxyz(nemid, lat, long, alt)

    def handlelocationevent2(self, rxnemid, eid, data):
        """
        Handle an EMANE location event (EMANE 0.9.1+).
        """
        events = LocationEvent()
        events.restore(data)
        for event in events:
            (txnemid, attrs) = event
            if 'latitude' not in attrs or 'longitude' not in attrs or \
                    'altitude' not in attrs:
                logger.warn("dropped invalid location event")
                continue
            # yaw,pitch,roll,azimuth,elevation,velocity are unhandled
            lat = attrs['latitude']
            long = attrs['longitude']
            alt = attrs['altitude']
            self.handlelocationeventtoxyz(txnemid, lat, long, alt)

    def handlelocationeventtoxyz(self, nemid, lat, long, alt):
        """
        Convert the (NEM ID, lat, long, alt) from a received location event
        into a node and x,y,z coordinate values, sending a Node Message.
        Returns True if successfully parsed and a Node Message was sent.
        """
        # convert nemid to node number
        (emanenode, netif) = self.nemlookup(nemid)
        if netif is None:
            logger.info("location event for unknown NEM %s" % nemid)
            return False
        n = netif.node.objid
        # convert from lat/long/alt to x,y,z coordinates
        x, y, z = self.session.location.getxyz(lat, long, alt)
        x = int(x)
        y = int(y)
        z = int(z)
        logger.info("location event NEM %s (%s, %s, %s) -> (%s, %s, %s)",
                    nemid, lat, long, alt, x, y, z)
        try:
            if (x.bit_length() > 16) or (y.bit_length() > 16) or \
                (z.bit_length() > 16) or (x < 0) or (y < 0) or (z < 0):
                warntxt = "Unable to build node location message since " \
                          "received lat/long/alt exceeds coordinate " \
                          "space: NEM %s (%d, %d, %d)" % (nemid, x, y, z)
                logger.error(warntxt)
                return False
        except AttributeError:
            # int.bit_length() not present on Python 2.6
            logger.exception("error wusing bit_length")

        # generate a node message for this location update
        try:
            node = self.session.get_object(n)
        except KeyError:
            logger.exception("location event NEM %s has no corresponding node %s" % (nemid, n))
            return False
        # don't use node.setposition(x,y,z) which generates an event
        node.position.set(x, y, z)

        node_data = node.data(message_type=0)
        self.session.broadcast_node(node_data)

        # TODO: determinehow to add SDT handlers
        # self.session.sdt.updatenodegeo(node.objid, lat, long, alt)

        return True


class EmaneGlobalModel(EmaneModel):
    """
    Global EMANE configuration options.
    """

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    # Over-The-Air channel required for EMANE 0.9.2
    _DEFAULT_OTA = '0'
    _DEFAULT_DEV = 'lo'
    if emane.VERSION >= emane.EMANE092:
        _DEFAULT_OTA = '1'
        _DEFAULT_DEV = 'ctrl0'

    name = "emane"
    _confmatrix_platform_base = [
        ("otamanagerchannelenable", ConfigDataTypes.BOOL.value, _DEFAULT_OTA,
         'on,off', 'enable OTA Manager channel'),
        ("otamanagergroup", ConfigDataTypes.STRING.value, '224.1.2.8:45702',
         '', 'OTA Manager group'),
        ("otamanagerdevice", ConfigDataTypes.STRING.value, _DEFAULT_DEV,
         '', 'OTA Manager device'),
        ("eventservicegroup", ConfigDataTypes.STRING.value, '224.1.2.8:45703',
         '', 'Event Service group'),
        ("eventservicedevice", ConfigDataTypes.STRING.value, _DEFAULT_DEV,
         '', 'Event Service device'),
        ("platform_id_start", ConfigDataTypes.INT32.value, '1',
         '', 'starting Platform ID'),
    ]
    _confmatrix_platform_081 = [
        ("debugportenable", ConfigDataTypes.BOOL.value, '0',
         'on,off', 'enable debug port'),
        ("debugport", ConfigDataTypes.UINT16.value, '47000',
         '', 'debug port number'),
    ]
    _confmatrix_platform_091 = [
        ("controlportendpoint", ConfigDataTypes.STRING.value, '0.0.0.0:47000',
         '', 'Control port address'),
        ("antennaprofilemanifesturi", ConfigDataTypes.STRING.value, '',
         '', 'antenna profile manifest URI'),
    ]
    _confmatrix_nem = [
        ("transportendpoint", ConfigDataTypes.STRING.value, 'localhost',
         '', 'Transport endpoint address (port is automatic)'),
        ("platformendpoint", ConfigDataTypes.STRING.value, 'localhost',
         '', 'Platform endpoint address (port is automatic)'),
        ("nem_id_start", ConfigDataTypes.INT32.value, '1',
         '', 'starting NEM ID'),
    ]
    _confmatrix_nem_092 = [
        ("nem_id_start", ConfigDataTypes.INT32.value, '1',
         '', 'starting NEM ID'),
    ]

    if emane.VERSION >= emane.EMANE091:
        _confmatrix_platform = _confmatrix_platform_base + \
                               _confmatrix_platform_091
        if emane.VERSION >= emane.EMANE092:
            _confmatrix_nem = _confmatrix_nem_092
    else:
        _confmatrix_platform = _confmatrix_platform_base + \
                               _confmatrix_platform_081
    config_matrix = _confmatrix_platform + _confmatrix_nem
    config_groups = "Platform Attributes:1-%d|NEM Parameters:%d-%d" % \
                    (len(_confmatrix_platform), len(_confmatrix_platform) + 1,
                     len(config_matrix))
