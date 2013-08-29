#!/usr/bin/python
#
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# Test 3D range calculation of the BasicRangeModel by adding n nodes to a WLAN
# stacked 100 units above each other (using z-axis).
#


import optparse, sys, os, datetime, time

from core import pycore
from core.misc import ipaddr
from core.misc.utils import mutecall
from core.mobility import BasicRangeModel
from core.netns.vnet import EbtablesQueue

def test(numnodes):
    # node list
    n = []
    prefix = ipaddr.IPv4Prefix("10.83.0.0/16")
    session = pycore.Session(persistent = True)
    wlanid = numnodes + 1
    net = session.addobj(cls = pycore.nodes.WlanNode, name = "wlan%d" % wlanid,
                         objid = wlanid, verbose = True)
    net.setmodel(BasicRangeModel, BasicRangeModel.getdefaultvalues())
    for i in xrange(1, numnodes + 1):
        tmp = session.addobj(cls = pycore.nodes.LxcNode, name = "n%d" % i,
                             objid = i)
        tmp.newnetif(net, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        # set increasing Z coordinates
        tmp.setposition(10, 10, 100*i)
        n.append(tmp)

    n[0].term("bash")
    # wait for rate seconds to allow ebtables commands to commit
    time.sleep(EbtablesQueue.rate)
    #session.shutdown()

def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)

    parser.set_defaults(numnodes = 2)
    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes to test; default = %s" %
                      parser.defaults["numnodes"])

    def usage(msg = None, err = 0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    # parse command line options
    (options, args) = parser.parse_args()

    if options.numnodes < 2:
        usage("invalid number of nodes: %s" % options.numnodes)

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()

    test(options.numnodes)

    print >> sys.stderr, \
          "elapsed time: %s" % (datetime.datetime.now() - start)

if __name__ == "__main__":
    main()
