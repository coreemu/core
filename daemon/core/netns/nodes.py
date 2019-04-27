"""
Definition of LxcNode, CoreNode, and other node classes that inherit from the CoreNode,
implementing specific node types.
"""

import logging
import socket
import threading
from socket import AF_INET
from socket import AF_INET6

from core import CoreCommandError
from core import constants
from core.coreobj import PyCoreNetIf
from core.coreobj import PyCoreNode
from core.coreobj import PyCoreObj
from core.data import LinkData
from core.enumerations import LinkTypes
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.misc import ipaddress
from core.misc import utils
from core.netns.vnet import GreTapBridge
from core.netns.vnet import LxBrNet
from core.netns.vnode import LxcNode


class CtrlNet(LxBrNet):
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
        "172.19.0.0/24 172.19.1.0/24 172.19.2.0/24 172.19.3.0/24 172.19.4.0/24"
    ]

    def __init__(self, session, _id="ctrlnet", name=None, prefix=None,
                 hostid=None, start=True, assign_address=True,
                 updown_script=None, serverintf=None):
        """
        Creates a CtrlNet instance.

        :param core.session.Session session: core session instance
        :param int _id: node id
        :param str name: node namee
        :param prefix: control network ipv4 prefix
        :param hostid: host id
        :param bool start: start flag
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
        LxBrNet.__init__(self, session, _id=_id, name=name, start=start)

    def startup(self):
        """
        Startup functionality for the control network.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.detectoldbridge():
            return

        LxBrNet.startup(self)

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
            logging.info("interface %s updown script (%s startup) called", self.brname, self.updown_script)
            utils.check_cmd([self.updown_script, self.brname, "startup"])

        if self.serverintf:
            # sets the interface as a port of the bridge
            utils.check_cmd([constants.BRCTL_BIN, "addif", self.brname, self.serverintf])

            # bring interface up
            utils.check_cmd([constants.IP_BIN, "link", "set", self.serverintf, "up"])

    def detectoldbridge(self):
        """
        Occassionally, control net bridges from previously closed sessions are not cleaned up.
        Check if there are old control net bridges and delete them

        :return: True if an old bridge was detected, False otherwise
        :rtype: bool
        """
        status, output = utils.cmd_output([constants.BRCTL_BIN, "show"])
        if status != 0:
            logging.error("Unable to retrieve list of installed bridges")
        else:
            lines = output.split("\n")
            for line in lines[1:]:
                cols = line.split("\t")
                oldbr = cols[0]
                flds = cols[0].split(".")
                if len(flds) == 3:
                    if flds[0] == "b" and flds[1] == self.id:
                        logging.error(
                            "error: An active control net bridge (%s) found. "
                            "An older session might still be running. "
                            "Stop all sessions and, if needed, delete %s to continue.", oldbr, oldbr
                        )
                        return True
        return False

    def shutdown(self):
        """
        Control network shutdown.

        :return: nothing
        """
        if self.serverintf is not None:
            try:
                utils.check_cmd([constants.BRCTL_BIN, "delif", self.brname, self.serverintf])
            except CoreCommandError:
                logging.exception("error deleting server interface %s from bridge %s", self.serverintf, self.brname)

        if self.updown_script is not None:
            try:
                logging.info("interface %s updown script (%s shutdown) called", self.brname, self.updown_script)
                utils.check_cmd([self.updown_script, self.brname, "shutdown"])
            except CoreCommandError:
                logging.exception("error issuing shutdown script shutdown")

        LxBrNet.shutdown(self)

    def all_link_data(self, flags):
        """
        Do not include CtrlNet in link messages describing this session.

        :param flags: message flags
        :return: list of link data
        :rtype: list[core.data.LinkData]
        """
        return []


class CoreNode(LxcNode):
    """
    Basic core node class for nodes to extend.
    """
    apitype = NodeTypes.DEFAULT.value


