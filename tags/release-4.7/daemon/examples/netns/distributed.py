#!/usr/bin/python -i

# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.

# A distributed example where CORE API messaging is used to create a session
# distributed across the local server and one slave server. The slave server
# must be specified using the '-s <ip address>' parameter, and needs to be
# running the daemon with listenaddr=0.0.0.0 in the core.conf file.
#

import sys, datetime, optparse, time

from core import pycore
from core.misc import ipaddr
from core.constants import *
from core.api import coreapi

# declare classes for use with Broker
coreapi.add_node_class("CORE_NODE_DEF", 
                       coreapi.CORE_NODE_DEF, pycore.nodes.CoreNode)
coreapi.add_node_class("CORE_NODE_SWITCH",
                       coreapi.CORE_NODE_SWITCH, pycore.nodes.SwitchNode)

# node list (count from 1)
n = [None]

def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 5, slave = None)

    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes")
    parser.add_option("-s", "--slave-server", dest = "slave", type = str,
                      help = "slave server IP address")

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
    if not options.slave:
        usage("slave server IP address (-s) is a required argument")

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()

    prefix = ipaddr.IPv4Prefix("10.83.0.0/16")
    session = pycore.Session(persistent=True)
    if 'server' in globals():
        server.addsession(session)

    # distributed setup - connect to slave server
    slaveport = options.slave.split(':')
    slave = slaveport[0]
    if len(slaveport) > 1:
        port = slaveport[1]
    else:
        port = coreapi.CORE_API_PORT
    print "connecting to slave at %s:%d" % (slave, port)
    session.broker.addserver(slave, slave, port)
    session.broker.setupserver(slave)
    session.setstate(coreapi.CORE_EVENT_CONFIGURATION_STATE)
    tlvdata = coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                        coreapi.CORE_EVENT_CONFIGURATION_STATE)
    session.broker.handlerawmsg(coreapi.CoreEventMessage.pack(0, tlvdata))

    switch = session.addobj(cls = pycore.nodes.SwitchNode, name = "switch")
    switch.setposition(x=80,y=50)
    num_local = options.numnodes / 2
    num_remote = options.numnodes / 2 +  options.numnodes % 2
    print "creating %d (%d local / %d remote) nodes with addresses from %s" % \
          (options.numnodes, num_local, num_remote, prefix)
    for i in xrange(1, num_local + 1):
        tmp = session.addobj(cls = pycore.nodes.CoreNode, name = "n%d" % i,
                             objid=i)
        tmp.newnetif(switch, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        tmp.cmd([SYSCTL_BIN, "net.ipv4.icmp_echo_ignore_broadcasts=0"])
        tmp.setposition(x=150*i,y=150)
        n.append(tmp)

    flags = coreapi.CORE_API_ADD_FLAG
    session.broker.handlerawmsg(switch.tonodemsg(flags=flags))

    # create remote nodes via API
    for i in xrange(num_local + 1, options.numnodes + 1):
        tmp = pycore.nodes.CoreNode(session = session, objid = i,
                                    name = "n%d" % i, start=False)
        tmp.setposition(x=150*i,y=150)
        tmp.server = slave
        session.broker.handlerawmsg(tmp.tonodemsg(flags=flags))

    # create remote links via API
    for i in xrange(num_local + 1, options.numnodes + 1):
        tlvdata = coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N1NUMBER,
                                           switch.objid)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N2NUMBER, i)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_TYPE,
                                            coreapi.CORE_LINK_WIRED)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2NUM, 0)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2IP4,
                                            prefix.addr(i))
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2IP4MASK,
                                            prefix.prefixlen)
        msg = coreapi.CoreLinkMessage.pack(flags, tlvdata)
        session.broker.handlerawmsg(msg)

    session.instantiate()
    tlvdata = coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                        coreapi.CORE_EVENT_INSTANTIATION_STATE)
    msg = coreapi.CoreEventMessage.pack(0, tlvdata)
    session.broker.handlerawmsg(msg)

    # start a shell on node 1
    n[1].term("bash")

    # TODO: access to remote nodes is currently limited in this script

    print "elapsed time: %s" % (datetime.datetime.now() - start)

    print "To stop this session, use the 'core-cleanup' script on this server"
    print "and on the remote slave server."

if __name__ == "__main__" or __name__ == "__builtin__":
    main()

