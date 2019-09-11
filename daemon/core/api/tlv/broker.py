"""
Broker class that is part of the session object. Handles distributing parts of the emulation out to
other emulation servers. The broker is consulted when handling messages to determine if messages
should be handled locally or forwarded on to another emulation server.
"""

import logging
import os
import select
import socket
import threading

from core import utils
from core.api.tlv import coreapi
from core.emulator.enumerations import (
    ConfigDataTypes,
    ConfigFlags,
    ConfigTlvs,
    EventTlvs,
    EventTypes,
    ExecuteTlvs,
    FileTlvs,
    LinkTlvs,
    MessageFlags,
    MessageTypes,
    NodeTlvs,
    NodeTypes,
    RegisterTlvs,
)
from core.nodes import nodeutils
from core.nodes.base import CoreNetworkBase, CoreNodeBase
from core.nodes.interface import GreTap
from core.nodes.ipaddress import IpAddress
from core.nodes.network import GreTapBridge
from core.nodes.physical import PhysicalNode


class CoreDistributedServer(object):
    """
    Represents CORE daemon servers for communication.
    """

    def __init__(self, name, host, port):
        """
        Creates a CoreServer instance.

        :param str name: name of the CORE server
        :param str host: server address
        :param int port: server port
        """
        self.name = name
        self.host = host
        self.port = port
        self.sock = None
        self.instantiation_complete = False

    def connect(self):
        """
        Connect to CORE server and save connection.

        :return: nothing
        """
        if self.sock:
            raise ValueError("socket already connected")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.connect((self.host, self.port))
        except IOError as e:
            sock.close()
            raise e

        self.sock = sock

    def close(self):
        """
        Close connection with CORE server.

        :return: nothing
        """
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class CoreBroker(object):
    """
    Helps with brokering messages between CORE daemon servers.
    """

    # configurable manager name
    name = "broker"

    # configurable manager type
    config_type = RegisterTlvs.UTILITY.value

    def __init__(self, session):
        """
        Creates a CoreBroker instance.

        :param core.emulator.session.Session session: session this manager is tied to
        :return: nothing
        """

        # ConfigurableManager.__init__(self)
        self.session = session
        self.session_clients = []
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
        # set of node numbers that are link-layer nodes (networks)
        self.network_nodes = set()
        # set of node numbers that are PhysicalNode nodes
        self.physical_nodes = set()
        # allows for other message handlers to process API messages (e.g. EMANE)
        self.handlers = set()
        # dict with tunnel key to tunnel device mapping
        self.tunnels = {}
        self.dorecvloop = False
        self.recvthread = None
        self.bootcount = 0

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
        self.reset()
        with self.servers_lock:
            while len(self.servers) > 0:
                name, server = self.servers.popitem()
                if server.sock is not None:
                    logging.info(
                        "closing connection with %s: %s:%s",
                        name,
                        server.host,
                        server.port,
                    )
                    server.close()
        self.dorecvloop = False
        if self.recvthread is not None:
            self.recvthread.join()

    def reset(self):
        """
        Reset to initial state.
        """
        logging.info("clearing state")
        self.nodemap_lock.acquire()
        self.nodemap.clear()
        for server in self.nodecounts:
            count = self.nodecounts[server]
            if count < 1:
                self.delserver(server)
        self.nodecounts.clear()
        self.bootcount = 0
        self.nodemap_lock.release()
        self.network_nodes.clear()
        self.physical_nodes.clear()
        while len(self.tunnels) > 0:
            _key, gt = self.tunnels.popitem()
            gt.shutdown()

    def startrecvloop(self):
        """
        Spawn the receive loop for receiving messages.
        """
        if self.recvthread is not None:
            logging.info("server receive loop already started")
            if self.recvthread.isAlive():
                return
            else:
                self.recvthread.join()
        # start reading data from connected sockets
        logging.info("starting server receive loop")
        self.dorecvloop = True
        self.recvthread = threading.Thread(target=self.recvloop)
        self.recvthread.daemon = True
        self.recvthread.start()

    def recvloop(self):
        """
        Receive loop for receiving messages from server sockets.
        """
        self.dorecvloop = True
        # note: this loop continues after emulation is stopped,
        # even with 0 servers
        while self.dorecvloop:
            rlist = []
            with self.servers_lock:
                # build a socket list for select call
                for name in self.servers:
                    server = self.servers[name]
                    if server.sock is not None:
                        rlist.append(server.sock)
            r, _w, _x = select.select(rlist, [], [], 1.0)
            for sock in r:
                server = self.getserverbysock(sock)
                logging.info(
                    "attempting to receive from server: peer:%s remote:%s",
                    server.sock.getpeername(),
                    server.sock.getsockname(),
                )
                if server is None:
                    # servers may have changed; loop again
                    continue
                rcvlen = self.recv(server)
                if rcvlen == 0:
                    logging.info(
                        "connection with server(%s) closed: %s:%s",
                        server.name,
                        server.host,
                        server.port,
                    )

    def recv(self, server):
        """
        Receive data on an emulation server socket and broadcast it to
        all connected session handlers. Returns the length of data recevied
        and forwarded. Return value of zero indicates the socket has closed
        and should be removed from the self.servers dict.

        :param CoreDistributedServer server: server to receive from
        :return: message length
        :rtype: int
        """
        msghdr = server.sock.recv(coreapi.CoreMessage.header_len)
        if len(msghdr) == 0:
            # server disconnected
            logging.info("server disconnected, closing server")
            server.close()
            return 0

        if len(msghdr) != coreapi.CoreMessage.header_len:
            logging.warning(
                "warning: broker received not enough data len=%s", len(msghdr)
            )
            return len(msghdr)

        msgtype, msgflags, msglen = coreapi.CoreMessage.unpack_header(msghdr)
        msgdata = server.sock.recv(msglen)
        data = msghdr + msgdata
        count = None
        logging.debug("received message type: %s", MessageTypes(msgtype))
        # snoop exec response for remote interactive TTYs
        if msgtype == MessageTypes.EXECUTE.value and msgflags & MessageFlags.TTY.value:
            data = self.fixupremotetty(msghdr, msgdata, server.host)
            logging.debug("created remote tty message: %s", data)
        elif msgtype == MessageTypes.NODE.value:
            # snoop node delete response to decrement node counts
            if msgflags & MessageFlags.DELETE.value:
                msg = coreapi.CoreNodeMessage(msgflags, msghdr, msgdata)
                nodenum = msg.get_tlv(NodeTlvs.NUMBER.value)
                if nodenum is not None:
                    count = self.delnodemap(server, nodenum)
        elif msgtype == MessageTypes.LINK.value:
            # this allows green link lines for remote WLANs
            msg = coreapi.CoreLinkMessage(msgflags, msghdr, msgdata)
            self.session.sdt.handle_distributed(msg)
        elif msgtype == MessageTypes.EVENT.value:
            msg = coreapi.CoreEventMessage(msgflags, msghdr, msgdata)
            eventtype = msg.get_tlv(EventTlvs.TYPE.value)
            if eventtype == EventTypes.INSTANTIATION_COMPLETE.value:
                server.instantiation_complete = True
                if self.instantiation_complete():
                    self.session.check_runtime()
        else:
            logging.error("unknown message type received: %s", msgtype)

        try:
            for session_client in self.session_clients:
                session_client.sendall(data)
        except IOError:
            logging.exception("error sending message")

        if count is not None and count < 1:
            return 0
        else:
            return len(data)

    def addserver(self, name, host, port):
        """
        Add a new server, and try to connect to it. If we"re already connected to this
        (host, port), then leave it alone. When host,port is None, do not try to connect.

        :param str name: name of server
        :param str host: server address
        :param int port: server port
        :return: nothing
        """
        with self.servers_lock:
            server = self.servers.get(name)
            if server is not None:
                if (
                    host == server.host
                    and port == server.port
                    and server.sock is not None
                ):
                    # leave this socket connected
                    return

                logging.info(
                    "closing connection with %s @ %s:%s", name, server.host, server.port
                )
                server.close()
                del self.servers[name]

            logging.info("adding broker server(%s): %s:%s", name, host, port)
            server = CoreDistributedServer(name, host, port)
            if host is not None and port is not None:
                try:
                    server.connect()
                except IOError:
                    logging.exception(
                        "error connecting to server(%s): %s:%s", name, host, port
                    )
                if server.sock is not None:
                    self.startrecvloop()
            self.servers[name] = server

    def delserver(self, server):
        """
        Remove a server and hang up any connection.

        :param CoreDistributedServer server: server to delete
        :return: nothing
        """
        with self.servers_lock:
            try:
                s = self.servers.pop(server.name)
                if s != server:
                    raise ValueError("server removed was not the server provided")
            except KeyError:
                logging.exception("error deleting server")

        if server.sock is not None:
            logging.info(
                "closing connection with %s @ %s:%s",
                server.name,
                server.host,
                server.port,
            )
            server.close()

    def getserverbyname(self, name):
        """
        Return the server object having the given name, or None.

        :param str name: name of server to retrieve
        :return: server for given name
        :rtype: CoreDistributedServer
        """
        with self.servers_lock:
            return self.servers.get(name)

    def getserverbysock(self, sock):
        """
        Return the server object corresponding to the given socket, or None.

        :param sock: socket associated with a server
        :return: core server associated wit the socket
        :rtype: CoreDistributedServer
        """
        with self.servers_lock:
            for name in self.servers:
                server = self.servers[name]
                if server.sock == sock:
                    return server
        return None

    def getservers(self):
        """
        Return a list of servers sorted by name.

        :return: sorted server list
        :rtype: list
        """
        with self.servers_lock:
            return sorted(self.servers.values(), key=lambda x: x.name)

    def getservernames(self):
        """
        Return a sorted list of server names (keys from self.servers).

        :return: sorted server names
        :rtype: list
        """
        with self.servers_lock:
            return sorted(self.servers.keys())

    def tunnelkey(self, n1num, n2num):
        """
        Compute a 32-bit key used to uniquely identify a GRE tunnel.
        The hash(n1num), hash(n2num) values are used, so node numbers may be
        None or string values (used for e.g. "ctrlnet").

        :param int n1num: node one id
        :param int n2num: node two id
        :return: tunnel key for the node pair
        :rtype: int
        """
        logging.debug("creating tunnel key for: %s, %s", n1num, n2num)
        sid = self.session_id_master
        if sid is None:
            # this is the master session
            sid = self.session.id

        key = (sid << 16) ^ utils.hashkey(n1num) ^ (utils.hashkey(n2num) << 8)
        return key & 0xFFFFFFFF

    def addtunnel(self, remoteip, n1num, n2num, localnum):
        """
        Adds a new GreTapBridge between nodes on two different machines.

        :param str remoteip: remote address for tunnel
        :param int n1num: node one id
        :param int n2num: node two id
        :param int localnum: local id
        :return: nothing
        """
        key = self.tunnelkey(n1num, n2num)
        if localnum == n2num:
            remotenum = n1num
        else:
            remotenum = n2num

        if key in self.tunnels.keys():
            logging.warning(
                "tunnel with key %s (%s-%s) already exists!", key, n1num, n2num
            )
        else:
            _id = key & ((1 << 16) - 1)
            logging.info(
                "adding tunnel for %s-%s to %s with key %s", n1num, n2num, remoteip, key
            )
            if localnum in self.physical_nodes:
                # no bridge is needed on physical nodes; use the GreTap directly
                gt = GreTap(
                    node=None,
                    name=None,
                    session=self.session,
                    remoteip=remoteip,
                    key=key,
                )
            else:
                gt = self.session.create_node(
                    cls=GreTapBridge,
                    _id=_id,
                    policy="ACCEPT",
                    remoteip=remoteip,
                    key=key,
                )
            gt.localnum = localnum
            gt.remotenum = remotenum
            self.tunnels[key] = gt

    def addnettunnels(self):
        """
        Add GreTaps between network devices on different machines.
        The GreTapBridge is not used since that would add an extra bridge.
        """
        logging.debug("adding network tunnels for nodes: %s", self.network_nodes)
        for n in self.network_nodes:
            self.addnettunnel(n)

    def addnettunnel(self, node_id):
        """
        Add network tunnel between node and broker.

        :param int node_id: node id of network to add tunnel to
        :return: list of gre taps
        :rtype: list
        """
        try:
            net = self.session.get_node(node_id)
            logging.info("adding net tunnel for: id(%s) %s", node_id, net)
        except KeyError:
            raise KeyError("network node %s not found" % node_id)

        # add other nets here that do not require tunnels
        if nodeutils.is_node(net, NodeTypes.EMANE_NET):
            logging.warning("emane network does not require a tunnel")
            return None

        server_interface = getattr(net, "serverintf", None)
        if (
            nodeutils.is_node(net, NodeTypes.CONTROL_NET)
            and server_interface is not None
        ):
            logging.warning(
                "control networks with server interfaces do not need a tunnel"
            )
            return None

        servers = self.getserversbynode(node_id)
        if len(servers) < 2:
            logging.warning("not enough servers to create a tunnel: %s", servers)
            return None

        hosts = []
        for server in servers:
            if server.host is None:
                continue
            logging.info("adding server host for net tunnel: %s", server.host)
            hosts.append(server.host)

        if len(hosts) == 0:
            for session_client in self.session_clients:
                # get IP address from API message sender (master)
                if session_client.client_address != "":
                    address = session_client.client_address[0]
                    logging.info("adding session_client host: %s", address)
                    hosts.append(address)

        r = []
        for host in hosts:
            if self.myip:
                # we are the remote emulation server
                myip = self.myip
            else:
                # we are the session master
                myip = host
            key = self.tunnelkey(node_id, IpAddress.to_int(myip))
            if key in self.tunnels.keys():
                logging.info(
                    "tunnel already exists, returning existing tunnel: %s", key
                )
                gt = self.tunnels[key]
                r.append(gt)
                continue
            logging.info(
                "adding tunnel for net %s to %s with key %s", node_id, host, key
            )
            gt = GreTap(
                node=None, name=None, session=self.session, remoteip=host, key=key
            )
            self.tunnels[key] = gt
            r.append(gt)
            # attaching to net will later allow gt to be destroyed
            # during net.shutdown()
            net.attach(gt)

        return r

    def deltunnel(self, n1num, n2num):
        """
        Delete tunnel between nodes.

        :param int n1num: node one id
        :param int n2num: node two id
        :return: nothing
        """
        key = self.tunnelkey(n1num, n2num)
        try:
            logging.info(
                "deleting tunnel between %s - %s with key: %s", n1num, n2num, key
            )
            gt = self.tunnels.pop(key)
        except KeyError:
            gt = None
        if gt:
            self.session.delete_node(gt.id)
            del gt

    def gettunnel(self, n1num, n2num):
        """
        Return the GreTap between two nodes if it exists.

        :param int n1num: node one id
        :param int n2num: node two id
        :return: gre tap between nodes or none
        """
        key = self.tunnelkey(n1num, n2num)
        logging.debug("checking for tunnel(%s) in: %s", key, self.tunnels.keys())
        if key in self.tunnels.keys():
            return self.tunnels[key]
        else:
            return None

    def addnodemap(self, server, nodenum):
        """
        Record a node number to emulation server mapping.

        :param CoreDistributedServer server: core server to associate node with
        :param int nodenum: node id
        :return: nothing
        """
        with self.nodemap_lock:
            if nodenum in self.nodemap:
                if server in self.nodemap[nodenum]:
                    return
                self.nodemap[nodenum].add(server)
            else:
                self.nodemap[nodenum] = {server}

            if server in self.nodecounts:
                self.nodecounts[server] += 1
            else:
                self.nodecounts[server] = 1

    def delnodemap(self, server, nodenum):
        """
        Remove a node number to emulation server mapping.
        Return the number of nodes left on this server.

        :param CoreDistributedServer server: server to remove from node map
        :param int nodenum: node id
        :return: number of nodes left on server
        :rtype: int
        """
        count = None
        with self.nodemap_lock:
            if nodenum not in self.nodemap:
                return count

            self.nodemap[nodenum].remove(server)
            if server in self.nodecounts:
                count = self.nodecounts[server]
                count -= 1
                self.nodecounts[server] = count

            return count

    def getserversbynode(self, nodenum):
        """
        Retrieve a set of emulation servers given a node number.

        :param int nodenum: node id
        :return: core server associated with node
        :rtype: set
        """
        with self.nodemap_lock:
            if nodenum not in self.nodemap:
                return set()
            return self.nodemap[nodenum]

    def addnet(self, nodenum):
        """
        Add a node number to the list of link-layer nodes.

        :param int nodenum: node id to add
        :return: nothing
        """
        logging.info("adding net to broker: %s", nodenum)
        self.network_nodes.add(nodenum)
        logging.info("broker network nodes: %s", self.network_nodes)

    def addphys(self, nodenum):
        """
        Add a node number to the list of physical nodes.

        :param int nodenum: node id to add
        :return: nothing
        """
        self.physical_nodes.add(nodenum)

    def handle_message(self, message):
        """
        Handle an API message. Determine whether this needs to be handled
        by the local server or forwarded on to another one.
        Returns True when message does not need to be handled locally,
        and performs forwarding if required.
        Returning False indicates this message should be handled locally.

        :param core.api.coreapi.CoreMessage message: message to handle
        :return: true or false for handling locally
        :rtype: bool
        """
        servers = set()
        handle_locally = False
        # Do not forward messages when in definition state
        # (for e.g. configuring services)
        if self.session.state == EventTypes.DEFINITION_STATE.value:
            return False

        # Decide whether message should be handled locally or forwarded, or both
        if message.message_type == MessageTypes.NODE.value:
            handle_locally, servers = self.handlenodemsg(message)
        elif message.message_type == MessageTypes.EVENT.value:
            # broadcast events everywhere
            servers = self.getservers()
        elif message.message_type == MessageTypes.CONFIG.value:
            # broadcast location and services configuration everywhere
            confobj = message.get_tlv(ConfigTlvs.OBJECT.value)
            if (
                confobj == "location"
                or confobj == "services"
                or confobj == "session"
                or confobj == "all"
            ):
                servers = self.getservers()
        elif message.message_type == MessageTypes.FILE.value:
            # broadcast hook scripts and custom service files everywhere
            filetype = message.get_tlv(FileTlvs.TYPE.value)
            if filetype is not None and (
                filetype[:5] == "hook:" or filetype[:8] == "service:"
            ):
                servers = self.getservers()
        if message.message_type == MessageTypes.LINK.value:
            # prepare a server list from two node numbers in link message
            handle_locally, servers, message = self.handlelinkmsg(message)
        elif len(servers) == 0:
            # check for servers based on node numbers in all messages but link
            nn = message.node_numbers()
            if len(nn) == 0:
                return False
            servers = self.getserversbynode(nn[0])

        # allow other handlers to process this message (this is used
        # by e.g. EMANE to use the link add message to keep counts of
        # interfaces on other servers)
        for handler in self.handlers:
            handler(message)

        # perform any message forwarding
        handle_locally |= self.forwardmsg(message, servers)
        return not handle_locally

    def setupserver(self, servername):
        """
        Send the appropriate API messages for configuring the specified emulation server.

        :param str servername: name of server to configure
        :return: nothing
        """
        server = self.getserverbyname(servername)
        if server is None:
            logging.warning("ignoring unknown server: %s", servername)
            return

        if server.sock is None or server.host is None or server.port is None:
            logging.info("ignoring disconnected server: %s", servername)
            return

        # communicate this session"s current state to the server
        tlvdata = coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, self.session.state)
        msg = coreapi.CoreEventMessage.pack(0, tlvdata)
        server.sock.send(msg)

        # send a Configuration message for the broker object and inform the
        # server of its local name
        tlvdata = b""
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.OBJECT.value, "broker")
        tlvdata += coreapi.CoreConfigTlv.pack(
            ConfigTlvs.TYPE.value, ConfigFlags.UPDATE.value
        )
        tlvdata += coreapi.CoreConfigTlv.pack(
            ConfigTlvs.DATA_TYPES.value, (ConfigDataTypes.STRING.value,)
        )
        tlvdata += coreapi.CoreConfigTlv.pack(
            ConfigTlvs.VALUES.value,
            "%s:%s:%s" % (server.name, server.host, server.port),
        )
        tlvdata += coreapi.CoreConfigTlv.pack(
            ConfigTlvs.SESSION.value, "%s" % self.session.id
        )
        msg = coreapi.CoreConfMessage.pack(0, tlvdata)
        server.sock.send(msg)

    @staticmethod
    def fixupremotetty(msghdr, msgdata, host):
        """
        When an interactive TTY request comes from the GUI, snoop the reply
        and add an SSH command to the appropriate remote server.

        :param msghdr: message header
        :param msgdata: message data
        :param str host: host address
        :return: packed core execute tlv data
        """
        msgtype, msgflags, _msglen = coreapi.CoreMessage.unpack_header(msghdr)
        msgcls = coreapi.CLASS_MAP[msgtype]
        msg = msgcls(msgflags, msghdr, msgdata)

        nodenum = msg.get_tlv(ExecuteTlvs.NODE.value)
        execnum = msg.get_tlv(ExecuteTlvs.NUMBER.value)
        cmd = msg.get_tlv(ExecuteTlvs.COMMAND.value)
        res = msg.get_tlv(ExecuteTlvs.RESULT.value)

        tlvdata = b""
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, nodenum)
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.NUMBER.value, execnum)
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, cmd)
        res = "ssh -X -f " + host + " xterm -e " + res
        tlvdata += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.RESULT.value, res)

        return coreapi.CoreExecMessage.pack(msgflags, tlvdata)

    def handlenodemsg(self, message):
        """
        Determine and return the servers to which this node message should
        be forwarded. Also keep track of link-layer nodes and the mapping of
        nodes to servers.

        :param core.api.coreapi.CoreMessage message: message to handle
        :return: boolean for handling locally and set of servers
        :rtype: tuple
        """
        servers = set()
        handle_locally = False
        serverfiletxt = None

        # snoop Node Message for emulation server TLV and record mapping
        n = message.tlv_data[NodeTlvs.NUMBER.value]

        # replicate link-layer nodes on all servers
        nodetype = message.get_tlv(NodeTlvs.TYPE.value)
        if nodetype is not None:
            try:
                nodecls = nodeutils.get_node_class(NodeTypes(nodetype))
            except KeyError:
                logging.warning("broker invalid node type %s", nodetype)
                return handle_locally, servers
            if nodecls is None:
                logging.warning("broker unimplemented node type %s", nodetype)
                return handle_locally, servers
            if (
                issubclass(nodecls, CoreNetworkBase)
                and nodetype != NodeTypes.WIRELESS_LAN.value
            ):
                # network node replicated on all servers; could be optimized
                # don"t replicate WLANs, because ebtables rules won"t work
                servers = self.getservers()
                handle_locally = True
                self.addnet(n)
                for server in servers:
                    self.addnodemap(server, n)
                # do not record server name for networks since network
                # nodes are replicated across all server
                return handle_locally, servers
            elif issubclass(nodecls, CoreNodeBase):
                name = message.get_tlv(NodeTlvs.NAME.value)
                if name:
                    serverfiletxt = "%s %s %s" % (n, name, nodecls)
                if issubclass(nodecls, PhysicalNode):
                    # remember physical nodes
                    self.addphys(n)

        # emulation server TLV specifies server
        servername = message.get_tlv(NodeTlvs.EMULATION_SERVER.value)
        server = self.getserverbyname(servername)
        if server is not None:
            self.addnodemap(server, n)
            if server not in servers:
                servers.add(server)
            if serverfiletxt and self.session.master:
                self.writenodeserver(serverfiletxt, server)

        # hook to update coordinates of physical nodes
        if n in self.physical_nodes:
            self.session.mobility.physnodeupdateposition(message)

        return handle_locally, servers

    def handlelinkmsg(self, message):
        """
        Determine and return the servers to which this link message should
        be forwarded. Also build tunnels between different servers or add
        opaque data to the link message before forwarding.

        :param core.api.coreapi.CoreMessage message: message to handle
        :return: boolean to handle locally, a set of server, and message
        :rtype: tuple
        """
        servers = set()
        handle_locally = False

        # determine link message destination using non-network nodes
        nn = message.node_numbers()
        logging.debug(
            "checking link nodes (%s) with network nodes (%s)", nn, self.network_nodes
        )
        if nn[0] in self.network_nodes:
            if nn[1] in self.network_nodes:
                # two network nodes linked together - prevent loops caused by
                # the automatic tunnelling
                handle_locally = True
            else:
                servers = self.getserversbynode(nn[1])
        elif nn[1] in self.network_nodes:
            servers = self.getserversbynode(nn[0])
        else:
            logging.debug("link nodes are not network nodes")
            servers1 = self.getserversbynode(nn[0])
            logging.debug("servers for node(%s): %s", nn[0], servers1)
            servers2 = self.getserversbynode(nn[1])
            logging.debug("servers for node(%s): %s", nn[1], servers2)
            # nodes are on two different servers, build tunnels as needed
            if servers1 != servers2:
                localn = None
                if len(servers1) == 0 or len(servers2) == 0:
                    handle_locally = True
                servers = servers1.union(servers2)
                host = None
                # get the IP of remote server and decide which node number
                # is for a local node
                for server in servers:
                    host = server.host
                    if host is None:
                        # server is local
                        handle_locally = True
                        if server in servers1:
                            localn = nn[0]
                        else:
                            localn = nn[1]
                if handle_locally and localn is None:
                    # having no local node at this point indicates local node is
                    # the one with the empty server set
                    if len(servers1) == 0:
                        localn = nn[0]
                    elif len(servers2) == 0:
                        localn = nn[1]
                if host is None:
                    host = self.getlinkendpoint(message, localn == nn[0])

                logging.debug(
                    "handle locally(%s) and local node(%s)", handle_locally, localn
                )
                if localn is None:
                    message = self.addlinkendpoints(message, servers1, servers2)
                elif message.flags & MessageFlags.ADD.value:
                    self.addtunnel(host, nn[0], nn[1], localn)
                elif message.flags & MessageFlags.DELETE.value:
                    self.deltunnel(nn[0], nn[1])
                    handle_locally = False
            else:
                servers = servers1.union(servers2)

        return handle_locally, servers, message

    def addlinkendpoints(self, message, servers1, servers2):
        """
        For a link message that is not handled locally, inform the remote
        servers of the IP addresses used as tunnel endpoints by adding
        opaque data to the link message.

        :param core.api.coreapi.CoreMessage message: message to link end points
        :param servers1:
        :param servers2:
        :return: core link message
        :rtype: coreapi.CoreLinkMessage
        """
        ip1 = ""
        for server in servers1:
            if server.host is not None:
                ip1 = server.host
                break
        ip2 = ""
        for server in servers2:
            if server.host is not None:
                ip2 = server.host
                break
        tlvdata = message.raw_message[coreapi.CoreMessage.header_len :]
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.OPAQUE.value, "%s:%s" % (ip1, ip2))
        newraw = coreapi.CoreLinkMessage.pack(message.flags, tlvdata)
        msghdr = newraw[: coreapi.CoreMessage.header_len]
        return coreapi.CoreLinkMessage(message.flags, msghdr, tlvdata)

    def getlinkendpoint(self, msg, first_is_local):
        """
        A link message between two different servers has been received,
        and we need to determine the tunnel endpoint. First look for
        opaque data in the link message, otherwise use the IP of the message
        sender (the master server).

        :param core.api.tlv.coreapi.CoreLinkMessage msg: link message
        :param bool first_is_local: is first local
        :return: host address
        :rtype: str
        """
        host = None
        opaque = msg.get_tlv(LinkTlvs.OPAQUE.value)
        if opaque is not None:
            if first_is_local:
                host = opaque.split(":")[1]
            else:
                host = opaque.split(":")[0]
            if host == "":
                host = None

        if host is None:
            for session_client in self.session_clients:
                # get IP address from API message sender (master)
                if session_client.client_address != "":
                    host = session_client.client_address[0]
                    break

        return host

    def handlerawmsg(self, msg):
        """
        Helper to invoke message handler, using raw (packed) message bytes.

        :param msg: raw message butes
        :return: should handle locally or not
        :rtype: bool
        """
        hdr = msg[: coreapi.CoreMessage.header_len]
        msgtype, flags, _msglen = coreapi.CoreMessage.unpack_header(hdr)
        msgcls = coreapi.CLASS_MAP[msgtype]
        return self.handle_message(
            msgcls(flags, hdr, msg[coreapi.CoreMessage.header_len :])
        )

    def forwardmsg(self, message, servers):
        """
        Forward API message to all given servers.

        Return True if an empty host/port is encountered, indicating
        the message should be handled locally.

        :param core.api.coreapi.CoreMessage message: message to forward
        :param list servers: server to forward message to
        :return: handle locally value
        :rtype: bool
        """
        handle_locally = len(servers) == 0
        for server in servers:
            if server.host is None and server.port is None:
                # local emulation server, handle this locally
                handle_locally = True
            elif server.sock is None:
                logging.info(
                    "server %s @ %s:%s is disconnected",
                    server.name,
                    server.host,
                    server.port,
                )
            else:
                logging.info(
                    "forwarding message to server(%s): %s:%s",
                    server.name,
                    server.host,
                    server.port,
                )
                logging.debug("message being forwarded:\n%s", message)
                server.sock.send(message.raw_message)
        return handle_locally

    def writeservers(self):
        """
        Write the server list to a text file in the session directory upon
        startup: /tmp/pycore.nnnnn/servers

        :return: nothing
        """
        servers = self.getservers()
        filename = os.path.join(self.session.session_dir, "servers")
        master = self.session_id_master
        if master is None:
            master = self.session.id
        try:
            with open(filename, "w") as f:
                f.write("master=%s\n" % master)
                for server in servers:
                    if server.name == "localhost":
                        continue

                    lhost, lport = None, None
                    if server.sock:
                        lhost, lport = server.sock.getsockname()
                    f.write(
                        "%s %s %s %s %s\n"
                        % (server.name, server.host, server.port, lhost, lport)
                    )
        except IOError:
            logging.exception("error writing server list to the file: %s", filename)

    def writenodeserver(self, nodestr, server):
        """
        Creates a /tmp/pycore.nnnnn/nX.conf/server file having the node
        and server info. This may be used by scripts for accessing nodes on
        other machines, much like local nodes may be accessed via the
        VnodeClient class.

        :param str nodestr: node string
        :param CoreDistributedServer server: core server
        :return: nothing
        """
        serverstr = "%s %s %s" % (server.name, server.host, server.port)
        name = nodestr.split()[1]
        dirname = os.path.join(self.session.session_dir, name + ".conf")
        filename = os.path.join(dirname, "server")
        try:
            os.makedirs(dirname)
        except OSError:
            # directory may already exist from previous distributed run
            logging.exception("error creating directory: %s", dirname)

        try:
            with open(filename, "w") as f:
                f.write("%s\n%s\n" % (serverstr, nodestr))
        except IOError:
            logging.exception(
                "error writing server file %s for node %s", filename, name
            )

    def local_instantiation_complete(self):
        """
        Set the local server"s instantiation-complete status to True.

        :return: nothing
        """
        # TODO: do we really want to allow a localhost to not exist?
        with self.servers_lock:
            server = self.servers.get("localhost")
            if server is not None:
                server.instantiation_complete = True

        # broadcast out instantiate complete
        tlvdata = b""
        tlvdata += coreapi.CoreEventTlv.pack(
            EventTlvs.TYPE.value, EventTypes.INSTANTIATION_COMPLETE.value
        )
        message = coreapi.CoreEventMessage.pack(0, tlvdata)
        for session_client in self.session_clients:
            session_client.sendall(message)

    def instantiation_complete(self):
        """
        Return True if all servers have completed instantiation, False
        otherwise.

        :return: have all server completed instantiation
        :rtype: bool
        """
        with self.servers_lock:
            for name in self.servers:
                server = self.servers[name]
                if not server.instantiation_complete:
                    return False
            return True
