"""
Defines network nodes used within core.
"""

import logging
import os
import socket
import threading
import time
from socket import AF_INET, AF_INET6

from core import constants, utils
from core.emulator import distributed
from core.emulator.data import LinkData
from core.emulator.enumerations import LinkTypes, NodeTypes, RegisterTlvs
from core.errors import CoreCommandError, CoreError
from core.nodes import ipaddress
from core.nodes.base import CoreNetworkBase
from core.nodes.interface import GreTap, Veth

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
                logging.exception(
                    "error deleting last update time for wlan, ignored before: %s", wlan
                )

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
                    # Check if wlan is from a previously closed session. Because of the
                    # rate limiting scheme employed here, this may happen if a new session
                    # is started soon after closing a previous session.
                    # TODO: if these are WlanNodes, this will never throw an exception
                    try:
                        wlan.session
                    except Exception:
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
        args = self.ebatomiccmd(["--atomic-save"])
        utils.check_cmd(args)

        # modify the table file using queued ebtables commands
        for c in self.cmds:
            args = self.ebatomiccmd(c)
            utils.check_cmd(args)
        self.cmds = []

        # commit the table file to the kernel
        args = self.ebatomiccmd(["--atomic-commit"])
        utils.check_cmd(args)

        try:
            os.unlink(self.atomic_file)
        except OSError:
            logging.exception("error removing atomic file: %s", self.atomic_file)

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
            self.cmds.extend([["-F", wlan.brname]])
            # rebuild the chain
            for netif1, v in wlan._linked.items():
                for netif2, linked in v.items():
                    if wlan.policy == "DROP" and linked:
                        self.cmds.extend(
                            [
                                [
                                    "-A",
                                    wlan.brname,
                                    "-i",
                                    netif1.localname,
                                    "-o",
                                    netif2.localname,
                                    "-j",
                                    "ACCEPT",
                                ],
                                [
                                    "-A",
                                    wlan.brname,
                                    "-o",
                                    netif1.localname,
                                    "-i",
                                    netif2.localname,
                                    "-j",
                                    "ACCEPT",
                                ],
                            ]
                        )
                    elif wlan.policy == "ACCEPT" and not linked:
                        self.cmds.extend(
                            [
                                [
                                    "-A",
                                    wlan.brname,
                                    "-i",
                                    netif1.localname,
                                    "-o",
                                    netif2.localname,
                                    "-j",
                                    "DROP",
                                ],
                                [
                                    "-A",
                                    wlan.brname,
                                    "-o",
                                    netif1.localname,
                                    "-i",
                                    netif2.localname,
                                    "-j",
                                    "DROP",
                                ],
                            ]
                        )


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


