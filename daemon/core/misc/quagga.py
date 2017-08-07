#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Tom Goff <thomas.goff@boeing.com>
#

"""
quagga.py: helper class for generating Quagga configuration.
"""

from string import Template

from core.misc import utils


def addrstr(x):
    if x.find(".") >= 0:
        return "ip address %s" % x
    elif x.find(":") >= 0:
        return "ipv6 address %s" % x
    else:
        raise ValueError("invalid address: %s" % x)


class NetIf(object):
    """
    Represents a network interface.
    """

    def __init__(self, name, addrlist=None):
        """
        Create a NetIf instance.

        :param str name: interface name
        :param addrlist: address list for the interface
        """
        self.name = name

        if addrlist:
            self.addrlist = addrlist
        else:
            self.addrlist = []


class Conf(object):
    """
    Provides a configuration object.
    """

    template = Template("")

    def __init__(self, **kwargs):
        """
        Create a Conf instance.

        :param dict kwargs: configuration keyword arguments
        """
        self.kwargs = kwargs

    def __str__(self):
        """
        Provides a string representation of a configuration object.

        :return: string representation
        :rtype: str
        """
        tmp = self.template.substitute(**self.kwargs)
        if tmp[-1] == "\n":
            tmp = tmp[:-1]
        return tmp


class QuaggaOSPF6Interface(Conf):
    """
    Provides quagga ospf6 interface functionality.
    """
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

    def __init__(self, netif, instanceid=AF_IPV4_ID, network="manet-designated-router", **kwargs):
        """
        Create a QuaggaOSPF6Interface instance.

        :param netif: network interface
        :param int instanceid: instance id
        :param network: network
        :param dict kwargs: keyword arguments
        """
        self.netif = netif
        addr = "\n  ".join(map(addrstr, netif.addrlist))
        self.instanceid = instanceid
        self.network = network
        Conf.__init__(self, interface=netif.name, addr=addr,
                      instanceid=instanceid, network=network, **kwargs)

    def name(self):
        """
        Retrieve network interface name.

        :return: network interface name
        :rtype: str
        """
        return self.netif.name


class QuaggaOSPF6(Conf):
    """
    Provides quagga ospf6 functionality.
    """
    template = Template("""\
$interfaces
!
router ospf6
  router-id $routerid
  $ospfifs
  $redistribute
""")

    def __init__(self, ospf6ifs, area, routerid, redistribute="! no redistribute"):
        """
        Create a QuaggaOSPF6 instance.

        :param list ospf6ifs: ospf6 interfaces
        :param area: area
        :param routerid: router id
        :param str redistribute: redistribute value
        """
        ospf6ifs = utils.maketuple(ospf6ifs)
        interfaces = "\n!\n".join(map(str, ospf6ifs))
        ospfifs = "\n  ".join(map(lambda x: "interface %s area %s" % (x.name(), area), ospf6ifs))
        Conf.__init__(self, interfaces=interfaces, routerid=routerid, ospfifs=ospfifs, redistribute=redistribute)


class QuaggaConf(Conf):
    """
    Provides quagga configuration functionality.
    """
    template = Template("""\
log file $logfile
$debugs
!
$routers
!
$forwarding
""")

    def __init__(self, routers, logfile, debugs=()):
        """
        Create a QuaggaConf instance.

        :param list routers: routers
        :param str logfile: log file name
        :param debugs: debug options
        """
        routers = "\n!\n".join(map(str, utils.maketuple(routers)))
        if debugs:
            debugs = "\n".join(utils.maketuple(debugs))
        else:
            debugs = "! no debugs"
        forwarding = "ip forwarding\nipv6 forwarding"
        Conf.__init__(self, logfile=logfile, debugs=debugs, routers=routers, forwarding=forwarding)
