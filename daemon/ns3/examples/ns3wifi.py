"""
ns3wifi.py - This script demonstrates using CORE with the ns-3 Wifi model.

How to run this:

    pushd ~/ns-allinone-3.16/ns-3.16
    sudo ./waf shell
    popd
    python -i ns3wifi.py

To run with the CORE GUI:

    pushd ~/ns-allinone-3.16/ns-3.16
    sudo ./waf shell
    core-daemon

    # in another terminal
    core-daemon -e ./ns3wifi.py
    # in a third terminal
    core
    # now select the running session

"""

import optparse
import sys

import ns.core

from core import logger
from core.misc import ipaddress

from corens3.obj import Ns3Session
from corens3.obj import Ns3WifiNet


def add_to_server(session):
    """
    Add this session to the server's list if this script is executed from
    the core-daemon server.
    """
    global server
    try:
        server.addsession(session)
        return True
    except NameError:
        return False


def wifisession(opt):
    """
    Run a test wifi session.
    """
    session = Ns3Session(persistent=True, duration=opt.duration)
    session.name = "ns3wifi"
    session.filename = session.name + ".py"
    session.node_count = str(opt.numnodes + 1)
    add_to_server(session)

    wifi = session.add_object(cls=Ns3WifiNet, name="wlan1")
    wifi.setposition(30, 30, 0)
    wifi.phy.Set("RxGain", ns.core.DoubleValue(18.0))

    prefix = ipaddress.Ipv4Prefix("10.0.0.0/16")
    nodes = []
    for i in xrange(1, opt.numnodes + 1):
        node = session.addnode(name="n%d" % i)
        node.newnetif(wifi, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        nodes.append(node)
    session.setupconstantmobility()
    wifi.usecorepositions()
    # PHY tracing
    # wifi.phy.EnableAsciiAll("ns3wifi")
    session.thread = session.run(vis=False)
    return session


def main():
    """
    Main routine when running from command-line.
    """
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage=usagestr)
    parser.set_defaults(numnodes=10, duration=600, verbose=False)

    parser.add_option("-d", "--duration", dest="duration", type=int,
                      help="number of seconds to run the simulation")
    parser.add_option("-n", "--numnodes", dest="numnodes", type=int,
                      help="number of nodes")
    parser.add_option("-v", "--verbose", dest="verbose",
                      action="store_true", help="be more verbose")

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
        logger.warn("ignoring command line argument: '%s'", a)

    return wifisession(opt)


if __name__ == "__main__" or __name__ == "__builtin__":
    session = main()
    logger.info("\nsession =%s", session)
