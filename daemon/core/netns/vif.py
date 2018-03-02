"""
virtual ethernet classes that implement the interfaces available under Linux.
"""

import subprocess
import time

from core import constants
from core import logger
from core.coreobj import PyCoreNetIf
from core.enumerations import NodeTypes
from core.misc import nodeutils
from core.misc import utils

utils.check_executables([constants.IP_BIN])


class VEth(PyCoreNetIf):
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
        :raises subprocess.CalledProcessError: when there is a command exception
        """
        # note that net arg is ignored
        PyCoreNetIf.__init__(self, node=node, name=name, mtu=mtu)
        self.localname = localname
        self.up = False
        if start:
            self.startup()

    def startup(self):
        """
        Interface startup logic.

        :return: nothing
        :raises subprocess.CalledProcessError: when there is a command exception
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
            except subprocess.CalledProcessError as e:
                logger.exception("error shutting down interface: %s", e.output)

        if self.localname:
            try:
                utils.check_cmd([constants.IP_BIN, "link", "delete", self.localname])
            except subprocess.CalledProcessError as e:
                logger.exception("error deleting link: %s", e.output)

        self.up = False


class TunTap(PyCoreNetIf):
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
        PyCoreNetIf.__init__(self, node=node, name=name, mtu=mtu)
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
        except subprocess.CalledProcessError as e:
            logger.exception("error shutting down tunnel tap: %s", e.output)

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
                logger.info(msg)
                time.sleep(delay)
                delay += delay
                if delay > maxretrydelay:
                    delay = maxretrydelay
            else:
                msg += ", giving up"
                logger.info(msg)

        return result

    def waitfordevicelocal(self):
        """
        Check for presence of a local device - tap device may not
        appear right away waits

        :return: wait for device local response
        :rtype: int
        """

        def localdevexists():
            args = [constants.IP_BIN, "link", "show", self.localname]
            return utils.cmd(args)

        self.waitfor(localdevexists)

    def waitfordevicenode(self):
        """
        Check for presence of a node device - tap device may not appear right away waits.

        :return: nothing
        """

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
        :raises subprocess.CalledProcessError: when there is a command exception
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


class GreTap(PyCoreNetIf):
    """
    GRE TAP device for tunneling between emulation servers.
    Uses the "gretap" tunnel device type from Linux which is a GRE device
    having a MAC address. The MAC address is required for bridging.
    """

    def __init__(self, node=None, name=None, session=None, mtu=1458,
                 remoteip=None, objid=None, localip=None, ttl=255,
                 key=None, start=True):
        """
        Creates a GreTap instance.

        :param core.netns.vnode.SimpleLxcNode node: related core node
        :param str name: interface name
        :param core.session.Session session: core session instance
        :param mtu: interface mtu
        :param str remoteip: remote address
        :param int objid: object id
        :param str localip: local address
        :param ttl: ttl value
        :param key: gre tap key
        :param bool start: start flag
        :raises subprocess.CalledProcessError: when there is a command exception
        """
        PyCoreNetIf.__init__(self, node=node, name=name, mtu=mtu)
        self.session = session
        if objid is None:
            # from PyCoreObj
            objid = ((id(self) >> 16) ^ (id(self) & 0xffff)) & 0xffff
        self.objid = objid
        sessionid = self.session.short_session_id()
        # interface name on the local host machine
        self.localname = "gt.%s.%s" % (self.objid, sessionid)
        self.transport_type = "raw"
        if not start:
            self.up = False
            return

        if remoteip is None:
            raise ValueError, "missing remote IP required for GRE TAP device"
        args = ["ip", "link", "add", self.localname, "type", "gretap",
                "remote", str(remoteip)]
        if localip:
            args += ["local", str(localip)]
        if ttl:
            args += ["ttl", str(ttl)]
        if key:
            args += ["key", str(key)]
        utils.check_cmd(args)
        args = ["ip", "link", "set", self.localname, "up"]
        utils.check_cmd(args)
        self.up = True

    def shutdown(self):
        """
        Shutdown logic for a GreTap.

        :return: nothing
        """
        if self.localname:
            try:
                args = ["ip", "link", "set", self.localname, "down"]
                utils.check_cmd(args)
                args = ["ip", "link", "del", self.localname]
                utils.check_cmd(args)
            except subprocess.CalledProcessError as e:
                logger.exception("error during shutdown: %s", e.output)

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
