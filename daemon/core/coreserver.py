#!/usr/bin/env python
#
# CORE
# Copyright (c)2010-2016 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#          Rod Santiago
#

import sys
import os
import gc
import shlex
import shutil
import threading
import time
import traceback
import SocketServer

from core import pycore
from core.api import coreapi
from core.misc.utils import hexdump, cmdresult, mutedetach, closeonexec
from core.misc.xmlsession import opensessionxml, savesessionxml


'''
Defines server classes and request handlers for TCP and UDP. Also defined here is a TCP based auxiliary server class for supporting externally defined handlers.
'''



class CoreServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    ''' TCP server class, manages sessions and spawns request handlers for
        incoming connections.
    '''
    daemon_threads = True
    allow_reuse_address = True
    servers = set()

    def __init__(self, server_address, RequestHandlerClass, cfg = None):
        ''' Server class initialization takes configuration data and calls
            the SocketServer constructor
        '''
        self.cfg = cfg
        self._sessions = {}
        self._sessionslock = threading.Lock()
        self.newserver(self)
        SocketServer.TCPServer.__init__(self, server_address,
                                        RequestHandlerClass)

    @classmethod
    def newserver(cls, server):
        cls.servers.add(server)

    @classmethod
    def delserver(cls, server):
        try:
            cls.servers.remove(server)
        except KeyError:
            pass

    def shutdown(self):
        for session in self._sessions.values():
            session.shutdown()
        if self.cfg['daemonize']:
            pidfilename = self.cfg['pidfile']
            try:
                os.unlink(pidfilename)
            except OSError:
                pass
        self.delserver(self)

    def addsession(self, session):
        ''' Add a session to our dictionary of sessions, ensuring a unique
            session number
        '''
        self._sessionslock.acquire()
        try:
            if session.sessionid in self._sessions:
                raise KeyError, "non-unique session id %s for %s" % \
                    (session.sessionid, session)
            self._sessions[session.sessionid] = session
        finally:
            self._sessionslock.release()
        return session

    def delsession(self, session):
        ''' Remove a session from our dictionary of sessions.
        '''
        with self._sessionslock:
            if session.sessionid not in self._sessions:
                print "session id %s not found (sessions=%s)" % \
                    (session.sessionid, self._sessions.keys())
            else:
                del(self._sessions[session.sessionid])
        return session
        
    def getsessionids(self):
        ''' Return a list of active session numbers.
        '''
        with self._sessionslock:
            sids = self._sessions.keys()
        return sids

    def getsession(self, sessionid = None, useexisting = True):
        ''' Create a new session or retrieve an existing one from our
            dictionary of sessions. When the sessionid=0 and the useexisting
            flag is set, return on of the existing sessions.
        '''
        if not useexisting:
            session = pycore.Session(sessionid, cfg = self.cfg, server = self)
            self.addsession(session)
            return session

        with self._sessionslock:
            # look for the specified session id
            if sessionid in self._sessions:
                session = self._sessions[sessionid]
            else:
                session = None
                # pick an existing session
                if sessionid == 0:
                    for s in self._sessions.itervalues():
                        if s.getstate() == coreapi.CORE_EVENT_RUNTIME_STATE:
                            if session is None:
                                session = s
                            elif s.node_count > session.node_count:
                                session = s
                    if session is None:
                        for s in self._sessions.itervalues():
                            session = s
                            break
        return session

    def tosessionmsg(self, flags = 0):
        ''' Build CORE API Sessions message based on current session info.
        '''
        idlist = []
        namelist = []
        filelist = []
        nclist = []
        datelist = []
        thumblist = []
        num_sessions = 0

        with self._sessionslock:
            for sessionid in self._sessions:
                session = self._sessions[sessionid]
                # debug: session.dumpsession()
                num_sessions += 1
                idlist.append(str(sessionid))
                name = session.name
                if name is None:
                    name = ""
                namelist.append(name)
                file = session.filename
                if file is None:
                    file = ""
                filelist.append(file)
                nc = session.node_count
                if nc is None:
                    nc = ""
                nclist.append(str(nc))
                datelist.append(time.ctime(session._time))
                thumb = session.thumbnail
                if thumb is None:
                    thumb = ""
                thumblist.append(thumb)
        sids = "|".join(idlist)
        names = "|".join(namelist)
        files = "|".join(filelist)
        ncs = "|".join(nclist)
        dates = "|".join(datelist)
        thumbs = "|".join(thumblist)

        if num_sessions > 0:
            tlvdata = ""
            if len(sids) > 0:
                tlvdata += coreapi.CoreSessionTlv.pack( \
                                        coreapi.CORE_TLV_SESS_NUMBER, sids)
            if len(names) > 0:
                tlvdata += coreapi.CoreSessionTlv.pack( \
                                        coreapi.CORE_TLV_SESS_NAME, names)
            if len(files) > 0:
                tlvdata += coreapi.CoreSessionTlv.pack( \
                                        coreapi.CORE_TLV_SESS_FILE, files)
            if len(ncs) > 0:
                tlvdata += coreapi.CoreSessionTlv.pack( \
                                        coreapi.CORE_TLV_SESS_NODECOUNT, ncs)
            if len(dates) > 0:
                tlvdata += coreapi.CoreSessionTlv.pack( \
                                        coreapi.CORE_TLV_SESS_DATE, dates)
            if len(thumbs) > 0:
                tlvdata += coreapi.CoreSessionTlv.pack( \
                                        coreapi.CORE_TLV_SESS_THUMB, thumbs)
            msg = coreapi.CoreSessionMessage.pack(flags, tlvdata)
        else:
            msg = None
        return(msg)

    def dumpsessions(self):
        ''' Debug print all session info.
        '''
        print "sessions:"
        self._sessionslock.acquire()
        try:
            for sessionid in self._sessions:
                print sessionid,
        finally:
            self._sessionslock.release()
        print ""
        sys.stdout.flush()

    def setsessionmaster(self, handler):
        ''' Call the setmaster() method for every session. Returns True when
            a session having the given handler was updated.
        '''
        found = False
        self._sessionslock.acquire()
        try:
            for sessionid in self._sessions:
                found = self._sessions[sessionid].setmaster(handler)
                if found is True:
                    break
        finally:
            self._sessionslock.release()
        return found


class CoreUdpServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
    ''' UDP server class, manages sessions and spawns request handlers for
        incoming connections.
    '''
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, mainserver):
        ''' Server class initialization takes configuration data and calls
            the SocketServer constructor
        '''
        self.mainserver = mainserver
        SocketServer.UDPServer.__init__(self, server_address,
                                        RequestHandlerClass)
                                        
    def start(self):
        ''' Thread target to run concurrently with the TCP server.
        '''
        self.serve_forever()
        



class CoreAuxServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    ''' An auxiliary TCP server.
    '''
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, mainserver):
        self.mainserver = mainserver
        sys.stdout.write("auxiliary server started, listening on: %s:%s\n" % server_address)
        sys.stdout.flush()
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)

    def start(self):
        self.serve_forever()

    def setsessionmaster(self, handler):
        return self.mainserver.setsessionmaster(handler)

    def getsession(self, sessionid = None, useexisting = True):
        return self.mainserver.getsession(sessionid, useexisting)

    def tosessionmsg(self, flags = 0):
        return self.mainserver.tosessionmsg(flags)






