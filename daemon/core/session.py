#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
session.py: defines the Session class used by the core-daemon daemon program
that manages a CORE session.
'''

import os, sys, tempfile, shutil, shlex, atexit, gc, pwd
import threading, time, random
import traceback

from core.api import coreapi
if os.uname()[0] == "Linux":
    from core.netns import nodes
    from core.netns.vnet import GreTapBridge
elif os.uname()[0] == "FreeBSD":
    from core.bsd import nodes
from core.emane import emane
from core.misc.utils import check_call, mutedetach, readfileintodict, \
                            filemunge, filedemunge

from core.conf import ConfigurableManager, Configurable
from core.location import CoreLocation
from core.service import CoreServices
from core.broker import CoreBroker
from core.mobility import MobilityManager
from core.sdt import Sdt
from core.misc.ipaddr import MacAddr
from core.misc.event import EventLoop
from core.constants import *
from core.misc.xmlsession import savesessionxml

from core.xen import xenconfig

class Session(object):

    # sessions that get automatically shutdown when the process
    # terminates normally
    __sessions = set()

    ''' CORE session manager.
    '''
    def __init__(self, sessionid = None, cfg = {}, server = None,
                 persistent = False, mkdir = True):
        if sessionid is None:
            # try to keep this short since it's used to construct
            # network interface names
            pid = os.getpid()
            sessionid = ((pid >> 16) ^
                         (pid & ((1 << 16) - 1)))
            sessionid ^= ((id(self) >> 16) ^ (id(self) & ((1 << 16) - 1)))
            sessionid &= 0xffff
        self.sessionid = sessionid
        self.sessiondir = os.path.join(tempfile.gettempdir(),
                                       "pycore.%s" % self.sessionid)
        if mkdir:
            os.mkdir(self.sessiondir)
        self.name = None
        self.filename = None
        self.thumbnail = None
        self.user = None
        self.node_count = None
        self._time = time.time()
        self.evq = EventLoop()
        # dict of objects: all nodes and nets
        self._objs = {}
        self._objslock = threading.Lock()
        # dict of configurable objects
        self._confobjs = {}
        self._confobjslock = threading.Lock()
        self._handlers = set()
        self._handlerslock = threading.Lock()
        self._state = None
        self._hooks = {}
        self._state_hooks = {}
        # dict of configuration items from /etc/core/core.conf config file
        self.cfg = cfg
        self.add_state_hook(coreapi.CORE_EVENT_RUNTIME_STATE,
                            self.runtime_state_hook)
        self.setstate(state=coreapi.CORE_EVENT_DEFINITION_STATE,
                      info=False, sendevent=False)
        self.server = server
        if not persistent:
            self.addsession(self)
        self.master = False
        self.broker = CoreBroker(session=self, verbose=True)
        self.location = CoreLocation(self)
        self.mobility = MobilityManager(self)
        self.services = CoreServices(self)
        self.emane = emane.Emane(self)
        self.xen = xenconfig.XenConfigManager(self)
        self.sdt = Sdt(self)
        # future parameters set by the GUI may go here
        self.options = SessionConfig(self)
        self.metadata = SessionMetaData(self)

    @classmethod
    def addsession(cls, session):
        cls.__sessions.add(session)

    @classmethod
    def delsession(cls, session):
        try:
            cls.__sessions.remove(session)
        except KeyError:
            pass

    @classmethod
    def atexit(cls):
        while cls.__sessions:
            s = cls.__sessions.pop()
            print >> sys.stderr, "WARNING: automatically shutting down " \
                "non-persistent session %s" % s.sessionid
            s.shutdown()

    def shutdown(self):
        ''' Shut down all emulation objects and remove the session directory.
        '''
        if hasattr(self, 'emane'):
            self.emane.shutdown()
        if hasattr(self, 'broker'):
            self.broker.shutdown()
        if hasattr(self, 'sdt'):
            self.sdt.shutdown()
        self.delobjs()
        preserve = False
        if hasattr(self.options, 'preservedir'):
            if self.options.preservedir == '1':
                preserve = True
        if not preserve:
            shutil.rmtree(self.sessiondir, ignore_errors = True)
        if self.server:
            self.server.delsession(self)
        self.delsession(self)

    def isconnected(self):
        ''' Returns true if this session has a request handler.
        '''
        with self._handlerslock:
            if len(self._handlers) == 0:
                return False
            else:
                return True

    def connect(self, handler):
        ''' Set the request handler for this session, making it connected.
        '''
        # the master flag will only be set after a GUI has connected with the
        # handler, e.g. not during normal startup
        if handler.master is True:
            self.master = True
        with self._handlerslock:
            self._handlers.add(handler)

    def disconnect(self, handler):
        ''' Disconnect a request handler from this session. Shutdown this
            session if there is no running emulation.
        '''
        with self._handlerslock:
            try:
                self._handlers.remove(handler)
            except KeyError:
                raise ValueError, \
                    "Handler %s not associated with this session" % handler
            num_handlers = len(self._handlers)
        if num_handlers == 0:
            # shut down this session unless we are instantiating, running,
            # or collecting final data
            if self.getstate() < coreapi.CORE_EVENT_INSTANTIATION_STATE or \
                    self.getstate() > coreapi.CORE_EVENT_DATACOLLECT_STATE:
                self.shutdown()

    def broadcast(self, src, msg):
        ''' Send Node and Link CORE API messages to all handlers connected to this session.
        '''
        self._handlerslock.acquire()
        for handler in self._handlers:
            if handler == src:
                continue
            if isinstance(msg, coreapi.CoreNodeMessage) or \
                    isinstance(msg, coreapi.CoreLinkMessage):
                try:
                    handler.sendall(msg.rawmsg)
                except Exception, e:
                    self.warn("sendall() error: %s" % e)
        self._handlerslock.release()

    def broadcastraw(self, src, data):
        ''' Broadcast raw data to all handlers except src.
        '''
        self._handlerslock.acquire()
        for handler in self._handlers:
            if handler == src:
                continue
            try:
                handler.sendall(data)
            except Exception, e:
                self.warn("sendall() error: %s" % e)
        self._handlerslock.release()

    def gethandler(self):
        ''' Get one of the connected handlers, preferrably the master.
        '''
        with self._handlerslock:
            if len(self._handlers) == 0:
                return None
            for handler in self._handlers:
                if handler.master:
                    return handler
            for handler in self._handlers:
                return handler

    def setstate(self, state, info = False, sendevent = False,
                 returnevent = False):
        ''' Set the session state. When info is true, log the state change
            event using the session handler's info method. When sendevent is
            true, generate a CORE API Event Message and send to the connected
            entity.
        '''
        if state == self._state:
            return []
        self._time = time.time()
        self._state = state
        self.run_state_hooks(state)
        replies = []
        if self.isconnected() and info:
            statename = coreapi.state_name(state)
            with self._handlerslock:
                for handler in self._handlers:
                    handler.info("SESSION %s STATE %d: %s at %s" % \
                                (self.sessionid, state, statename,
                                 time.ctime()))
        self.writestate(state)
        self.runhook(state)
        if sendevent:
            tlvdata = ""
            tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                                 state)
            msg = coreapi.CoreEventMessage.pack(0, tlvdata)
            # send Event Message to connected handlers (e.g. GUI)
            if self.isconnected():
                try:
                    if returnevent:
                        replies.append(msg)
                    else:
                        self.broadcastraw(None, msg)
                except Exception, e:
                    self.warn("Error sending Event Message: %s" % e)
            # also inform slave servers
            tmp = self.broker.handlerawmsg(msg)
        return replies


    def getstate(self):
        ''' Retrieve the current state of the session.
        '''
        return self._state

    def writestate(self, state):
        ''' Write the current state to a state file in the session dir.
        '''
        try:
            f = open(os.path.join(self.sessiondir, "state"), "w")
            f.write("%d %s\n" % (state, coreapi.state_name(state)))
            f.close()
        except Exception, e:
            self.warn("Error writing state file: %s" % e)

    def runhook(self, state, hooks=None):
        ''' Run hook scripts upon changing states.
        If hooks is not specified, run all hooks in the given state.
        '''
        if state not in self._hooks:
            return
        if hooks is None:
            hooks = self._hooks[state]
        for (filename, data) in hooks:
            try:
                f = open(os.path.join(self.sessiondir, filename), "w")
                f.write(data)
                f.close()
            except Exception, e:
                self.warn("Error writing hook '%s': %s" % (filename, e))
            self.info("Running hook %s for state %s" % (filename, state))
            try:
                check_call(["/bin/sh", filename], cwd=self.sessiondir,
                           env=self.getenviron())
            except Exception, e:
                self.warn("Error running hook '%s' for state %s: %s" %
                          (filename, state, e))

    def sethook(self, type, filename, srcname, data):
        ''' Store a hook from a received File Message.
        '''
        if srcname is not None:
            raise NotImplementedError
        (hookid, state) = type.split(':')[:2]
        if not state.isdigit():
            self.warn("Error setting hook having state '%s'" % state)
            return
        state = int(state)
        hook = (filename, data)
        if state not in self._hooks:
            self._hooks[state] = [hook,]
        else:
            self._hooks[state].append(hook)
        # immediately run a hook if it is in the current state
        # (this allows hooks in the definition and configuration states)
        if self.getstate() == state:
            self.runhook(state, hooks = [hook,])

    def delhooks(self):
        ''' Clear the hook scripts dict.
        '''
        self._hooks = {}

    def run_state_hooks(self, state):
        if state not in self._state_hooks:
            return
        for hook in self._state_hooks[state]:
            try:
                hook(state)
            except Exception, e:
                self.warn("ERROR: exception occured when running %s state "
                          "hook: %s: %s\n%s" % (coreapi.state_name(state),
                                                hook, e,
                                                traceback.format_exc()))

    def add_state_hook(self, state, hook):
        try:
            hooks = self._state_hooks[state]
            assert hook not in hooks
            hooks.append(hook)
        except KeyError:
            self._state_hooks[state] = [hook]
        if self._state == state:
            hook(state)

    def del_state_hook(self, state, hook):
        try:
            hooks = self._state_hooks[state]
            self._state_hooks[state] = filter(lambda x: x != hook, hooks)
        except KeyError:
            pass

    def runtime_state_hook(self, state):
        if state == coreapi.CORE_EVENT_RUNTIME_STATE:
            self.emane.poststartup()
            xmlfilever = self.getcfgitem('xmlfilever')
            if xmlfilever in ('1.0',):
                xmlfilename = os.path.join(self.sessiondir,
                                           'session-deployed.xml')
                savesessionxml(self, xmlfilename, xmlfilever)

    def getenviron(self, state=True):
        ''' Get an environment suitable for a subprocess.Popen call.
            This is the current process environment with some session-specific
            variables.
        '''
        env = os.environ.copy()
        env['SESSION'] = "%s" % self.sessionid
        env['SESSION_SHORT'] = "%s" % self.shortsessionid()
        env['SESSION_DIR'] = "%s" % self.sessiondir
        env['SESSION_NAME'] = "%s" % self.name
        env['SESSION_FILENAME'] = "%s" % self.filename
        env['SESSION_USER'] = "%s" % self.user
        env['SESSION_NODE_COUNT'] = "%s" % self.node_count
        if state:
            env['SESSION_STATE'] = "%s" % self.getstate()
        try:
            readfileintodict(os.path.join(CORE_CONF_DIR, "environment"), env)
        except IOError:
            pass
        if self.user:
            try:
                readfileintodict(os.path.join('/home', self.user, ".core",
                                 "environment"), env)
            except IOError:
                pass
        return env

    def setthumbnail(self, thumbfile):
        ''' Set the thumbnail filename. Move files from /tmp to session dir.
        '''
        if not os.path.exists(thumbfile):
            self.thumbnail = None
            return
        dstfile = os.path.join(self.sessiondir, os.path.basename(thumbfile))
        shutil.move(thumbfile, dstfile)
        #print "thumbnail: %s -> %s" % (thumbfile, dstfile)
        self.thumbnail = dstfile

    def setuser(self, user):
        ''' Set the username for this session. Update the permissions of the
            session dir to allow the user write access.
        '''
        if user is not None:
            try:
                uid = pwd.getpwnam(user).pw_uid
                gid = os.stat(self.sessiondir).st_gid
                os.chown(self.sessiondir, uid, gid)
            except Exception, e:
                self.warn("Failed to set permission on %s: %s" % (self.sessiondir, e))
        self.user = user

    def objs(self):
        ''' Return iterator over the emulation object dictionary.
        '''
        return self._objs.itervalues()

    def getobjid(self):
        ''' Return a unique, random object id.
        '''
        self._objslock.acquire()
        while True:
            id = random.randint(1, 0xFFFF)
            if id not in self._objs:
                break
        self._objslock.release()
        return id

    def addobj(self, cls, *clsargs, **clskwds):
        ''' Add an emulation object.
        '''
        obj = cls(self, *clsargs, **clskwds)
        self._objslock.acquire()
        if obj.objid in self._objs:
            self._objslock.release()
            obj.shutdown()
            raise KeyError, "non-unique object id %s for %s" % (obj.objid, obj)
        self._objs[obj.objid] = obj
        self._objslock.release()
        return obj

    def obj(self, objid):
        ''' Get an emulation object.
        '''
        if objid not in self._objs:
            raise KeyError, "unknown object id %s" % (objid)
        return self._objs[objid]

    def objbyname(self, name):
        ''' Get an emulation object using its name attribute.
        '''
        with self._objslock:
            for obj in self.objs():
                if hasattr(obj, "name") and obj.name == name:
                    return obj
        raise KeyError, "unknown object with name %s" % (name)

    def delobj(self, objid):
        ''' Remove an emulation object.
        '''
        self._objslock.acquire()
        try:
            o = self._objs.pop(objid)
        except KeyError:
            o = None
        self._objslock.release()
        if o:
            o.shutdown()
            del o
        gc.collect()
#         print "gc count:", gc.get_count()
#         for o in gc.get_objects():
#             if isinstance(o, PyCoreObj):
#                 print "XXX XXX XXX PyCoreObj:", o
#                 for r in gc.get_referrers(o):
#                     print "XXX XXX XXX referrer:", gc.get_referrers(o)

    def delobjs(self):
        ''' Clear the _objs dictionary, and call each obj.shutdown() routine.
        '''
        self._objslock.acquire()
        while self._objs:
            k, o = self._objs.popitem()
            o.shutdown()
        self._objslock.release()

    def writeobjs(self):
        ''' Write objects to a 'nodes' file in the session dir.
            The 'nodes' file lists:
                number, name, api-type, class-type
        '''
        try:
            f = open(os.path.join(self.sessiondir, "nodes"), "w")
            with self._objslock:
                for objid in sorted(self._objs.keys()):
                    o = self._objs[objid]
                    f.write("%s %s %s %s\n" % (objid, o.name, o.apitype, type(o)))
            f.close()
        except Exception, e:
            self.warn("Error writing nodes file: %s" % e)

    def addconfobj(self, objname, type, callback):
        ''' Objects can register configuration objects that are included in
            the Register Message and may be configured via the Configure
            Message. The callback is invoked when receiving a Configure Message.
        '''
        if type not in coreapi.reg_tlvs:
            raise Exception, "invalid configuration object type"
        self._confobjslock.acquire()
        self._confobjs[objname] = (type, callback)
        self._confobjslock.release()

    def confobj(self, objname, session, msg):
        ''' Invoke the callback for an object upon receipt of a Configure
            Message for that object. A no-op if the object doesn't exist.
        '''
        replies = []
        self._confobjslock.acquire()
        if objname == "all":
            for objname in self._confobjs:
                (type, callback) = self._confobjs[objname]
                reply = callback(session, msg)
                if reply is not None:
                    replies.append(reply)
            self._confobjslock.release()
            return replies
        if objname in self._confobjs:
            (type, callback) = self._confobjs[objname]
            self._confobjslock.release()
            reply = callback(session, msg)
            if reply is not None:
                replies.append(reply)
            return replies
        else:
            self.info("session object doesn't own model '%s', ignoring" % \
                      objname)
        self._confobjslock.release()
        return replies

    def confobjs_to_tlvs(self):
        ''' Turn the configuration objects into a list of Register Message TLVs.
        '''
        tlvdata = ""
        self._confobjslock.acquire()
        for objname in self._confobjs:
            (type, callback) = self._confobjs[objname]
            # type must be in coreapi.reg_tlvs
            tlvdata += coreapi.CoreRegTlv.pack(type, objname)
        self._confobjslock.release()
        return tlvdata

    def info(self, msg):
        ''' Utility method for writing output to stdout.
        '''
        print msg
        sys.stdout.flush()

    def warn(self, msg):
        ''' Utility method for writing output to stderr.
        '''
        print >> sys.stderr, msg
        sys.stderr.flush()

    def dumpsession(self):
        ''' Debug print this session.
        '''
        self.info("session id=%s name=%s state=%s connected=%s" % \
                  (self.sessionid, self.name, self._state, self.isconnected()))
        num = len(self._objs)
        self.info("        file=%s thumb=%s nc=%s/%s" % \
                  (self.filename, self.thumbnail, self.node_count, num))

    def exception(self, level, source, objid, text):
        ''' Generate an Exception Message
        '''
        vals = (objid, str(self.sessionid), level, source, time.ctime(), text)
        types = ("NODE", "SESSION", "LEVEL", "SOURCE", "DATE", "TEXT")
        tlvdata = ""
        for (t,v) in zip(types, vals):
            if v is not None:
                tlvdata += coreapi.CoreExceptionTlv.pack(
                                    eval("coreapi.CORE_TLV_EXCP_%s" % t), v)
        msg = coreapi.CoreExceptionMessage.pack(0, tlvdata)
        self.warn("exception: %s (%s) %s" % (source, objid, text))
        # send Exception Message to connected handlers (e.g. GUI)
        self.broadcastraw(None, msg)

    def getcfgitem(self, cfgname):
        ''' Return an entry from the configuration dictionary that comes from
            command-line arguments and/or the core.conf config file.
        '''
        if cfgname not in self.cfg:
            return None
        else:
            return self.cfg[cfgname]

    def getcfgitembool(self, cfgname, defaultifnone = None):
        ''' Return a boolean entry from the configuration dictionary, may
            return None if undefined.
        '''
        item = self.getcfgitem(cfgname)
        if item is None:
            return defaultifnone
        return bool(item.lower() == "true")

    def getcfgitemint(self, cfgname, defaultifnone = None):
        ''' Return an integer entry from the configuration dictionary, may
            return None if undefined.
        '''
        item = self.getcfgitem(cfgname)
        if item is None:
            return defaultifnone
        return int(item)

    def instantiate(self, handler=None):
        ''' We have entered the instantiation state, invoke startup methods
            of various managers and boot the nodes. Validate nodes and check
            for transition to the runtime state.
        '''
        
        self.writeobjs()
        # controlnet may be needed by some EMANE models
        self.addremovectrlif(node=None, remove=False)
        if self.emane.startup() == self.emane.NOT_READY:
            return # instantiate() will be invoked again upon Emane.configure()
        self.broker.startup()
        self.mobility.startup()
        # boot the services on each node
        self.bootnodes(handler)
        # allow time for processes to start
        time.sleep(0.125)
        self.validatenodes()
        # assume either all nodes have booted already, or there are some
        # nodes on slave servers that will be booted and those servers will
        # send a node status response message
        self.checkruntime()

    def getnodecount(self):
        ''' Returns the number of CoreNodes and CoreNets, except for those
        that are not considered in the GUI's node count.
        '''

        with self._objslock:
            count = len(filter(lambda(x): \
                               not isinstance(x, (nodes.PtpNet, nodes.CtrlNet)),
                               self.objs()))
            # on Linux, GreTapBridges are auto-created, not part of
            # GUI's node count
            if 'GreTapBridge' in globals():
                count -= len(filter(lambda(x): \
                                    isinstance(x, GreTapBridge) and not \
                                    isinstance(x, nodes.TunnelNode),
                                    self.objs()))
        return count

    def checkruntime(self):
        ''' Check if we have entered the runtime state, that all nodes have been
            started and the emulation is running. Start the event loop once we
            have entered runtime (time=0).
        '''
        # this is called from instantiate() after receiving an event message
        # for the instantiation state, and from the broker when distributed
        # nodes have been started
        if self.node_count is None:
            return
        if self.getstate() == coreapi.CORE_EVENT_RUNTIME_STATE:
            return
        session_node_count = int(self.node_count)
        nc = self.getnodecount()
        # count booted nodes not emulated on this server
        # TODO: let slave server determine RUNTIME and wait for Event Message
        # broker.getbootocunt() counts all CoreNodes from status reponse
        #  messages, plus any remote WLANs; remote EMANE, hub, switch, etc.
        #  are already counted in self._objs
        nc += self.broker.getbootcount()
        self.info("Checking for runtime with %d of %d session nodes" % \
                    (nc, session_node_count))
        if nc < session_node_count:
            return # do not have information on all nodes yet
        # information on all nodes has been received and they have been started
        # enter the runtime state
        # TODO: more sophisticated checks to verify that all nodes and networks
        #       are running
        state = coreapi.CORE_EVENT_RUNTIME_STATE
        self.evq.run()
        self.setstate(state, info=True, sendevent=True)

    def datacollect(self):
        ''' Tear down a running session. Stop the event loop and any running
            nodes, and perform clean-up.
        '''
        self.evq.stop()
        with self._objslock:
            for obj in self.objs():
                if isinstance(obj, nodes.PyCoreNode):
                    self.services.stopnodeservices(obj)
        self.emane.shutdown()
        self.updatectrlifhosts(remove=True)
        # Remove all four possible control networks. Does nothing if ctrlnet is not installed.
        self.addremovectrlif(node=None, remove=True)
        self.addremovectrlif(node=None, netidx=1, remove=True)
        self.addremovectrlif(node=None, netidx=2, remove=True)
        self.addremovectrlif(node=None, netidx=3, remove=True)

        # self.checkshutdown() is currently invoked from node delete handler

    def checkshutdown(self):
        ''' Check if we have entered the shutdown state, when no running nodes
            and links remain.
        '''
        nc = self.getnodecount()
        # TODO: this doesn't consider slave server node counts
        # wait for slave servers to enter SHUTDOWN state, then master session
        # can enter SHUTDOWN
        replies = ()
        if self.getcfgitembool('verbose', False):
            self.info("Session %d shutdown: %d nodes remaining" % \
                      (self.sessionid, nc))
        if nc == 0:
            replies = self.setstate(state=coreapi.CORE_EVENT_SHUTDOWN_STATE,
                                    info=True, sendevent=True, returnevent=True)
            self.sdt.shutdown()
        return replies

    def setmaster(self, handler):
        ''' Look for the specified handler and set our master flag
            appropriately. Returns True if we are connected to the given
            handler.
        '''
        with self._handlerslock:
            for h in self._handlers:
                if h != handler:
                    continue
                self.master = h.master
                return True
        return False

    def shortsessionid(self):
        ''' Return a shorter version of the session ID, appropriate for
            interface names, where length may be limited.
        '''
        ssid = (self.sessionid >> 8) ^ (self.sessionid & ((1 << 8) - 1))
        return "%x" % ssid

    def sendnodeemuid(self, handler, nodenum):
        ''' Send back node messages to the GUI for node messages that had
            the status request flag.
        '''
        if handler is None:
            return
        if nodenum in handler.nodestatusreq:
            tlvdata = ""
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_NUMBER,
                                                nodenum)
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_EMUID,
                                                nodenum)
            reply = coreapi.CoreNodeMessage.pack(coreapi.CORE_API_ADD_FLAG \
                                               | coreapi.CORE_API_LOC_FLAG,
                                                 tlvdata)
            try:
                handler.request.sendall(reply)
            except Exception, e:
                self.warn("sendall() for node: %d error: %s" % (nodenum, e))
            del handler.nodestatusreq[nodenum]

    def bootnodes(self, handler):
        ''' Invoke the boot() procedure for all nodes and send back node
            messages to the GUI for node messages that had the status
            request flag.
        '''
        with self._objslock:
            for n in self.objs():
                if isinstance(n, nodes.PyCoreNode) and \
                  not isinstance(n, nodes.RJ45Node):
                    # add a control interface if configured
                    self.addremovectrlif(node=n, remove=False)
                    n.boot()
                self.sendnodeemuid(handler, n.objid)
        self.updatectrlifhosts()

    def validatenodes(self):
        with self._objslock:
            for n in self.objs():
                # TODO: this can be extended to validate everything
                # such as vnoded process, bridges, etc.
                if not isinstance(n, nodes.PyCoreNode):
                    continue
                if isinstance(n, nodes.RJ45Node):
                    continue
                n.validate()

    def getctrlnetprefixes(self):
        p = getattr(self.options, 'controlnet', self.cfg.get('controlnet'))
        p0 = getattr(self.options, 'controlnet0', self.cfg.get('controlnet0'))
        p1 = getattr(self.options, 'controlnet1', self.cfg.get('controlnet1'))
        p2 = getattr(self.options, 'controlnet2', self.cfg.get('controlnet2'))
        p3 = getattr(self.options, 'controlnet3', self.cfg.get('controlnet3'))
        if not p0 and p:
            p0 = p
        return [p0,p1,p2,p3]
        

    def getctrlnetserverintf(self):
        d0 = self.cfg.get('controlnetif0')
        if d0:
            self.warn("controlnet0 cannot be assigned with a host interface")
        d1 = self.cfg.get('controlnetif1')
        d2 = self.cfg.get('controlnetif2')
        d3 = self.cfg.get('controlnetif3')
        return [None,d1,d2,d3]
    
    def getctrlnetidx(self, dev):
        if dev[0:4] == 'ctrl' and int(dev[4]) in [0,1,2,3]:
            idx = int(dev[4])
            if idx == 0:
                return idx
            if idx < 4 and self.getctrlnetprefixes()[idx] is not None:
                return idx
        return -1
        

    def getctrlnetobj(self, netidx):
        oid = "ctrl%dnet" % netidx
        return self.obj(oid)
    

    def addremovectrlnet(self, netidx, remove=False, conf_reqd=True):
        ''' Create a control network bridge as necessary.
        When the remove flag is True, remove the bridge that connects control
        interfaces. The conf_reqd flag, when False, causes a control network
        bridge to be added even if one has not been configured.
        '''
        prefixspeclist = self.getctrlnetprefixes()
        prefixspec = prefixspeclist[netidx]
        if not prefixspec:
            if conf_reqd:
                return None  # no controlnet needed
            else:
                prefixspec = nodes.CtrlNet.DEFAULT_PREFIX_LIST[netidx]
                
        serverintf = self.getctrlnetserverintf()[netidx]

        # return any existing controlnet bridge
        try:
            ctrlnet = self.getctrlnetobj(netidx)
            if remove:
                self.delobj(ctrlnet.objid)
                return None
            return ctrlnet
        except KeyError:
            if remove:
                return None

        # build a new controlnet bridge
        oid = "ctrl%dnet" % netidx

        # use the updown script for control net 0 only.
        updown_script = None
        if netidx == 0:
            try:
                if self.cfg['controlnet_updown_script']:
                    updown_script = self.cfg['controlnet_updown_script']
            except KeyError:
                pass
            # Check if session option set, overwrite if so
            if hasattr(self.options, 'controlnet_updown_script'):
                new_uds = self.options.controlnet_updown_script
            if new_uds:
                updown_script = new_uds
                

        prefixes = prefixspec.split()
        if len(prefixes) > 1: 
            # A list of per-host prefixes is provided
            assign_address = True
            if self.master:
                try:
                    # split first (master) entry into server and prefix
                    prefix = prefixes[0].split(':', 1)[1]
                except IndexError:
                    # no server name. possibly only one server
                    prefix = prefixes[0] 
            else:
                # slave servers have their name and localhost in the serverlist
                servers = self.broker.getserverlist()
                servers.remove('localhost')
                prefix = None
                for server_prefix in prefixes:
                    try:
                        # split each entry into server and prefix
                        server, p = server_prefix.split(':')
                    except ValueError:
                        server = ""
                        p = None
                        
                    if server == servers[0]:
                        # the server name in the list matches this server
                        prefix = p
                        break
                if not prefix:
                    msg = "Control network prefix not found for server '%s'" % \
                            servers[0]
                    self.exception(coreapi.CORE_EXCP_LEVEL_ERROR,
                                   "Session.addremovectrlnet()", None, msg)
                    assign_address = False
                    try:
                        prefix = prefixes[0].split(':', 1)[1]
                    except IndexError:
                        prefix = prefixes[0]
        else: # len(prefixes) == 1 
            # TODO: can we get the server name from the servers.conf or from the node assignments?
            # with one prefix, only master gets a ctrlnet address
            assign_address = self.master
            prefix = prefixes[0]

        ctrlnet = self.addobj(cls=nodes.CtrlNet, objid=oid, prefix=prefix, 
                              assign_address=assign_address,
                              updown_script=updown_script, serverintf=serverintf)

        # tunnels between controlnets will be built with Broker.addnettunnels()
        self.broker.addnet(oid)
        for server in self.broker.getserverlist():
            self.broker.addnodemap(server, oid)
        
        return ctrlnet

    def addremovectrlif(self, node, netidx=0,  remove=False, conf_reqd=True):
        ''' Add a control interface to a node when a 'controlnet' prefix is
            listed in the config file or session options. Uses
            addremovectrlnet() to build or remove the control bridge.
            If conf_reqd is False, the control network may be built even
            when the user has not configured one (e.g. for EMANE.)
        '''
        ctrlnet = self.addremovectrlnet(netidx, remove, conf_reqd)
        if ctrlnet is None:
            return
        if node is None:
            return
        if node.netif(ctrlnet.CTRLIF_IDX_BASE + netidx):
            return  # ctrl# already exists
        ctrlip = node.objid
        try:
            addrlist = ["%s/%s" % (ctrlnet.prefix.addr(ctrlip),
                                   ctrlnet.prefix.prefixlen)]
        except ValueError:
            msg = "Control interface not added to node %s. " % node.objid
            msg += "Invalid control network prefix (%s). " % ctrlnet.prefix
            msg += "A longer prefix length may be required for this many nodes."
            node.exception(coreapi.CORE_EXCP_LEVEL_ERROR,
                           "Session.addremovectrlif()", msg)
            return
        ifi = node.newnetif(net = ctrlnet, ifindex = ctrlnet.CTRLIF_IDX_BASE + netidx,
                            ifname = "ctrl%d" % netidx, hwaddr = MacAddr.random(),
                            addrlist = addrlist)
        node.netif(ifi).control = True

    def updatectrlifhosts(self, netidx=0, remove=False):
        ''' Add the IP addresses of control interfaces to the /etc/hosts file.
        '''
        if not self.getcfgitembool('update_etc_hosts', False):
            return
        
        try:
            ctrlnet = self.getctrlnetobj(netidx)
        except KeyError:
            return
        header = "CORE session %s host entries" % self.sessionid
        if remove:
            if self.getcfgitembool('verbose', False):
                self.info("Removing /etc/hosts file entries.")
            filedemunge('/etc/hosts', header)
            return
        entries = []
        for ifc in ctrlnet.netifs():
            name = ifc.node.name
            for addr in ifc.addrlist:
                entries.append("%s %s" % (addr.split('/')[0], ifc.node.name))
        if self.getcfgitembool('verbose', False):
            self.info("Adding %d /etc/hosts file entries." % len(entries))
        filemunge('/etc/hosts', header, '\n'.join(entries) + '\n')

    def runtime(self):
        ''' Return the current time we have been in the runtime state, or zero
            if not in runtime.
        '''
        if self.getstate() == coreapi.CORE_EVENT_RUNTIME_STATE:
            return time.time() - self._time
        else:
            return 0.0

    def addevent(self, etime, node=None, name=None, data=None):
        ''' Add an event to the event queue, with a start time relative to the
            start of the runtime state.
        '''
        etime = float(etime)
        runtime = self.runtime()
        if runtime > 0.0:
            if time <= runtime:
                self.warn("Could not schedule past event for time %s " \
                          "(run time is now %s)" % (time, runtime))
                return
            etime = etime - runtime
        func = self.runevent
        self.evq.add_event(etime, func, node=node, name=name, data=data)
        if name is None:
            name = ""
        self.info("scheduled event %s at time %s data=%s" % \
                  (name, etime + runtime, data))

    def runevent(self, node=None, name=None, data=None):
        ''' Run a scheduled event, executing commands in the data string.
        '''
        now = self.runtime()
        if name is None:
            name = ""
        self.info("running event %s at time %s cmd=%s" % (name, now, data))
        if node is None:
            mutedetach(shlex.split(data))
        else:
            n = self.obj(node)
            n.cmd(shlex.split(data), wait=False)

    def sendobjs(self):
        ''' Return API messages that describe the current session.
        '''
        replies = []
        nn = 0
        # send node messages for node and network objects
        with self._objslock:
            for obj in self.objs():
                msg = obj.tonodemsg(flags = coreapi.CORE_API_ADD_FLAG)
                if msg is not None:
                    replies.append(msg)
                    nn += 1

        nl = 0
        # send link messages from net objects
        with self._objslock:
            for obj in self.objs():
                linkmsgs = obj.tolinkmsgs(flags = coreapi.CORE_API_ADD_FLAG)
                for msg in linkmsgs:
                    replies.append(msg)
                    nl += 1
        # send model info
        configs = self.mobility.getallconfigs()
        configs += self.emane.getallconfigs()
        for (nodenum, cls, values) in configs:
            #cls = self.mobility._modelclsmap[conftype]
            msg = cls.toconfmsg(flags=0, nodenum=nodenum,
                                typeflags=coreapi.CONF_TYPE_FLAGS_UPDATE,
                                values=values)
            replies.append(msg)
        # service customizations
        svc_configs = self.services.getallconfigs()
        for (nodenum, svc) in svc_configs:
            opaque = "service:%s" % svc._name
            tlvdata = ""
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_NODE,
                                                nodenum)
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_OPAQUE,
                                                opaque)
            tmp = coreapi.CoreConfMessage(flags=0, hdr="", data=tlvdata)
            replies.append(self.services.configure_request(tmp))
            for (filename, data) in self.services.getallfiles(svc):
                flags = coreapi.CORE_API_ADD_FLAG
                tlvdata = coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_NODE,
                                                   nodenum)
                tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_NAME,
                                                    str(filename))
                tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_TYPE,
                                                    opaque)
                tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_DATA,
                                                    str(data))
                replies.append(coreapi.CoreFileMessage.pack(flags, tlvdata))

        # TODO: send location info
        # replies.append(self.location.toconfmsg())
        # send hook scripts
        for state in sorted(self._hooks.keys()):
            for (filename, data) in self._hooks[state]:
                flags = coreapi.CORE_API_ADD_FLAG
                tlvdata = coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_NAME,
                                                    str(filename))
                tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_TYPE,
                                                    "hook:%s" % state)
                tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_DATA,
                                                    str(data))
                replies.append(coreapi.CoreFileMessage.pack(flags, tlvdata))

        # send meta data
        tmp = coreapi.CoreConfMessage(flags=0, hdr="", data="")
        opts = self.options.configure_request(tmp,
                                    typeflags = coreapi.CONF_TYPE_FLAGS_UPDATE)
        if opts:
            replies.append(opts)
        meta = self.metadata.configure_request(tmp,
                                    typeflags = coreapi.CONF_TYPE_FLAGS_UPDATE)
        if meta:
            replies.append(meta)

        self.info("informing GUI about %d nodes and %d links" % (nn, nl))
        return replies



class SessionConfig(ConfigurableManager, Configurable):
    _name = 'session'
    _type = coreapi.CORE_TLV_REG_UTILITY
    _confmatrix = [
        ("controlnet", coreapi.CONF_DATA_TYPE_STRING, '', '',
         'Control network'),
        ("controlnet_updown_script", coreapi.CONF_DATA_TYPE_STRING, '', '',
         'Control network script'),
        ("enablerj45", coreapi.CONF_DATA_TYPE_BOOL, '1', 'On,Off',
         'Enable RJ45s'),
        ("preservedir", coreapi.CONF_DATA_TYPE_BOOL, '0', 'On,Off',
         'Preserve session dir'),
        ("enablesdt", coreapi.CONF_DATA_TYPE_BOOL, '0', 'On,Off',
         'Enable SDT3D output'),
        ("sdturl", coreapi.CONF_DATA_TYPE_STRING, Sdt.DEFAULT_SDT_URL, '',
         'SDT3D URL'),
        ]
    _confgroups = "Options:1-%d" % len(_confmatrix)

    def __init__(self, session):
        ConfigurableManager.__init__(self, session)
        session.broker.handlers += (self.handledistributed, )
        self.reset()

    def reset(self):
        defaults = self.getdefaultvalues()
        for k in self.getnames():
            # value may come from config file
            v = self.session.getcfgitem(k)
            if v is None:
                v = self.valueof(k, defaults)
                v = self.offontobool(v)
            setattr(self, k, v)

    def configure_values(self, msg, values):
        return self.configure_values_keyvalues(msg, values, self,
                                               self.getnames())

    def configure_request(self, msg, typeflags = coreapi.CONF_TYPE_FLAGS_NONE):
        nodenum = msg.gettlv(coreapi.CORE_TLV_CONF_NODE)
        values = []
        for k in self.getnames():
            v = getattr(self, k)
            if v is None:
                v = ""
            values.append("%s" % v)
        return self.toconfmsg(0, nodenum, typeflags, values)

    def handledistributed(self, msg):
        ''' Handle the session options config message as it has reached the
        broker. Options requiring modification for distributed operation should
        be handled here.
        '''
        if not self.session.master:
            return
        if msg.msgtype != coreapi.CORE_API_CONF_MSG or \
           msg.gettlv(coreapi.CORE_TLV_CONF_OBJ) != "session":
            return
        values_str = msg.gettlv(coreapi.CORE_TLV_CONF_VALUES)
        if values_str is None:
            return
        values = values_str.split('|')
        if not self.haskeyvalues(values):
            return
        for v in values:
            key, value = v.split('=', 1)
            if key == "controlnet":
                self.handledistributedcontrolnet(msg, values, values.index(v))

    def handledistributedcontrolnet(self, msg, values, idx):
        ''' Modify Config Message if multiple control network prefixes are
        defined. Map server names to prefixes and repack the message before
        it is forwarded to slave servers.
        '''
        kv = values[idx]
        key, value = kv.split('=', 1)
        controlnets = value.split()
        if len(controlnets) < 2:
            return # multiple controlnet prefixes do not exist
        servers = self.session.broker.getserverlist()
        if len(servers) < 2:
            return # not distributed
        servers.remove("localhost")
        servers.insert(0, "localhost") # master always gets first prefix
        # create list of "server1:ctrlnet1 server2:ctrlnet2 ..."
        controlnets = map(lambda(x): "%s:%s" % (x[0],x[1]),
                          zip(servers, controlnets))
        values[idx] = "controlnet=%s" % (' '.join(controlnets))
        values_str = '|'.join(values)
        msg.tlvdata[coreapi.CORE_TLV_CONF_VALUES] = values_str
        msg.repack()


class SessionMetaData(ConfigurableManager):
    ''' Metadata is simply stored in a configs[] dict. Key=value pairs are
    passed in from configure messages destined to the "metadata" object.
    The data is not otherwise interpreted or processed.
    '''
    _name = "metadata"
    _type = coreapi.CORE_TLV_REG_UTILITY

    def configure_values(self, msg, values):
        if values is None:
            return None
        kvs = values.split('|')
        for kv in kvs:
            try:
                (key, value) = kv.split('=', 1)
            except ValueError:
                raise ValueError, "invalid key in metdata: %s" % kv
            self.additem(key, value)
        return None

    def configure_request(self, msg, typeflags = coreapi.CONF_TYPE_FLAGS_NONE):
        nodenum = msg.gettlv(coreapi.CORE_TLV_CONF_NODE)
        values_str = "|".join(map(lambda(k,v): "%s=%s" % (k,v), self.items()))
        return self.toconfmsg(0, nodenum, typeflags, values_str)

    def toconfmsg(self, flags, nodenum, typeflags, values_str):
        tlvdata = ""
        if nodenum is not None:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_NODE,
                                                nodenum)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_OBJ,
                                            self._name)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_TYPE,
                                            typeflags)
        datatypes = tuple( map(lambda(k,v): coreapi.CONF_DATA_TYPE_STRING,
                               self.items()) )
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_DATA_TYPES,
                                            datatypes)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_VALUES,
                                            values_str)
        msg = coreapi.CoreConfMessage.pack(flags, tlvdata)
        return msg

    def additem(self, key, value):
        self.configs[key] = value

    def items(self):
        return self.configs.iteritems()

atexit.register(Session.atexit)
