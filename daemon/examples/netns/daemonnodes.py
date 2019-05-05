#!/usr/bin/python -i

# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.

# A distributed example where CORE API messaging is used to create a session
# on a daemon server. The daemon server defaults to 127.0.0.1:4038
# to target a remote machine specify "-d <ip address>" parameter, it needs to be
# running the daemon with listenaddr=0.0.0.0 in the core.conf file.
# This script creates no nodes locally and therefore can be run as an
# unprivileged user.

import datetime
import optparse
import sys
from builtins import range

import core.nodes.base
import core.nodes.network
from core.api.tlv import coreapi, dataconversion
from core.api.tlv.coreapi import CoreExecuteTlv
from core.emulator.enumerations import CORE_API_PORT
from core.emulator.enumerations import EventTlvs
from core.emulator.enumerations import EventTypes
from core.emulator.enumerations import ExecuteTlvs
from core.emulator.enumerations import LinkTlvs
from core.emulator.enumerations import LinkTypes
from core.emulator.enumerations import MessageFlags
from core.emulator.enumerations import MessageTypes
from core.emulator.session import Session
from core.nodes import ipaddress

# declare classes for use with Broker

# node list (count from 1)
n = [None]
exec_num = 1


def cmd(node, exec_cmd):
    """
    :param node: The node the command should be issued too
    :param exec_cmd: A string with the command to be run
    :return: Returns the result of the command
    """
    global exec_num

    # Set up the command api message
    tlvdata = CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node.id)
    tlvdata += CoreExecuteTlv.pack(ExecuteTlvs.NUMBER.value, exec_num)
    tlvdata += CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, exec_cmd)
    msg = coreapi.CoreExecMessage.pack(MessageFlags.STRING.value | MessageFlags.TEXT.value, tlvdata)
    node.session.broker.handlerawmsg(msg)
    exec_num += 1

    # Now wait for the response
    server = node.session.broker.servers["localhost"]
    server.sock.settimeout(50.0)

    # receive messages until we get our execute response
    result = None
    while True:
        msghdr = server.sock.recv(coreapi.CoreMessage.header_len)
        msgtype, msgflags, msglen = coreapi.CoreMessage.unpack_header(msghdr)
        msgdata = server.sock.recv(msglen)

        # If we get the right response return the results
        print("received response message: %s" % MessageTypes(msgtype))
        if msgtype == MessageTypes.EXECUTE.value:
            msg = coreapi.CoreExecMessage(msgflags, msghdr, msgdata)
            result = msg.get_tlv(ExecuteTlvs.RESULT.value)
            break

    return result


def main():
    usagestr = "usage: %prog [-n] number of nodes [-d] daemon address"
    parser = optparse.OptionParser(usage=usagestr)
    parser.set_defaults(numnodes=5, daemon="127.0.0.1:" + str(CORE_API_PORT))

    parser.add_option("-n", "--numnodes", dest="numnodes", type=int,
                      help="number of nodes")
    parser.add_option("-d", "--daemon-server", dest="daemon", type=str,
                      help="daemon server IP address")

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
    if not options.daemon:
        usage("daemon server IP address (-d) is a required argument")

    for a in args:
        sys.stderr.write("ignoring command line argument: %s\n" % a)

    start = datetime.datetime.now()

    prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
    session = Session(1)
    if "server" in globals():
        server.addsession(session)

    # distributed setup - connect to daemon server
    daemonport = options.daemon.split(":")
    daemonip = daemonport[0]

    # Localhost is already set in the session but we change it to be the remote daemon
    # This stops the remote daemon trying to build a tunnel back which would fail
    daemon = "localhost"
    if len(daemonport) > 1:
        port = int(daemonport[1])
    else:
        port = CORE_API_PORT
    print("connecting to daemon at %s:%d" % (daemon, port))
    session.broker.addserver(daemon, daemonip, port)

    # Set the local session id to match the port.
    # Not necessary but seems neater.
    session.broker.setupserver(daemon)

    # We do not want the recvloop running as we will deal ourselves
    session.broker.dorecvloop = False

    # Change to configuration state on both machines
    session.set_state(EventTypes.CONFIGURATION_STATE)
    tlvdata = coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, EventTypes.CONFIGURATION_STATE.value)
    session.broker.handlerawmsg(coreapi.CoreEventMessage.pack(0, tlvdata))

    flags = MessageFlags.ADD.value
    switch = core.nodes.network.SwitchNode(session=session, name="switch", start=False)
    switch.setposition(x=80, y=50)
    switch.server = daemon
    switch_data = switch.data(flags)
    switch_message = dataconversion.convert_node(switch_data)
    session.broker.handlerawmsg(switch_message)

    number_of_nodes = options.numnodes

    print("creating %d remote nodes with addresses from %s" % (options.numnodes, prefix))

    # create remote nodes via API
    for i in range(1, number_of_nodes + 1):
        node = core.nodes.base.CoreNode(session=session, _id=i, name="n%d" % i, start=False)
        node.setposition(x=150 * i, y=150)
        node.server = daemon
        node_data = node.data(flags)
        node_message = dataconversion.convert_node(node_data)
        session.broker.handlerawmsg(node_message)
        n.append(node)

    # create remote links via API
    for i in range(1, number_of_nodes + 1):
        tlvdata = coreapi.CoreLinkTlv.pack(LinkTlvs.N1_NUMBER.value, switch.id)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.N2_NUMBER.value, i)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.TYPE.value, LinkTypes.WIRED.value)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_NUMBER.value, 0)
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_IP4.value, prefix.addr(i))
        tlvdata += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_IP4_MASK.value, prefix.prefixlen)
        msg = coreapi.CoreLinkMessage.pack(flags, tlvdata)
        session.broker.handlerawmsg(msg)

    # We change the daemon to Instantiation state
    # We do not change the local session as it would try and build a tunnel and fail
    tlvdata = coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, EventTypes.INSTANTIATION_STATE.value)
    msg = coreapi.CoreEventMessage.pack(0, tlvdata)
    session.broker.handlerawmsg(msg)

    # Get the ip or last node and ping it from the first
    print("Pinging from the first to the last node")
    pingip = cmd(n[-1], "ip -4 -o addr show dev eth0").split()[3].split("/")[0]
    print(cmd(n[1], "ping -c 5 " + pingip))
    print("elapsed time: %s" % (datetime.datetime.now() - start))
    print("To stop this session, use the core-cleanup script on the remote daemon server.")
    raw_input("press enter to exit")


if __name__ == "__main__" or __name__ == "__builtin__":
    main()