class CoreRequestHandler(SocketServer.BaseRequestHandler):
    ''' The SocketServer class uses the RequestHandler class for servicing
    requests, mainly through the handle() method. The CoreRequestHandler
    has the following basic flow:
       1. Client connects and request comes in via handle().
       2. handle() calls recvmsg() in a loop.
       3. recvmsg() does a recv() call on the socket performs basic
          checks that this we received a CoreMessage, returning it.
       4. The message data is queued using queuemsg().
       5. The handlerthread() thread pops messages from the queue and uses
          handlemsg() to invoke the appropriate handler for that message type.
       
    '''

    maxmsgqueuedtimes = 8

    def __init__(self, request, client_address, server):
        self.done = False
        self.msghandler = {
            coreapi.CORE_API_NODE_MSG: self.handlenodemsg,
            coreapi.CORE_API_LINK_MSG: self.handlelinkmsg,
            coreapi.CORE_API_EXEC_MSG: self.handleexecmsg,
            coreapi.CORE_API_REG_MSG: self.handleregmsg,
            coreapi.CORE_API_CONF_MSG: self.handleconfmsg,
            coreapi.CORE_API_FILE_MSG: self.handlefilemsg,
            coreapi.CORE_API_IFACE_MSG: self.handleifacemsg,
            coreapi.CORE_API_EVENT_MSG: self.handleeventmsg,
            coreapi.CORE_API_SESS_MSG: self.handlesessionmsg,
        }
        self.msgq = []
        self.msgcv = threading.Condition()
        self.nodestatusreq = {}
        numthreads = int(server.cfg['numthreads'])
        if numthreads < 1:
            raise ValueError, \
                  "invalid number of threads: %s" % numthreads
        self.handlerthreads = []
        while numthreads:
            t = threading.Thread(target = self.handlerthread)
            self.handlerthreads.append(t)
            t.start()
            numthreads -= 1
        self.master = False
        self.verbose = bool(server.cfg['verbose'].lower() == "true")
        self.debug = bool(server.cfg['debug'].lower() == "true")
        self.session = None
        #self.numwlan = 0
        closeonexec(request.fileno())
        SocketServer.BaseRequestHandler.__init__(self, request,
                                                 client_address, server)

    def setup(self):
        ''' Client has connected, set up a new connection.
        '''
        self.info("new TCP connection: %s:%s" % self.client_address)
        #self.register()


    def finish(self):
        ''' Client has disconnected, end this request handler and disconnect
            from the session. Shutdown sessions that are not running.
        '''
        if self.verbose:
            self.info("client disconnected: notifying threads")
        max_attempts = 5
        timeout = 0.0625 # wait for 1.9375s max
        while len(self.msgq) > 0 and max_attempts > 0:
            if self.verbose:
                self.info("%d messages remain in queue (%d)" % \
                          (len(self.msgq), max_attempts))
            max_attempts -= 1
            self.msgcv.acquire()
            self.msgcv.notifyAll() # drain msgq before dying
            self.msgcv.release()
            time.sleep(timeout) # allow time for msg processing
            timeout *= 2  # backoff timer
        self.msgcv.acquire()
        self.done = True
        self.msgcv.notifyAll()
        self.msgcv.release()
        for t in self.handlerthreads:
            if self.verbose:
                self.info("waiting for thread: %s" % t.getName())
            timeout = 2.0               # seconds
            t.join(timeout)
            if t.isAlive():
                self.warn("joining %s failed: still alive after %s sec" %
                          (t.getName(), timeout))
        self.info("connection closed: %s:%s" % self.client_address)
        if self.session:
            self.session.disconnect(self)
        return SocketServer.BaseRequestHandler.finish(self)


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

    def register(self):
        ''' Return a Register Message
        '''
        self.info("GUI has connected to session %d at %s" % \
                  (self.session.sessionid, time.ctime()))
        tlvdata = ""
        tlvdata += coreapi.CoreRegTlv.pack(coreapi.CORE_TLV_REG_EXECSRV,
                                                    "core-daemon")
        tlvdata += coreapi.CoreRegTlv.pack(coreapi.CORE_TLV_REG_EMULSRV,
                                                    "core-daemon")
        tlvdata += self.session.confobjs_to_tlvs()
        return coreapi.CoreRegMessage.pack(coreapi.CORE_API_ADD_FLAG, tlvdata)

    def sendall(self, data):
        ''' Send raw data to the other end of this TCP connection 
        using socket's sendall().
        '''
        return self.request.sendall(data)

    def recvmsg(self):
        ''' Receive data and return a CORE API message object.
        '''
        try:
            msghdr = self.request.recv(coreapi.CoreMessage.hdrsiz)
            if self.debug and len(msghdr) > 0:
                self.info("received message header:\n%s" % hexdump(msghdr))
        except Exception, e:
            raise IOError, "error receiving header (%s)" % e
        if len(msghdr) != coreapi.CoreMessage.hdrsiz:
            if len(msghdr) == 0:
                raise EOFError, "client disconnected"
            else:            
                raise IOError, "invalid message header size"
        msgtype, msgflags, msglen = coreapi.CoreMessage.unpackhdr(msghdr)
        if msglen == 0:
            self.warn("received message with no data")
        data = ""
        while len(data) < msglen:
            data += self.request.recv(msglen - len(data))
            if self.debug:
                self.info("received message data:\n%s" % hexdump(data))
            if len(data) > msglen:
                self.warn("received message length does not match received data "  \
                            "(%s != %s)" % (len(data), msglen))
                raise IOError
        try:
            msgcls = coreapi.msg_class(msgtype)
            msg = msgcls(msgflags, msghdr, data)
        except KeyError:
            msg = coreapi.CoreMessage(msgflags, msghdr, data)
            msg.msgtype = msgtype
            self.warn("unimplemented core message type: %s" % msg.typestr())
        return msg


    def queuemsg(self, msg):
        ''' Queue an API message for later processing.
        '''
        if msg.queuedtimes >= self.maxmsgqueuedtimes:
            self.warn("dropping message queued %d times: %s" %
                      (msg.queuedtimes, msg))
            return
        if self.debug:
            self.info("queueing msg (queuedtimes = %s): type %s" %
                      (msg.queuedtimes, msg.msgtype))
        msg.queuedtimes += 1
        self.msgcv.acquire()
        self.msgq.append(msg)
        self.msgcv.notify()
        self.msgcv.release()

    def handlerthread(self):
        ''' CORE API message handling loop that is spawned for each server
            thread; get CORE API messages from the incoming message queue,
            and call handlemsg() for processing.
        '''
        while not self.done:
            # get a coreapi.CoreMessage() from the incoming queue
            self.msgcv.acquire()
            while not self.msgq:
                self.msgcv.wait()
                if self.done:
                    self.msgcv.release()
                    return
            msg = self.msgq.pop(0)
            self.msgcv.release()
            self.handlemsg(msg)

        
    def handlemsg(self, msg):
        ''' Handle an incoming message; dispatch based on message type,
            optionally sending replies.
        '''
        if self.session and self.session.broker.handlemsg(msg):
            if self.debug:
                self.info("%s forwarding message:\n%s" %
                          (threading.currentThread().getName(), msg))
            return

        if self.debug:
            self.info("%s handling message:\n%s" %
                      (threading.currentThread().getName(), msg))

        if msg.msgtype not in self.msghandler:
            self.warn("no handler for message type: %s" %
                      msg.typestr())
            return
        msghandler = self.msghandler[msg.msgtype]

        try:
            replies = msghandler(msg)
            self.dispatchreplies(replies,msg)
        except Exception, e:
            self.warn("%s: exception while handling msg:\n%s\n%s" %
                      (threading.currentThread().getName(), msg,
                       traceback.format_exc()))

    # Added to allow the auxiliary handlers to define a different behavior when replying 
    # to messages from clients
    def dispatchreplies(self, replies, msg):
        '''
        Dispatch replies by CORE to message msg previously received from the client.
        '''
        for reply in replies:
            if self.debug:
                msgtype, msgflags, msglen = \
                    coreapi.CoreMessage.unpackhdr(reply)
                try:
                    rmsg = coreapi.msg_class(msgtype)(msgflags,
                                                      reply[:coreapi.CoreMessage.hdrsiz],
                                                      reply[coreapi.CoreMessage.hdrsiz:])
                except KeyError:
                    # multiple TLVs of same type cause KeyError exception
                    rmsg = "CoreMessage (type %d flags %d length %d)" % \
                           (msgtype, msgflags, msglen)
                self.info("%s: reply msg:\n%s" %
                          (threading.currentThread().getName(), rmsg))
            try:
                self.sendall(reply)
            except Exception, e:
                self.warn("Error sending reply data: %s" % e)


    def handle(self):
        ''' Handle a new connection request from a client. Dispatch to the
            recvmsg() method for receiving data into CORE API messages, and
            add them to an incoming message queue.
        '''
        # use port as session id
        port = self.request.getpeername()[1]
        self.session = self.server.getsession(sessionid = port, 
                                              useexisting = False)
        self.session.connect(self)
        while True:
            try:
                msg = self.recvmsg()
            except EOFError:
                break
            except IOError, e:
                self.warn("IOError: %s" % e)
                break
            msg.queuedtimes = 0
            self.queuemsg(msg)
            if (msg.msgtype == coreapi.CORE_API_SESS_MSG):
                # delay is required for brief connections, allow session joining
                time.sleep(0.125)
            self.session.broadcast(self, msg)
        #self.session.shutdown()
        #del self.session
        gc.collect()
