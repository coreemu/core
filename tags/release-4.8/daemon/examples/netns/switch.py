#!/usr/bin/python -i

# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.

# connect n nodes to a virtual switch/hub

import sys, datetime, optparse

from core import pycore
from core.misc import ipaddr
from core.constants import *

# node list (count from 1)
n = [None]

def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 5)

    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes")

    def usage(msg = None, err = 0):
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
    prefix = ipaddr.IPv4Prefix("10.83.0.0/16")
    session = pycore.Session(persistent=True)
    if 'server' in globals():
        server.addsession(session)
    # emulated Ethernet switch
    switch = session.addobj(cls = pycore.nodes.SwitchNode, name = "switch")
    switch.setposition(x=80,y=50)
    print "creating %d nodes with addresses from %s" % \
          (options.numnodes, prefix)
    for i in xrange(1, options.numnodes + 1):
        tmp = session.addobj(cls = pycore.nodes.CoreNode, name = "n%d" % i,
                             objid=i)
        tmp.newnetif(switch, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        tmp.cmd([SYSCTL_BIN, "net.ipv4.icmp_echo_ignore_broadcasts=0"])
        tmp.setposition(x=150*i,y=150)
        n.append(tmp)

    session.node_count = str(options.numnodes + 1)
    session.instantiate()
    # start a shell on node 1
    n[1].term("bash")

    print "elapsed time: %s" % (datetime.datetime.now() - start)

if __name__ == "__main__" or __name__ == "__builtin__":
    main()

