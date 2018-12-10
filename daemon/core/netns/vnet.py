"""
PyCoreNet and LxBrNet classes that implement virtual networks using
Linux Ethernet bridging and ebtables rules.
"""

import os
import threading
import time

from core import CoreCommandError
from core import constants
from core import logger
from core.coreobj import PyCoreNet
from core.misc import utils
from core.netns.vif import GreTap
from core.netns.vif import VEth

utils.check_executables([
    constants.BRCTL_BIN,
    constants.IP_BIN,
    constants.EBTABLES_BIN,
    constants.TC_BIN
])

ebtables_lock = threading.Lock()


class EbtablesQueue(object):
    """
    Helper class for queuing up ebtables commands into rate-limited
    atomic commits. This improves performance and reliability when there are
    many WLAN link updates.
    """
    # update rate is every 300ms
    rate = 0.3
    # ebtables
    atomic_file = "/tmp/pycore.ebtables.atomic"

    def __init__(self):
        """
        Initialize the helper class, but don't start the update thread
        until a WLAN is instantiated.
        """
        self.doupdateloop = False
        self.updatethread = None
        # this lock protects cmds and updates lists
        self.updatelock = threading.Lock()
        # list of pending ebtables commands
        self.cmds = []
        # list of WLANs requiring update
        self.updates = []
        # timestamps of last WLAN update; this keeps track of WLANs that are
        # using this queue
        self.last_update_time = {}

    def startupdateloop(self, wlan):
        """
        Kick off the update loop; only needs to be invoked once.

        :return: nothing
        """
        with self.updatelock:
            self.last_update_time[wlan] = time.time()

        if self.doupdateloop:
            return

        self.doupdateloop = True
        self.updatethread = threading.Thread(target=self.updateloop)
        self.updatethread.daemon = True
        self.updatethread.start()

    def stopupdateloop(self, wlan):
        """
        Kill the update loop thread if there are no more WLANs using it.

        :return: nothing
        """
        with self.updatelock:
            try:
                del self.last_update_time[wlan]
            except KeyError:
                logger.exception("error deleting last update time for wlan, ignored before: %s", wlan)

        if len(self.last_update_time) > 0:
            return

        self.doupdateloop = False
        if self.updatethread:
            self.updatethread.join()
            self.updatethread = None

    def ebatomiccmd(self, cmd):
        """
        Helper for building ebtables atomic file command list.

        :param list[str] cmd: ebtable command
        :return: ebtable atomic command
        :rtype: list[str]
        """
        r = [constants.EBTABLES_BIN, "--atomic-file", self.atomic_file]
        if cmd:
            r.extend(cmd)
        return r

    def lastupdate(self, wlan):
        """
        Return the time elapsed since this WLAN was last updated.

        :param wlan: wlan entity
        :return: elpased time
        :rtype: float
        """
        try:
            elapsed = time.time() - self.last_update_time[wlan]
        except KeyError:
            self.last_update_time[wlan] = time.time()
            elapsed = 0.0

        return elapsed

    def updated(self, wlan):
        """
        Keep track of when this WLAN was last updated.

        :param wlan: wlan entity
        :return: nothing
        """
        self.last_update_time[wlan] = time.time()
        self.updates.remove(wlan)

    def updateloop(self):
        """
        Thread target that looks for WLANs needing update, and
        rate limits the amount of ebtables activity. Only one userspace program
        should use ebtables at any given time, or results can be unpredictable.

        :return: nothing
        """
        while self.doupdateloop:
            with self.updatelock:
                for wlan in self.updates:
                    """
                    Check if wlan is from a previously closed session. Because of the
                    rate limiting scheme employed here, this may happen if a new session
                    is started soon after closing a previous session.
                    """
                    # TODO: if these are WlanNodes, this will never throw an exception
                    try:
                        wlan.session
                    except:
                        # Just mark as updated to remove from self.updates.
                        self.updated(wlan)
                        continue

                    if self.lastupdate(wlan) > self.rate:
                        self.buildcmds(wlan)
                        self.ebcommit(wlan)
                        self.updated(wlan)

            time.sleep(self.rate)

    def ebcommit(self, wlan):
        """
        Perform ebtables atomic commit using commands built in the self.cmds list.

        :return: nothing
        """
        # save kernel ebtables snapshot to a file
        args = self.ebatomiccmd(["--atomic-save", ])
        utils.check_cmd(args)

        # modify the table file using queued ebtables commands
        for c in self.cmds:
            args = self.ebatomiccmd(c)
            utils.check_cmd(args)
        self.cmds = []

        # commit the table file to the kernel
        args = self.ebatomiccmd(["--atomic-commit", ])
        utils.check_cmd(args)

        try:
            os.unlink(self.atomic_file)
        except OSError:
            logger.exception("error removing atomic file: %s", self.atomic_file)

    def ebchange(self, wlan):
        """
        Flag a change to the given WLAN"s _linked dict, so the ebtables
        chain will be rebuilt at the next interval.

        :return: nothing
        """
        with self.updatelock:
            if wlan not in self.updates:
                self.updates.append(wlan)

    def buildcmds(self, wlan):
        """
        Inspect a _linked dict from a wlan, and rebuild the ebtables chain for that WLAN.

        :return: nothing
        """
        with wlan._linked_lock:
            # flush the chain
            self.cmds.extend([["-F", wlan.brname], ])
            # rebuild the chain
            for netif1, v in wlan._linked.items():
                for netif2, linked in v.items():
                    if wlan.policy == "DROP" and linked:
                        self.cmds.extend([["-A", wlan.brname, "-i", netif1.localname,
                                           "-o", netif2.localname, "-j", "ACCEPT"],
                                          ["-A", wlan.brname, "-o", netif1.localname,
                                           "-i", netif2.localname, "-j", "ACCEPT"]])
                    elif wlan.policy == "ACCEPT" and not linked:
                        self.cmds.extend([["-A", wlan.brname, "-i", netif1.localname,
                                           "-o", netif2.localname, "-j", "DROP"],
                                          ["-A", wlan.brname, "-o", netif1.localname,
                                           "-i", netif2.localname, "-j", "DROP"]])


