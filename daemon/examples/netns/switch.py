#!/usr/bin/python -i

# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.

# connect n nodes to a virtual switch/hub

import datetime
import optparse
import sys

from core import constants
from core.misc import ipaddress, nodeutils, nodemaps
from core.netns import nodes

# node list (count from 1)
from core.session import Session

n = [None]


def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage=usagestr)
    parser.set_defaults(numnodes=5)

    parser.add_option("-n", "--numnodes", dest="numnodes", type=int,
                      help="number of nodes")

    def usage(msg=None, err=0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    # parse command line options
    (options, args) = parser.parse_args()

    if options.numnodes < 1:
        usage("invalid number of nodes: %s" % options.numnodes)

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()

    # IP subnet
    prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
    session = Session(1, persistent=True)
    if 'server' in globals():
        server.addsession(session)
    # emulated Ethernet switch
    switch = session.add_object(cls=nodes.SwitchNode, name="switch")
    switch.setposition(x=80, y=50)
    print "creating %d nodes with addresses from %s" % (options.numnodes, prefix)
    for i in xrange(1, options.numnodes + 1):
        tmp = session.add_object(cls=nodes.CoreNode, name="n%d" % i, objid=i)
        tmp.newnetif(switch, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        tmp.cmd([constants.SYSCTL_BIN, "net.ipv4.icmp_echo_ignore_broadcasts=0"])
        tmp.setposition(x=150 * i, y=150)
        n.append(tmp)

    session.node_count = str(options.numnodes + 1)
    session.instantiate()
    print "elapsed time: %s" % (datetime.datetime.now() - start)

    # start a shell on node 1
    n[1].term("bash")

    raw_input("press enter to exit")
    session.shutdown()


if __name__ == "__main__" or __name__ == "__builtin__":
    # configure nodes to use
    node_map = nodemaps.CLASSIC_NODES
    nodeutils.set_node_map(node_map)

    main()
