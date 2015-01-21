#!/usr/bin/python

# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.

# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

import optparse, sys, os, datetime

from core import pycore
from core.misc import ipaddr
from core.misc.utils import mutecall

try:
    mutecall(["iperf", "-v"])
except OSError:
    sys.stderr.write("ERROR: running iperf failed\n")
    sys.exit(1)

def test(numnodes, testsec):
    # node list
    n = []
    # IP subnet
    prefix = ipaddr.IPv4Prefix("10.83.0.0/16")
    session = pycore.Session()
    # emulated network
    net = session.addobj(cls = pycore.nodes.WlanNode)
    for i in xrange(1, numnodes + 1):
        tmp = session.addobj(cls = pycore.nodes.LxcNode, objid= "%d" % i, name = "n%d" % i)
        tmp.newnetif(net, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        n.append(tmp)
    net.link(n[0].netif(0), n[-1].netif(0))
    n[0].cmd(["iperf", "-s", "-D"])
    n[-1].icmd(["iperf", "-t", str(int(testsec)), "-c", str(prefix.addr(1))])
    n[0].cmd(["killall", "-9", "iperf"])
    session.shutdown()

def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)

    parser.set_defaults(minnodes = 2)
    parser.add_option("-m", "--minnodes", dest = "minnodes", type = int,
                      help = "min number of nodes to test; default = %s" %
                      parser.defaults["minnodes"])

    parser.set_defaults(maxnodes = 2)
    parser.add_option("-n", "--maxnodes", dest = "maxnodes", type = int,
                      help = "max number of nodes to test; default = %s" %
                      parser.defaults["maxnodes"])

    parser.set_defaults(testsec = 10)
    parser.add_option("-t", "--testsec", dest = "testsec", type = int,
                      help = "test time in seconds; default = %s" %
                      parser.defaults["testsec"])

    parser.set_defaults(nodestep = 1)
    parser.add_option("-s", "--nodestep", dest = "nodestep", type = int,
                      help = "number of nodes step size; default = %s" %
                      parser.defaults["nodestep"])

    def usage(msg = None, err = 0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    # parse command line options
    (options, args) = parser.parse_args()

    if options.minnodes < 2:
        usage("invalid min number of nodes: %s" % options.minnodes)
    if options.maxnodes < options.minnodes:
        usage("invalid max number of nodes: %s" % options.maxnodes)
    if options.testsec < 1:
        usage("invalid test time: %s" % options.testsec)
    if options.nodestep < 1:
        usage("invalid node step: %s" % options.nodestep)

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()

    for i in xrange(options.minnodes, options.maxnodes + 1, options.nodestep):
        print >> sys.stderr, "%s node test:" % i
        test(i, options.testsec)
        print >> sys.stderr, ""

    print >> sys.stderr, \
          "elapsed time: %s" % (datetime.datetime.now() - start)

if __name__ == "__main__":
    main()