#         print "gc count:", gc.get_count()
#         for o in gc.get_objects():
#             if isinstance(o, pycore.PyCoreObj):
#                 print "XXX XXX XXX PyCoreObj:", o
#                 for r in gc.get_referrers(o):
#                     print "XXX XXX XXX referrer:", gc.get_referrers(o)


    def handlenodemsg(self, msg):
        ''' Node Message handler
        '''
        replies = []
        if msg.flags & coreapi.CORE_API_ADD_FLAG and \
                msg.flags & coreapi.CORE_API_DEL_FLAG:
            self.warn("ignoring invalid message: "
                      "add and delete flag both set")
            return ()
        nodenum = msg.tlvdata[coreapi.CORE_TLV_NODE_NUMBER]
        nodexpos = msg.gettlv(coreapi.CORE_TLV_NODE_XPOS)
        nodeypos = msg.gettlv(coreapi.CORE_TLV_NODE_YPOS)
        canvas = msg.gettlv(coreapi.CORE_TLV_NODE_CANVAS)
        icon = msg.gettlv(coreapi.CORE_TLV_NODE_ICON)
        lat = msg.gettlv(coreapi.CORE_TLV_NODE_LAT)
        lng = msg.gettlv(coreapi.CORE_TLV_NODE_LONG)
        alt = msg.gettlv(coreapi.CORE_TLV_NODE_ALT)
        if nodexpos is None and nodeypos is None and \
                lat is not None and lng is not None and alt is not None:
            (x, y, z) = self.session.location.getxyz(float(lat), float(lng),
                                                     float(alt))
            nodexpos = int(x)
            nodeypos = int(y)
            # GUI can't handle lat/long, so generate another X/Y position message
            tlvdata = ""
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_NUMBER,
                                                nodenum)
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_XPOS,
                                                nodexpos)
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_YPOS,
                                                nodeypos)
            self.session.broadcastraw(self, coreapi.CoreNodeMessage.pack(0, tlvdata))

        if msg.flags & coreapi.CORE_API_ADD_FLAG:
            nodetype = msg.tlvdata[coreapi.CORE_TLV_NODE_TYPE]
            try:
                nodecls = coreapi.node_class(nodetype)
            except KeyError:
                try:
                    nodetypestr = " (%s)" % coreapi.node_types[nodetype]
                except KeyError:
                    nodetypestr = ""
                self.warn("warning: unimplemented node type: %s%s" % \
                          (nodetype, nodetypestr))
                return ()
            start = False
            if self.session.getstate() > coreapi.CORE_EVENT_DEFINITION_STATE:
                start = True

            nodename =  msg.tlvdata[coreapi.CORE_TLV_NODE_NAME]
            model = msg.gettlv(coreapi.CORE_TLV_NODE_MODEL)
            clsargs = { 'verbose': self.verbose, 'start': start }
            if nodetype == coreapi.CORE_NODE_XEN:
                clsargs['model'] = model
            if nodetype == coreapi.CORE_NODE_RJ45:
                if hasattr(self.session.options, 'enablerj45'):
                    if self.session.options.enablerj45 == '0':
                        clsargs['start'] = False
            # this instantiates an object of class nodecls, 
            # creating the node or network
            n = self.session.addobj(cls = nodecls, objid = nodenum,
                                    name = nodename, **clsargs)
            if nodexpos is not None and nodeypos is not None:
                n.setposition(nodexpos, nodeypos, None)
            if canvas is not None:
                n.canvas = canvas
            if icon is not None:
                n.icon = icon
            opaque = msg.gettlv(coreapi.CORE_TLV_NODE_OPAQUE)
            if opaque is not None:
                n.opaque = opaque

            # add services to a node, either from its services TLV or 
            # through the configured defaults for this node type
            if nodetype == coreapi.CORE_NODE_DEF or \
               nodetype == coreapi.CORE_NODE_PHYS or \
               nodetype == coreapi.CORE_NODE_XEN:
                if model is None:
                    # TODO: default model from conf file?
                    model = "router"
                n.type = model
                services_str = msg.gettlv(coreapi.CORE_TLV_NODE_SERVICES)
                self.session.services.addservicestonode(n, model, services_str,
                                                        self.verbose)
            # boot nodes if they are added after runtime (like 
            # session.bootnodes())
            if self.session.getstate() == coreapi.CORE_EVENT_RUNTIME_STATE:
                if isinstance(n, pycore.nodes.PyCoreNode) and \
                   not isinstance(n, pycore.nodes.RJ45Node):
                    self.session.writeobjs()
                    self.session.addremovectrlif(node=n, remove=False)
                    n.boot()
                    # self.session.updatectrlifhosts()
                    # n.validate()
                if msg.flags & coreapi.CORE_API_STR_FLAG:
                    self.nodestatusreq[nodenum] = True
                    self.session.sendnodeemuid(self, nodenum)

            elif msg.flags & coreapi.CORE_API_STR_FLAG:
                self.nodestatusreq[nodenum] = True

        elif msg.flags & coreapi.CORE_API_DEL_FLAG:
            n = None
            try:
                n = self.session.obj(nodenum)
            except KeyError:
                pass
            self.session.delobj(nodenum)
            
            if msg.flags & coreapi.CORE_API_STR_FLAG:
                tlvdata = ""
                tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_NUMBER,
                                                    nodenum)
                flags = coreapi.CORE_API_DEL_FLAG | coreapi.CORE_API_LOC_FLAG
                replies.append(coreapi.CoreNodeMessage.pack(flags, tlvdata))
            for reply in self.session.checkshutdown():
                replies.append(reply)
        # Node modify message (no add/del flag)
        else:
            n = None
            try:
                n = self.session.obj(nodenum)
            except KeyError:
                if self.verbose:
                    self.warn("ignoring node message: unknown node number %s" \
                              % nodenum)
            #nodeemuid = msg.gettlv(coreapi.CORE_TLV_NODE_EMUID)
            if nodexpos is None or nodeypos is None:
                if self.verbose:
                    self.info("ignoring node message: nothing to do")
            else:
                if n:
                    n.setposition(nodexpos, nodeypos, None)
            if n:
                if canvas is not None:
                    n.canvas = canvas
                if icon is not None:
                    n.icon = icon
        
        return replies


    def handlelinkmsg(self, msg):
        ''' Link Message handler
        '''

        nodenum1 = msg.gettlv(coreapi.CORE_TLV_LINK_N1NUMBER)
        ifindex1 = msg.gettlv(coreapi.CORE_TLV_LINK_IF1NUM)
        ipv41 = msg.gettlv(coreapi.CORE_TLV_LINK_IF1IP4)
        ipv4mask1 = msg.gettlv(coreapi.CORE_TLV_LINK_IF1IP4MASK)
        mac1 = msg.gettlv(coreapi.CORE_TLV_LINK_IF1MAC)
        ipv61 = msg.gettlv(coreapi.CORE_TLV_LINK_IF1IP6)
        ipv6mask1 = msg.gettlv(coreapi.CORE_TLV_LINK_IF1IP6MASK)
        ifname1 = msg.gettlv(coreapi.CORE_TLV_LINK_IF1NAME)

        nodenum2 = msg.gettlv(coreapi.CORE_TLV_LINK_N2NUMBER)
        ifindex2 = msg.gettlv(coreapi.CORE_TLV_LINK_IF2NUM)
        ipv42 = msg.gettlv(coreapi.CORE_TLV_LINK_IF2IP4)
        ipv4mask2 = msg.gettlv(coreapi.CORE_TLV_LINK_IF2IP4MASK)
        mac2 = msg.gettlv(coreapi.CORE_TLV_LINK_IF2MAC)
        ipv62 = msg.gettlv(coreapi.CORE_TLV_LINK_IF2IP6)
        ipv6mask2 = msg.gettlv(coreapi.CORE_TLV_LINK_IF2IP6MASK)
        ifname2 = msg.gettlv(coreapi.CORE_TLV_LINK_IF2NAME)

        node1 = None
        node2 = None
        net = None
        net2 = None
        
        uni = msg.gettlv(coreapi.CORE_TLV_LINK_UNI)
        if uni is not None and uni == 1:
            unidirectional = True
        else:
            unidirectional = False
        

        # one of the nodes may exist on a remote server
        if nodenum1 is not None and nodenum2 is not None:
            t = self.session.broker.gettunnel(nodenum1, nodenum2)
            if isinstance(t, pycore.nodes.PyCoreNet):
                net = t
                if t.remotenum == nodenum1:
                    nodenum1 = None
                else:
                    nodenum2 = None
            # PhysicalNode connected via GreTap tunnel; uses adoptnetif() below
            elif t is not None:
                if t.remotenum == nodenum1:
                    nodenum1 = None
                else:
                    nodenum2 = None


        if nodenum1 is not None:
            try:
                n = self.session.obj(nodenum1)
            except KeyError:
                # XXX wait and queue this message to try again later
                # XXX maybe this should be done differently
                time.sleep(0.125)
                self.queuemsg(msg)
                return ()
            if isinstance(n, pycore.nodes.PyCoreNode):
                node1 = n
            elif isinstance(n, pycore.nodes.PyCoreNet):
                if net is None:
                    net = n
                else:
                    net2 = n
            else:
                raise ValueError, "unexpected object class: %s" % n

        if nodenum2 is not None:
            try:
                n = self.session.obj(nodenum2)
            except KeyError:
                # XXX wait and queue this message to try again later
                # XXX maybe this should be done differently
                time.sleep(0.125)
                self.queuemsg(msg)
                return ()
            if isinstance(n, pycore.nodes.PyCoreNode):
                node2 = n
            elif isinstance(n, pycore.nodes.PyCoreNet):
                if net is None:
                    net = n
                else:
                    net2 = n
            else:
                raise ValueError, "unexpected object class: %s" % n

        link_msg_type = msg.gettlv(coreapi.CORE_TLV_LINK_TYPE)

        if node1:
            node1.lock.acquire()
        if node2:
            node2.lock.acquire()

        try:
            if link_msg_type == coreapi.CORE_LINK_WIRELESS:
                ''' Wireless link/unlink event
                '''
                numwlan = 0
                objs = [node1, node2, net, net2]
                objs = filter( lambda(x): x is not None, objs )
                if len(objs) < 2:
                    raise ValueError, "wireless link/unlink message between unknown objects"
                
                nets = objs[0].commonnets(objs[1])
                for (netcommon, netif1, netif2) in nets:
                    if not isinstance(netcommon, pycore.nodes.WlanNode) and \
                       not isinstance(netcommon, pycore.nodes.EmaneNode):
                        continue
                    if msg.flags & coreapi.CORE_API_ADD_FLAG:
                        netcommon.link(netif1, netif2)
                    elif msg.flags & coreapi.CORE_API_DEL_FLAG:
                        netcommon.unlink(netif1, netif2)
                    else:
                        raise ValueError,  "invalid flags for wireless link/unlink message"
                    numwlan += 1
                if numwlan == 0:
                    raise ValueError, \
                        "no common network found for wireless link/unlink"
                        
            elif msg.flags & coreapi.CORE_API_ADD_FLAG:
                ''' Add a new link.
                '''
                start = False
                if self.session.getstate() > coreapi.CORE_EVENT_DEFINITION_STATE:
                    start = True

                if node1 and node2 and not net:
                    # a new wired link
                    net = self.session.addobj(cls = pycore.nodes.PtpNet,
                                              verbose = self.verbose,
                                              start = start)

                bw = msg.gettlv(coreapi.CORE_TLV_LINK_BW)
                delay = msg.gettlv(coreapi.CORE_TLV_LINK_DELAY)
                loss = msg.gettlv(coreapi.CORE_TLV_LINK_PER)
                duplicate = msg.gettlv(coreapi.CORE_TLV_LINK_DUP)
                jitter = msg.gettlv(coreapi.CORE_TLV_LINK_JITTER)
                key = msg.gettlv(coreapi.CORE_TLV_LINK_KEY)

                netaddrlist = []
                #print " n1=%s n2=%s net=%s net2=%s" % (node1, node2, net, net2)
                if node1 and net:
                    addrlist = []
                    if ipv41 is not None and ipv4mask1 is not None:
                        addrlist.append("%s/%s" % (ipv41, ipv4mask1))
                    if ipv61 is not None and ipv6mask1 is not None:
                        addrlist.append("%s/%s" % (ipv61, ipv6mask1))
                    if ipv42 is not None and ipv4mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv42, ipv4mask2))
                    if ipv62 is not None and ipv6mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv62, ipv6mask2))
                    ifindex1 = node1.newnetif(net, addrlist = addrlist,
                                   hwaddr = mac1, ifindex = ifindex1, ifname=ifname1)
                    net.linkconfig(node1.netif(ifindex1, net), bw = bw,
                                   delay = delay, loss = loss,
                                   duplicate = duplicate, jitter = jitter)
                if node1 is None and net:
                    if ipv41 is not None and ipv4mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv41, ipv4mask1))
                        # don't add this address again if node2 and net
                        ipv41 = None
                    if ipv61 is not None and ipv6mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv61, ipv6mask1))
                        # don't add this address again if node2 and net
                        ipv61 = None
                if node2 and net:
                    addrlist = []
                    if ipv42 is not None and ipv4mask2 is not None:
                        addrlist.append("%s/%s" % (ipv42, ipv4mask2))
                    if ipv62 is not None and ipv6mask2 is not None:
                        addrlist.append("%s/%s" % (ipv62, ipv6mask2))
                    if ipv41 is not None and ipv4mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv41, ipv4mask1))
                    if ipv61 is not None and ipv6mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv61, ipv6mask1))
                    ifindex2 = node2.newnetif(net, addrlist = addrlist,
                                   hwaddr = mac2, ifindex = ifindex2, ifname=ifname2)
                    if not unidirectional:
                        net.linkconfig(node2.netif(ifindex2, net), bw = bw,
                                   delay = delay, loss = loss,
                                   duplicate = duplicate, jitter = jitter)
                if node2 is None and net2:
                    if ipv42 is not None and ipv4mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv42, ipv4mask2))
                    if ipv62 is not None and ipv6mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv62, ipv6mask2))               

                # tunnel node finalized with this link message
                if key and isinstance(net, pycore.nodes.TunnelNode):
                    net.setkey(key)
                    if len(netaddrlist) > 0:
                        net.addrconfig(netaddrlist)
                if key and isinstance(net2, pycore.nodes.TunnelNode):
                    net2.setkey(key)
                    if len(netaddrlist) > 0:
                        net2.addrconfig(netaddrlist)
                
                if net and net2:
                    # two layer-2 networks linked together
                    if isinstance(net2, pycore.nodes.RJ45Node):
                        netif = net2.linknet(net) # RJ45 nodes have different linknet()
                    else:
                        netif = net.linknet(net2)
                    net.linkconfig(netif, bw = bw, delay = delay, loss = loss,
                                   duplicate = duplicate, jitter = jitter)
                    if not unidirectional:
                        netif.swapparams('_params_up')
                        net2.linkconfig(netif, bw = bw, delay = delay, loss = loss,
                                   duplicate = duplicate, jitter = jitter,
                                   devname = netif.name)
                        netif.swapparams('_params_up')

                    
                elif net is None and net2 is None and \
                  (node1 is None or node2 is None):
                    # apply address/parameters to PhysicalNodes
                    fx = (bw, delay, loss, duplicate, jitter)
                    addrlist = []
                    if node1 and isinstance(node1, pycore.pnodes.PhysicalNode):
                        if ipv41 is not None and ipv4mask1 is not None:
                            addrlist.append("%s/%s" % (ipv41, ipv4mask1))
                        if ipv61 is not None and ipv6mask1 is not None:
                            addrlist.append("%s/%s" % (ipv61, ipv6mask1))
                        node1.adoptnetif(t, ifindex1, mac1, addrlist)
                        node1.linkconfig(t, bw, delay, loss, duplicate, jitter)
                    elif node2 and isinstance(node2, pycore.pnodes.PhysicalNode):
                        if ipv42 is not None and ipv4mask2 is not None:
                            addrlist.append("%s/%s" % (ipv42, ipv4mask2))
                        if ipv62 is not None and ipv6mask2 is not None:
                            addrlist.append("%s/%s" % (ipv62, ipv6mask2))
                        node2.adoptnetif(t, ifindex2, mac2, addrlist)
                        node2.linkconfig(t, bw, delay, loss, duplicate, jitter)
            # delete a link
            elif msg.flags & coreapi.CORE_API_DEL_FLAG:
                ''' Remove a link.
                '''
                if node1 and node2:
                    # TODO: fix this for the case where ifindex[1,2] are
                    #       not specified
                    # a wired unlink event, delete the connecting bridge
                    netif1 = node1.netif(ifindex1)
                    netif2 = node2.netif(ifindex2)
                    if netif1 is None and netif2 is None:
                        nets = node1.commonnets(node2)
                        for (netcommon, tmp1, tmp2) in nets:
                            if (net and netcommon == net) or net is None:
                                netif1 = tmp1
                                netif2 = tmp2
                                break
                    if netif1 is None or netif2 is None:
                        pass
                    elif netif1.net or netif2.net:
                        if netif1.net != netif2.net:
                            if not netif1.up or not netif2.up:
                                pass
                            else:
                                raise ValueError, "no common network found"
                        net = netif1.net
                        netif1.detachnet()
                        netif2.detachnet()
                        if net.numnetif() == 0:
                            self.session.delobj(net.objid)
                        node1.delnetif(ifindex1)
                        node2.delnetif(ifindex2)
            else:
                ''' Modify a link.
                '''
                bw = msg.gettlv(coreapi.CORE_TLV_LINK_BW)
                delay = msg.gettlv(coreapi.CORE_TLV_LINK_DELAY)
                loss = msg.gettlv(coreapi.CORE_TLV_LINK_PER)
                duplicate = msg.gettlv(coreapi.CORE_TLV_LINK_DUP)
                jitter = msg.gettlv(coreapi.CORE_TLV_LINK_JITTER)
                numnet = 0
                # TODO: clean up all this logic. Having the add flag or not
                #       should use the same code block.
                if node1 is None and node2 is None:
                    if net and net2:
                        # modify link between nets
                        netif = net.getlinknetif(net2)
                        upstream = False
                        if netif is None:
                            upstream = True
                            netif = net2.getlinknetif(net)
                        if netif is None:
                            raise ValueError, "modify unknown link between nets"
                        if upstream:
                            netif.swapparams('_params_up')
                            net.linkconfig(netif, bw = bw, delay = delay,
                                       loss = loss, duplicate = duplicate,
                                       jitter = jitter, devname = netif.name)
                            netif.swapparams('_params_up')
                        else:
                            net.linkconfig(netif, bw = bw, delay = delay,
                                           loss = loss, duplicate = duplicate,
                                           jitter = jitter)
                        if not unidirectional:
                            if upstream:
                                net2.linkconfig(netif, bw = bw, delay = delay,
                                                loss = loss, 
                                                duplicate = duplicate,
                                                jitter = jitter)
                            else:
                                netif.swapparams('_params_up')
                                net2.linkconfig(netif, bw = bw, delay = delay,
                                                loss = loss,
                                                duplicate = duplicate,
                                                jitter = jitter,
                                                devname = netif.name)
                                netif.swapparams('_params_up')
                    else:
                        raise ValueError, "modify link for unknown nodes"
                elif node1 is None:
                    # node1 = layer 2node, node2 = layer3 node
                    net.linkconfig(node2.netif(ifindex2, net), bw = bw,
                                   delay = delay, loss = loss, 
                                   duplicate = duplicate, jitter = jitter)
                elif node2 is None:
                    # node2 = layer 2node, node1 = layer3 node
                    net.linkconfig(node1.netif(ifindex1, net), bw = bw,
                                   delay = delay, loss = loss, 
                                   duplicate = duplicate, jitter = jitter)
                else:
                    nets = node1.commonnets(node2)
                    for (net, netif1, netif2) in nets:
                        if ifindex1 is not None and \
                            ifindex1 != node1.getifindex(netif1):
                            continue
                        net.linkconfig(netif1, bw = bw, delay = delay,
                                       loss = loss, duplicate = duplicate,
                                       jitter = jitter, netif2 = netif2)
                        if not unidirectional:
                            net.linkconfig(netif2, bw = bw, delay = delay,
                                       loss = loss, duplicate = duplicate,
                                       jitter = jitter, netif2 = netif1)
                        numnet += 1
                    if numnet == 0:
                        raise ValueError, "no common network found"

        
        finally:
            if node1:
                node1.lock.release()
            if node2:
                node2.lock.release()
        return ()

    def handleexecmsg(self, msg):
        ''' Execute Message handler
        '''
        nodenum = msg.gettlv(coreapi.CORE_TLV_EXEC_NODE)
        execnum = msg.gettlv(coreapi.CORE_TLV_EXEC_NUM)
        exectime = msg.gettlv(coreapi.CORE_TLV_EXEC_TIME)
        cmd = msg.gettlv(coreapi.CORE_TLV_EXEC_CMD)
        
        # local flag indicates command executed locally, not on a node
        if nodenum is None and not msg.flags & coreapi.CORE_API_LOC_FLAG:
            raise ValueError, "Execute Message is missing node number."
        if execnum is None:
            raise ValueError, "Execute Message is missing execution number."
        if exectime is not None:
            self.session.addevent(exectime, node=nodenum, name=None, data=cmd)
            return ()

        try:
            n = self.session.obj(nodenum)
        except KeyError:
            # XXX wait and queue this message to try again later
            # XXX maybe this should be done differently
            if not msg.flags & coreapi.CORE_API_LOC_FLAG:
                time.sleep(0.125)
                self.queuemsg(msg)
                return ()
            else:
                pass
        # build common TLV items for reply
        tlvdata = ""
        if nodenum is not None:
            tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_NODE,
                                                nodenum)
        tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_NUM, execnum)
        tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_CMD, cmd)
        
        if msg.flags & coreapi.CORE_API_TTY_FLAG:
            if nodenum is None:
                raise NotImplementedError
            # echo back exec message with cmd for spawning interactive terminal
            if cmd == "bash":
                cmd = "/bin/bash"
            res = n.termcmdstring(cmd)
            tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_RESULT,
                                                res)
            reply = coreapi.CoreExecMessage.pack(coreapi.CORE_API_TTY_FLAG,
                                                 tlvdata)
            return (reply, )
        else:
            if self.verbose:
                self.info("execute message with cmd = '%s'" % cmd)
            # execute command and send a response
            if msg.flags & coreapi.CORE_API_STR_FLAG or \
               msg.flags & coreapi.CORE_API_TXT_FLAG:
                # shlex.split() handles quotes within the string
                if msg.flags & coreapi.CORE_API_LOC_FLAG:
                    status, res = cmdresult(shlex.split(cmd))
                else:
                    status, res = n.cmdresult(shlex.split(cmd))
                if self.verbose:
                    self.info("done exec cmd='%s' with status=%d res=(%d bytes)"
                              % (cmd, status, len(res)))
                if msg.flags & coreapi.CORE_API_TXT_FLAG:
                    tlvdata += coreapi.CoreExecTlv.pack( \
                                        coreapi.CORE_TLV_EXEC_RESULT, res)
                if msg.flags & coreapi.CORE_API_STR_FLAG:
                    tlvdata += coreapi.CoreExecTlv.pack( \
                                        coreapi.CORE_TLV_EXEC_STATUS, status)
                reply = coreapi.CoreExecMessage.pack(0, tlvdata)
                return (reply, )
            # execute the command with no response
            else:
                if msg.flags & coreapi.CORE_API_LOC_FLAG:
                    mutedetach(shlex.split(cmd))
                else:
                    n.cmd(shlex.split(cmd), wait=False)
        return ()


    def handleregmsg(self, msg):
        ''' Register Message Handler
        '''
        replies = []
        # execute a Python script or XML file
        ex = msg.gettlv(coreapi.CORE_TLV_REG_EXECSRV)
        if ex:
            try:
                self.info("executing '%s'" % ex)
                if not isinstance(self.server, CoreServer): # CoreUdpServer):
                    server = self.server.mainserver
                    # elif isinstance(self.server, CoreAuxServer):
                    # server = self.server.mainserver
                else:
                    server = self.server
                if msg.flags & coreapi.CORE_API_STR_FLAG:
                    old_session_ids = set(server.getsessionids())
                sys.argv = shlex.split(ex)
                filename = sys.argv[0]
                if os.path.splitext(filename)[1].lower() == '.xml':
                    session = server.getsession(useexisting=False)
                    try:
                        opensessionxml(session, filename, start=True)
                    except:
                        session.shutdown()
                        server.delsession(session)
                        raise
                else:
                    t = threading.Thread(target = execfile,
                                         args=(filename, {'__file__': filename,
                                                          'server': server}))
                    t.daemon = True
                    t.start()
                    time.sleep(0.25) # allow time for session creation
                if msg.flags & coreapi.CORE_API_STR_FLAG:
                    new_session_ids = set(server.getsessionids())
                    new_sid = new_session_ids.difference(old_session_ids)
                    try:
                        sid = new_sid.pop()
                        self.info("executed '%s' as session %d" % (ex, sid))
                    except KeyError:
                        self.info("executed '%s' with unknown session ID" % ex)
                        return replies
                    self.info("checking session %d for RUNTIME state" % sid)
                    session = self.server.getsession(sessionid=sid, useexisting=True)
                    retries = 10
                    # wait for session to enter RUNTIME state, to prevent GUI from
                    # connecting while nodes are still being instantiated
                    while session.getstate() != coreapi.CORE_EVENT_RUNTIME_STATE:
                        self.info("waiting for session %d to enter RUNTIME state" % sid)
                        time.sleep(1)
                        retries -= 1
                        if retries <= 0:
                            self.info("session %d did not enter RUNTIME state" % sid)
                            return replies
                    tlvdata = coreapi.CoreRegTlv.pack( \
                                            coreapi.CORE_TLV_REG_EXECSRV, ex)
                    tlvdata += coreapi.CoreRegTlv.pack( \
                                    coreapi.CORE_TLV_REG_SESSION, "%s" % sid)
                    msg = coreapi.CoreRegMessage.pack(0, tlvdata)
                    replies.append(msg)
            except Exception, e:
                self.warn("error executing '%s': %s" % \
                          (ex, traceback.format_exc()))
                tlvdata = coreapi.CoreExceptionTlv.pack( \
                    coreapi.CORE_TLV_EXCP_LEVEL, 2)
                tlvdata += coreapi.CoreExceptionTlv.pack( \
                    coreapi.CORE_TLV_EXCP_TEXT, str(e))
                msg = coreapi.CoreExceptionMessage.pack(0, tlvdata)
                replies.append(msg)
            return replies
            
        gui = msg.gettlv(coreapi.CORE_TLV_REG_GUI)
        if gui is None:
            self.info("ignoring Register message")
        else:
            # register capabilities with the GUI
            self.master = True
            found = self.server.setsessionmaster(self)
            replies.append(self.register())
            replies.append(self.server.tosessionmsg())
        return replies

    def handleconfmsg(self, msg):
        ''' Configuration Message handler
        '''
        nodenum = msg.gettlv(coreapi.CORE_TLV_CONF_NODE)
        objname = msg.gettlv(coreapi.CORE_TLV_CONF_OBJ)
        if self.verbose:
            self.info("Configuration message for %s node %s" % \
                      (objname, nodenum))
        # dispatch to any registered callback for this object type
        replies = self.session.confobj(objname, self.session, msg)
        # config requests usually have a reply with default data
        return replies

    def handlefilemsg(self, msg):
        ''' File Message handler
        '''
        if msg.flags & coreapi.CORE_API_ADD_FLAG:
            nodenum = msg.gettlv(coreapi.CORE_TLV_NODE_NUMBER)
            filename = msg.gettlv(coreapi.CORE_TLV_FILE_NAME)
            type = msg.gettlv(coreapi.CORE_TLV_FILE_TYPE)
            srcname = msg.gettlv(coreapi.CORE_TLV_FILE_SRCNAME)
            data = msg.gettlv(coreapi.CORE_TLV_FILE_DATA)
            cmpdata = msg.gettlv(coreapi.CORE_TLV_FILE_CMPDATA)

            if cmpdata is not None:
                self.warn("Compressed file data not implemented for File " \
                          "message.")
                return ()
            if srcname is not None and data is not None:
                self.warn("ignoring invalid File message: source and data " \
                         "TLVs are both present")
                return ()
                
            # some File Messages store custom files in services, 
            # prior to node creation
            if type is not None:
                if type[:8] == "service:":                
                    self.session.services.setservicefile(nodenum, type, 
                                                         filename, srcname, data)
                    return ()
                elif type[:5] == "hook:":
                    self.session.sethook(type, filename, srcname, data)
                    return ()
            # writing a file to the host
            if nodenum is None:
                if srcname is not None:
                    shutil.copy2(srcname, filename)
                else:
                    with open(filename, "w") as f:
                        f.write(data)
                return ()
            try:
                n = self.session.obj(nodenum)
            except KeyError:
                # XXX wait and queue this message to try again later
                # XXX maybe this should be done differently
                self.warn("File message for %s for node number %s queued." % \
                          (filename, nodenum))
                time.sleep(0.125)
                self.queuemsg(msg)
                return ()
            if srcname is not None:
                n.addfile(srcname, filename)
            elif data is not None:
                n.nodefile(filename, data)
        else:
            raise NotImplementedError
        return ()

    def handleifacemsg(self, msg):
        ''' Interface Message handler
        '''
        self.info("ignoring Interface message")
        return ()

    def handleeventmsg(self, msg):
        ''' Event Message handler
        '''
        eventtype = msg.gettlv(coreapi.CORE_TLV_EVENT_TYPE)
        if eventtype is None:
            raise NotImplementedError, "Event message missing event type"
        node = msg.gettlv(coreapi.CORE_TLV_EVENT_NODE)

        if self.verbose:
            self.info("EVENT %d: %s at %s" % \
                (eventtype, coreapi.event_types[eventtype], time.ctime()))
        if eventtype <= coreapi.CORE_EVENT_SHUTDOWN_STATE:
            if node is not None:
                try:
                    n = self.session.obj(node)
                except KeyError:
                    raise KeyError, "Event message for unknown node %d" % node
                if eventtype == coreapi.CORE_EVENT_INSTANTIATION_STATE:
                    # configure mobility models for WLAN added during runtime
                    if isinstance(n, pycore.nodes.WlanNode):
                        return (self.session.mobility.startup(nodenums=(n.objid,)))
                self.warn("dropping unhandled Event message with node number")
                return ()
            self.session.setstate(state=eventtype, info=True, sendevent=False)
            
        if eventtype == coreapi.CORE_EVENT_DEFINITION_STATE:
            # clear all session objects in order to receive new definitions
            self.session.delobjs()
            self.session.delhooks()
            self.session.broker.reset()
        elif eventtype == coreapi.CORE_EVENT_CONFIGURATION_STATE:
            pass
        elif eventtype == coreapi.CORE_EVENT_INSTANTIATION_STATE:
            if len(self.handlerthreads) > 1:
                # TODO: sync handler threads here before continuing
                time.sleep(2.0) # XXX
            # done receiving node/link configuration, ready to instantiate
            self.session.instantiate(handler=self)
        elif eventtype == coreapi.CORE_EVENT_RUNTIME_STATE:
            if self.session.master:
                self.warn("Unexpected event message: RUNTIME state received " \
                          "at session master")
            else:
                # master event queue is started in session.checkruntime()
                self.session.evq.run()
        elif eventtype == coreapi.CORE_EVENT_DATACOLLECT_STATE:
            self.session.datacollect()
        elif eventtype == coreapi.CORE_EVENT_SHUTDOWN_STATE:
            if self.session.master:
                self.warn("Unexpected event message: SHUTDOWN state received " \
                          "at session master")
        elif eventtype in (coreapi.CORE_EVENT_START,  coreapi.CORE_EVENT_STOP, \
                           coreapi.CORE_EVENT_RESTART, \
                           coreapi.CORE_EVENT_PAUSE, \
                           coreapi.CORE_EVENT_RECONFIGURE):
            handled = False
            name = msg.gettlv(coreapi.CORE_TLV_EVENT_NAME)
            if name:
                # TODO: register system for event message handlers,
                # like confobjs
                if name.startswith("service:"):
                    self.session.services.handleevent(msg)
                    handled = True
                elif name.startswith("mobility:"):
                    self.session.mobility.handleevent(msg)
                    handled = True
                else:
                    pass
            if not handled:
                self.warn("Unhandled event message: event type %s (%s)" % \
                              (eventtype, coreapi.state_name(eventtype)))
        elif eventtype == coreapi.CORE_EVENT_FILE_OPEN:
            self.session.delobjs()
            self.session.delhooks()
            self.session.broker.reset()
            filename = msg.tlvdata[coreapi.CORE_TLV_EVENT_NAME]
            opensessionxml(self.session, filename)
            return self.session.sendobjs()
        elif eventtype == coreapi.CORE_EVENT_FILE_SAVE:
            filename = msg.tlvdata[coreapi.CORE_TLV_EVENT_NAME]
            savesessionxml(self.session, filename, self.session.cfg['xmlfilever'])
        elif eventtype == coreapi.CORE_EVENT_SCHEDULED:
            etime = msg.gettlv(coreapi.CORE_TLV_EVENT_TIME)
            node = msg.gettlv(coreapi.CORE_TLV_EVENT_NODE)
            name = msg.gettlv(coreapi.CORE_TLV_EVENT_NAME)
            data = msg.gettlv(coreapi.CORE_TLV_EVENT_DATA)
            if etime is None:
                self.warn("Event message scheduled event missing start time")
                return ()
            if msg.flags & coreapi.CORE_API_ADD_FLAG:
                self.session.addevent(float(etime), node=node, name=name, 
                                      data=data)
            else:
                raise NotImplementedError
        else:
            self.warn("Unhandled event message: event type %d" % eventtype)
        return ()

    def handlesessionmsg(self, msg):
        ''' Session Message handler
        '''
        replies = []
        sid_str = msg.gettlv(coreapi.CORE_TLV_SESS_NUMBER)
        name_str = msg.gettlv(coreapi.CORE_TLV_SESS_NAME)
        file_str = msg.gettlv(coreapi.CORE_TLV_SESS_FILE)
        nc_str = msg.gettlv(coreapi.CORE_TLV_SESS_NODECOUNT)
        thumb = msg.gettlv(coreapi.CORE_TLV_SESS_THUMB)
        user = msg.gettlv(coreapi.CORE_TLV_SESS_USER)
        sids = coreapi.str_to_list(sid_str)
        names = coreapi.str_to_list(name_str)
        files = coreapi.str_to_list(file_str)
        ncs = coreapi.str_to_list(nc_str)
        self.info("SESSION message flags=0x%x sessions=%s" % (msg.flags, sid_str))

        if msg.flags == 0:
            # modify a session
            i = 0
            for sid in sids:
                sid = int(sid)
                if sid == 0:
                    session = self.session
                else:
                    session = self.server.getsession(sessionid = sid, 
                                                     useexisting = True)
                if session is None:
                    self.info("session %s not found" % sid)
                    i += 1
                    continue
                self.info("request to modify to session %s" % session.sessionid)
                if names is not None:
                    session.name = names[i]
                if files is not None:
                    session.filename = files[i]
                if ncs is not None:
                    session.node_count = ncs[i]
                if thumb is not None:
                    session.setthumbnail(thumb)
                if user is not None:
                    session.setuser(user)
                i += 1
        else:
            if msg.flags & coreapi.CORE_API_STR_FLAG and not \
                msg.flags & coreapi.CORE_API_ADD_FLAG:
                # status request flag: send list of sessions
                return (self.server.tosessionmsg(), )
            # handle ADD or DEL flags
            for sid in sids:
                sid = int(sid)
                session = self.server.getsession(sessionid = sid, 
                                                 useexisting = True)
                if session is None:
                    self.info("session %s not found (flags=0x%x)" % \
                              (sid, msg.flags))
                    continue
                if session.server is None:
                    # this needs to be set when executing a Python script
                    session.server = self.server
                if msg.flags & coreapi.CORE_API_ADD_FLAG:
                    # connect to the first session that exists
                    self.info("request to connect to session %s" % sid)
                    # this may shutdown the session if no handlers exist
                    self.session.disconnect(self)
                    self.session = session
                    self.session.connect(self)
                    if user is not None:
                        self.session.setuser(user)
                    if msg.flags & coreapi.CORE_API_STR_FLAG:
                        replies.extend(self.session.sendobjs())
                elif msg.flags & coreapi.CORE_API_DEL_FLAG:
                    # shut down the specified session(s)
                    self.info("request to terminate session %s" % sid)
                    session.setstate(state=coreapi.CORE_EVENT_DATACOLLECT_STATE,
                                    info=True, sendevent=True)
                    session.setstate(state=coreapi.CORE_EVENT_SHUTDOWN_STATE,
                                    info=True, sendevent=True)
                    session.shutdown()
                else:
                    self.warn("unhandled session flags for session %s" % sid)
        return replies

