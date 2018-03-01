#!/usr/bin/python -i

# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.

# A distributed example where CORE API messaging is used to create a session
# distributed across the local server and one slave server. The slave server
# must be specified using the '-s <ip address>' parameter, and needs to be
# running the daemon with listenaddr=0.0.0.0 in the core.conf file.
#

import datetime
import optparse
import sys

from core import constants
from core.api import coreapi, dataconversion
from core.enumerations import CORE_API_PORT, EventTypes, EventTlvs, LinkTlvs, LinkTypes, MessageFlags
from core.misc import ipaddress
from core.netns import nodes
from core.session import Session

# node list (count from 1)
n = [None]


def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage=usagestr)
    parser.set_defaults(numnodes=5, slave=None)

    parser.add_option("-n", "--numnodes", dest="numnodes", type=int,
                      help="number of nodes")
    parser.add_option("-s", "--slave-server", dest="slave", type=str,
                      help="slave server IP address")

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
    if not options.slave:
        usage("slave server IP address (-s) is a required argument")

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()

    prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
    session = Session(1, persistent=True)
    if 'server' in globals():
        server.addsession(session)

    # distributed setup - connect to slave server
    slaveport = options.slave.split(':')
    slave = slaveport[0]
    if len(slaveport) > 1:
        port = int(slaveport[1])
    else:
        port = CORE_API_PORT
    print "connecting to slave at %s:%d" % (slave, port)
    session.broker.addserver(slave, slave, port)
    session.broker.setupserver(slave)
    session.set_state(EventTypes.CONFIGURATION_STATE.value)
    tlvdata = coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, EventTypes.CONFIGURATION_STATE.value)
    session.broker.handlerawmsg(coreapi.CoreEventMessage.pack(0, tlvdata))

    switch = session.add_object(cls=nodes.SwitchNode, name="switch")
    switch.setposition(x=80, y=50)
    num_local = options.numnodes / 2
    num_remote = options.numnodes / 2 + options.numnodes % 2
    print "creating %d (%d local / %d remote) nodes with addresses from %s" % \
          (options.numnodes, num_local, num_remote, prefix)
    for i in xrange(1, num_local + 1):
        node = session.add_object(cls=nodes.CoreNode, name="n%d" % i, objid=i)
        node.newnetif(switch, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
        node.cmd([constants.SYSCTL_BIN, "net.ipv4.icmp_echo_ignore_broadcasts=0"])
        node.setposition(x=150 * i, y=150)
        n.append(node)

    flags = MessageFlags.ADD.value
    session.broker.handlerawmsg(switch.tonodemsg(flags=flags))

    # create remote nodes via API
    for i in xrange(num_local + 1, options.numnodes + 1):
        node = nodes.CoreNode(session=session, objid=i, name="n%d" % i, start=False)
        node.setposition(x=150 * i, y=150)
        node.server = slave
        n.append(node)
        node_data = node.data(flags)
        node_message = dataconversion.convert_node(node_data)
        session.broker.handlerawmsg(node_message)

    # create remote links via API
    for i in xrange(num_local + 1, options.numnodes + 1):
        tlvdata = coreapi.CoreLinkTlv.pack(LinkTlvs.N1_NUMBER.value, switch.objid)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.N2_NUMBER.value, i)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.TYPE.value, LinkTypes.WIRED.value)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_NUMBER.value, 0)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_IP4.value, prefix.addr(i))
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_IP4_MASK.value, prefix.prefixlen)
        msg = coreapi.CoreLinkMessage.pack(flags, tlvdata)
        session.broker.handlerawmsg(msg)

    session.instantiate()
    tlvdata = coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, EventTypes.INSTANTIATION_STATE.value)
    msg = coreapi.CoreEventMessage.pack(0, tlvdata)
    session.broker.handlerawmsg(msg)

    # start a shell on node 1
    n[1].client.term("bash")

    print "elapsed time: %s" % (datetime.datetime.now() - start)
    print "To stop this session, use the 'core-cleanup' script on this server"
    print "and on the remote slave server."


if __name__ == "__main__" or __name__ == "__builtin__":
    main()