class PtpNet(LxBrNet):
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
            raise ValueError("Point-to-point links support at most 2 network interfaces")

        LxBrNet.attach(self, netif)

    def data(self, message_type, lat=None, lon=None, alt=None):
        """
        Do not generate a Node Message for point-to-point links. They are
        built using a link message instead.

        :param message_type: purpose for the data object we are creating
        :param float lat: latitude
        :param float lon: longitude
        :param float alt: altitude
        :return: node data object
        :rtype: core.data.NodeData
        """
        return None

    def all_link_data(self, flags):
        """
        Build CORE API TLVs for a point-to-point link. One Link message
        describes this network.

        :param flags: message flags
        :return: list of link data
        :rtype: list[core.data.LinkData]
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
                delay=if1.getparam("delay"),
                bandwidth=if1.getparam("bw"),
                dup=if1.getparam("duplicate"),
                jitter=if1.getparam("jitter"),
                unidirectional=1,
                interface1_id=if2.node.getifindex(if2),
                interface2_id=if1.node.getifindex(if1)
            )
            all_links.append(link_data)

        return all_links


class SwitchNode(LxBrNet):
    """
    Provides switch functionality within a core node.
    """
    apitype = NodeTypes.SWITCH.value
    policy = "ACCEPT"
    type = "lanswitch"


class HubNode(LxBrNet):
    """
    Provides hub functionality within a core node, forwards packets to all bridge
    ports by turning off MAC address learning.
    """
    apitype = NodeTypes.HUB.value
    policy = "ACCEPT"
    type = "hub"

    def __init__(self, session, _id=None, name=None, start=True):
        """
        Creates a HubNode instance.

        :param core.session.Session session: core session instance
        :param int _id: node id
        :param str name: node namee
        :param bool start: start flag
        :raises CoreCommandError: when there is a command exception
        """
        LxBrNet.__init__(self, session, _id, name, start)

        # TODO: move to startup method
        if start:
            utils.check_cmd([constants.BRCTL_BIN, "setageing", self.brname, "0"])


class WlanNode(LxBrNet):
    """
    Provides wireless lan functionality within a core node.
    """
    apitype = NodeTypes.WIRELESS_LAN.value
    linktype = LinkTypes.WIRELESS.value
    policy = "DROP"
    type = "wlan"

    def __init__(self, session, _id=None, name=None, start=True, policy=None):
        """
        Create a WlanNode instance.

        :param core.session.Session session: core session instance
        :param int _id: node id
        :param str name: node name
        :param bool start: start flag
        :param policy: wlan policy
        """
        LxBrNet.__init__(self, session, _id, name, start, policy)
        # wireless model such as basic range
        self.model = None
        # mobility model such as scripted
        self.mobility = None

    def attach(self, netif):
        """
        Attach a network interface.

        :param core.netns.vif.VEth netif: network interface
        :return: nothing
        """
        LxBrNet.attach(self, netif)
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

        :param core.mobility.WirelessModel.cls model: wireless model to set to
        :param dict config: configuration for model being set
        :return: nothing
        """
        logging.info("adding model: %s", model.name)
        if model.config_type == RegisterTlvs.WIRELESS.value:
            self.model = model(session=self.session, object_id=self.id)
            self.model.update_config(config)
            if self.model.position_callback:
                for netif in self.netifs():
                    netif.poshook = self.model.position_callback
                    if netif.node is not None:
                        x, y, z = netif.node.position.get()
                        netif.poshook(netif, x, y, z)
            self.model.setlinkparams()
        elif model.config_type == RegisterTlvs.MOBILITY.value:
            self.mobility = model(session=self.session, object_id=self.id)
            self.mobility.update_config(config)

    def update_mobility(self, config):
        if not self.mobility:
            raise ValueError("no mobility set to update for node(%s)", self.id)
        self.mobility.set_configs(config, node_id=self.id)

    def updatemodel(self, config):
        if not self.model:
            raise ValueError("no model set to update for node(%s)", self.id)
        logging.info("node(%s) updating model(%s): %s", self.id, self.model.name, config)
        self.model.set_configs(config, node_id=self.id)
        if self.model.position_callback:
            for netif in self.netifs():
                netif.poshook = self.model.position_callback
                if netif.node is not None:
                    x, y, z = netif.node.position.get()
                    netif.poshook(netif, x, y, z)
        self.model.updateconfig()

    def all_link_data(self, flags):
        """
        Retrieve all link data.

        :param flags: message flags
        :return: list of link data
        :rtype: list[core.data.LinkData]
        """
        all_links = LxBrNet.all_link_data(self, flags)

        if self.model:
            all_links.extend(self.model.all_link_data(flags))

        return all_links


