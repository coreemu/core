#
# CORE
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
xorp.py: defines routing services provided by the XORP routing suite.
'''

import os

from core.service import CoreService, addservice
from core.misc.ipaddr import IPv4Prefix
from core.constants import *

class XorpRtrmgr(CoreService):
    ''' XORP router manager service builds a config.boot file based on other 
    enabled XORP services, and launches necessary daemons upon startup.
    '''
    _name = "xorp_rtrmgr"
    _group = "XORP"
    _depends = ()
    _dirs = ("/etc/xorp",)
    _configs = ("/etc/xorp/config.boot",)
    _startindex = 35
    _startup = ("xorp_rtrmgr -d -b %s -l /var/log/%s.log -P /var/run/%s.pid" % (_configs[0], _name, _name),)
    _shutdown = ("killall xorp_rtrmgr", )
    _validate = ("pidof xorp_rtrmgr", )

    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Returns config.boot configuration file text. Other services that 
        depend on this will have generatexorpconfig() hooks that are 
        invoked here. Filename currently ignored.
        '''
        cfg = "interfaces {\n"
        for ifc in node.netifs():
            cfg += "    interface %s {\n" % ifc.name
            cfg += "\tvif %s {\n" % ifc.name
            cfg += "".join(map(cls.addrstr, ifc.addrlist))
            cfg += cls.lladdrstr(ifc)
            cfg += "\t}\n"
            cfg += "    }\n"
        cfg += "}\n\n"

        for s in services:
            try:
                s._depends.index(cls._name)
                cfg += s.generatexorpconfig(node)
            except ValueError:
                pass
        return cfg
    
    @staticmethod
    def addrstr(x):
        ''' helper for mapping IP addresses to XORP config statements
        '''
        try:
            (addr, plen) = x.split("/")
        except Exception:
            raise ValueError, "invalid address"
        cfg = "\t    address %s {\n" % addr
        cfg += "\t\tprefix-length: %s\n" % plen
        cfg +="\t    }\n"
        return cfg
    
    @staticmethod
    def lladdrstr(ifc):
        ''' helper for adding link-local address entries (required by OSPFv3)
        '''
        cfg = "\t    address %s {\n" % ifc.hwaddr.tolinklocal()
        cfg += "\t\tprefix-length: 64\n"
        cfg += "\t    }\n"
        return cfg
            
addservice(XorpRtrmgr)

class XorpService(CoreService):
    ''' Parent class for XORP services. Defines properties and methods
        common to XORP's routing daemons.
    '''
    _name = "XorpDaemon"
    _group = "XORP"
    _depends = ("xorp_rtrmgr", )
    _dirs = ()
    _configs = ()
    _startindex = 40
    _startup = ()
    _shutdown = ()
    _meta = "The config file for this service can be found in the xorp_rtrmgr service."

    @staticmethod
    def fea(forwarding):
        ''' Helper to add a forwarding engine entry to the config file.
        '''
        cfg = "fea {\n"
        cfg += "    %s {\n" % forwarding
        cfg += "\tdisable:false\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
    
    @staticmethod
    def mfea(forwarding, ifcs):
        ''' Helper to add a multicast forwarding engine entry to the config file.
        '''
        names = []
        for ifc in ifcs:
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            names.append(ifc.name)
        names.append("register_vif")

        cfg = "plumbing {\n"
        cfg += "    %s {\n" % forwarding
        for name in names:
            cfg += "\tinterface %s {\n" % name
            cfg += "\t    vif %s {\n" % name
            cfg += "\t\tdisable: false\n"
            cfg += "\t    }\n"
            cfg += "\t}\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg

        
    @staticmethod
    def policyexportconnected():
        ''' Helper to add a policy statement for exporting connected routes.
        '''
        cfg = "policy {\n"
        cfg += "    policy-statement export-connected {\n"
        cfg += "\tterm 100 {\n"
        cfg += "\t    from {\n"
        cfg += "\t\tprotocol: \"connected\"\n"
        cfg += "\t    }\n"
        cfg += "\t}\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg

    @staticmethod
    def routerid(node):
        ''' Helper to return the first IPv4 address of a node as its router ID.
        '''
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            for a in ifc.addrlist:
                if a.find(".") >= 0:
                    return a.split('/')[0]          
        #raise ValueError,  "no IPv4 address found for router ID"
        return "0.0.0.0"

    @classmethod
    def generateconfig(cls,  node, filename, services):
        return ""

    @classmethod
    def generatexorpconfig(cls,  node):
        return ""

