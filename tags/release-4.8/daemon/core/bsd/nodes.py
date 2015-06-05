#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: core-dev@pf.itd.nrl.navy.mil
#

'''
nodes.py: definition of CoreNode classes and other node classes that inherit
from the CoreNode, implementing specific node types.
'''

from vnode import *
from vnet import * 
from core.constants import *
from core.misc.ipaddr import *
from core.api import coreapi
from core.bsd.netgraph import ngloadkernelmodule

checkexec([IFCONFIG_BIN])

class CoreNode(JailNode):
    apitype = coreapi.CORE_NODE_DEF

class PtpNet(NetgraphPipeNet):
    def tonodemsg(self, flags):
        ''' Do not generate a Node Message for point-to-point links. They are
            built using a link message instead.
        '''
        pass

    def tolinkmsgs(self, flags):
        ''' Build CORE API TLVs for a point-to-point link. One Link message
            describes this network.
        '''
        tlvdata = ""
        if len(self._netif) != 2:
            return tlvdata
        (if1, if2) = self._netif.items()
        if1 = if1[1]
        if2 = if2[1]
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N1NUMBER,
                                            if1.node.objid)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N2NUMBER,
                                            if2.node.objid)
        delay = if1.getparam('delay')
        bw = if1.getparam('bw')
        loss = if1.getparam('loss')
        duplicate = if1.getparam('duplicate')
        jitter = if1.getparam('jitter')
        if delay is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_DELAY,
                                                delay)
        if bw is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_BW, bw)
        if loss is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_PER,
                                                str(loss))
        if duplicate is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_DUP,
                                                str(duplicate))
        if jitter is not None:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_JITTER,
                                                jitter)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_TYPE,
                                            self.linktype)

        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF1NUM, \
                                            if1.node.getifindex(if1))
        if if1.hwaddr:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF1MAC,
                                                if1.hwaddr)
        for addr in if1.addrlist:
            (ip, sep, mask)  = addr.partition('/')
            mask = int(mask)
            if isIPv4Address(ip):
                family = AF_INET
                tlvtypeip = coreapi.CORE_TLV_LINK_IF1IP4
                tlvtypemask = coreapi.CORE_TLV_LINK_IF1IP4MASK
            else:
                family = AF_INET6
                tlvtypeip = coreapi.CORE_TLV_LINK_IF1IP6
                tlvtypemask = coreapi.CORE_TLV_LINK_IF1IP6MASK
            ipl = socket.inet_pton(family, ip)
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypeip,
                                                IPAddr(af=family, addr=ipl))
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypemask, mask)

        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2NUM, \
                                            if2.node.getifindex(if2))
        if if2.hwaddr:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2MAC,
                                                if2.hwaddr)
        for addr in if2.addrlist:
            (ip, sep, mask)  = addr.partition('/')
            mask = int(mask)
            if isIPv4Address(ip):
                family = AF_INET
                tlvtypeip = coreapi.CORE_TLV_LINK_IF2IP4
                tlvtypemask = coreapi.CORE_TLV_LINK_IF2IP4MASK
            else:
                family = AF_INET6
                tlvtypeip = coreapi.CORE_TLV_LINK_IF2IP6
                tlvtypemask = coreapi.CORE_TLV_LINK_IF2IP6MASK
            ipl = socket.inet_pton(family, ip)
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypeip,
                                                IPAddr(af=family, addr=ipl))
            tlvdata += coreapi.CoreLinkTlv.pack(tlvtypemask, mask)

        msg = coreapi.CoreLinkMessage.pack(flags, tlvdata)
        return [msg,]

class SwitchNode(NetgraphNet):
    ngtype = "bridge"
    nghooks = "link0 link0\nmsg .link0 setpersistent"
    apitype = coreapi.CORE_NODE_SWITCH
    policy = "ACCEPT"

class HubNode(NetgraphNet):
    ngtype = "hub"
    nghooks = "link0 link0\nmsg .link0 setpersistent"
    apitype = coreapi.CORE_NODE_HUB
    policy = "ACCEPT"
    
class WlanNode(NetgraphNet):
    ngtype = "wlan"
    nghooks = "anchor anchor"
    apitype = coreapi.CORE_NODE_WLAN
    linktype = coreapi.CORE_LINK_WIRELESS
    policy = "DROP"
    
    def __init__(self, session, objid = None, name = None, verbose = False,
                        start = True, policy = None):
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
            (x,y,z) = netif.node.position.get()
            netif.poshook(netif, x, y, z)

    def setmodel(self, model, config):
        ''' Mobility and wireless model.
        '''
        if (self.verbose):
            self.info("adding model %s" % model._name)
        if model._type == coreapi.CORE_TLV_REG_WIRELESS:
            self.model = model(session=self.session, objid=self.objid,
                               verbose=self.verbose, values=config)
            if self.model._positioncallback:
                for netif in self.netifs():
                    netif.poshook = self.model._positioncallback
                    if netif.node is not None:
                        (x,y,z) = netif.node.position.get()
                        netif.poshook(netif, x, y, z)
            self.model.setlinkparams()
        elif model._type == coreapi.CORE_TLV_REG_MOBILITY:
            self.mobility = model(session=self.session, objid=self.objid,
                                  verbose=self.verbose, values=config)


class RJ45Node(NetgraphPipeNet):
    apitype = coreapi.CORE_NODE_RJ45
    policy = "ACCEPT"

    def __init__(self, session, objid, name, verbose, start = True):
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
        check_call([IFCONFIG_BIN, self.name, "up", p])

    def attach(self, netif):
        if len(self._netif) > 0:
            raise ValueError, \
                  "RJ45 networks support at most 1 network interface"
        NetgraphPipeNet.attach(self, netif)
        connectngnodes(self.ngname, self.name, self.gethook(), "lower")

class TunnelNode(NetgraphNet):
    ngtype = "pipe"
    nghooks = "upper lower"
    apitype = coreapi.CORE_NODE_TUNNEL
    policy = "ACCEPT"

