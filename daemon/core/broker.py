"""
broker.py: definition of CoreBroker class that is part of the
pycore session object. Handles distributing parts of the emulation out to
other emulation servers. The broker is consulted during the
CoreRequestHandler.handlemsg() loop to determine if messages should be handled
locally or forwarded on to another emulation server.
"""

import os
import select
import socket
import threading

from core.api import coreapi
from core.conf import ConfigurableManager
from core.coreobj import PyCoreNet
from core.coreobj import PyCoreNode
from core.enumerations import ConfigDataTypes
from core.enumerations import ConfigFlags
from core.enumerations import ConfigTlvs
from core.enumerations import EventTlvs
from core.enumerations import EventTypes
from core.enumerations import ExecuteTlvs
from core.enumerations import FileTlvs
from core.enumerations import LinkTlvs
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.enumerations import NodeTlvs
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.misc import log
from core.misc import nodeutils
from core.misc.ipaddress import IpAddress
from core.netns.vif import GreTap
from core.netns.vnet import GreTapBridge
from core.phys.pnodes import PhysicalNode

logger = log.get_logger(__name__)


class CoreBroker(ConfigurableManager):
    """
    Member of pycore session class for handling global emulation server data.
    """
    name = "broker"
    config_type = RegisterTlvs.UTILITY.value

    def __init__(self, session):
        """
        Creates a CoreBroker instance.

        :param core.session.Session session: session this manager is tied to
        :return: nothing
        """

        ConfigurableManager.__init__(self)
        self.session = session
        self.session_handler = None
        self.session_id_master = None
        self.myip = None
        # dict containing tuples of (host, port, sock)
        self.servers = {}
        self.servers_lock = threading.Lock()
        self.addserver("localhost", None, None)
        # dict containing node number to server name mapping
        self.nodemap = {}
        # this lock also protects self.nodecounts
        self.nodemap_lock = threading.Lock()
        # reference counts of nodes on servers
        self.nodecounts = {}
        self.bootcount = 0
        # list of node numbers that are link-layer nodes (networks)
        self.network_nodes = []
        # list of node numbers that are PhysicalNode nodes
        self.physical_nodes = []
        # allows for other message handlers to process API messages (e.g. EMANE)
        self.handlers = ()
        # dict with tunnel key to tunnel device mapping
        self.tunnels = {}
        self.dorecvloop = False
        self.recvthread = None

    def startup(self):
        """
        Build tunnels between network-layer nodes now that all node
        and link information has been received; called when session
        enters the instantation state.
        """
        self.addnettunnels()
        self.writeservers()

    def shutdown(self):
        """
        Close all active sockets; called when the session enters the
        data collect state
        """
        with self.servers_lock:
            while len(self.servers) > 0:
                server, v = self.servers.popitem()
                host, port, sock = v
                if sock is None:
                    continue
                logger.info("closing connection with %s @ %s:%s", server, host, port)
                sock.close()
        self.reset()
        self.dorecvloop = False
        if self.recvthread is not None:
            self.recvthread.join()

    def reset(self):
        """
        Reset to initial state.
        """
        self.nodemap_lock.acquire()
        self.nodemap.clear()
        for server in self.nodecounts:
            if self.nodecounts[server] < 1:
                self.delserver(server)
        self.nodecounts.clear()
        self.bootcount = 0
        self.nodemap_lock.release()
        del self.network_nodes[:]
        del self.physical_nodes[:]
        while len(self.tunnels) > 0:
            key, gt = self.tunnels.popitem()
            gt.shutdown()

    def startrecvloop(self):
        """
        Spawn the recvloop() thread if it hasn't been already started.
        """
        if self.recvthread is not None:
            if self.recvthread.isAlive():
                return
            else:
                self.recvthread.join()
        # start reading data from connected sockets
        self.dorecvloop = True
        self.recvthread = threading.Thread(target=self.recvloop)
        self.recvthread.daemon = True
        self.recvthread.start()

    def recvloop(self):
        """
        Thread target that receives messages from server sockets.
        """
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
                    logger.exception("get server by sock error")
                    break
                rcvlen = self.recv(sock, h)
                if rcvlen == 0:
                    logger.info("connection with %s @ %s:%s has closed", name, h, p)
                    self.servers[name] = (h, p, None)

    def recv(self, sock, host):
        """
        Receive data on an emulation server socket and broadcast it to
        all connected session handlers. Returns the length of data recevied
        and forwarded. Return value of zero indicates the socket has closed
        and should be removed from the self.servers dict.
        """
        msghdr = sock.recv(coreapi.CoreMessage.header_len)
        if len(msghdr) == 0:
            # server disconnected
            sock.close()
            return 0
        if len(msghdr) != coreapi.CoreMessage.header_len:
            logger.info("warning: broker received not enough data len=%s" % len(msghdr))
            return len(msghdr)

        msgtype, msgflags, msglen = coreapi.CoreMessage.unpack_header(msghdr)
        msgdata = sock.recv(msglen)
        data = msghdr + msgdata
        count = None
        # snoop exec response for remote interactive TTYs
        if msgtype == MessageTypes.EXECUTE.value and msgflags & MessageFlags.TTY.value:
            data = self.fixupremotetty(msghdr, msgdata, host)
        elif msgtype == MessageTypes.NODE.value:
            # snoop node delete response to decrement node counts
            if msgflags & MessageFlags.DELETE.value:
                msg = coreapi.CoreNodeMessage(msgflags, msghdr, msgdata)
                nodenum = msg.get_tlv(NodeTlvs.NUMBER.value)
                if nodenum is not None:
                    count = self.delnodemap(sock, nodenum)
            # snoop node add response to increment booted node count
            # (only CoreNodes send these response messages)
            elif msgflags & (MessageFlags.ADD.value | MessageFlags.LOCAL.value):
                self.incrbootcount()
                self.session.check_runtime()
        elif msgtype == MessageTypes.LINK.value:
            # this allows green link lines for remote WLANs
            msg = coreapi.CoreLinkMessage(msgflags, msghdr, msgdata)
            self.session.sdt.handle_distributed(msg)
        else:
            logger.error("unknown message type received: %s", msgtype)

        try:
            self.session_handler.sendall(data)
        except IOError:
            logger.exception("error sending message")

        if count is not None and count < 1:
            return 0
        else:
            return len(data)

    def addserver(self, name, host, port):
        """
        Add a new server, and try to connect to it. If we're already
        connected to this (host, port), then leave it alone. When host,port
        is None, do not try to connect.
        """
        self.servers_lock.acquire()
        if name in self.servers:
            oldhost, oldport, sock = self.servers[name]
            if host == oldhost or port == oldport:
                # leave this socket connected
                if sock is not None:
                    self.servers_lock.release()
                    return
            if host is not None and sock is not None:
                logger.info("closing connection with %s @ %s:%s", name, host, port)
            if sock is not None:
                sock.close()
        self.servers_lock.release()
        if host is not None:
            logger.info("adding server %s @ %s:%s", name, host, port)
        if host is None:
            sock = None
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # sock.setblocking(0)
            # error = sock.connect_ex((host, port))
            try:
                sock.connect((host, port))
                self.startrecvloop()
            except IOError:
                logger.exception("error connecting to server %s:%s", host, port)
                sock.close()
                sock = None
        self.servers_lock.acquire()
        self.servers[name] = (host, port, sock)
        self.servers_lock.release()

    def delserver(self, name):
        """
        Remove a server and hang up any connection.
        """
        self.servers_lock.acquire()
        if name not in self.servers:
            self.servers_lock.release()
            return
        (host, port, sock) = self.servers.pop(name)
        if sock is not None:
            logger.info("closing connection with %s @ %s:%s", name, host, port)
            sock.close()
        self.servers_lock.release()

    def getserver(self, name):
        """
        Return the (host, port, sock) tuple, or raise a KeyError exception.
        """
        if name not in self.servers:
            raise KeyError("emulation server %s not found" % name)
        return self.servers[name]

    def getserverbysock(self, sockfd):
        """
        Return a (host, port, sock, name) tuple based on socket file
        descriptor, or raise a KeyError exception.
        """
        with self.servers_lock:
            for name in self.servers:
                (host, port, sock) = self.servers[name]
                if sock is None:
                    continue
                if sock.fileno() == sockfd:
                    return host, port, sock, name
        raise KeyError("socket fd %s not found" % sockfd)

    def getserverlist(self):
        """
        Return the list of server names (keys from self.servers).
        """
        with self.servers_lock:
            serverlist = sorted(self.servers.keys())
        return serverlist

    def tunnelkey(self, n1num, n2num):
        """
        Compute a 32-bit key used to uniquely identify a GRE tunnel.
        The hash(n1num), hash(n2num) values are used, so node numbers may be
        None or string values (used for e.g. "ctrlnet").
        """
        sid = self.session_id_master
        if sid is None:
            # this is the master session
            sid = self.session.session_id

        key = (sid << 16) ^ hash(n1num) ^ (hash(n2num) << 8)
        return key & 0xFFFFFFFF

    def addtunnel(self, remoteip, n1num, n2num, localnum):
        """
        Add a new GreTapBridge between nodes on two different machines.
        """
        key = self.tunnelkey(n1num, n2num)
        if localnum == n2num:
            remotenum = n1num
        else:
            remotenum = n2num
        if key in self.tunnels.keys():
            logger.warn("tunnel with key %s (%s-%s) already exists!" % (key, n1num, n2num))
        else:
            objid = key & ((1 << 16) - 1)
            logger.info("Adding tunnel for %s-%s to %s with key %s", n1num, n2num, remoteip, key)
            if localnum in self.physical_nodes:
                # no bridge is needed on physical nodes; use the GreTap directly
                gt = GreTap(node=None, name=None, session=self.session,
                            remoteip=remoteip, key=key)
            else:
                gt = self.session.add_object(cls=GreTapBridge, objid=objid,
                                             policy="ACCEPT", remoteip=remoteip, key=key)
            gt.localnum = localnum
            gt.remotenum = remotenum
            self.tunnels[key] = gt

    def addnettunnels(self):
        """
        Add GreTaps between network devices on different machines.
        The GreTapBridge is not used since that would add an extra bridge.
        """
        for n in self.network_nodes:
            self.addnettunnel(n)

    def addnettunnel(self, n):
        try:
            net = self.session.get_object(n)
        except KeyError:
            raise KeyError, "network node %s not found" % n
        # add other nets here that do not require tunnels
        if nodeutils.is_node(net, NodeTypes.EMANE_NET):
            return None
        if nodeutils.is_node(net, NodeTypes.CONTROL_NET):
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
            key = self.tunnelkey(n, IpAddress.to_int(myip))
            if key in self.tunnels.keys():
                continue
            logger.info("Adding tunnel for net %s to %s with key %s" % (n, host, key))
            gt = GreTap(node=None, name=None, session=self.session, remoteip=host, key=key)
            self.tunnels[key] = gt
            r.append(gt)
            # attaching to net will later allow gt to be destroyed
            # during net.shutdown()
            net.attach(gt)
        return r

    def deltunnel(self, n1num, n2num):
        """
        Cleanup of the GreTapBridge.
        """
        key = self.tunnelkey(n1num, n2num)
        try:
            gt = self.tunnels.pop(key)
        except KeyError:
            gt = None
        if gt:
            self.session.delete_object(gt.objid)
            del gt

    def gettunnel(self, n1num, n2num):
        """
        Return the GreTap between two nodes if it exists.
        """
        key = self.tunnelkey(n1num, n2num)
        if key in self.tunnels.keys():
            return self.tunnels[key]
        else:
            return None

    def addnodemap(self, server, nodenum):
        """
        Record a node number to emulation server mapping.
        """
        self.nodemap_lock.acquire()
        if nodenum in self.nodemap:
            if server in self.nodemap[nodenum]:
                self.nodemap_lock.release()
                return
            self.nodemap[nodenum].append(server)
        else:
            self.nodemap[nodenum] = [server, ]
        if server in self.nodecounts:
            self.nodecounts[server] += 1
        else:
            self.nodecounts[server] = 1
        self.nodemap_lock.release()

    def delnodemap(self, sock, nodenum):
        """
        Remove a node number to emulation server mapping.
        Return the number of nodes left on this server.
        """
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
        """
        Count a node that has booted.
        """
        self.bootcount += 1
        return self.bootcount

    def getbootcount(self):
        """
        Return the number of booted nodes.
        """
        return self.bootcount

    def getserversbynode(self, nodenum):
        """
        Retrieve a list of emulation servers given a node number.
        """
        self.nodemap_lock.acquire()
        if nodenum not in self.nodemap:
            self.nodemap_lock.release()
            return []
        r = self.nodemap[nodenum]
        self.nodemap_lock.release()
        return r

    def addnet(self, nodenum):
        """
        Add a node number to the list of link-layer nodes.
        """
        if nodenum not in self.network_nodes:
            self.network_nodes.append(nodenum)

    def addphys(self, nodenum):
        """
        Add a node number to the list of physical nodes.
        """
        if nodenum not in self.physical_nodes:
            self.physical_nodes.append(nodenum)

    def configure_reset(self, config_data):
        """
        Ignore reset messages, because node delete responses may still
        arrive and require the use of nodecounts.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :return: None
        """
        return None

    def configure_values(self, config_data):
        """
        Receive configuration message with a list of server:host:port
        combinations that we'll need to connect with.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :return: None
        """
        values = config_data.data_values
        session_id = config_data.session

        if values is None:
            logger.info("emulation server data missing")
            return None
        values = values.split('|')

        # string of "server:ip:port,server:ip:port,..."
        server_strings = values[0]
        server_list = server_strings.split(',')

        for server in server_list:
            server_items = server.split(':')
            (name, host, port) = server_items[:3]

            if host == '':
                host = None

            if port == '':
                port = None
            else:
                port = int(port)

            if session_id is not None:
                # receive session ID and my IP from master
                self.session_id_master = int(session_id.split('|')[0])
                self.myip = host
                host = None
                port = None

            # this connects to the server immediately; maybe we should wait
            # or spin off a new "client" thread here
            self.addserver(name, host, port)
            self.setupserver(name)

        return None

    def handle_message(self, message):
        """
        Handle an API message. Determine whether this needs to be handled
        by the local server or forwarded on to another one.
        Returns True when message does not need to be handled locally,
        and performs forwarding if required.
        Returning False indicates this message should be handled locally.
        """
        serverlist = []
        handle_locally = False
        # Do not forward messages when in definition state
        # (for e.g. configuring services)
        if self.session.state == EventTypes.DEFINITION_STATE.value:
            handle_locally = True
            return not handle_locally
        # Decide whether message should be handled locally or forwarded, or both
        if message.message_type == MessageTypes.NODE.value:
            (handle_locally, serverlist) = self.handlenodemsg(message)
        elif message.message_type == MessageTypes.EVENT.value:
            # broadcast events everywhere
            serverlist = self.getserverlist()
        elif message.message_type == MessageTypes.CONFIG.value:
            # broadcast location and services configuration everywhere
            confobj = message.get_tlv(ConfigTlvs.OBJECT.value)
            if confobj == "location" or confobj == "services" or \
                    confobj == "session" or confobj == "all":
                serverlist = self.getserverlist()
        elif message.message_type == MessageTypes.FILE.value:
            # broadcast hook scripts and custom service files everywhere
            filetype = message.get_tlv(FileTlvs.TYPE.value)
            if filetype is not None and (filetype[:5] == "hook:" or filetype[:8] == "service:"):
                serverlist = self.getserverlist()
        if message.message_type == MessageTypes.LINK.value:
            # prepare a serverlist from two node numbers in link message
            (handle_locally, serverlist, message) = self.handlelinkmsg(message)
        elif len(serverlist) == 0:
            # check for servers based on node numbers in all messages but link
            nn = message.node_numbers()
            if len(nn) == 0:
                return False
            serverlist = self.getserversbynode(nn[0])

        if len(serverlist) == 0:
            handle_locally = True

        # allow other handlers to process this message
        # (this is used by e.g. EMANE to use the link add message to keep counts
        # of interfaces on other servers)
        for handler in self.handlers:
            handler(message)

        # Perform any message forwarding
        handle_locally = self.forwardmsg(message, serverlist, handle_locally)
        return not handle_locally

    def setupserver(self, server):
        """
        Send the appropriate API messages for configuring the specified
        emulation server.
        """
        host, port, sock = self.getserver(server)
        if host is None or sock is None:
            return

        # communicate this session's current state to the server
        tlvdata = coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, self.session.state)
        msg = coreapi.CoreEventMessage.pack(0, tlvdata)
        sock.send(msg)

        # send a Configuration message for the broker object and inform the
        # server of its local name
        tlvdata = ""
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.OBJECT.value, "broker")
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.TYPE.value, ConfigFlags.UPDATE.value)
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.DATA_TYPES.value, (ConfigDataTypes.STRING.value,))
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.VALUES.value, "%s:%s:%s" % (server, host, port))
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.SESSION.value, "%s" % self.session.session_id)
        msg = coreapi.CoreConfMessage.pack(0, tlvdata)
        sock.send(msg)

    @staticmethod
    def fixupremotetty(msghdr, msgdata, host):
        """
        When an interactive TTY request comes from the GUI, snoop the reply
        and add an SSH command to the appropriate remote server.
        """
        msgtype, msgflags, msglen = coreapi.CoreMessage.unpack_header(msghdr)
        msgcls = coreapi.CLASS_MAP[msgtype]
        msg = msgcls(msgflags, msghdr, msgdata)

        nodenum = msg.get_tlv(ExecuteTlvs.NODE.value)
        execnum = msg.get_tlv(ExecuteTlvs.NUMBER.value)
        cmd = msg.get_tlv(ExecuteTlvs.COMMAND.value)
        res = msg.get_tlv(ExecuteTlvs.RESULT.value)

        tlvdata = ""
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, nodenum)
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.NUMBER.value, execnum)
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, cmd)
        title = "\\\"CORE: n%s @ %s\\\"" % (nodenum, host)
        res = "ssh -X -f " + host + " xterm -e " + res
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.RESULT.value, res)

        return coreapi.CoreExecMessage.pack(msgflags, tlvdata)

    def handlenodemsg(self, msg):
        """
        Determine and return the servers to which this node message should
        be forwarded. Also keep track of link-layer nodes and the mapping of
        nodes to servers.
        """
        serverlist = []
        handle_locally = False
        serverfiletxt = None
        # snoop Node Message for emulation server TLV and record mapping
        n = msg.tlv_data[NodeTlvs.NUMBER.value]
        # replicate link-layer nodes on all servers
        nodetype = msg.get_tlv(NodeTlvs.TYPE.value)
        if nodetype is not None:
            try:
                nodecls = nodeutils.get_node_class(NodeTypes(nodetype))
            except KeyError:
                logger.exception("broker invalid node type %s", nodetype)
                return False, serverlist
            if nodecls is None:
                logger.warn("broker unimplemented node type %s" % nodetype)
                return False, serverlist
            if issubclass(nodecls, PyCoreNet) and nodetype != NodeTypes.WIRELESS_LAN.value:
                # network node replicated on all servers; could be optimized
                # don't replicate WLANs, because ebtables rules won't work
                serverlist = self.getserverlist()
                handle_locally = True
                self.addnet(n)
                for server in serverlist:
                    self.addnodemap(server, n)
                # do not record server name for networks since network
                # nodes are replicated across all server
                return handle_locally, serverlist
            if issubclass(nodecls, PyCoreNet) and nodetype == NodeTypes.WIRELESS_LAN.value:
                # special case where remote WLANs not in session._objs, and no
                # node response message received, so they are counted here
                if msg.get_tlv(NodeTlvs.EMULATION_SERVER.value) is not None:
                    self.incrbootcount()
            elif issubclass(nodecls, PyCoreNode):
                name = msg.get_tlv(NodeTlvs.NAME.value)
                if name:
                    serverfiletxt = "%s %s %s" % (n, name, nodecls)
                if issubclass(nodecls, PhysicalNode):
                    # remember physical nodes
                    self.addphys(n)

        # emulation server TLV specifies server
        server = msg.get_tlv(NodeTlvs.EMULATION_SERVER.value)
        if server is not None:
            self.addnodemap(server, n)
            if server not in serverlist:
                serverlist.append(server)
            if serverfiletxt and self.session.master:
                self.writenodeserver(serverfiletxt, server)
        # hook to update coordinates of physical nodes
        if n in self.physical_nodes:
            self.session.mobility.physnodeupdateposition(msg)
        return handle_locally, serverlist

    def handlelinkmsg(self, msg):
        """
        Determine and return the servers to which this link message should
        be forwarded. Also build tunnels between different servers or add
        opaque data to the link message before forwarding.
        """
        serverlist = []
        handle_locally = False

        # determine link message destination using non-network nodes
        nn = msg.node_numbers()
        if nn[0] in self.network_nodes:
            if nn[1] in self.network_nodes:
                # two network nodes linked together - prevent loops caused by
                # the automatic tunnelling
                handle_locally = True
            else:
                serverlist = self.getserversbynode(nn[1])
        elif nn[1] in self.network_nodes:
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
                elif msg.flags & MessageFlags.ADD.value:
                    self.addtunnel(host, nn[0], nn[1], localn)
                elif msg.flags & MessageFlags.DELETE.value:
                    self.deltunnel(nn[0], nn[1])
                    handle_locally = False
            else:
                serverlist = list(serverset1 | serverset2)

        return handle_locally, serverlist, msg

    def addlinkendpoints(self, msg, serverset1, serverset2):
        """
        For a link message that is not handled locally, inform the remote
        servers of the IP addresses used as tunnel endpoints by adding
        opaque data to the link message.
        """
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
        tlvdata = msg.rawmsg[coreapi.CoreMessage.header_len:]
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.OPAQUE.value, "%s:%s" % (ip1, ip2))
        newraw = coreapi.CoreLinkMessage.pack(msg.flags, tlvdata)
        msghdr = newraw[:coreapi.CoreMessage.header_len]
        return coreapi.CoreLinkMessage(msg.flags, msghdr, tlvdata)

    def getlinkendpoint(self, msg, first_is_local):
        """
        A link message between two different servers has been received,
        and we need to determine the tunnel endpoint. First look for
        opaque data in the link message, otherwise use the IP of the message
        sender (the master server).
        """
        host = None
        opaque = msg.get_tlv(LinkTlvs.OPAQUE.value)
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
        """
        Helper to invoke handlemsg() using raw (packed) message bytes.
        """
        hdr = msg[:coreapi.CoreMessage.header_len]
        msgtype, flags, msglen = coreapi.CoreMessage.unpack_header(hdr)
        msgcls = coreapi.CLASS_MAP[msgtype]
        return self.handle_message(msgcls(flags, hdr, msg[coreapi.CoreMessage.header_len:]))

    def forwardmsg(self, message, serverlist, handle_locally):
        """
        Forward API message to all servers in serverlist; if an empty
        host/port is encountered, set the handle_locally flag. Returns the
        value of the handle_locally flag, which may be unchanged.

        :param coreapi.CoreMessage message: core message to forward
        :param list serverlist: server list to forward to
        :param bool handle_locally: used to determine if this should be handled locally
        :return: should message be handled locally
        :rtype: bool
        """
        for server in serverlist:
            try:
                (host, port, sock) = self.getserver(server)
            except KeyError:
                # server not found, don't handle this message locally
                logger.exception("broker could not find server %s, message with type %s dropped",
                                 server, message.message_type)
                continue
            if host is None and port is None:
                # local emulation server, handle this locally
                handle_locally = True
            else:
                if sock is None:
                    logger.info("server %s @ %s:%s is disconnected", server, host, port)
                else:
                    sock.send(message.raw_message)

        return handle_locally

    def writeservers(self):
        """
        Write the server list to a text file in the session directory upon
        startup: /tmp/pycore.nnnnn/servers
        """
        filename = os.path.join(self.session.session_dir, "servers")
        try:
            f = open(filename, "w")
            master = self.session_id_master
            if master is None:
                master = self.session.session_id
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
        except IOError:
            logger.exception("Error writing server list to the file: %s", filename)
        finally:
            self.servers_lock.release()

    def writenodeserver(self, nodestr, server):
        """
        Creates a /tmp/pycore.nnnnn/nX.conf/server file having the node
        and server info. This may be used by scripts for accessing nodes on
        other machines, much like local nodes may be accessed via the
        VnodeClient class.
        """
        (host, port, sock) = self.getserver(server)
        serverstr = "%s %s %s" % (server, host, port)
        name = nodestr.split()[1]
        dirname = os.path.join(self.session.session_dir, name + ".conf")
        filename = os.path.join(dirname, "server")

        try:
            os.makedirs(dirname)
        except OSError:
            logger.exception("error creating directory: %s", dirname)

        try:
            f = open(filename, "w")
            f.write("%s\n%s\n" % (serverstr, nodestr))
            f.close()
            return True
        except IOError:
            msg = "Error writing server file '%s'" % filename
            msg += "for node %s" % name
            logger.exception(msg)
            return False
