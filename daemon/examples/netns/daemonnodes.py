#!/usr/bin/python -i

# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.

# A distributed example where CORE API messaging is used to create a session
# on a daemon server. The daemon server defaults to 127.0.0.1:4038
# to target a remote machine specify '-d <ip address>' parameter, it needs to be
# running the daemon with listenaddr=0.0.0.0 in the core.conf file.
# This script creates no nodes locally and therefore can be run as an
# unprivileged user.

import sys, datetime, optparse, time

from core import pycore
from core.misc import ipaddr
from core.constants import *
from core.api import coreapi

# declare classes for use with Broker
import select

coreapi.add_node_class("CORE_NODE_DEF",
                       coreapi.CORE_NODE_DEF, pycore.nodes.CoreNode)
coreapi.add_node_class("CORE_NODE_SWITCH",
                       coreapi.CORE_NODE_SWITCH, pycore.nodes.SwitchNode)

# node list (count from 1)
n = [None]
exec_num = 1

def cmd(node, exec_cmd):
    '''
    :param node: The node the command should be issued too
    :param exec_cmd: A string with the command to be run
    :return: Returns the result of the command
    '''
    global exec_num

    # Set up the command api message
    tlvdata = coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_NODE, node.objid)
    tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_NUM, exec_num)
    tlvdata += coreapi.CoreExecTlv.pack(coreapi.CORE_TLV_EXEC_CMD, exec_cmd)
    msg = coreapi.CoreExecMessage.pack(coreapi.CORE_API_STR_FLAG | coreapi.CORE_API_TXT_FLAG, tlvdata)
    node.session.broker.handlerawmsg(msg)
    exec_num += 1

    # Now wait for the response
    (h, p, sock) = node.session.broker.servers['localhost']
    sock.settimeout(50.0)
    msghdr = sock.recv(coreapi.CoreMessage.hdrsiz)
    msgtype, msgflags, msglen = coreapi.CoreMessage.unpackhdr(msghdr)
    msgdata = sock.recv(msglen)

    # If we get the right response return the results
    if msgtype == coreapi.CORE_API_EXEC_MSG:
        msg = coreapi.CoreExecMessage(msgflags, msghdr, msgdata)
        return msg.gettlv(coreapi.CORE_TLV_EXEC_RESULT)
    else:
        return None

def main():
    usagestr = "usage: %prog [-n] number of nodes [-d] daemon address"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 5, daemon = '127.0.0.1:'+str(coreapi.CORE_API_PORT))

    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes")
    parser.add_option("-d", "--daemon-server", dest = "daemon", type = str,
                      help = "daemon server IP address")

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
    if not options.daemon:
        usage("daemon server IP address (-d) is a required argument")

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()

    prefix = ipaddr.IPv4Prefix("10.83.0.0/16")
    session = pycore.Session(persistent=True)
    if 'server' in globals():
        server.addsession(session)

    # distributed setup - connect to daemon server
    daemonport = options.daemon.split(':')
    daemonip = daemonport[0]

    # Localhost is already set in the session but we change it to be the remote daemon
    # This stops the remote daemon trying to build a tunnel back which would fail
    daemon = 'localhost'
    if len(daemonport) > 1:
        port = int(daemonport[1])
    else:
        port = coreapi.CORE_API_PORT
    print "connecting to daemon at %s:%d" % (daemon, port)
    session.broker.addserver(daemon, daemonip, port)

    # Set the local session id to match the port.
    # Not necessary but seems neater.
    session.sessionid = session.broker.getserver('localhost')[2].getsockname()[1]
    session.broker.setupserver(daemon)

    # We do not want the recvloop running as we will deal ourselves
    session.broker.dorecvloop = False

    # Change to configuration state on both machines
    session.setstate(coreapi.CORE_EVENT_CONFIGURATION_STATE)
    tlvdata = coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                        coreapi.CORE_EVENT_CONFIGURATION_STATE)
    session.broker.handlerawmsg(coreapi.CoreEventMessage.pack(0, tlvdata))

    flags = coreapi.CORE_API_ADD_FLAG
    switch = pycore.nodes.SwitchNode(session = session, name='switch', start=False)
    switch.setposition(x=80,y=50)
    switch.server = daemon
    session.broker.handlerawmsg(switch.tonodemsg(flags=flags))

    numberOfNodes = options.numnodes

    print "creating %d remote nodes with addresses from %s" % \
          (options.numnodes, prefix)

    # create remote nodes via API
    for i in xrange(1, numberOfNodes + 1):
        tmp = pycore.nodes.CoreNode(session = session, objid = i,
                                    name = "n%d" % i, start=False)
        tmp.setposition(x=150*i,y=150)
        tmp.server = daemon
        session.broker.handlerawmsg(tmp.tonodemsg(flags=flags))
        n.append(tmp)

    # create remote links via API
    for i in xrange(1, numberOfNodes + 1):
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

    # We change the daemon to Instantiation state
    # We do not change the local session as it would try and build a tunnel and fail
    tlvdata = coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                    coreapi.CORE_EVENT_INSTANTIATION_STATE)
    msg = coreapi.CoreEventMessage.pack(0, tlvdata)
    session.broker.handlerawmsg(msg)

    # Get the ip or last node and ping it from the first
    print 'Pinging from the first to the last node'
    pingip = cmd(n[-1], 'ip -4 -o addr show dev eth0').split()[3].split('/')[0]
    print cmd(n[1], 'ping -c 5 ' + pingip)

    print "elapsed time: %s" % (datetime.datetime.now() - start)

    print "To stop this session, use the 'core-cleanup' script on the remote daemon server."

if __name__ == "__main__" or __name__ == "__builtin__":
    main()

