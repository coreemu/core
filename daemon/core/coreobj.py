#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
coreobj.py: defines the basic objects for emulation: the PyCoreObj base class, 
along with PyCoreNode, PyCoreNet, and PyCoreNetIf
'''
import sys, threading, os, shutil

from core.api import coreapi
from core.misc.ipaddr import *

class Position(object):
    ''' Helper class for Cartesian coordinate position
    '''
    def __init__(self, x = None, y = None, z = None):
        self.x = None
        self.y = None
        self.z = None
        self.set(x, y, z)

    def set(self, x = None, y = None, z = None):
        ''' Returns True if the position has actually changed.
        '''
        if self.x == x and self.y == y and self.z == z:
            return False
        self.x = x
        self.y = y
        self.z = z
        return True

    def get(self):
        ''' Fetch the (x,y,z) position tuple.
        '''
        return (self.x, self.y, self.z)

class PyCoreObj(object):
    ''' Base class for pycore objects (nodes and nets)
    '''
    apitype = None

    def __init__(self, session, objid = None, name = None, verbose = False, 
                start = True):
        self.session = session
        if objid is None:
            objid = session.getobjid()            
        self.objid = objid
        if name is None:
            name = "o%s" % self.objid
        self.name = name
        # ifindex is key, PyCoreNetIf instance is value
        self._netif = {}
        self.ifindex = 0
        self.canvas = None
        self.icon = None
        self.opaque = None
        self.verbose = verbose
        self.position = Position()

    def startup(self):
        ''' Each object implements its own startup method.
        '''
        raise NotImplementedError

    def shutdown(self):
        ''' Each object implements its own shutdown method.
        '''
        raise NotImplementedError

    def setposition(self, x = None, y = None, z = None):
        ''' Set the (x,y,z) position of the object.
        '''
        return self.position.set(x = x, y = y, z = z)

    def getposition(self):
        ''' Return an (x,y,z) tuple representing this object's position.
        '''
        return self.position.get()

    def ifname(self, ifindex):
        return self.netif(ifindex).name

    def netifs(self, sort=False):
        ''' Iterate over attached network interfaces.
        '''
        if sort:
            return map(lambda k: self._netif[k], sorted(self._netif.keys()))
        else:
            return self._netif.itervalues()

    def numnetif(self):
        ''' Return the attached interface count.
        '''
        return len(self._netif)
    
    def getifindex(self, netif):
        for ifindex in self._netif:
            if self._netif[ifindex] is netif:
                return ifindex
        return -1

    def newifindex(self):
        while self.ifindex in self._netif:
            self.ifindex += 1
        ifindex = self.ifindex
        self.ifindex += 1
        return ifindex

    def tonodemsg(self, flags):
        ''' Build a CORE API Node Message for this object. Both nodes and
            networks can be represented by a Node Message.
        '''
        if self.apitype is None:
            return None
        tlvdata = ""
        (x, y, z) = self.getposition()
        tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_NUMBER,
                                            self.objid)
        tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_TYPE,
                                            self.apitype)
        tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_NAME,
                                            self.name)
        if hasattr(self, "type") and self.type is not None:
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_MODEL,
                                                self.type)
        if hasattr(self, "server") and self.server is not None:
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_EMUSRV,
                                                self.server)
        if hasattr(self, "services") and len(self.services) != 0:
            nodeservices = []
            for s in self.services:
                 nodeservices.append(s._name)
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_SERVICES,
                                                "|".join(nodeservices))


        if x is not None:
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_XPOS, x)
        if y is not None:
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_YPOS, y)
        if self.canvas is not None:
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_CANVAS,
                                                self.canvas)
        tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_EMUID,
                                            self.objid)
        if self.icon is not None:
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_ICON,
                                                self.icon)
        if self.opaque is not None:
            tlvdata += coreapi.CoreNodeTlv.pack(coreapi.CORE_TLV_NODE_OPAQUE,
                                                self.opaque)
        msg = coreapi.CoreNodeMessage.pack(flags, tlvdata)
        return msg

    def tolinkmsgs(self, flags):
        ''' Build CORE API Link Messages for this object. There is no default
            method for PyCoreObjs as PyCoreNodes do not implement this but
            PyCoreNets do.
        '''
        return []
        
    def info(self, msg):
        ''' Utility method for printing informational messages when verbose
            is turned on.
        '''
        if self.verbose:
            print "%s: %s" % (self.name, msg)
            sys.stdout.flush()

    def warn(self, msg):
        ''' Utility method for printing warning/error messages
        '''
        print >> sys.stderr, "%s: %s" % (self.name, msg)
        sys.stderr.flush()
        
    def exception(self, level, source, text):
        ''' Generate an Exception Message for this session, providing this
            object number.
        '''
        if self.session:
            id = None
            if isinstance(self.objid, int):
                id = self.objid
            elif isinstance(self.objid, str) and self.objid.isdigit():
                id = int(self.objid)
            self.session.exception(level, source, id, text)


class PyCoreNode(PyCoreObj):
    ''' Base class for nodes
    '''
    def __init__(self, session, objid = None, name = None, verbose = False,
                 start = True):
        ''' Initialization for node objects.
        '''
        PyCoreObj.__init__(self,  session,  objid,  name, verbose=verbose,
                           start=start)
        self.services = []
        if not hasattr(self, "type"):
            self.type = None
        self.nodedir = None

    def nodeid(self):
        return self.objid
        
    def addservice(self,  service):
        if service is not None:
            self.services.append(service)

    def makenodedir(self):
        if self.nodedir is None:
            self.nodedir = \
                os.path.join(self.session.sessiondir, self.name + ".conf")
            os.makedirs(self.nodedir)
            self.tmpnodedir = True
        else:
            self.tmpnodedir = False
    
    def rmnodedir(self):
        if hasattr(self.session.options, 'preservedir'):
            if self.session.options.preservedir == '1':
                return
        if self.tmpnodedir:
            shutil.rmtree(self.nodedir, ignore_errors = True)

    def addnetif(self, netif, ifindex):
        if ifindex in self._netif:
            raise ValueError, "ifindex %s already exists" % ifindex
        self._netif[ifindex] = netif
        netif.netindex = ifindex

    def delnetif(self, ifindex):
        if ifindex not in self._netif:
            raise ValueError, "ifindex %s does not exist" % ifindex
        netif = self._netif.pop(ifindex)
        netif.shutdown()
        del netif

    def netif(self, ifindex, net = None):
        if ifindex in self._netif:
            return self._netif[ifindex]
        else:
            return None
        
    def attachnet(self, ifindex, net):
        if ifindex not in self._netif:
            raise ValueError, "ifindex %s does not exist" % ifindex
        self._netif[ifindex].attachnet(net)

    def detachnet(self, ifindex):
        if ifindex not in self._netif:
            raise ValueError, "ifindex %s does not exist" % ifindex
        self._netif[ifindex].detachnet()

    def setposition(self, x = None, y = None, z = None):
        changed = PyCoreObj.setposition(self, x = x, y = y, z = z)
        if not changed:
            # save extra interface range calculations
            return
        for netif in self.netifs(sort=True):
            netif.setposition(x, y, z)

    def commonnets(self, obj, want_ctrl=False):
        ''' Given another node or net object, return common networks between
            this node and that object. A list of tuples is returned, with each tuple
            consisting of (network, interface1, interface2).
        '''
        r = []
        for netif1 in self.netifs():
            if not want_ctrl and hasattr(netif1, 'control'):
                continue
            for netif2 in obj.netifs():
                if netif1.net == netif2.net:
                    r += (netif1.net, netif1, netif2),                    
        return r



class PyCoreNet(PyCoreObj):
    ''' Base class for networks
    '''
    linktype = coreapi.CORE_LINK_WIRED

    def __init__(self, session, objid, name, verbose = False, start = True):
        ''' Initialization for network objects.
        '''
        PyCoreObj.__init__(self, session, objid, name, verbose=verbose,
                           start=start)
        self._linked = {}
        self._linked_lock = threading.Lock()

    def attach(self, netif):
        i = self.newifindex()
        self._netif[i] = netif
        netif.netifi = i
        with self._linked_lock:
            self._linked[netif] = {}
        
    def detach(self, netif):
        del self._netif[netif.netifi]
        netif.netifi = None
        with self._linked_lock:
            del self._linked[netif]

    def netifparamstolink(self, netif):
        ''' Helper for tolinkmsgs() to build TLVs having link parameters
            from interface parameters.
        '''
        tlvdata = ""
        delay = netif.getparam('delay')
        bw = netif.getparam('bw')
        loss = netif.getparam('loss')
        duplicate = netif.getparam('duplicate')
        jitter = netif.getparam('jitter')
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
        return tlvdata

        
    def tolinkmsgs(self, flags):
        ''' Build CORE API Link Messages for this network. Each link message
            describes a link between this network and a node.
        '''
        msgs = []
        # build a link message from this network node to each node having a
        # connected interface
        for netif in self.netifs(sort=True):
            if not hasattr(netif, "node"):
                continue
            otherobj = netif.node
            uni = False
            if otherobj is None:
                # two layer-2 switches/hubs linked together via linknet()
                if not hasattr(netif, "othernet"):
                    continue
                otherobj = netif.othernet
                if otherobj.objid == self.objid:
                    continue
                netif.swapparams('_params_up')
                upstream_params = netif.getparams()
                netif.swapparams('_params_up')
                if netif.getparams() != upstream_params:
                    uni = True
                
            tlvdata = ""
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N1NUMBER,
                                                self.objid)
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N2NUMBER,
                                                otherobj.objid)
            tlvdata += self.netifparamstolink(netif)
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_TYPE,
                                                self.linktype)
            if uni:
                tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_UNI,
                                                    1)
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2NUM,
                                                otherobj.getifindex(netif))
            if netif.hwaddr:
                tlvdata += \
                    coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2MAC,
                                             netif.hwaddr)
            for addr in netif.addrlist:
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
                tlvdata += coreapi.CoreLinkTlv.pack(tlvtypeip, \
                                                    IPAddr(af=family, addr=ipl))
                tlvdata += coreapi.CoreLinkTlv.pack(tlvtypemask, mask)

            msg = coreapi.CoreLinkMessage.pack(flags, tlvdata)
            msgs.append(msg)
            if not uni:
                continue
            # build a 2nd link message for any upstream link parameters
            tlvdata = ""
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N1NUMBER,
                                                otherobj.objid)
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N2NUMBER,
                                                self.objid)
            netif.swapparams('_params_up')
            tlvdata += self.netifparamstolink(netif)
            netif.swapparams('_params_up')
            tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_UNI, 1)
            msg = coreapi.CoreLinkMessage.pack(0, tlvdata)
            msgs.append(msg)
        return msgs 

class PyCoreNetIf(object):
    ''' Base class for interfaces.
    '''
    def __init__(self, node, name, mtu):
        self.node = node
        self.name = name
        if not isinstance(mtu, (int, long)):
            raise ValueError
        self.mtu = mtu
        self.net = None
        self._params = {}
        self.addrlist = []
        self.hwaddr = None
        self.poshook = None
        # used with EMANE
        self.transport_type = None
        # interface index on the network
        self.netindex = None

    def startup(self):
        pass

    def shutdown(self):
        pass
    
    def attachnet(self, net):
        if self.net:
            self.detachnet()
            self.net = None
        net.attach(self)
        self.net = net

    def detachnet(self):
        if self.net is not None:
            self.net.detach(self)

    def addaddr(self, addr):
        self.addrlist.append(addr)

    def deladdr(self, addr):
        self.addrlist.remove(addr)

    def sethwaddr(self, addr):
        self.hwaddr = addr

    def getparam(self, key):
        ''' Retrieve a parameter from the _params dict,
            or None if the parameter does not exist.
        '''
        if key not in self._params:
            return None
        return self._params[key]
        
    def getparams(self):
        ''' Return (key, value) pairs from the _params dict.
        '''
        r = []
        for k in sorted(self._params.keys()):
            r.append((k, self._params[k]))
        return r
    
    def setparam(self, key, value):
        ''' Set a parameter in the _params dict.
            Returns True if the parameter has changed.
        '''
        if key in self._params:
            if self._params[key] == value:
                return False
            elif self._params[key] <= 0 and value <= 0:
                # treat None and 0 as unchanged values
                return False
        self._params[key] = value
        return True
        
    def swapparams(self, name):
        ''' Swap out the _params dict for name. If name does not exist,
        intialize it. This is for supporting separate upstream/downstream
        parameters when two layer-2 nodes are linked together.
        '''
        tmp = self._params
        if not hasattr(self, name):
            setattr(self, name, {})
        self._params = getattr(self, name)
        setattr(self, name, tmp)

    def setposition(self, x, y, z):
        ''' Dispatch to any position hook (self.poshook) handler.
        '''
        if self.poshook is not None:
            self.poshook(self, x, y, z)

