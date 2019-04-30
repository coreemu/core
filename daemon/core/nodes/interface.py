"""
virtual ethernet classes that implement the interfaces available under Linux.
"""

import logging
import time

from core import CoreCommandError, utils
from core import constants
from core.emulator.enumerations import NodeTypes
from core.nodes import nodeutils

utils.check_executables([constants.IP_BIN])


class CoreInterface(object):
    """
    Base class for network interfaces.
    """

    def __init__(self, node, name, mtu):
        """
        Creates a PyCoreNetIf instance.

        :param core.coreobj.PyCoreNode node: node for interface
        :param str name: interface name
        :param mtu: mtu value
        """

        self.node = node
        self.name = name
        if not isinstance(mtu, (int, long)):
            raise ValueError
        self.mtu = mtu
        self.net = None
        self._params = {}
        self.addrlist = []
        self.hwaddr = None
        # placeholder position hook
        self.poshook = lambda a, b, c, d: None
        # used with EMANE
        self.transport_type = None
        # interface index on the network
        self.netindex = None
        # index used to find flow data
        self.flow_id = None

    def startup(self):
        """
        Startup method for the interface.

        :return: nothing
        """
        pass

    def shutdown(self):
        """
        Shutdown method for the interface.

        :return: nothing
        """
        pass

    def attachnet(self, net):
        """
        Attach network.

        :param core.coreobj.PyCoreNet net: network to attach
        :return: nothing
        """
        if self.net:
            self.detachnet()
            self.net = None

        net.attach(self)
        self.net = net

    def detachnet(self):
        """
        Detach from a network.

        :return: nothing
        """
        if self.net is not None:
            self.net.detach(self)

    def addaddr(self, addr):
        """
        Add address.

        :param str addr: address to add
        :return: nothing
        """

        self.addrlist.append(addr)

    def deladdr(self, addr):
        """
        Delete address.

        :param str addr: address to delete
        :return: nothing
        """
        self.addrlist.remove(addr)

    def sethwaddr(self, addr):
        """
        Set hardware address.

        :param core.misc.ipaddress.MacAddress addr: hardware address to set to.
        :return: nothing
        """
        self.hwaddr = addr

    def getparam(self, key):
        """
        Retrieve a parameter from the, or None if the parameter does not exist.

        :param key: parameter to get value for
        :return: parameter value
        """
        return self._params.get(key)

    def getparams(self):
        """
        Return (key, value) pairs for parameters.
        """
        parameters = []
        for k in sorted(self._params.keys()):
            parameters.append((k, self._params[k]))
        return parameters

    def setparam(self, key, value):
        """
        Set a parameter value, returns True if the parameter has changed.

        :param key: parameter name to set
        :param value: parameter value
        :return: True if parameter changed, False otherwise
        """
        # treat None and 0 as unchanged values
        current_value = self._params.get(key)
        if current_value == value or current_value <= 0 and value <= 0:
            return False

        self._params[key] = value
        return True

    def swapparams(self, name):
        """
        Swap out parameters dict for name. If name does not exist,
        intialize it. This is for supporting separate upstream/downstream
        parameters when two layer-2 nodes are linked together.

        :param str name: name of parameter to swap
        :return: nothing
        """
        tmp = self._params
        if not hasattr(self, name):
            setattr(self, name, {})
        self._params = getattr(self, name)
        setattr(self, name, tmp)

    def setposition(self, x, y, z):
        """
        Dispatch position hook handler.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        self.poshook(self, x, y, z)


class Veth(CoreInterface):
    """
    Provides virtual ethernet functionality for core nodes.
    """

    # TODO: network is not used, why was it needed?
    def __init__(self, node, name, localname, mtu=1500, net=None, start=True):
        """
        Creates a VEth instance.

        :param core.netns.vnode.SimpleLxcNode node: related core node
        :param str name: interface name
        :param str localname: interface local name
        :param mtu: interface mtu
        :param net: network
        :param bool start: start flag
        :raises CoreCommandError: when there is a command exception
        """
        # note that net arg is ignored
        CoreInterface.__init__(self, node=node, name=name, mtu=mtu)
        self.localname = localname
        self.up = False
        if start:
            self.startup()

    def startup(self):
        """
        Interface startup logic.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        utils.check_cmd([constants.IP_BIN, "link", "add", "name", self.localname,
                         "type", "veth", "peer", "name", self.name])
        utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "up"])
        self.up = True

    def shutdown(self):
        """
        Interface shutdown logic.

        :return: nothing
        """
        if not self.up:
            return

        if self.node:
            try:
                self.node.check_cmd([constants.IP_BIN, "-6", "addr", "flush", "dev", self.name])
            except CoreCommandError:
                logging.exception("error shutting down interface")

        if self.localname:
            try:
                utils.check_cmd([constants.IP_BIN, "link", "delete", self.localname])
            except CoreCommandError:
                logging.exception("error deleting link")

        self.up = False


