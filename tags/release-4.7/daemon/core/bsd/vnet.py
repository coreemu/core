#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: core-dev@pf.itd.nrl.navy.mil
#
'''
vnet.py: NetgraphNet and NetgraphPipeNet classes that implement virtual networks
using the FreeBSD Netgraph subsystem.
'''

import sys, threading

from core.misc.utils import *
from core.constants import *
from core.coreobj import PyCoreNet, PyCoreObj
from core.bsd.netgraph import *
from core.bsd.vnode import VEth

class NetgraphNet(PyCoreNet):
    ngtype = None
    nghooks = ()

    def __init__(self, session, objid = None, name = None, verbose = False,
                        start = True, policy = None):
        PyCoreNet.__init__(self, session, objid, name)
        if name is None:
            name = str(self.objid)
        if policy is not None:
            self.policy = policy
        self.name = name
        self.ngname = "n_%s_%s" % (str(self.objid), self.session.sessionid)
        self.ngid = None
        self.verbose = verbose
        self._netif = {}
        self._linked = {}
        self.up = False
        if start:
            self.startup()

    def startup(self):
        tmp, self.ngid = createngnode(type=self.ngtype, hookstr=self.nghooks,
                                      name=self.ngname)
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        self.up = False
        while self._netif:
            k, netif = self._netif.popitem()
            if netif.pipe:
                pipe = netif.pipe
                netif.pipe = None
                pipe.shutdown()
            else:
                netif.shutdown()
        self._netif.clear()
        self._linked.clear()
        del self.session
        destroyngnode(self.ngname)

    def attach(self, netif):
        ''' Attach an interface to this netgraph node. Create a pipe between
            the interface and the hub/switch/wlan node.
            (Note that the PtpNet subclass overrides this method.)
        '''
        if self.up:
            pipe = self.session.addobj(cls = NetgraphPipeNet,
                                verbose = self.verbose, start = True)
            pipe.attach(netif)
            hook = "link%d" % len(self._netif)
            pipe.attachnet(self, hook)
        PyCoreNet.attach(self, netif)

    def detach(self, netif):
        if self.up:
            pass
        PyCoreNet.detach(self, netif)

    def linked(self, netif1, netif2):
        # check if the network interfaces are attached to this network
        if self._netif[netif1] != netif1:
            raise ValueError, "inconsistency for netif %s" % netif1.name
        if self._netif[netif2] != netif2:
            raise ValueError, "inconsistency for netif %s" % netif2.name
        try:
            linked = self._linked[netif1][netif2]
        except KeyError:
            linked = False
            self._linked[netif1][netif2] = linked
        return linked

    def unlink(self, netif1, netif2):
        if not self.linked(netif1, netif2):
            return
        msg = ["unlink", "{", "node1=0x%s" % netif1.pipe.ngid]
        msg += ["node2=0x%s" % netif2.pipe.ngid, "}"]
        ngmessage(self.ngname, msg)
        self._linked[netif1][netif2] = False

    def link(self, netif1, netif2):
        if self.linked(netif1, netif2):
            return
        msg = ["link", "{", "node1=0x%s" % netif1.pipe.ngid]
        msg += ["node2=0x%s" % netif2.pipe.ngid, "}"]
        ngmessage(self.ngname, msg)
        self._linked[netif1][netif2] = True

    def linknet(self, net):
        ''' Link this bridge with another by creating a veth pair and installing
            each device into each bridge.
        '''
        raise NotImplementedError

    def linkconfig(self, netif, bw = None, delay = None,
                   loss = None, duplicate = None, jitter = None, netif2=None):
        ''' Set link effects by modifying the pipe connected to an interface.
        '''
        if not netif.pipe:
            self.warn("linkconfig for %s but interface %s has no pipe" % \
                      (self.name, netif.name))
            return
        return netif.pipe.linkconfig(netif, bw, delay, loss, duplicate, jitter,
                                     netif2)

class NetgraphPipeNet(NetgraphNet):
    ngtype = "pipe"
    nghooks = "upper lower"

    def __init__(self, session, objid = None, name = None, verbose = False,
                        start = True, policy = None):
        NetgraphNet.__init__(self, session, objid, name, verbose, start, policy)
        if start:
            # account for Ethernet header
            ngmessage(self.ngname, ["setcfg", "{", "header_offset=14", "}"])

    def attach(self, netif):
        ''' Attach an interface to this pipe node.
            The first interface is connected to the "upper" hook, the second
            connected to the "lower" hook.
        '''
        if len(self._netif) > 1:
            raise ValueError, \
                  "Netgraph pipes support at most 2 network interfaces"
        if self.up:
            hook = self.gethook()
            connectngnodes(self.ngname, netif.localname, hook, netif.hook)
        if netif.pipe:
            raise ValueError, \
                  "Interface %s already attached to pipe %s" % \
                  (netif.name, netif.pipe.name)
        netif.pipe = self
        self._netif[netif] = netif
        self._linked[netif] = {}

    def attachnet(self, net, hook):
        ''' Attach another NetgraphNet to this pipe node.
        '''
        localhook = self.gethook()
        connectngnodes(self.ngname, net.ngname, localhook, hook)

    def gethook(self):
        ''' Returns the first hook (e.g. "upper") then the second hook
            (e.g. "lower") based on the number of connections.
        '''
        hooks = self.nghooks.split()
        if len(self._netif) == 0:
            return hooks[0]
        else:
            return hooks[1]

    def linkconfig(self, netif, bw = None, delay = None,
                   loss = None, duplicate = None, jitter = None, netif2 = None):
        ''' Set link effects by sending a Netgraph setcfg message to the pipe.
        '''
        netif.setparam('bw', bw)
        netif.setparam('delay', delay)
        netif.setparam('loss', loss)
        netif.setparam('duplicate', duplicate)
        netif.setparam('jitter', jitter)
        if not self.up:
            return
        params = []
        upstream = []
        downstream = []
        if bw is not None:
            if str(bw)=="0":
                bw="-1"
            params += ["bandwidth=%s" % bw,]
        if delay is not None:
            if str(delay)=="0":
                delay="-1"
            params += ["delay=%s" % delay,]
        if loss is not None:
            if str(loss)=="0":
                loss="-1"
            upstream += ["BER=%s" % loss,]
            downstream += ["BER=%s" % loss,]
        if duplicate is not None:
            if str(duplicate)=="0":
                duplicate="-1"
            upstream += ["duplicate=%s" % duplicate,]
            downstream += ["duplicate=%s" % duplicate,]
        if jitter:
            self.warn("jitter parameter ignored for link %s" % self.name)
        if len(params) > 0 or len(upstream) > 0 or len(downstream) > 0:
            setcfg = ["setcfg", "{",] + params
            if len(upstream) > 0:
                setcfg += ["upstream={",] + upstream + ["}",]
            if len(downstream) > 0:
                setcfg += ["downstream={",] + downstream + ["}",]
            setcfg += ["}",]
            ngmessage(self.ngname, setcfg)

