#!/usr/bin/python -i

# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
ns3wimax.py - This script demonstrates using CORE with the ns-3 Wimax model.
*** Note that this script is not currently functional, see notes below. ***
Current issues:
- large amount of base station chatter; huge trace files, 70% CPU usage
- PCAP files unreadable
- base station causes segfault if it sends packet; due to missing service flows
  (but AddFlow() is not available for bs devices)
- no packets are sent between nodes - no connection?
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
 
from core.misc import ipaddr 
from corens3.obj import Ns3Session, Ns3WimaxNet

def wimaxsession(opt):
    ''' Run a test wimax session.
    '''
    session = Ns3Session(persistent=True, duration=opt.duration)
    wimax = session.addobj(cls=Ns3WimaxNet, name="wlan1")
    #wimax.wimax.EnableLogComponents()

    prefix = ipaddr.IPv4Prefix("10.0.0.0/16")
    # create one classifier for ICMP (protocol 1) traffic
    # src port low/high, dst port low/high, protocol, priority
    #classifier = (0, 65000, 0, 65000, 1, 1)
    classifier = (0, 65000, 0, 65000, 17, 1)
    nodes = []
    for i in xrange(1, opt.numnodes + 1):
        node = session.addnode(name = "n%d" % i)
        if i == 1:
            wimax.setbasestation(node)
        node.newnetif(wimax, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        if i > 2:
            wimax.addflow(nodes[-1], node, classifier, classifier)
        nodes.append(node)
    session.setupconstantmobility()
    session.thread = session.run(vis=False)
    return session
    
def main():
    ''' Main routine when running from command-line.
    '''
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 3, duration = 600, verbose = False)

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

    return wimaxsession(opt)


if __name__ == "__main__":
    session = main()