class TunTap(CoreInterface):
    """
    TUN/TAP virtual device in TAP mode
    """

    # TODO: network is not used, why was it needed?
    def __init__(self, node, name, localname, mtu=1500, net=None, start=True):
        """
        Create a TunTap instance.

        :param core.netns.vnode.SimpleLxcNode node: related core node
        :param str name: interface name
        :param str localname: local interface name
        :param mtu: interface mtu
        :param net: related network
        :param bool start: start flag
        """
        CoreInterface.__init__(self, node=node, name=name, mtu=mtu)
        self.localname = localname
        self.up = False
        self.transport_type = "virtual"
        if start:
            self.startup()

    def startup(self):
        """
        Startup logic for a tunnel tap.

        :return: nothing
        """
        # TODO: more sophisticated TAP creation here
        #   Debian does not support -p (tap) option, RedHat does.
        #   For now, this is disabled to allow the TAP to be created by another
        #   system (e.g. EMANE"s emanetransportd)
        #   check_call(["tunctl", "-t", self.name])
        #   self.install()
        self.up = True

    def shutdown(self):
        """
        Shutdown functionality for a tunnel tap.

        :return: nothing
        """
        if not self.up:
            return

        try:
            self.node.check_cmd([constants.IP_BIN, "-6", "addr", "flush", "dev", self.name])
        except CoreCommandError:
            logging.exception("error shutting down tunnel tap")

        self.up = False

    def waitfor(self, func, attempts=10, maxretrydelay=0.25):
        """
        Wait for func() to return zero with exponential backoff.

        :param func: function to wait for a result of zero
        :param int attempts: number of attempts to wait for a zero result
        :param float maxretrydelay: maximum retry delay
        :return: True if wait succeeded, False otherwise
        :rtype: bool
        """
        delay = 0.01
        result = False
        for i in xrange(1, attempts + 1):
            r = func()
            if r == 0:
                result = True
                break
            msg = "attempt %s failed with nonzero exit status %s" % (i, r)
            if i < attempts + 1:
                msg += ", retrying..."
                logging.info(msg)
                time.sleep(delay)
                delay += delay
                if delay > maxretrydelay:
                    delay = maxretrydelay
            else:
                msg += ", giving up"
                logging.info(msg)

        return result

    def waitfordevicelocal(self):
        """
        Check for presence of a local device - tap device may not
        appear right away waits

        :return: wait for device local response
        :rtype: int
        """
        logging.debug("waiting for device local: %s", self.localname)

        def localdevexists():
            args = [constants.IP_BIN, "link", "show", self.localname]
            return utils.cmd(args)

        self.waitfor(localdevexists)

    def waitfordevicenode(self):
        """
        Check for presence of a node device - tap device may not appear right away waits.

        :return: nothing
        """
        logging.debug("waiting for device node: %s", self.name)

        def nodedevexists():
            args = [constants.IP_BIN, "link", "show", self.name]
            return self.node.cmd(args)

        count = 0
        while True:
            result = self.waitfor(nodedevexists)
            if result:
                break

            # check if this is an EMANE interface; if so, continue
            # waiting if EMANE is still running
            # TODO: remove emane code
            should_retry = count < 5
            is_emane_node = nodeutils.is_node(self.net, NodeTypes.EMANE)
            is_emane_running = self.node.session.emane.emanerunning(self.node)
            if all([should_retry, is_emane_node, is_emane_running]):
                count += 1
            else:
                raise RuntimeError("node device failed to exist")

    def install(self):
        """
        Install this TAP into its namespace. This is not done from the
        startup() method but called at a later time when a userspace
        program (running on the host) has had a chance to open the socket
        end of the TAP.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.waitfordevicelocal()
        netns = str(self.node.pid)
        utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "netns", netns])
        self.node.check_cmd([constants.IP_BIN, "link", "set", self.localname, "name", self.name])
        self.node.check_cmd([constants.IP_BIN, "link", "set", self.name, "up"])

    def setaddrs(self):
        """
        Set interface addresses based on self.addrlist.

        :return: nothing
        """
        self.waitfordevicenode()
        for addr in self.addrlist:
            self.node.check_cmd([constants.IP_BIN, "addr", "add", str(addr), "dev", self.name])


class GreTap(CoreInterface):
    """
    GRE TAP device for tunneling between emulation servers.
    Uses the "gretap" tunnel device type from Linux which is a GRE device
    having a MAC address. The MAC address is required for bridging.
    """

    def __init__(self, node=None, name=None, session=None, mtu=1458,
                 remoteip=None, _id=None, localip=None, ttl=255,
                 key=None, start=True):
        """
        Creates a GreTap instance.

        :param core.netns.vnode.SimpleLxcNode node: related core node
        :param str name: interface name
        :param core.session.Session session: core session instance
        :param mtu: interface mtu
        :param str remoteip: remote address
        :param int _id: object id
        :param str localip: local address
        :param ttl: ttl value
        :param key: gre tap key
        :param bool start: start flag
        :raises CoreCommandError: when there is a command exception
        """
        CoreInterface.__init__(self, node=node, name=name, mtu=mtu)
        self.session = session
        if _id is None:
            # from PyCoreObj
            _id = ((id(self) >> 16) ^ (id(self) & 0xffff)) & 0xffff
        self.id = _id
        sessionid = self.session.short_session_id()
        # interface name on the local host machine
        self.localname = "gt.%s.%s" % (self.id, sessionid)
        self.transport_type = "raw"
        if not start:
            self.up = False
            return

        if remoteip is None:
            raise ValueError, "missing remote IP required for GRE TAP device"
        args = [constants.IP_BIN, "link", "add", self.localname, "type", "gretap",
                "remote", str(remoteip)]
        if localip:
            args += ["local", str(localip)]
        if ttl:
            args += ["ttl", str(ttl)]
        if key:
            args += ["key", str(key)]
        utils.check_cmd(args)
        args = [constants.IP_BIN, "link", "set", self.localname, "up"]
        utils.check_cmd(args)
        self.up = True

    def shutdown(self):
        """
        Shutdown logic for a GreTap.

        :return: nothing
        """
        if self.localname:
            try:
                args = [constants.IP_BIN, "link", "set", self.localname, "down"]
                utils.check_cmd(args)
                args = [constants.IP_BIN, "link", "del", self.localname]
                utils.check_cmd(args)
            except CoreCommandError:
                logging.exception("error during shutdown")

            self.localname = None

    def data(self, message_type):
        """
        Data for a gre tap.

        :param message_type: message type for data
        :return: None
        """
        return None

    def all_link_data(self, flags):
        """
        Retrieve link data.

        :param flags: link flags
        :return: link data
        :rtype: list[core.data.LinkData]
        """
        return []
