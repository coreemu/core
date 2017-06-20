#!/usr/bin/python
#
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# Test 3D range calculation of the BasicRangeModel by adding n nodes to a WLAN
# stacked 100 units above each other (using z-axis).
#


import datetime
import optparse
import sys
import time

from core.misc import ipaddress, nodeutils
from core.misc import nodemaps
from core.mobility import BasicRangeModel
from core.netns.nodes import WlanNode
from core.netns.vnet import EbtablesQueue
from core.netns.vnode import LxcNode
from core.session import Session

# node list - global so you can play using 'python -i'
#             e.g. >>> n[0].session.shutdown()
n = []


def test(options):
    prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
    session = Session(1, persistent=True)
    if options.enablesdt:
        # GUI default
        session.location.setrefgeo(47.57917, -122.13232, 50.0)
        session.location.refscale = 100.0
        session.options.enablesdt = True
        session.options.sdturl = options.sdturl
    wlanid = options.numnodes + 1
    net = session.add_object(
        cls=WlanNode,
        name="wlan%d" % wlanid,
        objid=wlanid
    )

    values = list(BasicRangeModel.getdefaultvalues())
    # values[0] = 5000000  # 5000km range
    net.setmodel(BasicRangeModel, values)
    for i in xrange(1, options.numnodes + 1):
        node = session.add_object(cls=LxcNode, name="n%d" % i, objid=i)
        address = "%s/%s" % (prefix.addr(i), prefix.prefixlen)
        print "setting node address: %s - %s" % (node.objid, address)
        node.newnetif(net, [address])
        # set increasing Z coordinates
        node.setposition(10, 10, 100)
        n.append(node)

    # example setting node n2 to a high altitude
    # n[1].setposition(10, 10, 2000000) # 2000km
    # session.sdt.updatenode(n[1].objid, 0, 10, 10, 2000000)

    # launches terminal for the first node
    # n[0].term("bash")
    n[0].icmd(["ping", "-c",  "5", "127.0.0.1"])

    # wait for rate seconds to allow ebtables commands to commit
    time.sleep(EbtablesQueue.rate)

    raw_input("press enter to exit")
    session.shutdown()


def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage=usagestr)

    parser.set_defaults(numnodes=2, enablesdt=False, sdturl="tcp://127.0.0.1:50000/")
    parser.add_option(
        "-n", "--numnodes", dest="numnodes", type=int,
        help="number of nodes to test; default = %s" % parser.defaults["numnodes"]
    )
    parser.add_option("-s", "--sdt", dest="enablesdt", action="store_true", help="enable SDT output")
    parser.add_option(
        "-u", "--sdturl", dest="sdturl", type="string",
        help="URL for SDT connection, default = %s" % parser.defaults["sdturl"]
    )

    def usage(msg=None, err=0):
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

    print >> sys.stderr, "elapsed time: %s" % (datetime.datetime.now() - start)


if __name__ == "__main__":
    # configure nodes to use
    node_map = nodemaps.CLASSIC_NODES
    nodeutils.set_node_map(node_map)

    main()
