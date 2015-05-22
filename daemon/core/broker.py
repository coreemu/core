#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
broker.py: definition of CoreBroker class that is part of the
pycore session object. Handles distributing parts of the emulation out to
other emulation servers. The broker is consulted during the 
CoreRequestHandler.handlemsg() loop to determine if messages should be handled
locally or forwarded on to another emulation server.
'''

import os, socket, select, threading, sys
from core.api import coreapi
from core.coreobj import PyCoreNode, PyCoreNet
from core.emane.nodes import EmaneNet
from core.netns.nodes import CtrlNet
from core.phys.pnodes import PhysicalNode
from core.misc.ipaddr import IPAddr
from core.conf import ConfigurableManager
if os.uname()[0] == "Linux":
    from core.netns.vif import GreTap
    from core.netns.vnet import GreTapBridge
    

class CoreBroker(ConfigurableManager):
    ''' Member of pycore session class for handling global emulation server
        data.
    '''
    _name = "broker"
    _type = coreapi.CORE_TLV_REG_UTILITY
    
    def __init__(self, session, verbose = False):
        ConfigurableManager.__init__(self, session)
        self.session_id_master = None
        self.myip = None
        self.verbose = verbose
        # dict containing tuples of (host, port, sock)
        self.servers = {}
        self.servers_lock = threading.Lock()
        self.addserver("localhost", None, None)
        # dict containing node number to server name mapping
        self.nodemap = {}
        # this lock also protects self.nodecounts
        self.nodemap_lock = threading.Lock()
        # reference counts of nodes on servers
        self.nodecounts = { }
        self.bootcount = 0
        # list of node numbers that are link-layer nodes (networks)
        self.nets = []
        # list of node numbers that are PhysicalNode nodes
        self.phys = []
        # allows for other message handlers to process API messages (e.g. EMANE)
        self.handlers = ()
        # dict with tunnel key to tunnel device mapping
        self.tunnels = {}
        self.dorecvloop = False
        self.recvthread = None

    def startup(self):
        ''' Build tunnels between network-layer nodes now that all node
            and link information has been received; called when session
            enters the instantation state.
        '''
        self.addnettunnels()
        self.writeservers()
        
    def shutdown(self):
        ''' Close all active sockets; called when the session enters the 
            data collect state
        '''
        with self.servers_lock:
            while len(self.servers) > 0:
                (server, v) = self.servers.popitem()
                (host, port, sock) = v
                if sock is None:
                    continue
                if self.verbose:
                    self.session.info("closing connection with %s @ %s:%s" % \
                                      (server, host, port))
                sock.close()
        self.reset()
        self.dorecvloop = False
        if self.recvthread is not None:
            self.recvthread.join()

    def reset(self):
        ''' Reset to initial state.
        '''
        self.nodemap_lock.acquire()
        self.nodemap.clear()
        for server in self.nodecounts:
            if self.nodecounts[server] < 1:
                self.delserver(server)
        self.nodecounts.clear()
        self.bootcount = 0
        self.nodemap_lock.release()
        del self.nets[:]
        del self.phys[:]
        while len(self.tunnels) > 0:
            (key, gt) = self.tunnels.popitem()
            gt.shutdown()

    def startrecvloop(self):
        ''' Spawn the recvloop() thread if it hasn't been already started.
        '''
        if self.recvthread is not None:
            if self.recvthread.isAlive():
                return
            else:
                self.recvthread.join()
        # start reading data from connected sockets
        self.dorecvloop = True
        self.recvthread = threading.Thread(target = self.recvloop)
        self.recvthread.daemon = True
        self.recvthread.start()

    def recvloop(self):
        ''' Thread target that receives messages from server sockets.
        '''
        self.dorecvloop = True
        # note: this loop continues after emulation is stopped, 
        # even with 0 servers
        while self.dorecvloop:
            rlist = []
            with self.servers_lock:
                # build a socket list for select call
                for name in self.servers:
                    (h, p, sock) = self.servers[name]
                    if sock is not None:
                        rlist.append(sock.fileno())
            r, w, x = select.select(rlist, [], [], 1.0)
            for sockfd in r:
                try:
                    (h, p, sock, name) = self.getserverbysock(sockfd)
                except KeyError:
                    # servers may have changed; loop again
                    break
                rcvlen = self.recv(sock, h)
                if rcvlen == 0:
                    if self.verbose:
                        self.session.info("connection with %s @ %s:%s" \
                                          " has closed" % (name, h, p))
                    self.servers[name] = (h, p, None)


    def recv(self, sock, host):
        ''' Receive data on an emulation server socket and broadcast it to
            all connected session handlers. Returns the length of data recevied
            and forwarded. Return value of zero indicates the socket has closed
            and should be removed from the self.servers dict.
        '''
        msghdr = sock.recv(coreapi.CoreMessage.hdrsiz)
        if len(msghdr) == 0:
            # server disconnected
            sock.close()
            return 0
        if len(msghdr) != coreapi.CoreMessage.hdrsiz:
            if self.verbose:
                self.session.info("warning: broker received not enough data " \
                                  "len=%s" % len(msghdr))
            return len(msghdr)

        msgtype, msgflags, msglen = coreapi.CoreMessage.unpackhdr(msghdr)
        msgdata = sock.recv(msglen)
        data = msghdr + msgdata
        count = None
        # snoop exec response for remote interactive TTYs
        if msgtype == coreapi.CORE_API_EXEC_MSG and \
           msgflags & coreapi.CORE_API_TTY_FLAG:
            data = self.fixupremotetty(msghdr, msgdata, host)
        elif msgtype == coreapi.CORE_API_NODE_MSG:
            # snoop node delete response to decrement node counts
            if msgflags & coreapi.CORE_API_DEL_FLAG:
                msg = coreapi.CoreNodeMessage(msgflags, msghdr, msgdata)
                nodenum = msg.gettlv(coreapi.CORE_TLV_NODE_NUMBER)
                if nodenum is not None:
                    count = self.delnodemap(sock, nodenum)
            # snoop node add response to increment booted node count
            # (only CoreNodes send these response messages)
            elif msgflags & \
                (coreapi.CORE_API_ADD_FLAG | coreapi.CORE_API_LOC_FLAG):
                self.incrbootcount()
                self.session.checkruntime()
        elif msgtype == coreapi.CORE_API_LINK_MSG:
            # this allows green link lines for remote WLANs
            msg = coreapi.CoreLinkMessage(msgflags, msghdr, msgdata)
            self.session.sdt.handledistributed(msg)

        self.session.broadcastraw(None, data)
        if count is not None and count < 1:
            return 0
        else:
            return len(data)

    def addserver(self, name, host, port):
        ''' Add a new server, and try to connect to it. If we're already
            connected to this (host, port), then leave it alone. When host,port
            is None, do not try to connect.
        '''
        self.servers_lock.acquire()
        if name in self.servers:
            (oldhost, oldport, sock) = self.servers[name]
            if host == oldhost or port == oldport:
                # leave this socket connected
                if sock is not None:
                    self.servers_lock.release()
                    return
            if self.verbose and host is not None and sock is not None:
                self.session.info("closing connection with %s @ %s:%s" % \
                                  (name, host, port))
            if sock is not None:
                sock.close()
        self.servers_lock.release()
        if self.verbose and host is not None:
            self.session.info("adding server %s @ %s:%s" % (name, host, port))
        if host is None:
            sock = None
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #sock.setblocking(0)
            #error = sock.connect_ex((host, port))
            try:
                sock.connect((host, port))
                self.startrecvloop()
            except Exception, e:
                self.session.warn("error connecting to server %s:%s:\n\t%s" % \
                                  (host, port, e))
                sock.close()
                sock = None
        self.servers_lock.acquire()
        self.servers[name] = (host, port, sock)
        self.servers_lock.release()
    
    def delserver(self, name):
        ''' Remove a server and hang up any connection.
        '''
        self.servers_lock.acquire()
        if name not in self.servers:
            self.servers_lock.release()
            return
        (host, port, sock) = self.servers.pop(name)
        if sock is not None:
            if self.verbose:
                self.session.info("closing connection with %s @ %s:%s" % \
                                  (name, host, port))
            sock.close()
        self.servers_lock.release()

    def getserver(self, name):
        ''' Return the (host, port, sock) tuple, or raise a KeyError exception.
        '''
        if name not in self.servers:
            raise KeyError, "emulation server %s not found" % name
        return self.servers[name]
        
    def getserverbysock(self, sockfd):
        ''' Return a (host, port, sock, name) tuple based on socket file 
            descriptor, or raise a KeyError exception.
        '''
        with self.servers_lock:
            for name in self.servers:
                (host, port, sock) = self.servers[name]
                if sock is None:
                    continue
                if sock.fileno() == sockfd:
                    return (host, port, sock, name)
        raise KeyError, "socket fd %s not found" % sockfd
        
    def getserverlist(self):
        ''' Return the list of server names (keys from self.servers).
        '''
        with self.servers_lock:
            serverlist = sorted(self.servers.keys())
        return serverlist
        
    def tunnelkey(self, n1num, n2num):
        ''' Compute a 32-bit key used to uniquely identify a GRE tunnel.
        The hash(n1num), hash(n2num) values are used, so node numbers may be
        None or string values (used for e.g. "ctrlnet").
        '''
        sid = self.session_id_master
        if sid is None:
            # this is the master session
            sid = self.session.sessionid
            
        key = (sid  << 16) ^ hash(n1num)  ^ (hash(n2num) << 8)
        return key & 0xFFFFFFFF
    
    def addtunnel(self, remoteip, n1num, n2num, localnum):
        ''' Add a new GreTapBridge between nodes on two different machines.
        '''
        key = self.tunnelkey(n1num, n2num)
        if localnum == n2num:
            remotenum = n1num
        else:
            remotenum = n2num
        if key in self.tunnels.keys():
            self.session.warn("tunnel with key %s (%s-%s) already exists!" % \
                              (key, n1num, n2num))
        else:
            objid = key & ((1<<16)-1)
            self.session.info("Adding tunnel for %s-%s to %s with key %s" % \
                              (n1num, n2num, remoteip, key))
            if localnum in self.phys:
                # no bridge is needed on physical nodes; use the GreTap directly
                gt = GreTap(node=None, name=None, session=self.session,
                                remoteip=remoteip, key=key)
            else:
                gt = self.session.addobj(cls = GreTapBridge, objid = objid,
                                    policy="ACCEPT", remoteip=remoteip, key = key)
            gt.localnum = localnum
            gt.remotenum = remotenum
            self.tunnels[key] = gt
            
    def addnettunnels(self):
        ''' Add GreTaps between network devices on different machines.
        The GreTapBridge is not used since that would add an extra bridge.
        '''
        for n in self.nets:
            self.addnettunnel(n)
            
    def addnettunnel(self, n):
        try:
            net = self.session.obj(n)
        except KeyError:
            raise KeyError, "network node %s not found" % n
        # add other nets here that do not require tunnels
        if isinstance(net, EmaneNet):
            return None
        if isinstance(net, CtrlNet):
            if hasattr(net, 'serverintf'):
                if net.serverintf is not None:
                    return None
            
        servers = self.getserversbynode(n)
        if len(servers) < 2:
            return None
        hosts = []
        for server in servers:
            (host, port, sock) = self.getserver(server)
            if host is None:
                continue
            hosts.append(host)
        if len(hosts) == 0:
            # get IP address from API message sender (master)
            self.session._handlerslock.acquire()
            for h in self.session._handlers:
                if h.client_address != "":
                    hosts.append(h.client_address[0])
            self.session._handlerslock.release()
        
        r = []
        for host in hosts:
            if self.myip:
                # we are the remote emulation server
                myip = self.myip
            else:
                # we are the session master
                myip = host
            key = self.tunnelkey(n, IPAddr.toint(myip))
            if key in self.tunnels.keys():
                continue
            self.session.info("Adding tunnel for net %s to %s with key %s" % \
                              (n, host, key))
            gt = GreTap(node=None, name=None, session=self.session,
                            remoteip=host, key=key)
            self.tunnels[key] = gt
            r.append(gt)
            # attaching to net will later allow gt to be destroyed 
            # during net.shutdown()
            net.attach(gt)
        return r
            
    def deltunnel(self, n1num, n2num):
        ''' Cleanup of the GreTapBridge.
        '''
        key = self.tunnelkey(n1num, n2num)
        try:
            gt = self.tunnels.pop(key)
        except KeyError:
            gt = None
        if gt:
            self.session.delobj(gt.objid)
            del gt
    
    def gettunnel(self, n1num, n2num):
        ''' Return the GreTap between two nodes if it exists.
        '''
        key = self.tunnelkey(n1num, n2num)
        if key in self.tunnels.keys():
            return self.tunnels[key]
        else:
            return None

    def addnodemap(self, server, nodenum):
        ''' Record a node number to emulation server mapping.
        '''
        self.nodemap_lock.acquire()
        if nodenum in self.nodemap:
            if server in self.nodemap[nodenum]:
                self.nodemap_lock.release()
                return
            self.nodemap[nodenum].append(server)
        else:
            self.nodemap[nodenum] = [server,]
        if server in self.nodecounts:
            self.nodecounts[server] += 1
        else:
            self.nodecounts[server] = 1
        self.nodemap_lock.release()
    
    def delnodemap(self, sock, nodenum):
        ''' Remove a node number to emulation server mapping.
            Return the number of nodes left on this server.
        '''
        self.nodemap_lock.acquire()
        count = None
        if nodenum not in self.nodemap:
            self.nodemap_lock.release()
            return count
        found = False
        for server in self.nodemap[nodenum]:
            (host, port, srvsock) = self.getserver(server)
            if srvsock == sock:
                found = True
                break
        if server in self.nodecounts:
            count = self.nodecounts[server]
        if found:
            self.nodemap[nodenum].remove(server)
            if server in self.nodecounts:
                count -= 1
                self.nodecounts[server] = count
        self.nodemap_lock.release()
        return count
    
    def incrbootcount(self):
        ''' Count a node that has booted.
        '''
        self.bootcount += 1
        return self.bootcount
            
    def getbootcount(self):
        ''' Return the number of booted nodes.
        '''
        return self.bootcount

    def getserversbynode(self, nodenum):
        ''' Retrieve a list of emulation servers given a node number.
        '''
        self.nodemap_lock.acquire()
        if nodenum not in self.nodemap:
            self.nodemap_lock.release()
            return []
        r = self.nodemap[nodenum]
        self.nodemap_lock.release()
        return r

    def addnet(self, nodenum):
        ''' Add a node number to the list of link-layer nodes.
        '''
        if nodenum not in self.nets:
            self.nets.append(nodenum)

    def addphys(self, nodenum):
        ''' Add a node number to the list of physical nodes.
        '''
        if nodenum not in self.phys:
            self.phys.append(nodenum)

    def configure_reset(self, msg):
        ''' Ignore reset messages, because node delete responses may still 
            arrive and require the use of nodecounts.
        '''
        return None

    def configure_values(self, msg, values):
        ''' Receive configuration message with a list of server:host:port
            combinations that we'll need to connect with.
        '''
        objname = msg.gettlv(coreapi.CORE_TLV_CONF_OBJ)
        conftype = msg.gettlv(coreapi.CORE_TLV_CONF_TYPE)
        
        if values is None:
            self.session.info("emulation server data missing")
            return None
        values = values.split('|')       
        # string of "server:ip:port,server:ip:port,..."
        serverstrings = values[0]
        server_list = serverstrings.split(',')
        for server in server_list:
            server_items = server.split(':')
            (name, host, port) = server_items[:3]
            if host == '':
                host = None
            if port == '':
                port = None
            else:
                port = int(port)
            sid = msg.gettlv(coreapi.CORE_TLV_CONF_SESSION)
            if sid is not None:
                # receive session ID and my IP from master
                self.session_id_master = int(sid.split('|')[0])
                self.myip = host
                host = None
                port = None
            # this connects to the server immediately; maybe we should wait
            # or spin off a new "client" thread here
            self.addserver(name, host, port)
            self.setupserver(name)
        return None

    def handlemsg(self, msg):
        ''' Handle an API message. Determine whether this needs to be handled
            by the local server or forwarded on to another one. 
            Returns True when message does not need to be handled locally,
            and performs forwarding if required.
            Returning False indicates this message should be handled locally.
        '''
        serverlist = []
        handle_locally = False
        # Do not forward messages when in definition state 
        # (for e.g. configuring services)
        if self.session.getstate() == coreapi.CORE_EVENT_DEFINITION_STATE:
            handle_locally = True
            return not handle_locally
        # Decide whether message should be handled locally or forwarded, or both
        if msg.msgtype == coreapi.CORE_API_NODE_MSG:
            (handle_locally, serverlist) = self.handlenodemsg(msg)
        elif msg.msgtype == coreapi.CORE_API_EVENT_MSG:
            # broadcast events everywhere
            serverlist = self.getserverlist()
        elif msg.msgtype == coreapi.CORE_API_CONF_MSG:
            # broadcast location and services configuration everywhere
            confobj = msg.gettlv(coreapi.CORE_TLV_CONF_OBJ)
            if confobj == "location" or confobj == "services" or \
               confobj == "session" or confobj == "all":
                serverlist = self.getserverlist()
        elif msg.msgtype == coreapi.CORE_API_FILE_MSG:
            # broadcast hook scripts and custom service files everywhere
            filetype = msg.gettlv(coreapi.CORE_TLV_FILE_TYPE)
            if filetype is not None and \
                (filetype[:5] == "hook:" or filetype[:8] == "service:"):
                serverlist = self.getserverlist()

        if msg.msgtype == coreapi.CORE_API_LINK_MSG:
            # prepare a serverlist from two node numbers in link message
            (handle_locally, serverlist, msg) = self.handlelinkmsg(msg)
        elif len(serverlist) == 0:
            # check for servers based on node numbers in all messages but link
            nn = msg.nodenumbers()
            if len(nn) == 0:
                return False
            serverlist = self.getserversbynode(nn[0])

        if len(serverlist) == 0: 
            handle_locally = True

        # allow other handlers to process this message
        # (this is used by e.g. EMANE to use the link add message to keep counts
        # of interfaces on other servers)
        for handler in self.handlers:
            handler(msg)

        # Perform any message forwarding
        handle_locally = self.forwardmsg(msg, serverlist, handle_locally)
        return not handle_locally

    def setupserver(self, server):
        ''' Send the appropriate API messages for configuring the specified
            emulation server.
        '''
        (host, port, sock) = self.getserver(server)
        if host is None or sock is None:
            return
        # communicate this session's current state to the server
        tlvdata = coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                            self.session.getstate())
        msg = coreapi.CoreEventMessage.pack(0, tlvdata)
        sock.send(msg)
        # send a Configuration message for the broker object and inform the
        # server of its local name
        tlvdata = ""
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_OBJ, "broker")
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_TYPE,
                                            coreapi.CONF_TYPE_FLAGS_UPDATE)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_DATA_TYPES,
                                            (coreapi.CONF_DATA_TYPE_STRING,))
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_VALUES,
                                            "%s:%s:%s" % (server, host, port))
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_SESSION,
                                            "%s" % self.session.sessionid)
        msg = coreapi.CoreConfMessage.pack(0, tlvdata)
        sock.send(msg)

    @staticmethod
    def fixupremotetty(msghdr, msgdata, host):
        ''' When an interactive TTY request comes from the GUI, snoop the reply
            and add an SSH command to the appropriate remote server.
        '''
        msgtype, msgflags, msglen = coreapi.CoreMessage.unpackhdr(msghdr)
        msgcls = coreapi.msg_class(msgtype)
        msg = msgcls(msgflags, msghdr, msgdata)

        nodenum = msg.gettlv(coreapi.CORE_TLV_EXEC_NODE)
        execnum = msg.gettlv(coreapi.CORE_TLV_EXEC_NUM)
        cmd = msg.gettlv(coreapi.CORE_TLV_EXEC_CMD)
        res = msg.gettlv(coreapi.CORE_TLV_EXEC_RESULT)

        tlvdata = ""
        tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_NODE, nodenum)
        tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_NUM, execnum)
        tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_CMD, cmd)
        title = "\\\"CORE: n%s @ %s\\\"" % (nodenum, host)
        res = "ssh -X -f " + host + " xterm -e " + res
        tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_RESULT, res)

        return coreapi.CoreExecMessage.pack(msgflags, tlvdata)

    def handlenodemsg(self, msg):
        ''' Determine and return the servers to which this node message should
            be forwarded. Also keep track of link-layer nodes and the mapping of
            nodes to servers.
        '''
        serverlist = []
        handle_locally = False
        serverfiletxt = None
        # snoop Node Message for emulation server TLV and record mapping
        n = msg.tlvdata[coreapi.CORE_TLV_NODE_NUMBER]
        # replicate link-layer nodes on all servers
        nodetype = msg.gettlv(coreapi.CORE_TLV_NODE_TYPE)
        if nodetype is not None:
            try:
                nodecls = coreapi.node_class(nodetype)
            except KeyError:
                self.session.warn("broker invalid node type %s" % nodetype)
                return (False, serverlist)
            if nodecls is None:
                self.session.warn("broker unimplemented node type %s" % nodetype)
                return (False, serverlist)
            if issubclass(nodecls, PyCoreNet) and \
                nodetype != coreapi.CORE_NODE_WLAN:
                # network node replicated on all servers; could be optimized
                # don't replicate WLANs, because ebtables rules won't work
                serverlist = self.getserverlist()
                handle_locally = True
                self.addnet(n)
                for server in serverlist:
                    self.addnodemap(server, n)
                # do not record server name for networks since network
                # nodes are replicated across all server
                return (handle_locally, serverlist)
            if issubclass(nodecls, PyCoreNet) and \
                nodetype == coreapi.CORE_NODE_WLAN:
                # special case where remote WLANs not in session._objs, and no
                # node response message received, so they are counted here
                if msg.gettlv(coreapi.CORE_TLV_NODE_EMUSRV) is not None:
                    self.incrbootcount()
            elif issubclass(nodecls, PyCoreNode):
                name = msg.gettlv(coreapi.CORE_TLV_NODE_NAME)
                if name:
                    serverfiletxt = "%s %s %s" % (n, name, nodecls)
                if issubclass(nodecls, PhysicalNode):
                    # remember physical nodes
                    self.addphys(n)
            
        # emulation server TLV specifies server
        server = msg.gettlv(coreapi.CORE_TLV_NODE_EMUSRV)
        if server is not None:
            self.addnodemap(server, n)
            if server not in serverlist:
                serverlist.append(server)
            if serverfiletxt and self.session.master:
                self.writenodeserver(serverfiletxt, server)
        # hook to update coordinates of physical nodes
        if n in self.phys:
            self.session.mobility.physnodeupdateposition(msg)
        return (handle_locally, serverlist)
    
    def handlelinkmsg(self, msg):
        ''' Determine and return the servers to which this link message should
            be forwarded. Also build tunnels between different servers or add
            opaque data to the link message before forwarding.
        '''
        serverlist = []
        handle_locally = False

        # determine link message destination using non-network nodes
        nn = msg.nodenumbers()
        if nn[0] in self.nets:
            if nn[1] in self.nets:
                # two network nodes linked together - prevent loops caused by
                # the automatic tunnelling
                handle_locally = True
            else:
                serverlist = self.getserversbynode(nn[1])
        elif nn[1] in self.nets:
            serverlist = self.getserversbynode(nn[0])
        else:
            serverset1 = set(self.getserversbynode(nn[0]))
            serverset2 = set(self.getserversbynode(nn[1]))
            # nodes are on two different servers, build tunnels as needed
            if serverset1 != serverset2:
                localn = None
                if len(serverset1) == 0 or len(serverset2) == 0:
                    handle_locally = True
                serverlist = list(serverset1 | serverset2)
                host = None
                # get the IP of remote server and decide which node number
                # is for a local node
                for server in serverlist:
                    (host, port, sock) = self.getserver(server)
                    if host is None:
                        # named server is local
                        handle_locally = True
                        if server in serverset1:
                            localn = nn[0]
                        else:
                            localn = nn[1]
                if handle_locally and localn is None:
                    # having no local node at this point indicates local node is
                    # the one with the empty serverset
                    if len(serverset1) == 0:
                        localn = nn[0]
                    elif len(serverset2) == 0:
                        localn = nn[1]
                if host is None:
                    host = self.getlinkendpoint(msg, localn == nn[0])
                if localn is None:
                    msg = self.addlinkendpoints(msg, serverset1, serverset2)
                elif msg.flags & coreapi.CORE_API_ADD_FLAG:
                    self.addtunnel(host, nn[0], nn[1], localn)
                elif msg.flags & coreapi.CORE_API_DEL_FLAG:
                    self.deltunnel(nn[0], nn[1])
                    handle_locally = False
            else:
                serverlist = list(serverset1 | serverset2)

        return (handle_locally, serverlist, msg)

    def addlinkendpoints(self, msg, serverset1, serverset2):
        ''' For a link message that is not handled locally, inform the remote
            servers of the IP addresses used as tunnel endpoints by adding
            opaque data to the link message.
        '''
        ip1 = ""
        for server in serverset1:
            (host, port, sock) = self.getserver(server)
            if host is not None:
                ip1 = host
        ip2 = ""
        for server in serverset2:
            (host, port, sock) = self.getserver(server)
            if host is not None:
                ip2 = host
        tlvdata = msg.rawmsg[coreapi.CoreMessage.hdrsiz:] 
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_OPAQUE,
                                    "%s:%s" % (ip1, ip2))
        newraw = coreapi.CoreLinkMessage.pack(msg.flags, tlvdata)
        msghdr = newraw[:coreapi.CoreMessage.hdrsiz] 
        return coreapi.CoreLinkMessage(msg.flags, msghdr, tlvdata)

    def getlinkendpoint(self, msg, first_is_local):
        ''' A link message between two different servers has been received,
            and we need to determine the tunnel endpoint. First look for
            opaque data in the link message, otherwise use the IP of the message
            sender (the master server).
        '''
        host = None
        opaque = msg.gettlv(coreapi.CORE_TLV_LINK_OPAQUE)
        if opaque is not None:
            if first_is_local:
                host = opaque.split(':')[1]
            else:
                host = opaque.split(':')[0]
            if host == "":
                host = None
        if host is None:
            # get IP address from API message sender (master)
            self.session._handlerslock.acquire()
            for h in self.session._handlers:
                if h.client_address != "":
                    host = h.client_address[0]
            self.session._handlerslock.release()
        return host

    def handlerawmsg(self, msg):
        ''' Helper to invoke handlemsg() using raw (packed) message bytes.
        '''
        hdr = msg[:coreapi.CoreMessage.hdrsiz]
        msgtype, flags, msglen = coreapi.CoreMessage.unpackhdr(hdr)
        msgcls = coreapi.msg_class(msgtype)
        return self.handlemsg(msgcls(flags, hdr, msg[coreapi.CoreMessage.hdrsiz:]))
        
    def forwardmsg(self, msg, serverlist, handle_locally):
        ''' Forward API message to all servers in serverlist; if an empty 
            host/port is encountered, set the handle_locally flag. Returns the
            value of the handle_locally flag, which may be unchanged.
        '''
        for server in serverlist:
            try:
                (host, port, sock) = self.getserver(server)
            except KeyError:
                # server not found, don't handle this message locally
                self.session.info("broker could not find server %s, message " \
                                  "with type %s dropped" % \
                                  (server, msg.msgtype))
                continue
            if host is None and port is None:
                # local emulation server, handle this locally
                handle_locally = True
            else:
                if sock is None:
                    self.session.info("server %s @ %s:%s is disconnected" % \
                                      (server, host, port))
                else:
                    sock.send(msg.rawmsg)
        return handle_locally

    def writeservers(self):
        ''' Write the server list to a text file in the session directory upon
        startup: /tmp/pycore.nnnnn/servers
        '''
        filename = os.path.join(self.session.sessiondir, "servers")
        try:
            f = open(filename, "w")
            master = self.session_id_master
            if master is None:
                master = self.session.sessionid
            f.write("master=%s\n" % master)
            self.servers_lock.acquire()
            for name in sorted(self.servers.keys()):
                if name == "localhost":
                    continue
                (host, port, sock) = self.servers[name]
                try:
                    (lhost, lport) = sock.getsockname()
                except:
                    lhost, lport = None, None
                f.write("%s %s %s %s %s\n" % (name, host, port, lhost, lport))
            f.close()
        except Exception, e:
            self.session.warn("Error writing server list to the file: %s\n%s" \
                        % (filename, e))
        finally:
            self.servers_lock.release()

    def writenodeserver(self, nodestr, server):
        ''' Creates a /tmp/pycore.nnnnn/nX.conf/server file having the node
        and server info. This may be used by scripts for accessing nodes on
        other machines, much like local nodes may be accessed via the
        VnodeClient class.
        '''
        (host, port, sock) = self.getserver(server)
        serverstr = "%s %s %s" % (server, host, port)
        name = nodestr.split()[1]
        dirname = os.path.join(self.session.sessiondir, name + ".conf")
        filename = os.path.join(dirname, "server")
        try:
            os.makedirs(dirname)
        except OSError:
            # directory may already exist from previous distributed run
            pass
        try:
            f = open(filename, "w")
            f.write("%s\n%s\n" % (serverstr, nodestr))
            f.close()
            return True
        except Exception, e:
            msg = "Error writing server file '%s'" % filename
            msg += "for node %s:\n%s" % (name, e)
            self.session.warn(msg)
            return False