class CoreNetwork(CoreNetworkBase):
    """
    Provides linux bridge network functionality for core nodes.
    """

    policy = "DROP"

    def __init__(
        self, session, _id=None, name=None, start=True, server=None, policy=None
    ):
        """
        Creates a LxBrNet instance.

        :param core.session.Session session: core session instance
        :param int _id: object id
        :param str name: object name
        :param bool start: start flag
        :param fabric.connection.Connection server: remote server node will run on,
            default is None for localhost
        :param policy: network policy
        """
        CoreNetworkBase.__init__(self, session, _id, name, start, server)
        if name is None:
            name = str(self.id)
        if policy is not None:
            self.policy = policy
        self.name = name
        sessionid = self.session.short_session_id()
        self.brname = "b.%s.%s" % (str(self.id), sessionid)
        self.up = False
        if start:
            self.startup()
            ebq.startupdateloop(self)

    def net_cmd(self, args, env=None):
        """
        Runs a command that is used to configure and setup the network on the host
        system.

        :param list[str]|str args: command to run
        :param dict env: environment to run command with
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.info("network node(%s) cmd", self.name)
        output = utils.check_cmd(args, env=env)

        args = " ".join(args)
        for server in self.session.servers:
            conn = self.session.servers[server]
            distributed.remote_cmd(conn, args, env=env)

        return output

    def startup(self):
        """
        Linux bridge starup logic.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.net_client.create_bridge(self.brname)

        # create a new ebtables chain for this bridge
        ebtablescmds(
            utils.check_cmd,
            [
                [constants.EBTABLES_BIN, "-N", self.brname, "-P", self.policy],
                [
                    constants.EBTABLES_BIN,
                    "-A",
                    "FORWARD",
                    "--logical-in",
                    self.brname,
                    "-j",
                    self.brname,
                ],
            ],
        )

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
            self.net_client.delete_bridge(self.brname)
            ebtablescmds(
                utils.check_cmd,
                [
                    [
                        constants.EBTABLES_BIN,
                        "-D",
                        "FORWARD",
                        "--logical-in",
                        self.brname,
                        "-j",
                        self.brname,
                    ],
                    [constants.EBTABLES_BIN, "-X", self.brname],
                ],
            )
        except CoreCommandError:
            logging.exception("error during shutdown")

        # removes veth pairs used for bridge-to-bridge connections
        for netif in self.netifs():
            netif.shutdown()

        self._netif.clear()
        self._linked.clear()
        del self.session
        self.up = False

    # TODO: this depends on a subtype with localname defined, seems like the
    #  wrong place for this to live
    def attach(self, netif):
        """
        Attach a network interface.

        :param core.nodes.interface.Veth netif: network interface to attach
        :return: nothing
        """
        if self.up:
            netif.net_client.create_interface(self.brname, netif.localname)

        CoreNetworkBase.attach(self, netif)

    def detach(self, netif):
        """
        Detach a network interface.

        :param core.nodes.interface.Veth netif: network interface to detach
        :return: nothing
        """
        if self.up:
            netif.net_client.delete_interface(self.brname, netif.localname)

        CoreNetworkBase.detach(self, netif)

    def linked(self, netif1, netif2):
        """
        Determine if the provided network interfaces are linked.

        :param core.nodes.interface.CoreInterface netif1: interface one
        :param core.nodes.interface.CoreInterface netif2: interface two
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

        :param core.nodes.interface.CoreInterface netif1: interface one
        :param core.nodes.interface.CoreInterface netif2: interface two
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

        :param core.nodes.interface.CoreInterface netif1: interface one
        :param core.nodes.interface.CoreInterface netif2: interface two
        :return: nothing
        """
        with self._linked_lock:
            if self.linked(netif1, netif2):
                return
            self._linked[netif1][netif2] = True

        ebq.ebchange(self)

    def linkconfig(
        self,
        netif,
        bw=None,
        delay=None,
        loss=None,
        duplicate=None,
        jitter=None,
        netif2=None,
        devname=None,
    ):
        """
        Configure link parameters by applying tc queuing disciplines on the interface.

        :param core.nodes.interface.Veth netif: interface one
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
                limit = 0xFFFF
                tbf = ["tbf", "rate", str(bw), "burst", str(burst), "limit", str(limit)]
            if bw > 0:
                if self.up:
                    logging.debug(
                        "linkconfig: %s" % ([tc + parent + ["handle", "1:"] + tbf],)
                    )
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
            duplicate = int(duplicate)
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

        delay_check = delay is None or delay <= 0
        jitter_check = jitter is None or jitter <= 0
        loss_check = loss is None or loss <= 0
        duplicate_check = duplicate is None or duplicate <= 0
        if all([delay_check, jitter_check, loss_check, duplicate_check]):
            # possibly remove netem if it exists and parent queue wasn't removed
            if not netif.getparam("has_netem"):
                return
            tc[2] = "delete"
            if self.up:
                logging.debug("linkconfig: %s" % ([tc + parent + ["handle", "10:"]],))
                utils.check_cmd(tc + parent + ["handle", "10:"])
            netif.setparam("has_netem", False)
        elif len(netem) > 1:
            if self.up:
                logging.debug(
                    "linkconfig: %s" % ([tc + parent + ["handle", "10:"] + netem],)
                )
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
            _id = "%x" % self.id
        except TypeError:
            _id = "%s" % self.id

        try:
            net_id = "%x" % net.id
        except TypeError:
            net_id = "%s" % net.id

        localname = "veth%s.%s.%s" % (_id, net_id, sessionid)
        if len(localname) >= 16:
            raise ValueError("interface local name %s too long" % localname)

        name = "veth%s.%s.%s" % (net_id, _id, sessionid)
        if len(name) >= 16:
            raise ValueError("interface name %s too long" % name)

        netif = Veth(node=None, name=name, localname=localname, mtu=1500, start=self.up)
        self.attach(netif)
        if net.up:
            # this is similar to net.attach() but uses netif.name instead of localname
            netif.net_client.create_interface(net.brname, netif.name)
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

        :param core.nodes.base.CoreNetworkBase net: interface to get link for
        :return: interface the provided network is linked to
        :rtype: core.nodes.interface.CoreInterface
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
            self.net_client.create_address(self.brname, str(addr))


class GreTapBridge(CoreNetwork):
    """
    A network consisting of a bridge with a gretap device for tunneling to
    another system.
    """

    def __init__(
        self,
        session,
        remoteip=None,
        _id=None,
        name=None,
        policy="ACCEPT",
        localip=None,
        ttl=255,
        key=None,
        start=True,
        server=None,
    ):
        """
        Create a GreTapBridge instance.

        :param core.emulator.session.Session session: core session instance
        :param str remoteip: remote address
        :param int _id: object id
        :param str name: object name
        :param policy: network policy
        :param str localip: local address
        :param ttl: ttl value
        :param key: gre tap key
        :param bool start: start flag
        :param fabric.connection.Connection server: remote server node will run on,
            default is None for localhost
        """
        CoreNetwork.__init__(self, session, _id, name, False, server, policy)
        self.grekey = key
        if self.grekey is None:
            self.grekey = self.session.id ^ self.id
        self.localnum = None
        self.remotenum = None
        self.remoteip = remoteip
        self.localip = localip
        self.ttl = ttl
        if remoteip is None:
            self.gretap = None
        else:
            self.gretap = GreTap(
                node=self,
                session=session,
                remoteip=remoteip,
                localip=localip,
                ttl=ttl,
                key=self.grekey,
            )
        if start:
            self.startup()

    def startup(self):
        """
        Creates a bridge and adds the gretap device to it.

        :return: nothing
        """
        CoreNetwork.startup(self)
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
        CoreNetwork.shutdown(self)

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
        self.gretap = GreTap(
            session=self.session,
            remoteip=remoteip,
            localip=localip,
            ttl=self.ttl,
            key=self.grekey,
        )
        self.attach(self.gretap)

    def setkey(self, key):
        """
        Set the GRE key used for the GreTap device. This needs to be set
        prior to instantiating the GreTap device (before addrconfig).

        :param key: gre key
        :return: nothing
        """
        self.grekey = key


class CtrlNet(CoreNetwork):
    """
    Control network functionality.
    """

    policy = "ACCEPT"
    # base control interface index
    CTRLIF_IDX_BASE = 99
    DEFAULT_PREFIX_LIST = [
        "172.16.0.0/24 172.16.1.0/24 172.16.2.0/24 172.16.3.0/24 172.16.4.0/24",
        "172.17.0.0/24 172.17.1.0/24 172.17.2.0/24 172.17.3.0/24 172.17.4.0/24",
        "172.18.0.0/24 172.18.1.0/24 172.18.2.0/24 172.18.3.0/24 172.18.4.0/24",
        "172.19.0.0/24 172.19.1.0/24 172.19.2.0/24 172.19.3.0/24 172.19.4.0/24",
    ]

    def __init__(
        self,
        session,
        _id="ctrlnet",
        name=None,
        prefix=None,
        hostid=None,
        start=True,
        server=None,
        assign_address=True,
        updown_script=None,
        serverintf=None,
    ):
        """
        Creates a CtrlNet instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: node id
        :param str name: node namee
        :param prefix: control network ipv4 prefix
        :param hostid: host id
        :param bool start: start flag
        :param fabric.connection.Connection server: remote server node will run on,
            default is None for localhost
        :param str assign_address: assigned address
        :param str updown_script: updown script
        :param serverintf: server interface
        :return:
        """
        self.prefix = ipaddress.Ipv4Prefix(prefix)
        self.hostid = hostid
        self.assign_address = assign_address
        self.updown_script = updown_script
        self.serverintf = serverintf
        CoreNetwork.__init__(self, session, _id, name, start, server)

    def startup(self):
        """
        Startup functionality for the control network.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.net_client.existing_bridges(self.id):
            raise CoreError("old bridges exist for node: %s" % self.id)

        CoreNetwork.startup(self)

        if self.hostid:
            addr = self.prefix.addr(self.hostid)
        else:
            addr = self.prefix.max_addr()

        logging.info("added control network bridge: %s %s", self.brname, self.prefix)

        if self.assign_address:
            addrlist = ["%s/%s" % (addr, self.prefix.prefixlen)]
            self.addrconfig(addrlist=addrlist)
            logging.info("address %s", addr)

        if self.updown_script:
            logging.info(
                "interface %s updown script (%s startup) called",
                self.brname,
                self.updown_script,
            )
            utils.check_cmd([self.updown_script, self.brname, "startup"])

        if self.serverintf:
            self.net_client.create_interface(self.brname, self.serverintf)

    def shutdown(self):
        """
        Control network shutdown.

        :return: nothing
        """
        if self.serverintf is not None:
            try:
                self.net_client.delete_interface(self.brname, self.serverintf)
            except CoreCommandError:
                logging.exception(
                    "error deleting server interface %s from bridge %s",
                    self.serverintf,
                    self.brname,
                )

        if self.updown_script is not None:
            try:
                logging.info(
                    "interface %s updown script (%s shutdown) called",
                    self.brname,
                    self.updown_script,
                )
                utils.check_cmd([self.updown_script, self.brname, "shutdown"])
            except CoreCommandError:
                logging.exception("error issuing shutdown script shutdown")

        CoreNetwork.shutdown(self)

    def all_link_data(self, flags):
        """
        Do not include CtrlNet in link messages describing this session.

        :param flags: message flags
        :return: list of link data
        :rtype: list[core.data.LinkData]
        """
        return []


