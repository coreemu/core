#!/usr/bin/python

# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
ns3lte.py - This script demonstrates using CORE with the ns-3 LTE model.
*** Note that this script is not currently functional, see notes below. ***
- issues connecting TapBridge with LteNetDevice

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
from corens3.obj import Ns3Session, Ns3LteNet
import ns.core
import ns.mobility

def ltesession(opt):
    ''' Run a test LTE session.
    '''
    session = Ns3Session(persistent=True, duration=opt.duration)
    lte = session.addobj(cls=Ns3LteNet, name="wlan1")
    lte.setsubchannels(range(25), range(50, 100))
    if opt.verbose:
        ascii = ns.network.AsciiTraceHelper()
        stream = ascii.CreateFileStream('/tmp/ns3lte.tr')
        lte.lte.EnableAsciiAll(stream)
        #ns.core.LogComponentEnable("EnbNetDevice", ns.core.LOG_LEVEL_INFO)
        #ns.core.LogComponentEnable("UeNetDevice", ns.core.LOG_LEVEL_INFO)
        #lte.lte.EnableLogComponents()

    prefix = ipaddr.IPv4Prefix("10.0.0.0/16")
    mobb = None
    nodes = []
    for i in xrange(1, opt.numnodes + 1):
        node = session.addnode(name = "n%d" % i)
        mob = ns.mobility.ConstantPositionMobilityModel()
        mob.SetPosition( ns.core.Vector3D(10.0 * i, 0.0, 0.0) )
        if i == 1:
            lte.setnodeb(node) # first node is nodeb
            mobb = mob
        node.newnetif(lte, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        nodes.append(node)
        if i == 1:
            (tmp, ns3dev) = lte.findns3dev(node)
            lte.lte.AddMobility(ns3dev.GetPhy(), mob)
        if i > 1:
            lte.linknodeb(node, nodes[0], mob, mobb)
            
    session.thread = session.run(vis=opt.visualize)
    return session
    
def main():
    ''' Main routine when running from command-line.
    '''
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 4, duration = 600, verbose = False, visualize=False)

    parser.add_option("-d", "--duration", dest = "duration", type = int,
                      help = "number of seconds to run the simulation")
    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes")
    parser.add_option("-z", "--visualize", dest = "visualize",
                      action = "store_true", help = "enable visualizer")
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

    return ltesession(opt)

def cleanup():
    print "shutting down session"
    session.shutdown()
    print "joining simulator thread (please kill it)"
    session.thread.join()

if __name__ == "__main__":
    session = main()
