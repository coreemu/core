"""
nodes.py: definition of an LxcNode and CoreNode classes, and other node classes
that inherit from the CoreNode, implementing specific node types.
"""

import socket
import subprocess
import threading
from socket import AF_INET
from socket import AF_INET6

from core import constants
from core.coreobj import PyCoreNetIf
from core.coreobj import PyCoreNode
from core.coreobj import PyCoreObj
from core.data import LinkData
from core.enumerations import LinkTypes
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.misc import ipaddress
from core.misc import log
from core.misc import utils
from core.netns.vnet import GreTapBridge
from core.netns.vnet import LxBrNet
from core.netns.vnode import LxcNode

logger = log.get_logger(__name__)


class CtrlNet(LxBrNet):
    policy = "ACCEPT"
    # base control interface index
    CTRLIF_IDX_BASE = 99
    DEFAULT_PREFIX_LIST = [
        "172.16.0.0/24 172.16.1.0/24 172.16.2.0/24 172.16.3.0/24 172.16.4.0/24",
        "172.17.0.0/24 172.17.1.0/24 172.17.2.0/24 172.17.3.0/24 172.17.4.0/24",
        "172.18.0.0/24 172.18.1.0/24 172.18.2.0/24 172.18.3.0/24 172.18.4.0/24",
        "172.19.0.0/24 172.19.1.0/24 172.19.2.0/24 172.19.3.0/24 172.19.4.0/24"
    ]

    def __init__(self, session, objid="ctrlnet", name=None, prefix=None,
                 hostid=None, start=True, assign_address=True,
                 updown_script=None, serverintf=None):
        self.prefix = ipaddress.Ipv4Prefix(prefix)
        self.hostid = hostid
        self.assign_address = assign_address
        self.updown_script = updown_script
        self.serverintf = serverintf
        LxBrNet.__init__(self, session, objid=objid, name=name, start=start)

    def startup(self):
        if self.detectoldbridge():
            return

        LxBrNet.startup(self)
        if self.hostid:
            addr = self.prefix.addr(self.hostid)
        else:
            addr = self.prefix.max_addr()
        msg = "Added control network bridge: %s %s" % \
              (self.brname, self.prefix)
        addrlist = ["%s/%s" % (addr, self.prefix.prefixlen)]
        if self.assign_address:
            self.addrconfig(addrlist=addrlist)
            msg += " address %s" % addr
        logger.info(msg)
        if self.updown_script is not None:
            logger.info("interface %s updown script '%s startup' called" % \
                        (self.brname, self.updown_script))
            subprocess.check_call([self.updown_script, self.brname, "startup"])
        if self.serverintf is not None:
            try:
                subprocess.check_call([constants.BRCTL_BIN, "addif", self.brname, self.serverintf])
                subprocess.check_call([constants.IP_BIN, "link", "set", self.serverintf, "up"])
            except subprocess.CalledProcessError:
                logger.exception("Error joining server interface %s to controlnet bridge %s",
                                 self.serverintf, self.brname)

    def detectoldbridge(self):
        """
        Occassionally, control net bridges from previously closed sessions are not cleaned up.
        Check if there are old control net bridges and delete them
        """
        retstat, retstr = utils.cmdresult([constants.BRCTL_BIN, 'show'])
        if retstat != 0:
            logger.error("Unable to retrieve list of installed bridges")
        lines = retstr.split('\n')
        for line in lines[1:]:
            cols = line.split('\t')
            oldbr = cols[0]
            flds = cols[0].split('.')
            if len(flds) == 3:
                if flds[0] == 'b' and flds[1] == self.objid:
                    logger.error(
                        "Error: An active control net bridge (%s) found. " \
                        "An older session might still be running. " \
                        "Stop all sessions and, if needed, delete %s to continue." % \
                        (oldbr, oldbr)
                    )
                    return True
                    """
                    # Do this if we want to delete the old bridge
                    logger.warn("Warning: Old %s bridge found: %s" % (self.objid, oldbr))
                    try:
                        check_call([BRCTL_BIN, 'delbr', oldbr])
                    except subprocess.CalledProcessError as e:
                        logger.exception("Error deleting old bridge %s", oldbr, e)
                    logger.info("Deleted %s", oldbr)
                    """
        return False

    def shutdown(self):
        if self.serverintf is not None:
            try:
                subprocess.check_call([constants.BRCTL_BIN, "delif", self.brname, self.serverintf])
            except subprocess.CalledProcessError:
                logger.exception("Error deleting server interface %s to controlnet bridge %s",
                                 self.serverintf, self.brname)

        if self.updown_script is not None:
            logger.info("interface %s updown script '%s shutdown' called" % (self.brname, self.updown_script))
            subprocess.check_call([self.updown_script, self.brname, "shutdown"])
        LxBrNet.shutdown(self)

    def all_link_data(self, flags):
        """
        Do not include CtrlNet in link messages describing this session.
        """
        return []