class PtpNet(CoreNetwork):
    """
    Peer to peer network node.
    """

    policy = "ACCEPT"

    def attach(self, netif):
        """
        Attach a network interface, but limit attachment to two interfaces.

        :param core.netns.vif.VEth netif: network interface
        :return: nothing
        """
        if len(self._netif) >= 2:
            raise ValueError(
                "Point-to-point links support at most 2 network interfaces"
            )

        CoreNetwork.attach(self, netif)

    def data(self, message_type, lat=None, lon=None, alt=None):
        """
        Do not generate a Node Message for point-to-point links. They are
        built using a link message instead.

        :param message_type: purpose for the data object we are creating
        :param float lat: latitude
        :param float lon: longitude
        :param float alt: altitude
        :return: node data object
        :rtype: core.emulator.data.NodeData
        """
        return None

    def all_link_data(self, flags):
        """
        Build CORE API TLVs for a point-to-point link. One Link message
        describes this network.

        :param flags: message flags
        :return: list of link data
        :rtype: list[core.emulator.data.LinkData]
        """

        all_links = []

        if len(self._netif) != 2:
            return all_links

        if1, if2 = self._netif.values()
        unidirectional = 0
        if if1.getparams() != if2.getparams():
            unidirectional = 1

        interface1_ip4 = None
        interface1_ip4_mask = None
        interface1_ip6 = None
        interface1_ip6_mask = None
        for address in if1.addrlist:
            ip, _sep, mask = address.partition("/")
            mask = int(mask)
            if ipaddress.is_ipv4_address(ip):
                family = AF_INET
                ipl = socket.inet_pton(family, ip)
                interface1_ip4 = ipaddress.IpAddress(af=family, address=ipl)
                interface1_ip4_mask = mask
            else:
                family = AF_INET6
                ipl = socket.inet_pton(family, ip)
                interface1_ip6 = ipaddress.IpAddress(af=family, address=ipl)
                interface1_ip6_mask = mask

        interface2_ip4 = None
        interface2_ip4_mask = None
        interface2_ip6 = None
        interface2_ip6_mask = None
        for address in if2.addrlist:
            ip, _sep, mask = address.partition("/")
            mask = int(mask)
            if ipaddress.is_ipv4_address(ip):
                family = AF_INET
                ipl = socket.inet_pton(family, ip)
                interface2_ip4 = ipaddress.IpAddress(af=family, address=ipl)
                interface2_ip4_mask = mask
            else:
                family = AF_INET6
                ipl = socket.inet_pton(family, ip)
                interface2_ip6 = ipaddress.IpAddress(af=family, address=ipl)
                interface2_ip6_mask = mask

        link_data = LinkData(
            message_type=flags,
            node1_id=if1.node.id,
            node2_id=if2.node.id,
            link_type=self.linktype,
            unidirectional=unidirectional,
            delay=if1.getparam("delay"),
            bandwidth=if1.getparam("bw"),
            per=if1.getparam("loss"),
            dup=if1.getparam("duplicate"),
            jitter=if1.getparam("jitter"),
            interface1_id=if1.node.getifindex(if1),
            interface1_mac=if1.hwaddr,
            interface1_ip4=interface1_ip4,
            interface1_ip4_mask=interface1_ip4_mask,
            interface1_ip6=interface1_ip6,
            interface1_ip6_mask=interface1_ip6_mask,
            interface2_id=if2.node.getifindex(if2),
            interface2_mac=if2.hwaddr,
            interface2_ip4=interface2_ip4,
            interface2_ip4_mask=interface2_ip4_mask,
            interface2_ip6=interface2_ip6,
            interface2_ip6_mask=interface2_ip6_mask,
        )

        all_links.append(link_data)

        # build a 2nd link message for the upstream link parameters
        # (swap if1 and if2)
        if unidirectional:
            link_data = LinkData(
                message_type=0,
                node1_id=if2.node.id,
                node2_id=if1.node.id,
                delay=if2.getparam("delay"),
                bandwidth=if2.getparam("bw"),
                per=if2.getparam("loss"),
                dup=if2.getparam("duplicate"),
                jitter=if2.getparam("jitter"),
                unidirectional=1,
                interface1_id=if2.node.getifindex(if2),
                interface2_id=if1.node.getifindex(if1),
            )
            all_links.append(link_data)

        return all_links


