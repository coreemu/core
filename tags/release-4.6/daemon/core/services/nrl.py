#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
nrl.py: defines services provided by NRL protolib tools hosted here:
http://cs.itd.nrl.navy.mil/products/
'''

from core.service import CoreService, addservice
from core.misc.ipaddr import IPv4Prefix

class NrlService(CoreService):
    ''' Parent class for NRL services. Defines properties and methods
        common to NRL's routing daemons.
    '''
    _name = "NRLDaemon"
    _group = "Routing"
    _depends = ()
    _dirs = ()
    _configs = ()
    _startindex = 45
    _startup = ()
    _shutdown = ()

    @classmethod
    def generateconfig(cls,  node, filename, services):
        return ""
        
    @staticmethod
    def firstipv4prefix(node, prefixlen=24):
        ''' Similar to QuaggaService.routerid(). Helper to return the first IPv4
        prefix of a node, using the supplied prefix length. This ignores the
        interface's prefix length, so e.g. '/32' can turn into '/24'.
        '''
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            for a in ifc.addrlist:
                if a.find(".") >= 0:
                    addr = a.split('/')[0]
                    pre = IPv4Prefix("%s/%s" % (addr, prefixlen))
                    return str(pre)
        #raise ValueError,  "no IPv4 address found"
        return "0.0.0.0/%s" % prefixlen

class NrlNhdp(NrlService):
    ''' NeighborHood Discovery Protocol for MANET networks.
    '''
    _name = "NHDP"
    _startup = ("nrlnhdp", )
    _shutdown = ("killall nrlnhdp", )
    _validate = ("pidof nrlnhdp", )

    @classmethod
    def getstartup(cls,  node,  services):
        ''' Generate the appropriate command-line based on node interfaces.
        '''
        cmd = cls._startup[0]
        cmd += " -l /var/log/nrlnhdp.log"
        cmd += " -rpipe %s_nhdp" % node.name
        
        servicenames = map(lambda x: x._name,  services)
        if "SMF" in servicenames:
            cmd += " -flooding ecds"
            cmd += " -smfClient %s_smf" % node.name
        
        netifs = filter(lambda x: not getattr(x, 'control', False), \
                        node.netifs())
        if len(netifs) > 0:
            interfacenames = map(lambda x: x.name, netifs)
            cmd += " -i "
            cmd += " -i ".join(interfacenames)
        
        return (cmd, )
     
addservice(NrlNhdp)

class NrlSmf(NrlService):
    ''' Simplified Multicast Forwarding for MANET networks.
    '''
    _name = "SMF"
    _startup = ("nrlsmf", )
    _shutdown = ("killall nrlsmf", )
    _validate = ("pidof nrlsmf", )
    
    @classmethod
    def getstartup(cls,  node,  services):
        ''' Generate the appropriate command-line based on node interfaces.
        '''
        cmd = cls._startup[0]
        cmd += " instance %s_smf" % node.name

        servicenames = map(lambda x: x._name,  services)
        netifs = filter(lambda x: not getattr(x, 'control', False), \
                        node.netifs())
        if len(netifs) == 0:
            return ()
                        
        if "arouted" in servicenames:
            cmd += " tap %s_tap" % (node.name,)
            cmd += " unicast %s" % cls.firstipv4prefix(node, 24)
            cmd += " push lo,%s resequence on" % netifs[0].name
        if len(netifs) > 0:
            if "NHDP" in servicenames:
                cmd += " ecds "
            elif "OLSR" in servicenames:
                cmd += " smpr "
            else:
                cmd += " cf "
            interfacenames = map(lambda x: x.name,  netifs)
            cmd += ",".join(interfacenames)
            
        cmd += " hash MD5"
        cmd += " log /var/log/nrlsmf.log"
        return (cmd, )
     
addservice(NrlSmf)

class NrlOlsr(NrlService):
    ''' Optimized Link State Routing protocol for MANET networks.
    '''
    _name = "OLSR"
    _startup = ("nrlolsrd", )
    _shutdown = ("killall nrlolsrd", )
    _validate = ("pidof nrlolsrd", )
    
    @classmethod
    def getstartup(cls,  node,  services):
        ''' Generate the appropriate command-line based on node interfaces.
        '''
        cmd = cls._startup[0]
        # are multiple interfaces supported? No.
        netifs = list(node.netifs())
        if len(netifs) > 0:
            ifc = netifs[0]
            cmd += " -i %s" % ifc.name
        cmd += " -l /var/log/nrlolsrd.log"
        cmd += " -rpipe %s_olsr" % node.name

        servicenames = map(lambda x: x._name,  services)
        if "SMF" in servicenames and not "NHDP" in servicenames:
            cmd += " -flooding s-mpr"
            cmd += " -smfClient %s_smf" % node.name
        if "zebra" in servicenames:
            cmd += " -z"

        return (cmd, )
        
addservice(NrlOlsr)

class Arouted(NrlService):
    ''' Adaptive Routing
    '''
    _name = "arouted"
    _configs = ("startarouted.sh", )
    _startindex = NrlService._startindex + 10
    _startup = ("sh startarouted.sh", )
    _shutdown = ("pkill arouted", )
    _validate = ("pidof arouted", )
    
    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Return the Quagga.conf or quaggaboot.sh file contents.
        '''
        cfg = """
#!/bin/sh
for f in "/tmp/%s_smf"; do
    count=1
    until [ -e "$f" ]; do
        if [ $count -eq 10 ]; then
            echo "ERROR: nrlmsf pipe not found: $f" >&2
            exit 1
        fi
        sleep 0.1
        count=$(($count + 1))
    done
done

""" % (node.name)
        cfg += "ip route add %s dev lo\n" % cls.firstipv4prefix(node, 24)
        cfg += "arouted instance %s_smf tap %s_tap" % (node.name, node.name)
        cfg += " stability 10" # seconds to consider a new route valid
        cfg += " 2>&1 > /var/log/arouted.log &\n\n"
        return cfg

# experimental
#addservice(Arouted)
