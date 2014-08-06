#
# CORE
# Copyright (c)2010-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
emane.py: definition of an Emane class for implementing configuration
          control of an EMANE emulation.
'''

import sys, os, threading, subprocess, time, string
from xml.dom.minidom import parseString, Document
from core.constants import *
from core.api import coreapi
from core.misc.ipaddr import MacAddr
from core.misc.utils import maketuplefromstr
from core.misc.xmlutils import addtextelementsfromtuples, addparamlisttoparent
from core.conf import ConfigurableManager, Configurable
from core.mobility import WirelessModel
from core.emane.nodes import EmaneNode
# EMANE 0.7.4/0.8.1
try:
    import emaneeventservice
    import emaneeventlocation
except Exception, e:
    pass
# EMANE 0.9.1+
try:
    from emanesh.events import EventService
    from emanesh.events import LocationEvent
except Exception, e:
    pass


class Emane(ConfigurableManager):
    ''' EMANE controller object. Lives in a Session instance and is used for
        building EMANE config files from all of the EmaneNode objects in this
        emulation, and for controlling the EMANE daemons.
    '''
    _name = "emane"
    _type = coreapi.CORE_TLV_REG_EMULSRV
    _hwaddr_prefix = "02:02"
    (SUCCESS, NOT_NEEDED, NOT_READY) = (0, 1, 2)
    EVENTCFGVAR = 'LIBEMANEEVENTSERVICECONFIG'
    # possible self.version values
    (EMANE074, EMANE081, EMANE091) = (7, 8, 9)
    
    def __init__(self, session):
        ConfigurableManager.__init__(self, session)
        self.verbose = self.session.getcfgitembool('verbose', False)
        self._objs = {}
        self._objslock = threading.Lock()
        self._ifccounts = {}
        self._ifccountslock = threading.Lock()
        self._modelclsmap = {}
        # Port numbers are allocated from these counters
        self.platformport = self.session.getcfgitemint('emane_platform_port',
                                                       8100)
        self.transformport = self.session.getcfgitemint('emane_transform_port',
                                                        8200)
        self.doeventloop = False
        self.eventmonthread = None
        # detect between EMANE versions 0.7.4, 0.8.1, and 0.9.1+
        # to be removed as support for older EMANEs is deprecated
        self.version = self.EMANE081
        try:
            tmp = emaneeventlocation.EventLocation(1)
            # check if yaw parameter is supported by Location Events
            # if so, we have EMANE 0.8.1; if not, we have EMANE 0.7.4/earlier
            tmp.set(0, 1, 2, 2, 2, 3)
        except TypeError:
            self.version = self.EMANE074
        except Exception:
            # e.g. no Python bindings installed
            pass
        if 'EventService' in globals():
            self.version = self.EMANE091
        # model for global EMANE configuration options
        self.emane_config = EmaneGlobalModel(session, None, self.verbose)
        session.broker.handlers += (self.handledistributed, )
        self.loadmodels()
        self.initeventservice()

    def initeventservice(self, filename=None):
        ''' (Re-)initialize the EMANE Event service. The multicast group and/or
        port may be configured, and can be changed via XML config file and an
        environment variable pointing to that file.
        '''
        if hasattr(self, 'service'):
            del self.service
        self.service = None
        # EMANE 0.9.1+ does not require event service XML config
        if self.version == self.EMANE091:
            values = self.getconfig(None, "emane",
                                    self.emane_config.getdefaultvalues())[1]
            group, port = self.emane_config.valueof('eventservicegroup',
                                                        values).split(':')
            dev = self.emane_config.valueof('eventservicedevice', values)
            otachannel = None
            ota_enable = self.emane_config.valueof('otamanagerchannelenable',
                                                   values)
            if self.emane_config.offontobool(ota_enable):
                ogroup, oport = self.emane_config.valueof('otamanagergroup',
                                                          values).split(':')
                odev = self.emane_config.valueof('otamanagerdevice', values)
                otachannel = (ogroup, int(oport), odev)
            self.service = EventService(eventchannel=(group, int(port), dev),
                                        otachannel=otachannel)
            return True
        if filename is not None:
            tmp = os.getenv(self.EVENTCFGVAR)
            os.environ.update( {self.EVENTCFGVAR: filename} )
        rc = True
        try:
            self.service = emaneeventservice.EventService()
        except:
            self.service = None
            rc = False
        if filename is not None:
            os.environ.pop(self.EVENTCFGVAR)
            if tmp is not None:
                os.environ.update( {self.EVENTCFGVAR: tmp} )
        return rc

    def loadmodels(self):
        ''' dynamically load EMANE models that were specified in the config file
        '''
        self._modelclsmap.clear()
        self._modelclsmap[self.emane_config._name] = self.emane_config
        emane_models = self.session.getcfgitem('emane_models')
        if emane_models is None:
            return
        emane_models = emane_models.split(',')
        for model in emane_models:
            model = model.strip()
            try:
                modelfile = "%s" % model.lower()
                clsname = "Emane%sModel" % model
                importcmd = "from %s import %s" % (modelfile, clsname)
                exec(importcmd)
            except Exception, e:
                warntxt = "unable to load the EMANE model '%s'" % modelfile
                warntxt += " specified in the config file (%s)" % e
                self.session.exception(coreapi.CORE_EXCP_LEVEL_WARNING, "emane",
                                       None, warntxt)
                self.warn(warntxt)
                continue
            # record the model name to class name mapping
            # this should match clsname._name
            confname = "emane_%s" % model.lower()
            self._modelclsmap[confname] = eval(clsname)
            # each EmaneModel must have ModelName.configure() defined
            confmethod = eval("%s.configure_emane" % clsname)
            self.session.addconfobj(confname, coreapi.CORE_TLV_REG_WIRELESS,
                                    confmethod)

    def addobj(self, obj):
        ''' add a new EmaneNode object to this Emane controller object
        '''
        self._objslock.acquire()
        if obj.objid in self._objs:
            self._objslock.release()
            raise KeyError, "non-unique EMANE object id %s for %s" % \
                (obj.objid, obj)
        self._objs[obj.objid] = obj
        self._objslock.release()
        
    def getmodels(self, n):
        ''' Used with XML export; see ConfigurableManager.getmodels()
        '''
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
            return self.getconfig(ifc.node.objid, conftype, None)[1]

    def setup(self):
        ''' Populate self._objs with EmaneNodes; perform distributed setup;
        associate models with EmaneNodes from self.config. Returns
        Emane.(SUCCESS, NOT_NEEDED, NOT_READY) in order to delay session
        instantiation.
        '''
        with self.session._objslock:
            for obj in self.session.objs():
                if isinstance(obj, EmaneNode):
                    self.addobj(obj)
            if len(self._objs) == 0:
                return Emane.NOT_NEEDED
        if self.checkdistributed():
            # we are slave, but haven't received a platformid yet
            cfgval = self.getconfig(None, self.emane_config._name,
                                    self.emane_config.getdefaultvalues())[1]
            i = self.emane_config.getnames().index('platform_id_start')
            if cfgval[i] == self.emane_config.getdefaultvalues()[i]:
                return Emane.NOT_READY
        self.setnodemodels()
        return Emane.SUCCESS

    def startup(self):
        ''' After all the EmaneNode objects have been added, build XML files
            and start the daemons. Returns Emane.(SUCCESS, NOT_NEEDED, or
            NOT_READY) which is used to delay session instantiation.
        '''
        self.reset()
        r = self.setup()
        if r != Emane.SUCCESS:
            return r  # NOT_NEEDED or NOT_READY
        with self._objslock:
            self.buildxml()
            self.starteventmonitor()
            if self.numnems() > 0:
                # TODO: check and return failure for these methods
                self.startdaemons()
                self.installnetifs()
        return Emane.SUCCESS

    def poststartup(self):
        ''' Retransmit location events now that all NEMs are active.
        '''
        if self.doeventmonitor():
            return
        with self._objslock:
            for n in sorted(self._objs.keys()):
                e = self._objs[n]
                for netif in e.netifs():
                    (x, y, z) = netif.node.position.get()
                    e.setnemposition(netif, x, y, z)

    def reset(self):
        ''' remove all EmaneNode objects from the dictionary,
            reset port numbers and nem id counters
        '''
        with self._objslock:
            self._objs.clear()
        # don't clear self._ifccounts here; NEM counts are needed for buildxml
        self.platformport = self.session.getcfgitemint('emane_platform_port',
                                                       8100)
        self.transformport = self.session.getcfgitemint('emane_transform_port',
                                                        8200)

    def shutdown(self):
        ''' stop all EMANE daemons
        '''
        self._ifccountslock.acquire()
        self._ifccounts.clear()
        self._ifccountslock.release()
        self._objslock.acquire()
        if len(self._objs) == 0:
            self._objslock.release()
            return
        self.info("Stopping EMANE daemons.")
        self.deinstallnetifs()
        self.stopdaemons()
        self.stopeventmonitor()
        self._objslock.release()

    def handledistributed(self, msg):
        ''' Broker handler for processing CORE API messages as they are 
            received. This is used to snoop the Link add messages to get NEM
            counts of NEMs that exist on other servers.
        '''
        if msg.msgtype == coreapi.CORE_API_LINK_MSG and \
           msg.flags & coreapi.CORE_API_ADD_FLAG:
            nn = msg.nodenumbers()
            # first node is always link layer node in Link add message
            if nn[0] in self.session.broker.nets:
                serverlist = self.session.broker.getserversbynode(nn[1])
                for server in serverlist:
                    self._ifccountslock.acquire()
                    if server not in self._ifccounts:
                        self._ifccounts[server] = 1
                    else:
                        self._ifccounts[server] += 1
                    self._ifccountslock.release()

    def checkdistributed(self):
        ''' Check for EMANE nodes that exist on multiple emulation servers and
            coordinate the NEM id and port number space.
            If we are the master EMANE node, return False so initialization will
            proceed as normal; otherwise slaves return True here and
            initialization is deferred.
        '''
        # check with the session if we are the "master" Emane object?
        master = False
        self._objslock.acquire()
        if len(self._objs) > 0:
            master = self.session.master
            self.info("Setup EMANE with master=%s." % master)
        self._objslock.release()

        # we are not the master Emane object, wait for nem id and ports
        if not master:
            return True

        cfgval = self.getconfig(None, self.emane_config._name,
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
            typeflags = coreapi.CONF_TYPE_FLAGS_UPDATE
            values[names.index("platform_id_start")] = str(platformid)
            values[names.index("nem_id_start")] = str(nemid)
            msg = EmaneGlobalModel.toconfmsg(flags=0, nodenum=None,
                                             typeflags=typeflags, values=values)
            sock.send(msg)
            # increment nemid for next server by number of interfaces
            self._ifccountslock.acquire()
            if server in self._ifccounts:
                nemid += self._ifccounts[server]
            self._ifccountslock.release()

        return False

    def buildxml(self):
        ''' Build all of the XML files required to run EMANE.
        '''
        # assume self._objslock is already held here
        if self.verbose:
            self.info("Emane.buildxml()")
        self.buildplatformxml()
        self.buildnemxml()
        self.buildtransportxml()
        self.buildeventservicexml()

    def xmldoc(self, doctype):
        ''' Returns an XML xml.minidom.Document with a DOCTYPE tag set to the
            provided doctype string, and an initial element having the same
            name.
        '''
        # we hack in the DOCTYPE using the parser
        docstr = """<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE %s SYSTEM "file:///usr/share/emane/dtd/%s.dtd">
        <%s/>""" % (doctype, doctype, doctype)
        # normally this would be: doc = Document()
        return parseString(docstr)

    def xmlparam(self, doc, name, value):
        ''' Convenience function for building a parameter tag of the format:
              <param name="name" value="value" />
        '''
        p = doc.createElement("param")
        p.setAttribute("name", name)
        p.setAttribute("value", value)
        return p

    def xmlshimdefinition(self, doc, name):
        ''' Convenience function for building a definition tag of the format:
              <shim definition="name" />
        '''
        p = doc.createElement("shim")
        p.setAttribute("definition", name)
        return p

    def xmlwrite(self, doc, filename):
        ''' Write the given XML document to the specified filename.
        '''
        #self.info("%s" % doc.toprettyxml(indent="  "))
        pathname = os.path.join(self.session.sessiondir, filename)
        f = open(pathname, "w")
        doc.writexml(writer=f, indent="", addindent="  ", newl="\n", \
                     encoding="UTF-8")
        f.close()

    def setnodemodels(self):
        ''' Associate EmaneModel classes with EmaneNode nodes. The model
            configurations are stored in self.configs.
        '''
        for n in self._objs:
            self.setnodemodel(n)
            
    def setnodemodel(self, n):
        emanenode = self._objs[n]
        if n not in self.configs:
            return False
        for (t, v) in self.configs[n]:
            if t is None:
                continue
            if t == self.emane_config._name:
                continue
            # only use the first valid EmaneModel
            # convert model name to class (e.g. emane_rfpipe -> EmaneRfPipe)
            cls = self._modelclsmap[t]
            emanenode.setmodel(cls, v)
            return True
        # no model has been configured for this EmaneNode
        return False

    def nemlookup(self, nemid):
        ''' Look for the given numerical NEM ID and return the first matching
            EmaneNode and NEM interface.
        '''
        emanenode = None
        netif = None

        for n in self._objs:
            emanenode = self._objs[n]
            netif = emanenode.getnemnetif(nemid)
            if netif is not None:
                break
            else:
                emanenode = None
        return (emanenode, netif)
    
    def numnems(self):
        ''' Return the number of NEMs emulated locally.
        '''
        count = 0
        for o in self._objs.values():
            count += len(o.netifs())
        return count

    def buildplatformxml(self):
        ''' Build a platform.xml file now that all nodes are configured.
        '''
        values = self.getconfig(None, "emane",
                                self.emane_config.getdefaultvalues())[1]
        doc = self.xmldoc("platform")
        plat = doc.getElementsByTagName("platform").pop()
        platformid = self.emane_config.valueof("platform_id_start",  values)
        if self.version != self.EMANE091:
            plat.setAttribute("name", "Platform %s" % platformid)
            plat.setAttribute("id", platformid)

        names = list(self.emane_config.getnames())
        platform_names = names[:len(self.emane_config._confmatrix_platform)]
        platform_names.remove('platform_id_start')

        # append all platform options (except starting id) to doc
        map( lambda n: plat.appendChild(self.xmlparam(doc, n, \
                        self.emane_config.valueof(n, values))), platform_names)

        nemid = int(self.emane_config.valueof("nem_id_start",  values))
        # assume self._objslock is already held here
        for n in sorted(self._objs.keys()):
            emanenode = self._objs[n]
            nems = emanenode.buildplatformxmlentry(doc)
            for netif in sorted(nems, key=lambda n: n.node.objid):            
                # set ID, endpoints here
                nementry = nems[netif]
                nementry.setAttribute("id", "%d" % nemid)
                # insert nem options (except nem id) to doc
                trans_addr = self.emane_config.valueof("transportendpoint", \
                                                       values)
                nementry.insertBefore(self.xmlparam(doc, "transportendpoint", \
                                 "%s:%d" % (trans_addr, self.transformport)),
                                 nementry.firstChild)
                platform_addr = self.emane_config.valueof("platformendpoint", \
                                                          values)
                nementry.insertBefore(self.xmlparam(doc, "platformendpoint", \
                                 "%s:%d" % (platform_addr, self.platformport)),
                                 nementry.firstChild)
                plat.appendChild(nementry)
                emanenode.setnemid(netif, nemid)
                # NOTE: MAC address set before here is incorrect, including the one
                #  sent from the GUI via link message
                # MAC address determined by NEM ID: 02:02:00:00:nn:nn"
                macstr = self._hwaddr_prefix + ":00:00:"
                macstr += "%02X:%02X" % ((nemid >> 8) & 0xFF, nemid & 0xFF)
                netif.sethwaddr(MacAddr.fromstring(macstr))
                # increment counters used to manage IDs, endpoint port numbers
                nemid += 1
                self.platformport += 1
                self.transformport += 1
        self.xmlwrite(doc, "platform.xml")

    def buildnemxml(self):
        ''' Builds the xxxnem.xml, xxxmac.xml, and xxxphy.xml files which
            are defined on a per-EmaneNode basis.
        '''
        for n in sorted(self._objs.keys()):
           emanenode = self._objs[n]
           nems = emanenode.buildnemxmlfiles(self)

    def buildtransportxml(self):
        ''' Calls emanegentransportxml using a platform.xml file to build
            the transportdaemon*.xml.
        '''
        try:
            subprocess.check_call(["emanegentransportxml", "platform.xml"], \
                              cwd=self.session.sessiondir)
        except Exception, e:
            self.info("error running emanegentransportxml: %s" % e)
    
    def buildeventservicexml(self):
        ''' Build the libemaneeventservice.xml file if event service options
            were changed in the global config.
        '''
        defaults = self.emane_config.getdefaultvalues()
        values = self.getconfig(None, "emane",
                                self.emane_config.getdefaultvalues())[1]
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
            group, port = self.emane_config.valueof('eventservicegroup',
                                                        values).split(':')
        except ValueError:
            self.warn("invalid eventservicegroup in EMANE config")
            return
        dev = self.emane_config.valueof('eventservicedevice', values)

        doc = self.xmldoc("emaneeventmsgsvc")
        es = doc.getElementsByTagName("emaneeventmsgsvc").pop()
        kvs = ( ('group', group), ('port', port), ('device', dev),
                ('mcloop', '1'),  ('ttl', '32') )
        addtextelementsfromtuples(doc, es, kvs)
        filename = 'libemaneeventservice.xml'
        self.xmlwrite(doc, filename)
        pathname = os.path.join(self.session.sessiondir, filename)
        self.initeventservice(filename=pathname)

    def startdaemons(self):
        ''' Start the appropriate EMANE daemons. The transport daemon will
            bind to the TAP interfaces.
        '''
        if self.verbose:
            self.info("Emane.startdaemons()")
        path = self.session.sessiondir
        loglevel = "2"
        cfgloglevel = self.session.getcfgitemint("emane_log_level")
        realtime = self.session.getcfgitembool("emane_realtime", True)
        if cfgloglevel:
            self.info("setting user-defined EMANE log level: %d" % cfgloglevel)
            loglevel = str(cfgloglevel)
        emanecmd = ["emane", "-d", "--logl", loglevel, "-f", \
                                os.path.join(path, "emane.log")]
        if realtime:
            emanecmd += "-r",
        try:
            cmd = emanecmd + [os.path.join(path, "platform.xml")]
            if self.verbose:
                self.info("Emane.startdaemons() running %s" % str(cmd))
            subprocess.check_call(cmd, cwd=path)
        except Exception, e:
            errmsg = "error starting emane: %s" % e
            self.session.exception(coreapi.CORE_EXCP_LEVEL_FATAL, "emane",
                                       None, errmsg)
            self.info(errmsg)

        # start one transport daemon per transportdaemon*.xml file
        transcmd = ["emanetransportd", "-d", "--logl", loglevel, "-f", \
                    os.path.join(path, "emanetransportd.log")]
        if realtime:
            transcmd += "-r", 
        files = os.listdir(path)
        for file in files:
            if file[-3:] == "xml" and file[:15] == "transportdaemon":
                cmd = transcmd + [os.path.join(path, file)]
                try:
                    if self.verbose:
                        self.info("Emane.startdaemons() running %s" % str(cmd))
                    subprocess.check_call(cmd, cwd=path)
                except Exception, e:
                    errmsg = "error starting emanetransportd: %s" % e
                    self.session.exception(coreapi.CORE_EXCP_LEVEL_FATAL, "emane",
                                       None, errmsg)
                    self.info(errmsg)

    def stopdaemons(self):
        ''' Kill the appropriate EMANE daemons.
        '''
        # TODO: we may want to improve this if we had the PIDs from the
        #       specific EMANE daemons that we've started
        subprocess.call(["killall", "-q", "emane"])
        subprocess.call(["killall", "-q", "emanetransportd"])

    def installnetifs(self):
        ''' Install TUN/TAP virtual interfaces into their proper namespaces
            now that the EMANE daemons are running.
        '''
        for n in sorted(self._objs.keys()):
           emanenode = self._objs[n]
           if self.verbose:
               self.info("Emane.installnetifs() for node %d" % n)
           emanenode.installnetifs()
    
    def deinstallnetifs(self):
        ''' Uninstall TUN/TAP virtual interfaces.
        '''
        for n in sorted(self._objs.keys()):
            emanenode = self._objs[n]
            emanenode.deinstallnetifs()

    def configure(self, session, msg):
        ''' Handle configuration messages for global EMANE config.
        '''
        r = self.emane_config.configure_emane(session, msg)

        # extra logic to start slave Emane object after nemid has been 
        # configured from the master
        conftype = msg.gettlv(coreapi.CORE_TLV_CONF_TYPE)
        if conftype == coreapi.CONF_TYPE_FLAGS_UPDATE and \
           self.session.master == False:
            # instantiation was previously delayed by self.setup()
            # returning Emane.NOT_READY
            h = None
            with session._handlerslock:
                for h in self.session._handlers:
                    break
            self.session.instantiate(handler=h)

        return r

    def doeventmonitor(self):
        ''' Returns boolean whether or not EMANE events will be monitored.
        '''
        # this support must be explicitly turned on; by default, CORE will
        # generate the EMANE events when nodes are moved
        return self.session.getcfgitembool('emane_event_monitor', False)
        
    def starteventmonitor(self):
        ''' Start monitoring EMANE location events if configured to do so.
        '''
        if self.verbose:
            self.info("Emane.starteventmonitor()")
        if not self.doeventmonitor():
            return
        if self.service is None:
            errmsg = "Warning: EMANE events will not be generated " \
                          "because the emaneeventservice\n binding was " \
                          "unable to load " \
                          "(install the python-emaneeventservice bindings)"
            self.session.exception(coreapi.CORE_EXCP_LEVEL_WARNING, "emane",
                                       None, errmsg)
            self.warn(errmsg)

            return
        self.doeventloop = True
        self.eventmonthread = threading.Thread(target = self.eventmonitorloop)
        self.eventmonthread.daemon = True
        self.eventmonthread.start()


    def stopeventmonitor(self):
        ''' Stop monitoring EMANE location events.
        '''
        self.doeventloop = False
        if self.service is not None:
            self.service.breakloop()
            # reset the service, otherwise nextEvent won't work
            self.initeventservice()
        if self.eventmonthread is not None:
            if self.version == self.EMANE091:
                self.eventmonthread._Thread__stop()
            self.eventmonthread.join()
            self.eventmonthread = None

    def eventmonitorloop(self):
        ''' Thread target that monitors EMANE location events.
        '''
        if self.service is None:
            return
        self.info("Subscribing to EMANE location events (not generating them). " \
                  "(%s) " % threading.currentThread().getName())
        while self.doeventloop is True:
            if self.version == self.EMANE091:
                (uuid, seq, events) = self.service.nextEvent()
                if not self.doeventloop:
                    break # this occurs with 0.9.1 event service
                for event in events:
                    (nem, eid, data) = event
                    if eid == LocationEvent.IDENTIFIER:
                        self.handlelocationevent2(nem, eid, data)
            else:
                (event, platform, nem, cmp, data) = self.service.nextEvent()
                if event == emaneeventlocation.EVENT_ID:
                    self.handlelocationevent(event, platform, nem, cmp, data)
        self.info("Unsubscribing from EMANE location events. (%s) " % \
                  threading.currentThread().getName())

    def handlelocationevent(self, event, platform, nem, component, data):
        ''' Handle an EMANE location event (EMANE 0.8.1 and earlier).
        '''
        event = emaneeventlocation.EventLocation(data)
        entries = event.entries()
        for e in entries.values():
            # yaw,pitch,roll,azimuth,elevation,velocity are unhandled
            (nemid, lat, long, alt) = e[:4]
            self.handlelocationeventtoxyz(nemid, lat, long, alt)

    def handlelocationevent2(self, rxnemid, eid, data):
        ''' Handle an EMANE location event (EMANE 0.9.1+).
        '''
        events = LocationEvent()
        events.restore(data)
        for event in events:
            (txnemid, attrs) = event
            if 'latitude' not in attrs or 'longitude' not in attrs or \
              'altitude' not in attrs:
                self.warn("dropped invalid location event")
                continue
            # yaw,pitch,roll,azimuth,elevation,velocity are unhandled
            lat = attrs['latitude']
            long = attrs['longitude']
            alt = attrs['altitude']
            self.handlelocationeventtoxyz(txnemid, lat, long, alt)

    def handlelocationeventtoxyz(self, nemid, lat, long, alt):
        ''' Convert the (NEM ID, lat, long, alt) from a received location event
        into a node and x,y,z coordinate values, sending a Node Message.
        Returns True if successfully parsed and a Node Message was sent.
        '''
        # convert nemid to node number
        (emanenode, netif) = self.nemlookup(nemid)
        if netif is None:
            if self.verbose:
                self.info("location event for unknown NEM %s" % nemid)
            return False
        n = netif.node.objid
        # convert from lat/long/alt to x,y,z coordinates
        (x, y, z) = self.session.location.getxyz(lat, long, alt)
        x = int(x)
        y = int(y)
        z = int(z)
        if self.verbose:
            self.info("location event NEM %s (%s, %s, %s) -> (%s, %s, %s)" \
                      % (nemid, lat, long, alt, x, y, z))
        try:
            if (x.bit_length() > 16) or (y.bit_length() > 16) or \
               (z.bit_length() > 16) or (x < 0) or (y < 0) or (z < 0):
                warntxt = "Unable to build node location message since " \
                          "received lat/long/alt exceeds coordinate " \
                          "space: NEM %s (%d, %d, %d)" % (nemid, x, y, z)
                self.info(warntxt)
                self.session.exception(coreapi.CORE_EXCP_LEVEL_ERROR,
                                       "emane", None, warntxt)
                return False
        except AttributeError:
            # int.bit_length() not present on Python 2.6
            pass

        # generate a node message for this location update
        try:
            node = self.session.obj(n)
        except KeyError:
            self.warn("location event NEM %s has no corresponding node %s" \
                     % (nemid, n))
            return False
        # don't use node.setposition(x,y,z) which generates an event
        node.position.set(x,y,z)
        msg = node.tonodemsg(flags=0)
        self.session.broadcastraw(None, msg)
        self.session.sdt.updatenodegeo(node.objid, lat, long, alt)
        return True


class EmaneModel(WirelessModel):
    ''' EMANE models inherit from this parent class, which takes care of
        handling configuration messages based on the _confmatrix list of
        configurable parameters. Helper functions also live here.
    '''
    _prefix = {'y': 1e-24,  # yocto
               'z': 1e-21,  # zepto
               'a': 1e-18,  # atto
               'f': 1e-15,  # femto
               'p': 1e-12,  # pico
               'n': 1e-9,   # nano
               'u': 1e-6,   # micro
               'm': 1e-3,   # mili
               'c': 1e-2,   # centi
               'd': 1e-1,   # deci
               'k': 1e3,    # kilo
               'M': 1e6,    # mega
               'G': 1e9,    # giga
               'T': 1e12,   # tera
               'P': 1e15,   # peta
               'E': 1e18,   # exa
               'Z': 1e21,   # zetta
               'Y': 1e24,   # yotta
               }

    @classmethod
    def configure_emane(cls, session, msg):
        ''' Handle configuration messages for setting up a model.
        Pass the Emane object as the manager object.
        '''
        return cls.configure(session.emane, msg)

    @classmethod
    def emane074_fixup(cls, value, div=1.0):
        ''' Helper for converting 0.8.1 and newer values to EMANE 0.7.4 
        compatible values. 
        NOTE: This should be removed when support for 0.7.4 has been
        deprecated.
        '''
        if div == 0:
            return "0"
        if type(value) is not str:
            return str(value / div)
        if value.endswith(tuple(cls._prefix.keys())):
            suffix = value[-1]
            value = float(value[:-1]) * cls._prefix[suffix]
        return str(int(value / div))

    def buildnemxmlfiles(self, e, ifc):
        ''' Build the necessary nem, mac, and phy XMLs in the given path.
        '''
        raise NotImplementedError
        
    def buildplatformxmlnementry(self, doc, n, ifc):
        ''' Build the NEM definition that goes into the platform.xml file.
        This returns an XML element that will be added to the <platform/> element.
        This default method supports per-interface config
          (e.g. <nem definition="n2_0_63emane_rfpipe.xml" id="1"> or per-EmaneNode
        config (e.g. <nem definition="n1emane_rfpipe.xml" id="1">.
        This can be overriden by a model for NEM flexibility; n is the EmaneNode.
        '''
        nem = doc.createElement("nem")
        nem.setAttribute("name", ifc.localname)
        # if this netif contains a non-standard (per-interface) config,
        #  then we need to use a more specific xml file here
        nem.setAttribute("definition", self.nemxmlname(ifc))
        return nem

    def buildplatformxmltransportentry(self, doc, n, ifc):
        ''' Build the transport definition that goes into the platform.xml file.
        This returns an XML element that will added to the nem definition.
        This default method supports raw and virtual transport types, but may be
        overriden by a model to support the e.g. pluggable virtual transport.
        n is the EmaneNode.
        '''
        type = ifc.transport_type
        if not type:
            e.info("warning: %s interface type unsupported!" % ifc.name)
            type = "raw"
        trans = doc.createElement("transport")
        trans.setAttribute("definition", n.transportxmlname(type))
        trans.setAttribute("group", "1")
        param = doc.createElement("param")
        param.setAttribute("name", "device")
        if type == "raw":
            # raw RJ45 name e.g. 'eth0'
            param.setAttribute("value", ifc.name)
        else:
            # virtual TAP name e.g. 'n3.0.17'
            param.setAttribute("value", ifc.localname)
        trans.appendChild(param)
        return trans

    def basename(self, ifc = None):
        ''' Return the string that other names are based on.
            If a specific config is stored for a node's interface, a unique
            filename is needed; otherwise the name of the EmaneNode is used.
        '''
        emane = self.session.emane
        name = "n%s" % self.objid
        if ifc is not None:
            nodenum = ifc.node.objid
            if emane.getconfig(nodenum, self._name, None)[1] is not None:
                name = ifc.localname.replace('.','_')
        return "%s%s" % (name, self._name)

    def nemxmlname(self, ifc = None):
        ''' Return the string name for the NEM XML file, e.g. 'n3rfpipenem.xml'
        '''
        return "%snem.xml" % self.basename(ifc)

    def shimxmlname(self, ifc = None):
        ''' Return the string name for the SHIM XML file, e.g. 'commeffectshim.xml'
        '''
        return "%sshim.xml" % self.basename(ifc)

    def macxmlname(self, ifc = None):
        ''' Return the string name for the MAC XML file, e.g. 'n3rfpipemac.xml'
        '''
        return "%smac.xml" % self.basename(ifc)

    def phyxmlname(self, ifc = None):
        ''' Return the string name for the PHY XML file, e.g. 'n3rfpipephy.xml'
        '''
        return "%sphy.xml" % self.basename(ifc)
    
    def update(self, moved, moved_netifs):
        ''' invoked from MobilityModel when nodes are moved; this causes
            EMANE location events to be generated for the nodes in the moved 
            list, making EmaneModels compatible with Ns2ScriptedMobility
        '''
        try:
            wlan = self.session.obj(self.objid)
        except KeyError:
            return
        wlan.setnempositions(moved_netifs)
        
    def linkconfig(self, netif, bw = None, delay = None,
                loss = None, duplicate = None, jitter = None, netif2 = None):
        ''' Invoked when a Link Message is received. Default is unimplemented.
        '''
        warntxt = "EMANE model %s does not support link " % self._name
        warntxt += "configuration, dropping Link Message"
        self.session.warn(warntxt)
    
    @staticmethod
    def valuestrtoparamlist(dom, name, value):
        ''' Helper to convert a parameter to a paramlist.
        Returns a an XML paramlist, or None if the value does not expand to
        multiple values.
        '''
        try:
            values = maketuplefromstr(value, str)
        except SyntaxError:
            return None
        if len(values) < 2:
            return None
        return addparamlisttoparent(dom, parent=None, name=name, values=values)


class EmaneGlobalModel(EmaneModel):
    ''' Global EMANE configuration options.
    '''
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    _name = "emane"
    _confmatrix_platform_base = [
        ("otamanagerchannelenable", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'on,off', 'enable OTA Manager channel'), 
        ("otamanagergroup", coreapi.CONF_DATA_TYPE_STRING, '224.1.2.8:45702',
         '', 'OTA Manager group'), 
        ("otamanagerdevice", coreapi.CONF_DATA_TYPE_STRING, 'lo',
         '', 'OTA Manager device'), 
        ("eventservicegroup", coreapi.CONF_DATA_TYPE_STRING, '224.1.2.8:45703',
         '', 'Event Service group'), 
        ("eventservicedevice", coreapi.CONF_DATA_TYPE_STRING, 'lo',
         '', 'Event Service device'), 
        ("platform_id_start", coreapi.CONF_DATA_TYPE_INT32, '1',
         '', 'starting Platform ID'),
    ]
    _confmatrix_platform_081 = [
        ("debugportenable", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'on,off', 'enable debug port'), 
        ("debugport", coreapi.CONF_DATA_TYPE_UINT16, '47000',
         '', 'debug port number'),
    ] 
    _confmatrix_platform_091 = [
        ("controlportendpoint", coreapi.CONF_DATA_TYPE_STRING, '0.0.0.0:47000',
         '', 'Control port address'),
        ("antennaprofilemanifesturi", coreapi.CONF_DATA_TYPE_STRING, '',
         '','antenna profile manifest URI'),
    ]
    _confmatrix_nem = [
        ("transportendpoint", coreapi.CONF_DATA_TYPE_STRING, 'localhost',
         '', 'Transport endpoint address (port is automatic)'), 
        ("platformendpoint", coreapi.CONF_DATA_TYPE_STRING, 'localhost',
         '', 'Platform endpoint address (port is automatic)'), 
        ("nem_id_start", coreapi.CONF_DATA_TYPE_INT32, '1',
         '', 'starting NEM ID'), 
        ]
    if 'EventService' in globals():
        _confmatrix_platform = _confmatrix_platform_base + \
                               _confmatrix_platform_091
    else:
        _confmatrix_platform = _confmatrix_platform_base + \
                               _confmatrix_platform_081
    _confmatrix = _confmatrix_platform + _confmatrix_nem
    _confgroups = "Platform Attributes:1-%d|NEM Parameters:%d-%d" % \
                    (len(_confmatrix_platform), len(_confmatrix_platform) + 1,
                     len(_confmatrix))