class SwitchNode(CoreNetwork):
    """
    Provides switch functionality within a core node.
    """

    apitype = NodeTypes.SWITCH.value
    policy = "ACCEPT"
    type = "lanswitch"


class HubNode(CoreNetwork):
    """
    Provides hub functionality within a core node, forwards packets to all bridge
    ports by turning off MAC address learning.
    """

    apitype = NodeTypes.HUB.value
    policy = "ACCEPT"
    type = "hub"

    def __init__(self, session, _id=None, name=None, start=True, server=None):
        """
        Creates a HubNode instance.

        :param core.session.Session session: core session instance
        :param int _id: node id
        :param str name: node namee
        :param bool start: start flag
        :param str server: remote server node will run on, default is None for localhost
        :raises CoreCommandError: when there is a command exception
        """
        CoreNetwork.__init__(self, session, _id, name, start, server)

        # TODO: move to startup method
        if start:
            self.net_client.disable_mac_learning(self.brname)


class WlanNode(CoreNetwork):
    """
    Provides wireless lan functionality within a core node.
    """

    apitype = NodeTypes.WIRELESS_LAN.value
    linktype = LinkTypes.WIRELESS.value
    policy = "DROP"
    type = "wlan"

    def __init__(
        self, session, _id=None, name=None, start=True, server=None, policy=None
    ):
        """
        Create a WlanNode instance.

        :param core.session.Session session: core session instance
        :param int _id: node id
        :param str name: node name
        :param bool start: start flag
        :param str server: remote server node will run on, default is None for localhost
        :param policy: wlan policy
        """
        CoreNetwork.__init__(self, session, _id, name, start, server, policy)
        # wireless model such as basic range
        self.model = None
        # mobility model such as scripted
        self.mobility = None

        # TODO: move to startup method
        if start:
            self.net_client.disable_mac_learning(self.brname)

    def attach(self, netif):
        """
        Attach a network interface.

        :param core.nodes.interface.CoreInterface netif: network interface
        :return: nothing
        """
        CoreNetwork.attach(self, netif)
        if self.model:
            netif.poshook = self.model.position_callback
            if netif.node is None:
                return
            x, y, z = netif.node.position.get()
            # invokes any netif.poshook
            netif.setposition(x, y, z)

    def setmodel(self, model, config):
        """
        Sets the mobility and wireless model.

        :param core.location.mobility.WirelessModel.cls model: wireless model to set to
        :param dict config: configuration for model being set
        :return: nothing
        """
        logging.debug("node(%s) setting model: %s", self.name, model.name)
        if model.config_type == RegisterTlvs.WIRELESS.value:
            self.model = model(session=self.session, _id=self.id)
            for netif in self.netifs():
                netif.poshook = self.model.position_callback
                if netif.poshook and netif.node:
                    x, y, z = netif.node.position.get()
                    netif.poshook(netif, x, y, z)
            self.updatemodel(config)
        elif model.config_type == RegisterTlvs.MOBILITY.value:
            self.mobility = model(session=self.session, _id=self.id)
            self.mobility.update_config(config)

    def update_mobility(self, config):
        if not self.mobility:
            raise ValueError("no mobility set to update for node(%s)", self.id)
        self.mobility.update_config(config)

    def updatemodel(self, config):
        if not self.model:
            raise ValueError("no model set to update for node(%s)", self.id)
        logging.debug(
            "node(%s) updating model(%s): %s", self.id, self.model.name, config
        )
        self.model.update_config(config)
        for netif in self.netifs():
            if netif.poshook and netif.node:
                x, y, z = netif.node.position.get()
                netif.poshook(netif, x, y, z)

    def all_link_data(self, flags):
        """
        Retrieve all link data.

        :param flags: message flags
        :return: list of link data
        :rtype: list[core.emulator.data.LinkData]
        """
        all_links = CoreNetwork.all_link_data(self, flags)

        if self.model:
            all_links.extend(self.model.all_link_data(flags))

        return all_links


class TunnelNode(GreTapBridge):
    """
    Provides tunnel functionality in a core node.
    """

    apitype = NodeTypes.TUNNEL.value
    policy = "ACCEPT"
    type = "tunnel"
