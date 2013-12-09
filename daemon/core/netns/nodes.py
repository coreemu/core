#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
nodes.py: definition of an LxcNode and CoreNode classes, and other node classes
that inherit from the CoreNode, implementing specific node types.
'''

from vnode import *
from vnet import *
from core.misc.ipaddr import *
from core.api import coreapi
from core.coreobj import PyCoreNode

class CtrlNet(LxBrNet):
    policy = "ACCEPT"
    CTRLIF_IDX_BASE = 99  # base control interface index

    def __init__(self, session, objid = "ctrlnet", name = None,
                 verbose = False, netid = 1, prefix = None,
                 hostid = None, start = True, assign_address = True,
                 updown_script = None):
        if not prefix:
            prefix = "172.16.%d.0/24" % netid
        self.prefix = IPv4Prefix(prefix)
        self.hostid = hostid
        self.assign_address = assign_address
        self.updown_script = updown_script
        LxBrNet.__init__(self, session, objid = objid, name = name,
                         verbose = verbose, start = start)

    def startup(self):
        LxBrNet.startup(self)
        if self.hostid:
            addr = self.prefix.addr(self.hostid)
        else:
            addr = self.prefix.maxaddr()
        msg = "Added control network bridge: %s %s" % \
                (self.brname, self.prefix)
        addrlist = ["%s/%s" % (addr, self.prefix.prefixlen)]
        if self.assign_address:
            self.addrconfig(addrlist = addrlist)
            msg += " address %s" % addr
        self.session.info(msg)
        if self.updown_script is not None:
            self.info("interface %s updown script '%s startup' called" % \
                      (self.brname, self.updown_script))
            check_call([self.updown_script, self.brname, "startup"])

    def shutdown(self):
        if self.updown_script is not None:
            self.info("interface %s updown script '%s shutdown' called" % \
                      (self.brname, self.updown_script))
            check_call([self.updown_script, self.brname, "shutdown"])
        LxBrNet.shutdown(self)

    def tolinkmsgs(self, flags):
        ''' Do not include CtrlNet in link messages describing this session.
        '''
        return []

class CoreNode(LxcNode):
    apitype = coreapi.CORE_NODE_DEF

class PtpNet(LxBrNet):
    policy = "ACCEPT"

    def attach(self, netif):
        if len(self._netif) > 1:
            raise ValueError, \
                  "Point-to-point links support at most 2 network interfaces"
        LxBrNet.attach(self, netif)

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
        uni = False
        if if1.getparams() != if2.getparams():
            uni = True
        tlvdata += self.netifparamstolink(if1)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_TYPE,
                                            self.linktype)
        if uni:
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_UNI, 1)

        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF1NUM, \
                                            if1.node.getifindex(if1))
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
        if not uni:
            return [msg,]
        # build a 2nd link message for the upstream link parameters
        # (swap if1 and if2)
        tlvdata = ""
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N1NUMBER,
                                            if2.node.objid)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N2NUMBER,
                                            if1.node.objid)
        tlvdata += self.netifparamstolink(if2)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_UNI, 1)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF1NUM, \
                                            if2.node.getifindex(if2))
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2NUM, \
                                            if1.node.getifindex(if1))
        msg2 = coreapi.CoreLinkMessage.pack(0, tlvdata)
        return [msg, msg2]

class SwitchNode(LxBrNet):
    apitype = coreapi.CORE_NODE_SWITCH
    policy = "ACCEPT"
    type = "lanswitch"

class HubNode(LxBrNet):
    apitype = coreapi.CORE_NODE_HUB
    policy = "ACCEPT"
    type = "hub"
    
    def __init__(self, session, objid = None, name = None, verbose = False,
                        start = True):
        ''' the Hub node forwards packets to all bridge ports by turning off
            the MAC address learning
        '''
        LxBrNet.__init__(self, session, objid, name, verbose, start)
        if start:
            check_call([BRCTL_BIN, "setageing", self.brname, "0"])


class WlanNode(LxBrNet):
    apitype = coreapi.CORE_NODE_WLAN
    linktype = coreapi.CORE_LINK_WIRELESS
    policy = "DROP"
    type = "wlan"
    
    def __init__(self, session, objid = None, name = None, verbose = False,
                        start = True, policy = None):
        LxBrNet.__init__(self, session, objid, name, verbose, start, policy)
        # wireless model such as basic range
        self.model = None
        # mobility model such as scripted
        self.mobility = None
        
    def attach(self, netif):
        LxBrNet.attach(self, netif)
        if self.model:
            netif.poshook = self.model._positioncallback
            if netif.node is None:
                return
            (x,y,z) = netif.node.position.get()
            # invokes any netif.poshook
            netif.setposition(x, y, z)
            #self.model.setlinkparams()
        
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
                               
    def updatemodel(self, model_name, values):
        ''' Allow for model updates during runtime (similar to setmodel().)
        '''
        if (self.verbose):
            self.info("updating model %s" % model_name)
        if self.model is None or self.model._name != model_name:
            return
        model = self.model
        if model._type == coreapi.CORE_TLV_REG_WIRELESS:
            if not model.updateconfig(values):
                return
            if self.model._positioncallback:
                for netif in self.netifs():
                    netif.poshook = self.model._positioncallback
                    if netif.node is not None:
                        (x,y,z) = netif.node.position.get()
                        netif.poshook(netif, x, y, z)
            self.model.setlinkparams()
        
    def tolinkmsgs(self, flags):
        msgs = LxBrNet.tolinkmsgs(self, flags)
        if self.model:
            msgs += self.model.tolinkmsgs(flags)
        return msgs


class RJ45Node(PyCoreNode, PyCoreNetIf):
    ''' RJ45Node is a physical interface on the host linked to the emulated
        network.
    '''
    apitype = coreapi.CORE_NODE_RJ45
    type = "rj45"
    
    def __init__(self, session, objid = None, name = None, mtu = 1500,
                 verbose = False, start = True):
        PyCoreNode.__init__(self, session, objid, name, verbose=verbose,
                            start=start)
        # this initializes net, params, poshook
        PyCoreNetIf.__init__(self, node=self, name=name, mtu = mtu)
        self.up = False
        self.lock = threading.RLock()
        self.ifindex = None
        # the following are PyCoreNetIf attributes
        self.transport_type = "raw"
        self.localname = name
        if start:
            self.startup()

    def startup(self):
        ''' Set the interface in the up state.
        '''
        # interface will also be marked up during net.attach()
        self.savestate()
        try:
            check_call([IP_BIN, "link", "set", self.localname, "up"])
        except:
            self.warn("Failed to run command: %s link set %s up" % \
                      (IP_BIN, self.localname))
            return
        self.up = True
        
    def shutdown(self):
        ''' Bring the interface down. Remove any addresses and queuing
            disciplines.
        '''
        if not self.up:
            return
        check_call([IP_BIN, "link", "set", self.localname, "down"])
        check_call([IP_BIN, "addr", "flush", "dev", self.localname])
        mutecall([TC_BIN, "qdisc", "del", "dev", self.localname, "root"])
        self.up = False
        self.restorestate()
        
    def attachnet(self, net):
        PyCoreNetIf.attachnet(self, net)
        
    def detachnet(self):
        PyCoreNetIf.detachnet(self)

    def newnetif(self, net = None, addrlist = [], hwaddr = None,
                 ifindex = None, ifname = None):        
        ''' This is called when linking with another node. Since this node 
            represents an interface, we do not create another object here,
            but attach ourselves to the given network.
        '''
        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = 0
            if self.net is not None:
                raise ValueError, \
                        "RJ45 nodes support at most 1 network interface"
            self._netif[ifindex] = self
            self.node = self # PyCoreNetIf.node is self
            self.ifindex = ifindex
            if net is not None:
                self.attachnet(net)
            for addr in maketuple(addrlist):
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
        ''' This object is considered the network interface, so we only
            return self here. This keeps the RJ45Node compatible with
            real nodes.
        '''
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
            check_call([IP_BIN, "addr", "add", str(addr), "dev", self.name])
        PyCoreNetIf.addaddr(self, addr)

    def deladdr(self, addr):
        if self.up:
            check_call([IP_BIN, "addr", "del", str(addr), "dev", self.name])
        PyCoreNetIf.deladdr(self, addr)
        
    def savestate(self):
        ''' Save the addresses and other interface state before using the
        interface for emulation purposes. TODO: save/restore the PROMISC flag
        '''
        self.old_up = False
        self.old_addrs = []
        cmd = [IP_BIN, "addr", "show", "dev", self.localname]
        try:
            tmp = subprocess.Popen(cmd, stdout = subprocess.PIPE)
        except OSError:
            self.warn("Failed to run %s command: %s" % (IP_BIN, cmd))
        if tmp.wait():
            self.warn("Command failed: %s" % cmd)
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
        ''' Restore the addresses and other interface state after using it.
        '''
        for addr in self.old_addrs:
            if addr[1] is None:
                check_call([IP_BIN, "addr", "add", addr[0], "dev",
                            self.localname])
            else:
                check_call([IP_BIN, "addr", "add", addr[0], "brd", addr[1], 
                            "dev", self.localname])
        if self.old_up:
            check_call([IP_BIN, "link", "set", self.localname, "up"])
            
    def setposition(self, x=None, y=None, z=None):
        ''' Use setposition() from both parent classes.
        '''
        PyCoreObj.setposition(self, x, y, z)
        # invoke any poshook
        PyCoreNetIf.setposition(self, x, y, z)
               
            



class TunnelNode(GreTapBridge):
    apitype = coreapi.CORE_NODE_TUNNEL
    policy = "ACCEPT"
    type = "tunnel"