class XorpOspfv2(XorpService):
    ''' The OSPFv2 service provides IPv4 routing for wired networks. It does
        not build its own configuration file but has hooks for adding to the
        unified XORP configuration file.
    '''
    _name = "XORP_OSPFv2"

    @classmethod
    def generatexorpconfig(cls,  node):
        cfg = cls.fea("unicast-forwarding4")
        rtrid = cls.routerid(node)
        cfg += "\nprotocols {\n"
        cfg += "    ospf4 {\n"
        cfg += "\trouter-id: %s\n" % rtrid
        cfg += "\tarea 0.0.0.0 {\n"
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            cfg += "\t    interface %s {\n" % ifc.name
            cfg += "\t\tvif %s {\n" % ifc.name
            for a in ifc.addrlist:
                if a.find(".") < 0:
                    continue
                addr = a.split("/")[0]
                cfg += "\t\t    address %s {\n" % addr
                cfg += "\t\t    }\n"
            cfg += "\t\t}\n"
            cfg += "\t    }\n"
        cfg += "\t}\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
        
addservice(XorpOspfv2)

class XorpOspfv3(XorpService):
    ''' The OSPFv3 service provides IPv6 routing. It does
        not build its own configuration file but has hooks for adding to the
        unified XORP configuration file.
    '''
    _name = "XORP_OSPFv3"

    @classmethod
    def generatexorpconfig(cls,  node):
        cfg = cls.fea("unicast-forwarding6")
        rtrid = cls.routerid(node)
        cfg += "\nprotocols {\n"
        cfg += "    ospf6 0 { /* Instance ID 0 */\n"
        cfg += "\trouter-id: %s\n" % rtrid
        cfg += "\tarea 0.0.0.0 {\n"
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            cfg += "\t    interface %s {\n" % ifc.name
            cfg += "\t\tvif %s {\n" % ifc.name
            cfg += "\t\t}\n"
            cfg += "\t    }\n"
        cfg += "\t}\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
        
addservice(XorpOspfv3)

class XorpBgp(XorpService):
    ''' IPv4 inter-domain routing. AS numbers and peers must be customized.
    '''
    _name = "XORP_BGP"
    _custom_needed = True
    
    @classmethod
    def generatexorpconfig(cls, node):
        cfg = "/* This is a sample config that should be customized with\n"
        cfg += " appropriate AS numbers and peers */\n"
        cfg += cls.fea("unicast-forwarding4")
        cfg += cls.policyexportconnected()
        rtrid = cls.routerid(node)
        cfg += "\nprotocols {\n"
        cfg += "    bgp {\n"
        cfg += "\tbgp-id: %s\n" % rtrid
        cfg += "\tlocal-as: 65001 /* change this */\n"
        cfg += "\texport: \"export-connected\"\n"
        cfg += "\tpeer 10.0.1.1 { /* change this */\n"
        cfg += "\t    local-ip: 10.0.1.1\n"
        cfg += "\t    as: 65002\n"
        cfg += "\t    next-hop: 10.0.0.2\n"
        cfg += "\t}\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg

addservice(XorpBgp)

class XorpRip(XorpService):
    ''' RIP IPv4 unicast routing.
    '''
    _name = "XORP_RIP"

    @classmethod
    def generatexorpconfig(cls,  node):
        cfg = cls.fea("unicast-forwarding4")
        cfg += cls.policyexportconnected()
        cfg += "\nprotocols {\n"
        cfg += "    rip {\n"
        cfg += "\texport: \"export-connected\"\n"
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            cfg += "\tinterface %s {\n" % ifc.name
            cfg += "\t    vif %s {\n" % ifc.name
            for a in ifc.addrlist:
                if a.find(".") < 0:
                    continue
                addr = a.split("/")[0]
                cfg += "\t\taddress %s {\n" % addr
                cfg += "\t\t    disable: false\n"
                cfg += "\t\t}\n"
            cfg += "\t    }\n"
            cfg += "\t}\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
        
addservice(XorpRip)

class XorpRipng(XorpService):
    ''' RIP NG IPv6 unicast routing.
    '''
    _name = "XORP_RIPNG"

    @classmethod
    def generatexorpconfig(cls,  node):
        cfg = cls.fea("unicast-forwarding6")
        cfg += cls.policyexportconnected()
        cfg += "\nprotocols {\n"
        cfg += "    ripng {\n"
        cfg += "\texport: \"export-connected\"\n"
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            cfg += "\tinterface %s {\n" % ifc.name
            cfg += "\t    vif %s {\n" % ifc.name
#            for a in ifc.addrlist:
#                if a.find(":") < 0:
#                    continue
#                addr = a.split("/")[0]
#                cfg += "\t\taddress %s {\n" % addr
#                cfg += "\t\t    disable: false\n"
#                cfg += "\t\t}\n"
            cfg += "\t\taddress %s {\n" % ifc.hwaddr.tolinklocal()
            cfg += "\t\t    disable: false\n"
            cfg += "\t\t}\n"
            cfg += "\t    }\n"
            cfg += "\t}\n"            
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
        
addservice(XorpRipng)