class RJ45Node(PyCoreNode, PyCoreNetIf):
    """
    RJ45Node is a physical interface on the host linked to the emulated
    network.
    """
    apitype = NodeTypes.RJ45.value
    type = "rj45"

    def __init__(self, session, _id=None, name=None, mtu=1500, start=True):
        """
        Create an RJ45Node instance.

        :param core.session.Session session: core session instance
        :param int _id: node id
        :param str name: node name
        :param mtu: rj45 mtu
        :param bool start: start flag
        :return:
        """
        PyCoreNode.__init__(self, session, _id, name, start=start)
        PyCoreNetIf.__init__(self, node=self, name=name, mtu=mtu)
        self.up = False
        self.lock = threading.RLock()
        self.ifindex = None
        # the following are PyCoreNetIf attributes
        self.transport_type = "raw"
        self.localname = name
        self.old_up = False
        self.old_addrs = []

        if start:
            self.startup()

    def startup(self):
        """
        Set the interface in the up state.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        # interface will also be marked up during net.attach()
        self.savestate()
        utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "up"])
        self.up = True

    def shutdown(self):
        """
        Bring the interface down. Remove any addresses and queuing
        disciplines.

        :return: nothing
        """
        if not self.up:
            return

        try:
            utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "down"])
            utils.check_cmd([constants.IP_BIN, "addr", "flush", "dev", self.localname])
            utils.check_cmd([constants.TC_BIN, "qdisc", "del", "dev", self.localname, "root"])
        except CoreCommandError:
            logging.exception("error shutting down")

        self.up = False
        self.restorestate()

    # TODO: issue in that both classes inherited from provide the same method with different signatures
    def attachnet(self, net):
        """
        Attach a network.

        :param core.coreobj.PyCoreNet net: network to attach
        :return: nothing
        """
        PyCoreNetIf.attachnet(self, net)

    # TODO: issue in that both classes inherited from provide the same method with different signatures
    def detachnet(self):
        """
        Detach a network.

        :return: nothing
        """
        PyCoreNetIf.detachnet(self)

    def newnetif(self, net=None, addrlist=None, hwaddr=None, ifindex=None, ifname=None):
        """
        This is called when linking with another node. Since this node
        represents an interface, we do not create another object here,
        but attach ourselves to the given network.

        :param core.coreobj.PyCoreNet net: new network instance
        :param list[str] addrlist: address list
        :param str hwaddr: hardware address
        :param int ifindex: interface index
        :param str ifname: interface name
        :return: interface index
        :rtype: int
        :raises ValueError: when an interface has already been created, one max
        """
        with self.lock:
            if ifindex is None:
                ifindex = 0

            if self.net is not None:
                raise ValueError("RJ45 nodes support at most 1 network interface")

            self._netif[ifindex] = self
            # PyCoreNetIf.node is self
            self.node = self
            self.ifindex = ifindex

            if net is not None:
                self.attachnet(net)

            if addrlist:
                for addr in utils.make_tuple(addrlist):
                    self.addaddr(addr)

            return ifindex

    def delnetif(self, ifindex):
        """
        Delete a network interface.

        :param int ifindex: interface index to delete
        :return: nothing
        """
        if ifindex is None:
            ifindex = 0

        self._netif.pop(ifindex)

        if ifindex == self.ifindex:
            self.shutdown()
        else:
            raise ValueError("ifindex %s does not exist" % ifindex)

    def netif(self, ifindex, net=None):
        """
        This object is considered the network interface, so we only
        return self here. This keeps the RJ45Node compatible with
        real nodes.

        :param int ifindex: interface index to retrieve
        :param net: network to retrieve
        :return: a network interface
        :rtype: core.coreobj.PyCoreNetIf
        """
        if net is not None and net == self.net:
            return self

        if ifindex is None:
            ifindex = 0

        if ifindex == self.ifindex:
            return self

        return None

    def getifindex(self, netif):
        """
        Retrieve network interface index.

        :param core.coreobj.PyCoreNetIf netif: network interface to retrieve index for
        :return: interface index, None otherwise
        :rtype: int
        """
        if netif != self:
            return None

        return self.ifindex

    def addaddr(self, addr):
        """
        Add address to to network interface.

        :param str addr: address to add
        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.up:
            utils.check_cmd([constants.IP_BIN, "addr", "add", str(addr), "dev", self.name])

        PyCoreNetIf.addaddr(self, addr)

    def deladdr(self, addr):
        """
        Delete address from network interface.

        :param str addr: address to delete
        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.up:
            utils.check_cmd([constants.IP_BIN, "addr", "del", str(addr), "dev", self.name])

        PyCoreNetIf.deladdr(self, addr)

    def savestate(self):
        """
        Save the addresses and other interface state before using the
        interface for emulation purposes. TODO: save/restore the PROMISC flag

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.old_up = False
        self.old_addrs = []
        args = [constants.IP_BIN, "addr", "show", "dev", self.localname]
        output = utils.check_cmd(args)
        for line in output.split("\n"):
            items = line.split()
            if len(items) < 2:
                continue

            if items[1] == "%s:" % self.localname:
                flags = items[2][1:-1].split(",")
                if "UP" in flags:
                    self.old_up = True
            elif items[0] == "inet":
                self.old_addrs.append((items[1], items[3]))
            elif items[0] == "inet6":
                if items[1][:4] == "fe80":
                    continue
                self.old_addrs.append((items[1], None))

    def restorestate(self):
        """
        Restore the addresses and other interface state after using it.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        for addr in self.old_addrs:
            if addr[1] is None:
                utils.check_cmd([constants.IP_BIN, "addr", "add", addr[0], "dev", self.localname])
            else:
                utils.check_cmd([constants.IP_BIN, "addr", "add", addr[0], "brd", addr[1], "dev", self.localname])

        if self.old_up:
            utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "up"])

    def setposition(self, x=None, y=None, z=None):
        """
        Uses setposition from both parent classes.

        :param float x: x position
        :param float y: y position
        :param float z: z position
        :return: True if position changed, False otherwise
        :rtype: bool
        """
        result = PyCoreObj.setposition(self, x, y, z)
        PyCoreNetIf.setposition(self, x, y, z)
        return result

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: exist status and combined stdout and stderr
        :rtype: tuple[int, str]
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        raise NotImplementedError

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        raise NotImplementedError

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        raise NotImplementedError

    def termcmdstring(self, sh):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        raise NotImplementedError


class TunnelNode(GreTapBridge):
    """
    Provides tunnel functionality in a core node.
    """
    apitype = NodeTypes.TUNNEL.value
    policy = "ACCEPT"
    type = "tunnel"
