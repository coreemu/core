"""
Unit tests for testing with a CORE switch.
"""

import threading

from core.api import coreapi, dataconversion
from core.api.coreapi import CoreExecuteTlv
from core.enumerations import CORE_API_PORT
from core.enumerations import EventTlvs
from core.enumerations import EventTypes
from core.enumerations import ExecuteTlvs
from core.enumerations import LinkTlvs
from core.enumerations import LinkTypes
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.misc import ipaddress
from core.netns.nodes import SwitchNode


def command_message(node, command):
    """
    Create an execute command TLV message.

    :param node: node to execute command for
    :param command: command to execute
    :return: packed execute message
    """
    tlv_data = CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node.objid)
    tlv_data += CoreExecuteTlv.pack(ExecuteTlvs.NUMBER.value, 1)
    tlv_data += CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, command)
    return coreapi.CoreExecMessage.pack(MessageFlags.STRING.value | MessageFlags.TEXT.value, tlv_data)


def state_message(state):
    """
    Create a event TLV message for a new state.

    :param core.enumerations.EventTypes state: state to create message for
    :return: packed event message
    """
    tlv_data = coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, state.value)
    return coreapi.CoreEventMessage.pack(0, tlv_data)


def switch_link_message(switch, node, address, prefix_len):
    """
    Create a link TLV message for node to a switch, with the provided address and prefix length.

    :param switch: switch for link
    :param node: node for link
    :param address: address node on link
    :param prefix_len: prefix length of address
    :return: packed link message
    """
    tlv_data = coreapi.CoreLinkTlv.pack(LinkTlvs.N1_NUMBER.value, switch.objid)
    tlv_data += coreapi.CoreLinkTlv.pack(LinkTlvs.N2_NUMBER.value, node.objid)
    tlv_data += coreapi.CoreLinkTlv.pack(LinkTlvs.TYPE.value, LinkTypes.WIRED.value)
    tlv_data += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_NUMBER.value, 0)
    tlv_data += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_IP4.value, address)
    tlv_data += coreapi.CoreLinkTlv.pack(LinkTlvs.INTERFACE2_IP4_MASK.value, prefix_len)
    return coreapi.CoreLinkMessage.pack(MessageFlags.ADD.value, tlv_data)


def run_cmd(node, exec_cmd):
    """
    Convenience method for sending commands to a node using the legacy API.

    :param node: The node the command should be issued too
    :param exec_cmd: A string with the command to be run
    :return: Returns the result of the command
    """
    # Set up the command api message
    # tlv_data = CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node.objid)
    # tlv_data += CoreExecuteTlv.pack(ExecuteTlvs.NUMBER.value, 1)
    # tlv_data += CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, exec_cmd)
    # message = coreapi.CoreExecMessage.pack(MessageFlags.STRING.value | MessageFlags.TEXT.value, tlv_data)
    message = command_message(node, exec_cmd)
    node.session.broker.handlerawmsg(message)

    # Now wait for the response
    server = node.session.broker.servers["localhost"]
    server.sock.settimeout(50.0)

    # receive messages until we get our execute response
    result = None
    status = False
    while True:
        message_header = server.sock.recv(coreapi.CoreMessage.header_len)
        message_type, message_flags, message_length = coreapi.CoreMessage.unpack_header(message_header)
        message_data = server.sock.recv(message_length)

        # If we get the right response return the results
        print "received response message: %s" % MessageTypes(message_type)
        if message_type == MessageTypes.EXECUTE.value:
            message = coreapi.CoreExecMessage(message_flags, message_header, message_data)
            result = message.get_tlv(ExecuteTlvs.RESULT.value)
            status = message.get_tlv(ExecuteTlvs.STATUS.value)
            break

    return result, status


class TestGui:
    def test_broker(self, core, cored):
        """
        Test session broker creation.

        :param conftest.Core core: core fixture to test with
        """

        # set core daemon to run in the background
        thread = threading.Thread(target=cored.server.serve_forever)
        thread.daemon = True
        thread.start()

        # ip prefix for nodes
        prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
        daemon = "localhost"

        # add server
        core.session.broker.addserver(daemon, "127.0.0.1", CORE_API_PORT)

        # setup server
        core.session.broker.setupserver(daemon)

        # do not want the recvloop running as we will deal ourselves
        core.session.broker.dorecvloop = False

        # have broker handle a configuration state change
        core.session.set_state(EventTypes.CONFIGURATION_STATE.value)
        event_message = state_message(EventTypes.CONFIGURATION_STATE)
        core.session.broker.handlerawmsg(event_message)

        # create a switch node
        switch = core.session.add_object(cls=SwitchNode, name="switch", start=False)
        switch.setposition(x=80, y=50)
        switch.server = daemon

        # retrieve switch data representation, create a switch message for broker to handle
        switch_data = switch.data(MessageFlags.ADD.value)
        switch_message = dataconversion.convert_node(switch_data)
        core.session.broker.handlerawmsg(switch_message)

        # create node one
        core.create_node("n1")
        node_one = core.get_node("n1")
        node_one.server = daemon

        # create node two
        core.create_node("n2")
        node_two = core.get_node("n2")
        node_two.server = daemon

        # create node messages for the broker to handle
        for node in [node_one, node_two]:
            node_data = node.data(MessageFlags.ADD.value)
            node_message = dataconversion.convert_node(node_data)
            core.session.broker.handlerawmsg(node_message)

        # create links to switch from nodes for broker to handle
        for index, node in enumerate([node_one, node_two], start=1):
            ip4_address = prefix.addr(index)
            link_message = switch_link_message(switch, node, ip4_address, prefix.prefixlen)
            core.session.broker.handlerawmsg(link_message)

        # change session to instantiation state
        event_message = state_message(EventTypes.INSTANTIATION_STATE)
        core.session.broker.handlerawmsg(event_message)

        # Get the ip or last node and ping it from the first
        output, status = run_cmd(node_one, "ip -4 -o addr show dev eth0")
        pingip = output.split()[3].split("/")[0]
        output, status = run_cmd(node_two, "ping -c 5 " + pingip)
        assert not status