class XorpPimSm4(XorpService):
    ''' PIM Sparse Mode IPv4 multicast routing.
    '''
    _name = "XORP_PIMSM4"

    @classmethod
    def generatexorpconfig(cls,  node):
        cfg = cls.mfea("mfea4", node.netifs())
                
        cfg += "\nprotocols {\n"
        cfg += "    igmp {\n"
        names = []
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            names.append(ifc.name)
            cfg += "\tinterface %s {\n" % ifc.name
            cfg += "\t    vif %s {\n" % ifc.name
            cfg += "\t\tdisable: false\n"
            cfg += "\t    }\n"
            cfg += "\t}\n"            
        cfg += "    }\n"
        cfg += "}\n"
        
        cfg += "\nprotocols {\n"
        cfg += "    pimsm4 {\n"

        names.append("register_vif")
        for name in names:
            cfg += "\tinterface %s {\n" % name
            cfg += "\t    vif %s {\n" % name
            cfg += "\t\tdr-priority: 1\n"
            cfg += "\t    }\n"
            cfg += "\t}\n"
        cfg += "\tbootstrap {\n"
        cfg += "\t    cand-bsr {\n"
        cfg += "\t\tscope-zone 224.0.0.0/4 {\n"
        cfg += "\t\t    cand-bsr-by-vif-name: \"%s\"\n" % names[0]
        cfg += "\t\t}\n"
        cfg += "\t    }\n"
        cfg += "\t    cand-rp {\n"
        cfg += "\t\tgroup-prefix 224.0.0.0/4 {\n"
        cfg += "\t\t    cand-rp-by-vif-name: \"%s\"\n" % names[0]
        cfg += "\t\t}\n"
        cfg += "\t    }\n"
        cfg += "\t}\n"
        
        cfg += "    }\n"
        cfg += "}\n"
        
        cfg += "\nprotocols {\n"
        cfg += "    fib2mrib {\n"
        cfg += "\tdisable: false\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
        
addservice(XorpPimSm4)

class XorpPimSm6(XorpService):
    ''' PIM Sparse Mode IPv6 multicast routing.
    '''
    _name = "XORP_PIMSM6"

    @classmethod
    def generatexorpconfig(cls,  node):
        cfg = cls.mfea("mfea6", node.netifs())
                
        cfg += "\nprotocols {\n"
        cfg += "    mld {\n"
        names = []
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            names.append(ifc.name)
            cfg += "\tinterface %s {\n" % ifc.name
            cfg += "\t    vif %s {\n" % ifc.name
            cfg += "\t\tdisable: false\n"
            cfg += "\t    }\n"
            cfg += "\t}\n"            
        cfg += "    }\n"
        cfg += "}\n"
        
        cfg += "\nprotocols {\n"
        cfg += "    pimsm6 {\n"
        
        names.append("register_vif")
        for name in names:
            cfg += "\tinterface %s {\n" % name
            cfg += "\t    vif %s {\n" % name
            cfg += "\t\tdr-priority: 1\n"
            cfg += "\t    }\n"
            cfg += "\t}\n"
        cfg += "\tbootstrap {\n"
        cfg += "\t    cand-bsr {\n"
        cfg += "\t\tscope-zone ff00::/8 {\n"
        cfg += "\t\t    cand-bsr-by-vif-name: \"%s\"\n" % names[0]
        cfg += "\t\t}\n"
        cfg += "\t    }\n"
        cfg += "\t    cand-rp {\n"
        cfg += "\t\tgroup-prefix ff00::/8 {\n"
        cfg += "\t\t    cand-rp-by-vif-name: \"%s\"\n" % names[0]
        cfg += "\t\t}\n"
        cfg += "\t    }\n"
        cfg += "\t}\n"
        
        cfg += "    }\n"
        cfg += "}\n"
        
        cfg += "\nprotocols {\n"
        cfg += "    fib2mrib {\n"
        cfg += "\tdisable: false\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
        
addservice(XorpPimSm6)

class XorpOlsr(XorpService):
    ''' OLSR IPv4 unicast MANET routing.
    '''
    _name = "XORP_OLSR"

    @classmethod
    def generatexorpconfig(cls,  node):
        cfg = cls.fea("unicast-forwarding4")
        rtrid = cls.routerid(node)
        cfg += "\nprotocols {\n"
        cfg += "    olsr4 {\n"
        cfg += "\tmain-address: %s\n" % rtrid
        for ifc in node.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                continue
            cfg += "\tinterface %s {\n" % ifc.name
            cfg += "\t    vif %s {\n" % ifc.name
            for a in ifc.addrlist:
                if a.find(".") < 0:
                    continue
                addr = a.split("/")[0]
                cfg += "\t\taddress %s {\n" % addr
                cfg += "\t\t}\n"
            cfg += "\t    }\n"
        cfg += "\t}\n"
        cfg += "    }\n"
        cfg += "}\n"
        return cfg
        
addservice(XorpOlsr)
