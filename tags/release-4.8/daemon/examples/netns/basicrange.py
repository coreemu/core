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

# node list - global so you can play using 'python -i'
#             e.g. >>> n[0].session.shutdown()
n = []

def test(options):
    prefix = ipaddr.IPv4Prefix("10.83.0.0/16")
    session = pycore.Session(persistent = True)
    if options.enablesdt:
        session.location.setrefgeo(47.57917,-122.13232,50.0) # GUI default
        session.location.refscale = 100.0
        session.options.enablesdt = True
        session.options.sdturl = options.sdturl
    wlanid = options.numnodes + 1
    net = session.addobj(cls = pycore.nodes.WlanNode, name = "wlan%d" % wlanid,
                         objid = wlanid, verbose = True)
    values = list(BasicRangeModel.getdefaultvalues())
    #values[0] = 5000000  # 5000km range
    net.setmodel(BasicRangeModel, values)
    for i in xrange(1, options.numnodes + 1):
        tmp = session.addobj(cls = pycore.nodes.LxcNode, name = "n%d" % i,
                             objid = i)
        tmp.newnetif(net, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        # set increasing Z coordinates
        tmp.setposition(10, 10, 100*i)
        n.append(tmp)

    # example setting node n2 to a high altitude
    #n[1].setposition(10, 10, 2000000) # 2000km
    #session.sdt.updatenode(n[1].objid, 0, 10, 10, 2000000)

    n[0].term("bash")
    # wait for rate seconds to allow ebtables commands to commit
    time.sleep(EbtablesQueue.rate)
    #session.shutdown()

def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)

    parser.set_defaults(numnodes = 2, enablesdt = False,
                        sdturl = "tcp://127.0.0.1:50000/")
    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes to test; default = %s" %
                      parser.defaults["numnodes"])
    parser.add_option("-s", "--sdt", dest = "enablesdt", action = "store_true",
                      help = "enable SDT output")
    parser.add_option("-u", "--sdturl", dest = "sdturl", type = "string",
                      help = "URL for SDT connection, default = %s" % \
                      parser.defaults["sdturl"])

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

    test(options)

    print >> sys.stderr, \
          "elapsed time: %s" % (datetime.datetime.now() - start)

if __name__ == "__main__":
    main()
