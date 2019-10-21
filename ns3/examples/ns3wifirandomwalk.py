"""
ns3wifirandomwalk.py - This script demonstrates using CORE with the ns-3 Wifi
model and random walk mobility.
Patterned after the ns-3 example 'main-random-walk.cc'.

How to run this:

    pushd ~/ns-allinone-3.16/ns-3.16
    sudo ./waf shell
    popd
    python -i ns3wifirandomwalk.py
"""

import logging
import optparse
import sys
from builtins import range

import ns.core
import ns.network
from corens3.obj import Ns3Session
from corens3.obj import Ns3WifiNet

from core.nodes import ipaddress


def add_to_server(session):
    """
    Add this session to the server's list if this script is executed from
    the core-daemon server.
    """
    global server
    try:
        server.add_session(session)
        return True
    except NameError:
        return False


def wifisession(opt):
    """
    Run a random walk wifi session.
    """
    session = Ns3Session(1, persistent=True, duration=opt.duration)
    session.name = "ns3wifirandomwalk"
    session.filename = session.name + ".py"
    session.node_count = str(opt.numnodes + 1)
    add_to_server(session)
    wifi = session.create_node(cls=Ns3WifiNet, name="wlan1", rate="OfdmRate12Mbps")
    wifi.setposition(30, 30, 0)
    # for improved connectivity
    wifi.phy.Set("RxGain", ns.core.DoubleValue(18.0))

    prefix = ipaddress.Ipv4Prefix("10.0.0.0/16")
    services_str = "zebra|OSPFv3MDR|IPForward"
    nodes = []
    for i in range(1, opt.numnodes + 1):
        node = session.addnode(name="n%d" % i)
        node.newnetif(wifi, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        nodes.append(node)
        session.services.add_services(node, "router", services_str.split("|"))
        session.services.boot_services(node)
    session.setuprandomwalkmobility(bounds=(1000.0, 750.0, 0))

    # PHY tracing
    # wifi.phy.EnableAsciiAll("ns3wifirandomwalk")

    # mobility tracing
    # session.setupmobilitytracing(wifi, "ns3wifirandomwalk.mob.tr",
    #                             nodes, verbose=True)
    session.startns3mobility(refresh_ms=150)

    # start simulation
    # session.instantiate() ?
    session.thread = session.run(vis=opt.viz)
    return session


def main():
    """
    Main routine when running from command-line.
    """
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage=usagestr)
    parser.set_defaults(numnodes=5, duration=600, verbose=False, viz=False)
    opt = {'numnodes': 5, 'duration': 600, 'verbose': False, 'viz': False}

    parser.add_option("-d", "--duration", dest="duration", type=int,
                      help="number of seconds to run the simulation")
    parser.add_option("-n", "--numnodes", dest="numnodes", type=int,
                      help="number of nodes")
    parser.add_option("-v", "--verbose", dest="verbose",
                      action="store_true", help="be more verbose")
    parser.add_option("-V", "--visualize", dest="viz",
                      action="store_true", help="enable PyViz ns-3 visualizer")

    def usage(msg=None, err=0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    opt, args = parser.parse_args()

    if opt.numnodes < 2:
        usage("invalid numnodes: %s" % opt.numnodes)

    for a in args:
        logging.warn("ignoring command line argument: '%s'", a)

    return wifisession(opt)


if __name__ == "__main__" or __name__ == "__builtin__":
    session = main()
    logging.info("\nsession =%s", session)