class CoreDatagramRequestHandler(CoreRequestHandler):
    ''' A child of the CoreRequestHandler class for handling connectionless
    UDP messages. No new session is created; messages are handled immediately or
    sometimes queued on existing session handlers.
    '''

    def __init__(self, request, client_address, server):
        # TODO: decide which messages cannot be handled with connectionless UDP
        self.msghandler = {
            coreapi.CORE_API_NODE_MSG: self.handlenodemsg,
            coreapi.CORE_API_LINK_MSG: self.handlelinkmsg,
            coreapi.CORE_API_EXEC_MSG: self.handleexecmsg,
            coreapi.CORE_API_REG_MSG: self.handleregmsg,
            coreapi.CORE_API_CONF_MSG: self.handleconfmsg,
            coreapi.CORE_API_FILE_MSG: self.handlefilemsg,
            coreapi.CORE_API_IFACE_MSG: self.handleifacemsg,
            coreapi.CORE_API_EVENT_MSG: self.handleeventmsg,
            coreapi.CORE_API_SESS_MSG: self.handlesessionmsg,
        }
        self.nodestatusreq = {}
        self.master = False
        self.session = None
        self.verbose = bool(server.mainserver.cfg['verbose'].lower() == "true")
        self.debug = bool(server.mainserver.cfg['debug'].lower() == "true")
        SocketServer.BaseRequestHandler.__init__(self, request,
                                                 client_address, server)
    
    def setup(self):
        ''' Client has connected, set up a new connection.
        '''
        if self.verbose:
            self.info("new UDP connection: %s:%s" % self.client_address)
        
    def handle(self):
        msg = self.recvmsg()
        
    def finish(self):
        return SocketServer.BaseRequestHandler.finish(self)
        
    def recvmsg(self):
        ''' Receive data, parse a CoreMessage and queue it onto an existing
        session handler's queue, if available.
        '''
        data = self.request[0]
        socket = self.request[1]
        msghdr = data[:coreapi.CoreMessage.hdrsiz]
        if len(msghdr) < coreapi.CoreMessage.hdrsiz:
            raise IOError, "error receiving header (received %d bytes)" %  \
                           len(msghdr)
        msgtype, msgflags, msglen = coreapi.CoreMessage.unpackhdr(msghdr)
        if msglen == 0:
            self.warn("received message with no data")
            return
        if len(data) != coreapi.CoreMessage.hdrsiz + msglen:
            self.warn("received message length does not match received data " \
                      "(%s != %s)" % \
                      (len(data), coreapi.CoreMessage.hdrsiz + msglen))
            raise IOError
        elif self.verbose:
            self.info("UDP socket received message type=%d len=%d" % \
                      (msgtype, msglen))
        try:
            msgcls = coreapi.msg_class(msgtype)
            msg = msgcls(msgflags, msghdr, data[coreapi.CoreMessage.hdrsiz:])
        except KeyError:
            msg = coreapi.CoreMessage(msgflags, msghdr,
                                      data[coreapi.CoreMessage.hdrsiz:])
            msg.msgtype = msgtype
            self.warn("unimplemented core message type: %s" % msg.typestr())
            return
        sids = msg.sessionnumbers()
        msg.queuedtimes = 0
        #self.info("UDP message has session numbers: %s" % sids)
        if len(sids) > 0:
            for sid in sids:
                sess = self.server.mainserver.getsession(sessionid=sid, 
                                                        useexisting=True)
                if sess:
                    self.session = sess
                    sess.broadcast(self, msg)                    
                    self.handlemsg(msg)
                else:
                    self.warn("Session %d in %s message not found." % \
                              (sid, msg.typestr()))
        else:
            # no session specified, find an existing one
            sess = self.server.mainserver.getsession(sessionid=0, 
                                                    useexisting=True)
            if sess or msg.msgtype == coreapi.CORE_API_REG_MSG:
                self.session = sess
                if sess:
                    sess.broadcast(self, msg)
                self.handlemsg(msg)
            else:
                self.warn("No active session, dropping %s message." % \
                          msg.typestr())
        
    def queuemsg(self, msg):
        ''' UDP handlers are short-lived and do not have message queues.
        '''
        raise Exception, "Unable to queue %s message for later processing " \
                "using UDP!" % msg.typestr()
        
    def sendall(self, data):
        ''' Use sendto() on the connectionless UDP socket.
        '''
        self.request[1].sendto(data, self.client_address)




