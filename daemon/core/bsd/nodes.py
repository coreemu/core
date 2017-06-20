#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: core-dev@pf.itd.nrl.navy.mil
#

"""
nodes.py: definition of CoreNode classes and other node classes that inherit
from the CoreNode, implementing specific node types.
"""

import socket

from core import constants
from core.api import coreapi
from core.bsd.netgraph import connectngnodes
from core.bsd.netgraph import ngloadkernelmodule
from core.bsd.vnet import NetgraphNet
from core.bsd.vnet import NetgraphPipeNet
from core.bsd.vnode import JailNode
from core.enumerations import LinkTlvs
from core.enumerations import LinkTypes
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.misc import ipaddress
from core.misc import utils

utils.checkexec([constants.IFCONFIG_BIN])


class CoreNode(JailNode):
    apitype = NodeTypes.DEFAULT.value


class PtpNet(NetgraphPipeNet):
    def tonodemsg(self, flags):
        """ Do not generate a Node Message for point-to-point links. They are
            built using a link message instead.
        """
        pass

    def tolinkmsgs(self, flags):
        """ Build CORE API TLVs for a point-to-point link. One Link message
            describes this network.
        """
        tlvdata = ""
        if len(self._netif) != 2:
            return tlvdata
        (if1, if2) = self._netif.items()
        if1 = if1[1]
        if2 = if2[1]
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.N1_NUMBER.value, if1.node.objid)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.N2_NUMBER.value, if2.node.objid)
        delay = if1.getparam("delay")
        bw = if1.getparam("bw")
        loss = if1.getparam("loss")
        duplicate = if1.getparam("duplicate")
        jitter = if1.getparam("jitter")
        if delay is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.DELAY.value, delay)
        if bw is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.BANDWIDTH.value, bw)
        if loss is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.PER.value, str(loss))
        if duplicate is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.DUP.value, str(duplicate))
        if jitter is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.JITTER.value, jitter)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.TYPE.value, self.linktype)

        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE1_NUMBER.value, if1.node.getifindex(if1))
        if if1.hwaddr:
            tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE1_MAC.value, if1.hwaddr)
        for addr in if1.addrlist:
            (ip, sep, mask) = addr.partition("/")
            mask = int(mask)
            if ipaddress.is_ipv4_address(ip):
                family = socket.AF_INET
                tlvtypeip = LinkTlvs.INTERFACE1_IP4.value
                tlvtypemask = LinkTlvs.INTERFACE1_IP4_MASK
            else:
                family = socket.AF_INET6
                tlvtypeip = LinkTlvs.INTERFACE1_IP6.value
                tlvtypemask = LinkTlvs.INTERFACE1_IP6_MASK.value
            ipl = socket.inet_pton(family, ip)
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypeip, ipaddress.IpAddress(af=family, address=ipl))
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypemask, mask)

        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_NUMBER.value, if2.node.getifindex(if2))
        if if2.hwaddr:
            tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_MAC.value, if2.hwaddr)
        for addr in if2.addrlist:
            (ip, sep, mask) = addr.partition("/")
            mask = int(mask)
            if ipaddress.is_ipv4_address(ip):
                family = socket.AF_INET
                tlvtypeip = LinkTlvs.INTERFACE2_IP4.value
                tlvtypemask = LinkTlvs.INTERFACE2_IP4_MASK
            else:
                family = socket.AF_INET6
                tlvtypeip = LinkTlvs.INTERFACE2_IP6.value
                tlvtypemask = LinkTlvs.INTERFACE2_IP6_MASK.value
            ipl = socket.inet_pton(family, ip)
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypeip, ipaddress.IpAddress(af=family, address=ipl))
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypemask, mask)

        msg = coreapi.CoreLinkMessage.pack(flags, tlvdata)
        return [msg, ]


class SwitchNode(NetgraphNet):
    ngtype = "bridge"
    nghooks = "link0 link0\nmsg .link0 setpersistent"
    apitype = NodeTypes.SWITCH.value
    policy = "ACCEPT"


class HubNode(NetgraphNet):
    ngtype = "hub"
    nghooks = "link0 link0\nmsg .link0 setpersistent"
    apitype = NodeTypes.HUB.value
    policy = "ACCEPT"


class WlanNode(NetgraphNet):
    ngtype = "wlan"
    nghooks = "anchor anchor"
    apitype = NodeTypes.WIRELESS_LAN.value
    linktype = LinkTypes.WIRELESS.value
    policy = "DROP"

    def __init__(self, session, objid=None, name=None, verbose=False,
                 start=True, policy=None):
        NetgraphNet.__init__(self, session, objid, name, verbose, start, policy)
        # wireless model such as basic range
        self.model = None
        # mobility model such as scripted
        self.mobility = None

    def attach(self, netif):
        NetgraphNet.attach(self, netif)
        if self.model:
            netif.poshook = self.model._positioncallback
            if netif.node is None:
                return
            x, y, z = netif.node.position.get()
            netif.poshook(netif, x, y, z)

    def setmodel(self, model, config):
        """ Mobility and wireless model.
        """
        if self.verbose:
            self.info("adding model %s" % model._name)
        if model._type == RegisterTlvs.WIRELESS.value:
            self.model = model(session=self.session, objid=self.objid,
                               verbose=self.verbose, values=config)
            if self.model._positioncallback:
                for netif in self.netifs():
                    netif.poshook = self.model._positioncallback
                    if netif.node is not None:
                        (x, y, z) = netif.node.position.get()
                        netif.poshook(netif, x, y, z)
            self.model.setlinkparams()
        elif model._type == RegisterTlvs.MOBILITY.value:
            self.mobility = model(session=self.session, objid=self.objid,
                                  verbose=self.verbose, values=config)


class RJ45Node(NetgraphPipeNet):
    apitype = NodeTypes.RJ45.value
    policy = "ACCEPT"

    def __init__(self, session, objid, name, verbose, start=True):
        if start:
            ngloadkernelmodule("ng_ether")
        NetgraphPipeNet.__init__(self, session, objid, name, verbose, start)
        if start:
            self.setpromisc(True)

    def shutdown(self):
        self.setpromisc(False)
        NetgraphPipeNet.shutdown(self)

    def setpromisc(self, promisc):
        p = "promisc"
        if not promisc:
            p = "-" + p
        utils.check_call([constants.IFCONFIG_BIN, self.name, "up", p])

    def attach(self, netif):
        if len(self._netif) > 0:
            raise ValueError, \
                "RJ45 networks support at most 1 network interface"
        NetgraphPipeNet.attach(self, netif)
        connectngnodes(self.ngname, self.name, self.gethook(), "lower")


class TunnelNode(NetgraphNet):
    ngtype = "pipe"
    nghooks = "upper lower"
    apitype = NodeTypes.TUNNEL.value
    policy = "ACCEPT"
