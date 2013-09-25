#!/usr/bin/python -i

# Copyright (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
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

'''

import os, sys, time, optparse, datetime, math
try:
    from core import pycore
except ImportError:
    # hack for Fedora autoconf that uses the following pythondir:
    if "/usr/lib/python2.6/site-packages" in sys.path:
        sys.path.append("/usr/local/lib/python2.6/site-packages")
    if "/usr/lib64/python2.6/site-packages" in sys.path:
        sys.path.append("/usr/local/lib64/python2.6/site-packages")
    if "/usr/lib/python2.7/site-packages" in sys.path:
        sys.path.append("/usr/local/lib/python2.7/site-packages")
    if "/usr/lib64/python2.7/site-packages" in sys.path:
        sys.path.append("/usr/local/lib64/python2.7/site-packages")
    from core import pycore

import ns.core
from core.misc import ipaddr 
from corens3.obj import Ns3Session, Ns3WifiNet

def add_to_server(session):
    ''' Add this session to the server's list if this script is executed from
    the core-daemon server.
    '''
    global server
    try:
        server.addsession(session)
        return True
    except NameError:
        return False

def wifisession(opt):
    ''' Run a test wifi session.
    '''
    session = Ns3Session(persistent=True, duration=opt.duration)
    session.name = "ns3wifi"
    session.filename = session.name + ".py"
    session.node_count = str(opt.numnodes + 1)
    add_to_server(session)
    
    wifi = session.addobj(cls=Ns3WifiNet, name="wlan1")
    wifi.setposition(30, 30, 0)
    wifi.phy.Set("RxGain", ns.core.DoubleValue(18.0))

    prefix = ipaddr.IPv4Prefix("10.0.0.0/16")
    nodes = []
    for i in xrange(1, opt.numnodes + 1):
        node = session.addnode(name = "n%d" % i)
        node.newnetif(wifi, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        nodes.append(node)
    session.setupconstantmobility()
    wifi.usecorepositions()
    # PHY tracing
    #wifi.phy.EnableAsciiAll("ns3wifi")
    session.thread = session.run(vis=False)
    return session
    
def main():
    ''' Main routine when running from command-line.
    '''
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 10, duration = 600, verbose = False)

    parser.add_option("-d", "--duration", dest = "duration", type = int,
                      help = "number of seconds to run the simulation")
    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes")
    parser.add_option("-v", "--verbose", dest = "verbose",
                      action = "store_true", help = "be more verbose")

    def usage(msg = None, err = 0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    (opt, args) = parser.parse_args()

    if opt.numnodes < 2:
        usage("invalid numnodes: %s" % opt.numnodes)

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    return wifisession(opt)


if __name__ == "__main__" or __name__ == "__builtin__":
    session = main()
    print "\nsession =", session
