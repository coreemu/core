"""
virtual ethernet classes that implement the interfaces available under Linux.
"""

import subprocess
import time

from core import constants
from core.coreobj import PyCoreNetIf
from core.enumerations import NodeTypes
from core.misc import log
from core.misc import nodeutils
from core.misc import utils

logger = log.get_logger(__name__)

utils.check_executables([constants.IP_BIN])


class VEth(PyCoreNetIf):
    """
    Provides virtual ethernet functionality for core nodes.
    """

    # TODO: network is not used, why was it needed?
    def __init__(self, node, name, localname, mtu=1500, net=None, start=True):
        """
        Creates a VEth instance.

        :param core.netns.nodes.CoreNode node: related core node
        :param str name: interface name
        :param str localname: interface local name
        :param mtu: interface mtu
        :param net: network
        :param bool start: start flag
        :return:
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
        """
        subprocess.check_call([constants.IP_BIN, "link", "add", "name", self.localname,
                               "type", "veth", "peer", "name", self.name])
        subprocess.check_call([constants.IP_BIN, "link", "set", self.localname, "up"])
        self.up = True

    def shutdown(self):
        """
        Interface shutdown logic.

        :return: nothing
        """
        if not self.up:
            return
        if self.node:
            self.node.cmd([constants.IP_BIN, "-6", "addr", "flush", "dev", self.name])
        if self.localname:
            utils.mutedetach([constants.IP_BIN, "link", "delete", self.localname])
        self.up = False


class TunTap(PyCoreNetIf):
    """
    TUN/TAP virtual device in TAP mode
    """

    # TODO: network is not used, why was it needed?
    def __init__(self, node, name, localname, mtu=1500, net=None, start=True):
        """
        Create a TunTap instance.

        :param core.netns.nodes.CoreNode node: related core node
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
        # For now, this is disabled to allow the TAP to be created by another
        # system (e.g. EMANE"s emanetransportd)
        # check_call(["tunctl", "-t", self.name])
        # self.install()
        self.up = True

    def shutdown(self):
        """
        Shutdown functionality for a tunnel tap.

        :return: nothing
        """
        if not self.up:
            return
        self.node.cmd([constants.IP_BIN, "-6", "addr", "flush", "dev", self.name])
        # if self.name:
        #    mutedetach(["tunctl", "-d", self.localname])
        self.up = False

    def waitfor(self, func, attempts=10, maxretrydelay=0.25):
        """
        Wait for func() to return zero with exponential backoff.

        :param func: function to wait for a result of zero
        :param int attempts: number of attempts to wait for a zero result
        :param float maxretrydelay: maximum retry delay
        :return: nothing
        """
        delay = 0.01
        for i in xrange(1, attempts + 1):
            r = func()
            if r == 0:
                return
            msg = "attempt %s failed with nonzero exit status %s" % (i, r)
            if i < attempts + 1:
                msg += ", retrying..."
                logger.info(msg)
                time.sleep(delay)
                delay = delay + delay
                if delay > maxretrydelay:
                    delay = maxretrydelay
            else:
                msg += ", giving up"
                logger.info(msg)

        raise RuntimeError("command failed after %s attempts" % attempts)

    def waitfordevicelocal(self):
        """
        Check for presence of a local device - tap device may not
        appear right away waits

        :return: wait for device local response
        :rtype: int
        """

        def localdevexists():
            cmd = (constants.IP_BIN, "link", "show", self.localname)
            return utils.mutecall(cmd)

        self.waitfor(localdevexists)

    def waitfordevicenode(self):
        """
        Check for presence of a node device - tap device may not appear right away waits.

        :return: nothing
        """

        def nodedevexists():
            cmd = (constants.IP_BIN, "link", "show", self.name)
            return self.node.cmd(cmd)

        count = 0
        while True:
            try:
                self.waitfor(nodedevexists)
                break
            except RuntimeError as e:
                # check if this is an EMANE interface; if so, continue
                # waiting if EMANE is still running
                # TODO: remove emane code
                if count < 5 and nodeutils.is_node(self.net, NodeTypes.EMANE) and \
                        self.node.session.emane.emanerunning(self.node):
                    count += 1
                else:
                    raise e

    def install(self):
        """
        Install this TAP into its namespace. This is not done from the
        startup() method but called at a later time when a userspace
        program (running on the host) has had a chance to open the socket
        end of the TAP.

        :return: nothing
        """
        self.waitfordevicelocal()
        netns = str(self.node.pid)

        try:
            subprocess.check_call([constants.IP_BIN, "link", "set", self.localname, "netns", netns])
        except subprocess.CalledProcessError:
            msg = "error installing TAP interface %s, command:" % self.localname
            msg += "ip link set %s netns %s" % (self.localname, netns)
            logger.exception(msg)
            return

        self.node.cmd([constants.IP_BIN, "link", "set", self.localname, "name", self.name])
        self.node.cmd([constants.IP_BIN, "link", "set", self.name, "up"])

    def setaddrs(self):
        """
        Set interface addresses based on self.addrlist.

        :return: nothing
        """
        self.waitfordevicenode()
        for addr in self.addrlist:
            self.node.cmd([constants.IP_BIN, "addr", "add", str(addr), "dev", self.name])


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

        :param core.netns.nodes.CoreNode node: related core node
        :param str name: interface name
        :param core.session.Session session: core session instance
        :param mtu: interface mtu
        :param str remoteip: remote address
        :param int objid: object id
        :param str localip: local address
        :param ttl: ttl value
        :param key: gre tap key
        :param bool start: start flag
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
        cmd = ("ip", "link", "add", self.localname, "type", "gretap",
               "remote", str(remoteip))
        if localip:
            cmd += ("local", str(localip))
        if ttl:
            cmd += ("ttl", str(ttl))
        if key:
            cmd += ("key", str(key))
        subprocess.check_call(cmd)
        cmd = ("ip", "link", "set", self.localname, "up")
        subprocess.check_call(cmd)
        self.up = True

    def shutdown(self):
        """
        Shutdown logic for a GreTap.

        :return: nothing
        """
        if self.localname:
            cmd = ("ip", "link", "set", self.localname, "down")
            subprocess.check_call(cmd)
            cmd = ("ip", "link", "del", self.localname)
            subprocess.check_call(cmd)
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