class BaseAuxRequestHandler(CoreRequestHandler):
    ''' 
    This is the superclass for auxiliary handlers in CORE. A concrete auxiliary handler class
    must, at a minimum, define the recvmsg(), sendall(), and dispatchreplies() methods.
    See SockerServer.BaseRequestHandler for parameter details.
    '''

    def __init__(self, request, client_address, server):
        self.msghandler = {
            coreapi.CORE_API_NODE_MSG: self.handlenodemsg,
            coreapi.CORE_API_LINK_MSG: self.handlelinkmsg,
            coreapi.CORE_API_EXEC_MSG: self.handleexecmsg,
            coreapi.CORE_API_REG_MSG: self.handleregmsg,
            coreapi.CORE_API_CONF_MSG: self.handleconfmsg,
            coreapi.CORE_API_FILE_MSG: self.handlefilemsg,
            coreapi.CORE_API_IFACE_MSG: self.handleifacemsg,
            coreapi.CORE_API_EVENT_MSG: self.handleeventmsg,
            coreapi.CORE_API_SESS_MSG: self.handlesessionmsg,
        }
        self.handlerthreads = [] 
        self.nodestatusreq = {}
        self.master = False
        self.session = None
        self.verbose = bool(server.mainserver.cfg['verbose'].lower() == "true")
        self.debug = bool(server.mainserver.cfg['debug'].lower() == "true")
        SocketServer.BaseRequestHandler.__init__(self, request,
                                                 client_address, server)
    
    def setup(self):
        ''' New client has connected to the auxiliary server.
        '''
        if self.verbose:
            self.info("new auxiliary server client: %s:%s" % self.client_address)
        
    def handle(self):
        '''
        The handler main loop
        '''
        port = self.request.getpeername()[1]
        self.session = self.server.mainserver.getsession(sessionid = port, 
                                                         useexisting = False)
        self.session.connect(self)
        while True:
            try:
                msgs = self.recvmsg()
                if msgs:
                    for msg in msgs:
                        self.session.broadcast(self, msg)
                        self.handlemsg(msg)
            except EOFError:
                break;
            except IOError, e:
                self.warn("IOError in CoreAuxRequestHandler: %s" % e)
                break;
        
    def finish(self):
        '''
        Disconnect the client
        '''
        if self.session:
            self.session.disconnect(self)
        return SocketServer.BaseRequestHandler.finish(self)

    ''' 
    =======================================================================
    Concrete AuxRequestHandler classes must redefine the following methods
    =======================================================================
    '''


    def recvmsg(self):
        ''' 
        Receive data from the client in the supported format. Parse, transform to CORE API format and 
        return transformed messages.

        EXAMPLE:
        return self.handler.request.recv(siz)
        
        '''
        pass
        return None

    def dispatchreplies(self, replies, msg):
        ''' 
        Dispatch CORE 'replies' to a previously received message 'msg' from a client.
        Replies passed to this method follow the CORE API. This method allows transformation to
        the form supported by the auxiliary handler and within the context of 'msg'. 
        Add transformation and transmission code here.

        EXAMPLE:
        transformed_replies = stateful_transform (replies, msg) # stateful_transform method needs to be defined
        if transformed_replies:
            for reply in transformed_replies:
                try:
                    self.request.sendall(reply)
                except Exception, e:
                    if self.debug:
                        self.info("-"*60)
                        traceback.print_exc(file=sys.stdout)
                        self.info("-"*60)
                    raise e

        '''
        pass


    def sendall(self, data):
        ''' 
        CORE calls this method when data needs to be asynchronously sent to a client. The data is
        in CORE API format. This method allows transformation to the required format supported by this
        handler prior to transmission. 

        EXAMPLE:
        msgs = self.transform(data)  # transform method needs to be defined
        if msgs:
            for msg in msgs:
                try:
                    self.request.sendall(reply)
                except Exception, e:
                    if self.debug:
                        self.info("-"*60)
                        traceback.print_exc(file=sys.stdout)
                        self.info("-"*60)
                    raise e
        '''
        pass


        



        
