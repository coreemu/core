#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Tom Goff <thomas.goff@boeing.com>
#
'''
quagga.py: helper class for generating Quagga configuration.
'''

import os.path
from string import Template

def maketuple(obj):
    if hasattr(obj, "__iter__"):
        return tuple(obj)
    else:
        return (obj,)

class NetIf(object):
    def __init__(self, name, addrlist = []):
        self.name = name
        self.addrlist = addrlist

class Conf(object):
    def __init__(self, **kwds):
        self.kwds = kwds

    def __str__(self):
        tmp = self.template.substitute(**self.kwds)
        if tmp[-1] == '\n':
            tmp = tmp[:-1]
        return tmp

class QuaggaOSPF6Interface(Conf):
    AF_IPV6_ID = 0
    AF_IPV4_ID = 65

    template = Template("""\
interface $interface
  $addr
  ipv6 ospf6 instance-id $instanceid
  ipv6 ospf6 hello-interval 2
  ipv6 ospf6 dead-interval 11
  ipv6 ospf6 retransmit-interval 5
  ipv6 ospf6 network $network
  ipv6 ospf6 diffhellos
  ipv6 ospf6 adjacencyconnectivity uniconnected
  ipv6 ospf6 lsafullness mincostlsa
""")

#   ip address $ipaddr/32
#   ipv6 ospf6 simhelloLLtoULRecv :$simhelloport
#   !$ipaddr:$simhelloport

    def __init__(self, netif, instanceid = AF_IPV4_ID,
                 network = "manet-designated-router", **kwds):
        self.netif = netif
        def addrstr(x):
            if x.find(".") >= 0:
                return "ip address %s" % x
            elif x.find(":") >= 0:
                return "ipv6 address %s" % x
            else:
                raise Value, "invalid address: %s", x
        addr = "\n  ".join(map(addrstr, netif.addrlist))

        self.instanceid = instanceid
        self.network = network
        Conf.__init__(self, interface = netif.name, addr = addr,
                      instanceid = instanceid, network = network, **kwds)

    def name(self):
        return self.netif.name

class QuaggaOSPF6(Conf):

    template = Template("""\
$interfaces
!
router ospf6
  router-id $routerid
  $ospfifs
  $redistribute
""")

    def __init__(self, ospf6ifs, area, routerid,
                 redistribute = "! no redistribute"):
        ospf6ifs = maketuple(ospf6ifs)
        interfaces = "\n!\n".join(map(str, ospf6ifs))
        ospfifs = "\n  ".join(map(lambda x: "interface %s area %s" % \
                                (x.name(), area), ospf6ifs))
        Conf.__init__(self, interfaces = interfaces, routerid = routerid,
                      ospfifs = ospfifs, redistribute = redistribute)


class QuaggaConf(Conf):
    template = Template("""\
log file $logfile
$debugs
!
$routers
!
$forwarding
""")

    def __init__(self, routers, logfile, debugs = ()):
        routers = "\n!\n".join(map(str, maketuple(routers)))
        if debugs:
            debugs = "\n".join(maketuple(debugs))
        else:
            debugs = "! no debugs"
        forwarding = "ip forwarding\nipv6 forwarding"
        Conf.__init__(self, logfile = logfile, debugs = debugs,
                      routers = routers, forwarding = forwarding)