# a global object because all WLANs share the same queue
# cannot have multiple threads invoking the ebtables commnd
ebq = EbtablesQueue()


def ebtablescmds(call, cmds):
    """
    Run ebtable commands.

    :param func call: function to call commands
    :param list cmds: commands to call
    :return: nothing
    """
    with ebtables_lock:
        for args in cmds:
            call(args)


class LxBrNet(PyCoreNet):
    """
    Provides linux bridge network functionlity for core nodes.
    """
    policy = "DROP"

    def __init__(self, session, objid=None, name=None, start=True, policy=None):
        """
        Creates a LxBrNet instance.

        :param core.session.Session session: core session instance
        :param int objid: object id
        :param str name: object name
        :param bool start: start flag
        :param policy: network policy
        """
        PyCoreNet.__init__(self, session, objid, name, start)
        if name is None:
            name = str(self.objid)
        if policy is not None:
            self.policy = policy
        self.name = name
        sessionid = self.session.short_session_id()
        self.brname = "b.%s.%s" % (str(self.objid), sessionid)
        self.brcreate = True
        self.up = False
        if start:
            self.startup()
            ebq.startupdateloop(self)

    def startup(self):
        """
        Linux bridge starup logic.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if os.path.isdir("/sys/class/net/%s/bridge" % self.name):
            # attach to existing bridge when name matches
            logger.debug("joining existing bridge %s" % self.name)
            self.brname = self.name
            self.brcreate = False
        else:
            utils.check_cmd([constants.BRCTL_BIN, "addbr", self.brname])

            # turn off spanning tree protocol and forwarding delay
            utils.check_cmd([constants.BRCTL_BIN, "stp", self.brname, "off"])
            utils.check_cmd([constants.BRCTL_BIN, "setfd", self.brname, "0"])
        utils.check_cmd([constants.IP_BIN, "link", "set", self.brname, "up"])
        # create a new ebtables chain for this bridge
        ebtablescmds(utils.check_cmd, [
            [constants.EBTABLES_BIN, "-N", self.brname, "-P", self.policy],
            [constants.EBTABLES_BIN, "-A", "FORWARD", "--logical-in", self.brname, "-j", self.brname]
        ])
        # turn off multicast snooping so mcast forwarding occurs w/o IGMP joins
        snoop = "/sys/devices/virtual/net/%s/bridge/multicast_snooping" % self.brname
        if os.path.exists(snoop):
            with open(snoop, "w") as snoop_file:
                snoop_file.write("0")

        self.up = True

    def shutdown(self):
        """
        Linux bridge shutdown logic.

        :return: nothing
        """
        if not self.up:
            return

        ebq.stopupdateloop(self)

        try:
            if self.brcreate:
                utils.check_cmd([constants.IP_BIN, "link", "set", self.brname, "down"])
                utils.check_cmd([constants.BRCTL_BIN, "delbr", self.brname])
            ebtablescmds(utils.check_cmd, [
                [constants.EBTABLES_BIN, "-D", "FORWARD", "--logical-in", self.brname, "-j", self.brname],
                [constants.EBTABLES_BIN, "-X", self.brname]
            ])
        except CoreCommandError:
            logger.exception("error during shutdown")

        # removes veth pairs used for bridge-to-bridge connections
        for netif in self.netifs():
            netif.shutdown()

        self._netif.clear()
        self._linked.clear()
        del self.session
        self.up = False

    # TODO: this depends on a subtype with localname defined, seems like the wrong place for this to live
    def attach(self, netif):
        """
        Attach a network interface.

        :param core.netns.vnode.VEth netif: network interface to attach
        :return: nothing
        """
        if self.up:
            utils.check_cmd([constants.BRCTL_BIN, "addif", self.brname, netif.localname])
            utils.check_cmd([constants.IP_BIN, "link", "set", netif.localname, "up"])

        PyCoreNet.attach(self, netif)

    def detach(self, netif):
        """
        Detach a network interface.

        :param core.netns.vif.Veth netif: network interface to detach
        :return: nothing
        """
        if self.up:
            utils.check_cmd([constants.BRCTL_BIN, "delif", self.brname, netif.localname])

        PyCoreNet.detach(self, netif)

    def linked(self, netif1, netif2):
        """
        Determine if the provided network interfaces are linked.

        :param core.netns.vif.Veth netif1: interface one
        :param core.netns.vif.Veth netif2: interface two
        :return: True if interfaces are linked, False otherwise
        :rtype: bool
        """
        # check if the network interfaces are attached to this network
        if self._netif[netif1.netifi] != netif1:
            raise ValueError("inconsistency for netif %s" % netif1.name)

        if self._netif[netif2.netifi] != netif2:
            raise ValueError("inconsistency for netif %s" % netif2.name)

        try:
            linked = self._linked[netif1][netif2]
        except KeyError:
            if self.policy == "ACCEPT":
                linked = True
            elif self.policy == "DROP":
                linked = False
            else:
                raise Exception("unknown policy: %s" % self.policy)
            self._linked[netif1][netif2] = linked

        return linked

    def unlink(self, netif1, netif2):
        """
        Unlink two PyCoreNetIfs, resulting in adding or removing ebtables
        filtering rules.

        :param core.netns.vif.Veth netif1: interface one
        :param core.netns.vif.Veth netif2: interface two
        :return: nothing
        """
        with self._linked_lock:
            if not self.linked(netif1, netif2):
                return
            self._linked[netif1][netif2] = False

        ebq.ebchange(self)

    def link(self, netif1, netif2):
        """
        Link two PyCoreNetIfs together, resulting in adding or removing
        ebtables filtering rules.

        :param core.netns.vif.Veth netif1: interface one
        :param core.netns.vif.Veth netif2: interface two
        :return: nothing
        """
        with self._linked_lock:
            if self.linked(netif1, netif2):
                return
            self._linked[netif1][netif2] = True

        ebq.ebchange(self)

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None,
                   jitter=None, netif2=None, devname=None):
        """
        Configure link parameters by applying tc queuing disciplines on the interface.

        :param core.netns.vif.Veth netif: interface one
        :param bw: bandwidth to set to
        :param delay: packet delay to set to
        :param loss: packet loss to set to
        :param duplicate: duplicate percentage to set to
        :param jitter: jitter to set to
        :param core.netns.vif.Veth netif2: interface two
        :param devname: device name
        :return: nothing
        """
        if devname is None:
            devname = netif.localname
        tc = [constants.TC_BIN, "qdisc", "replace", "dev", devname]
        parent = ["root"]
        changed = False
        if netif.setparam("bw", bw):
            # from tc-tbf(8): minimum value for burst is rate / kernel_hz
            if bw is not None:
                burst = max(2 * netif.mtu, bw / 1000)
                # max IP payload
                limit = 0xffff
                tbf = ["tbf", "rate", str(bw),
                       "burst", str(burst), "limit", str(limit)]
            if bw > 0:
                if self.up:
                    logger.debug("linkconfig: %s" % ([tc + parent + ["handle", "1:"] + tbf],))
                    utils.check_cmd(tc + parent + ["handle", "1:"] + tbf)
                netif.setparam("has_tbf", True)
                changed = True
            elif netif.getparam("has_tbf") and bw <= 0:
                tcd = [] + tc
                tcd[2] = "delete"
                if self.up:
                    utils.check_cmd(tcd + parent)
                netif.setparam("has_tbf", False)
                # removing the parent removes the child
                netif.setparam("has_netem", False)
                changed = True
        if netif.getparam("has_tbf"):
            parent = ["parent", "1:1"]
        netem = ["netem"]
        changed = max(changed, netif.setparam("delay", delay))
        if loss is not None:
            loss = float(loss)
        changed = max(changed, netif.setparam("loss", loss))
        if duplicate is not None:
            duplicate = float(duplicate)
        changed = max(changed, netif.setparam("duplicate", duplicate))
        changed = max(changed, netif.setparam("jitter", jitter))
        if not changed:
            return
        # jitter and delay use the same delay statement
        if delay is not None:
            netem += ["delay", "%sus" % delay]
        if jitter is not None:
            if delay is None:
                netem += ["delay", "0us", "%sus" % jitter, "25%"]
            else:
                netem += ["%sus" % jitter, "25%"]

        if loss is not None and loss > 0:
            netem += ["loss", "%s%%" % min(loss, 100)]
        if duplicate is not None and duplicate > 0:
            netem += ["duplicate", "%s%%" % min(duplicate, 100)]
        if delay <= 0 and jitter <= 0 and loss <= 0 and duplicate <= 0:
            # possibly remove netem if it exists and parent queue wasn't removed
            if not netif.getparam("has_netem"):
                return
            tc[2] = "delete"
            if self.up:
                logger.debug("linkconfig: %s" % ([tc + parent + ["handle", "10:"]],))
                utils.check_cmd(tc + parent + ["handle", "10:"])
            netif.setparam("has_netem", False)
        elif len(netem) > 1:
            if self.up:
                logger.debug("linkconfig: %s" % ([tc + parent + ["handle", "10:"] + netem],))
                utils.check_cmd(tc + parent + ["handle", "10:"] + netem)
            netif.setparam("has_netem", True)

    def linknet(self, net):
        """
        Link this bridge with another by creating a veth pair and installing
        each device into each bridge.

        :param core.netns.vnet.LxBrNet net: network to link with
        :return: created interface
        :rtype: Veth
        """
        sessionid = self.session.short_session_id()
        try:
            self_objid = "%x" % self.objid
        except TypeError:
            self_objid = "%s" % self.objid

        try:
            net_objid = "%x" % net.objid
        except TypeError:
            net_objid = "%s" % net.objid

        localname = "veth%s.%s.%s" % (self_objid, net_objid, sessionid)
        if len(localname) >= 16:
            raise ValueError("interface local name %s too long" % localname)

        name = "veth%s.%s.%s" % (net_objid, self_objid, sessionid)
        if len(name) >= 16:
            raise ValueError("interface name %s too long" % name)

        netif = VEth(node=None, name=name, localname=localname, mtu=1500, net=self, start=self.up)
        self.attach(netif)
        if net.up:
            # this is similar to net.attach() but uses netif.name instead
            # of localname
            utils.check_cmd([constants.BRCTL_BIN, "addif", net.brname, netif.name])
            utils.check_cmd([constants.IP_BIN, "link", "set", netif.name, "up"])
        i = net.newifindex()
        net._netif[i] = netif
        with net._linked_lock:
            net._linked[netif] = {}
        netif.net = self
        netif.othernet = net
        return netif

    def getlinknetif(self, net):
        """
        Return the interface of that links this net with another net
        (that were linked using linknet()).

        :param core.netns.vnet.LxBrNet net: interface to get link for
        :return: interface the provided network is linked to
        :rtype: core.netns.vnet.LxBrNet
        """
        for netif in self.netifs():
            if hasattr(netif, "othernet") and netif.othernet == net:
                return netif

        return None

    def addrconfig(self, addrlist):
        """
        Set addresses on the bridge.

        :param list[str] addrlist: address list
        :return: nothing
        """
        if not self.up:
            return

        for addr in addrlist:
            utils.check_cmd([constants.IP_BIN, "addr", "add", str(addr), "dev", self.brname])


class GreTapBridge(LxBrNet):
    """
    A network consisting of a bridge with a gretap device for tunneling to
    another system.
    """

    def __init__(self, session, remoteip=None, objid=None, name=None,
                 policy="ACCEPT", localip=None, ttl=255, key=None, start=True):
        """
        Create a GreTapBridge instance.

        :param core.session.Session session: core session instance
        :param str remoteip: remote address
        :param int objid: object id
        :param str name: object name
        :param policy: network policy
        :param str localip: local address
        :param ttl: ttl value
        :param key: gre tap key
        :param bool start: start flag
        :return:
        """
        LxBrNet.__init__(self, session=session, objid=objid, name=name, policy=policy, start=False)
        self.grekey = key
        if self.grekey is None:
            self.grekey = self.session.session_id ^ self.objid
        self.localnum = None
        self.remotenum = None
        self.remoteip = remoteip
        self.localip = localip
        self.ttl = ttl
        if remoteip is None:
            self.gretap = None
        else:
            self.gretap = GreTap(node=self, session=session, remoteip=remoteip,
                                 localip=localip, ttl=ttl, key=self.grekey)
        if start:
            self.startup()

    def startup(self):
        """
        Creates a bridge and adds the gretap device to it.

        :return: nothing
        """
        LxBrNet.startup(self)
        if self.gretap:
            self.attach(self.gretap)

    def shutdown(self):
        """
        Detach the gretap device and remove the bridge.

        :return: nothing
        """
        if self.gretap:
            self.detach(self.gretap)
            self.gretap.shutdown()
            self.gretap = None
        LxBrNet.shutdown(self)

    def addrconfig(self, addrlist):
        """
        Set the remote tunnel endpoint. This is a one-time method for
        creating the GreTap device, which requires the remoteip at startup.
        The 1st address in the provided list is remoteip, 2nd optionally
        specifies localip.

        :param list addrlist: address list
        :return: nothing
        """
        if self.gretap:
            raise ValueError("gretap already exists for %s" % self.name)
        remoteip = addrlist[0].split("/")[0]
        localip = None
        if len(addrlist) > 1:
            localip = addrlist[1].split("/")[0]
        self.gretap = GreTap(session=self.session, remoteip=remoteip,
                             localip=localip, ttl=self.ttl, key=self.grekey)
        self.attach(self.gretap)

    def setkey(self, key):
        """
        Set the GRE key used for the GreTap device. This needs to be set
        prior to instantiating the GreTap device (before addrconfig).

        :param key: gre key
        :return: nothing
        """
        self.grekey = key