class CoreNode(LxcNode):
    apitype = NodeTypes.DEFAULT.value


class PtpNet(LxBrNet):
    policy = "ACCEPT"

    def attach(self, netif):
        if len(self._netif) > 1:
            raise ValueError, \
                "Point-to-point links support at most 2 network interfaces"
        LxBrNet.attach(self, netif)

    def data(self, message_type):
        """
        Do not generate a Node Message for point-to-point links. They are
        built using a link message instead.
        """
        pass

    def all_link_data(self, flags):
        """
        Build CORE API TLVs for a point-to-point link. One Link message
        describes this network.
        """

        all_links = []

        if len(self._netif) != 2:
            return all_links

        if1, if2 = self._netif.items()
        if1 = if1[1]
        if2 = if2[1]

        unidirectional = 0
        if if1.getparams() != if2.getparams():
            unidirectional = 1

        interface1_ip4 = None
        interface1_ip4_mask = None
        interface1_ip6 = None
        interface1_ip6_mask = None
        for address in if1.addrlist:
            ip, sep, mask = address.partition('/')
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
            ip, sep, mask = address.partition('/')
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

        # TODO: not currently used
        # loss=netif.getparam('loss')
        link_data = LinkData(
            message_type=flags,
            node1_id=if1.node.objid,
            node2_id=if2.node.objid,
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
                node1_id=if2.node.objid,
                node2_id=if1.node.objid,
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
    apitype = NodeTypes.SWITCH.value
    policy = "ACCEPT"
    type = "lanswitch"


class HubNode(LxBrNet):
    apitype = NodeTypes.HUB.value
    policy = "ACCEPT"
    type = "hub"

    def __init__(self, session, objid=None, name=None, start=True):
        """
        the Hub node forwards packets to all bridge ports by turning off
        the MAC address learning
        """
        LxBrNet.__init__(self, session, objid, name, start)
        if start:
            subprocess.check_call([constants.BRCTL_BIN, "setageing", self.brname, "0"])


class WlanNode(LxBrNet):
    apitype = NodeTypes.WIRELESS_LAN.value
    linktype = LinkTypes.WIRELESS.value
    policy = "DROP"
    type = "wlan"

    def __init__(self, session, objid=None, name=None, start=True, policy=None):
        LxBrNet.__init__(self, session, objid, name, start, policy)
        # wireless model such as basic range
        self.model = None
        # mobility model such as scripted
        self.mobility = None

    def attach(self, netif):
        LxBrNet.attach(self, netif)
        if self.model:
            netif.poshook = self.model.position_callback
            if netif.node is None:
                return
            (x, y, z) = netif.node.position.get()
            # invokes any netif.poshook
            netif.setposition(x, y, z)
            # self.model.setlinkparams()

    def setmodel(self, model, config):
        """
        Sets the mobility and wireless model.

        :param core.mobility.WirelessModel.cls model: wireless model to set to
        :param config:
        :return:
        """
        logger.info("adding model %s" % model.name)
        if model.config_type == RegisterTlvs.WIRELESS.value:
            self.model = model(session=self.session, object_id=self.objid, values=config)
            if self.model.position_callback:
                for netif in self.netifs():
                    netif.poshook = self.model.position_callback
                    if netif.node is not None:
                        x, y, z = netif.node.position.get()
                        netif.poshook(netif, x, y, z)
            self.model.setlinkparams()
        elif model.config_type == RegisterTlvs.MOBILITY.value:
            self.mobility = model(session=self.session, object_id=self.objid, values=config)

    def updatemodel(self, model_name, values):
        """
        Allow for model updates during runtime (similar to setmodel().)
        """
        logger.info("updating model %s" % model_name)
        if self.model is None or self.model.name != model_name:
            return
        model = self.model
        if model.config_type == RegisterTlvs.WIRELESS.value:
            if not model.updateconfig(values):
                return
            if self.model.position_callback:
                for netif in self.netifs():
                    netif.poshook = self.model.position_callback
                    if netif.node is not None:
                        (x, y, z) = netif.node.position.get()
                        netif.poshook(netif, x, y, z)
            self.model.setlinkparams()

    def all_link_data(self, flags):
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

    def __init__(self, session, objid=None, name=None, mtu=1500, start=True):
        PyCoreNode.__init__(self, session, objid, name, start=start)
        # this initializes net, params, poshook
        PyCoreNetIf.__init__(self, node=self, name=name, mtu=mtu)
        self.up = False
        self.lock = threading.RLock()
        self.ifindex = None
        # the following are PyCoreNetIf attributes
        self.transport_type = "raw"
        self.localname = name
        if start:
            self.startup()

    def startup(self):
        """
        Set the interface in the up state.
        """
        # interface will also be marked up during net.attach()
        self.savestate()
        try:
            subprocess.check_call([constants.IP_BIN, "link", "set", self.localname, "up"])
        except subprocess.CalledProcessError:
            logger.exception("failed to run command: %s link set %s up", constants.IP_BIN, self.localname)
            return
        self.up = True

    def shutdown(self):
        """
        Bring the interface down. Remove any addresses and queuing
        disciplines.
        """
        if not self.up:
            return
        subprocess.check_call([constants.IP_BIN, "link", "set", self.localname, "down"])
        subprocess.check_call([constants.IP_BIN, "addr", "flush", "dev", self.localname])
        utils.mutecall([constants.TC_BIN, "qdisc", "del", "dev", self.localname, "root"])
        self.up = False
        self.restorestate()

    def attachnet(self, net):
        PyCoreNetIf.attachnet(self, net)

    def detachnet(self):
        PyCoreNetIf.detachnet(self)

    def newnetif(self, net=None, addrlist=[], hwaddr=None,
                 ifindex=None, ifname=None):
        """
        This is called when linking with another node. Since this node
        represents an interface, we do not create another object here,
        but attach ourselves to the given network.
        """
        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = 0
            if self.net is not None:
                raise ValueError, \
                    "RJ45 nodes support at most 1 network interface"
            self._netif[ifindex] = self
            # PyCoreNetIf.node is self
            self.node = self
            self.ifindex = ifindex
            if net is not None:
                self.attachnet(net)
            for addr in utils.maketuple(addrlist):
                self.addaddr(addr)
            return ifindex
        finally:
            self.lock.release()

    def delnetif(self, ifindex):
        if ifindex is None:
            ifindex = 0
        if ifindex not in self._netif:
            raise ValueError, "ifindex %s does not exist" % ifindex
        self._netif.pop(ifindex)
        if ifindex == self.ifindex:
            self.shutdown()
        else:
            raise ValueError, "ifindex %s does not exist" % ifindex

    def netif(self, ifindex, net=None):
        """
        This object is considered the network interface, so we only
        return self here. This keeps the RJ45Node compatible with
        real nodes.
        """
        if net is not None and net == self.net:
            return self
        if ifindex is None:
            ifindex = 0
        if ifindex == self.ifindex:
            return self
        return None

    def getifindex(self, netif):
        if netif != self:
            return None
        return self.ifindex

    def addaddr(self, addr):
        if self.up:
            subprocess.check_call([constants.IP_BIN, "addr", "add", str(addr), "dev", self.name])
        PyCoreNetIf.addaddr(self, addr)

    def deladdr(self, addr):
        if self.up:
            subprocess.check_call([constants.IP_BIN, "addr", "del", str(addr), "dev", self.name])
        PyCoreNetIf.deladdr(self, addr)

    def savestate(self):
        """
        Save the addresses and other interface state before using the
        interface for emulation purposes. TODO: save/restore the PROMISC flag
        """
        self.old_up = False
        self.old_addrs = []
        cmd = [constants.IP_BIN, "addr", "show", "dev", self.localname]
        try:
            tmp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        except OSError:
            logger.exception("Failed to run %s command: %s", constants.IP_BIN, cmd)
        if tmp.wait():
            logger.warn("Command failed: %s", cmd)
            return
        lines = tmp.stdout.read()
        tmp.stdout.close()
        for l in lines.split('\n'):
            items = l.split()
            if len(items) < 2:
                continue
            if items[1] == "%s:" % self.localname:
                flags = items[2][1:-1].split(',')
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
        """
        for addr in self.old_addrs:
            if addr[1] is None:
                subprocess.check_call([constants.IP_BIN, "addr", "add", addr[0], "dev", self.localname])
            else:
                subprocess.check_call([constants.IP_BIN, "addr", "add", addr[0], "brd", addr[1], "dev", self.localname])
        if self.old_up:
            subprocess.check_call([constants.IP_BIN, "link", "set", self.localname, "up"])

    def setposition(self, x=None, y=None, z=None):
        """
        Use setposition() from both parent classes.
        """
        PyCoreObj.setposition(self, x, y, z)
        # invoke any poshook
        PyCoreNetIf.setposition(self, x, y, z)


class TunnelNode(GreTapBridge):
    apitype = NodeTypes.TUNNEL.value
    policy = "ACCEPT"
    type = "tunnel"
