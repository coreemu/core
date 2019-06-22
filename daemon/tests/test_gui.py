"""
Unit tests for testing with a CORE switch.
"""

import pytest

from core.api.tlv import coreapi
from core.api.tlv.coreapi import CoreExecuteTlv
from core.emulator.enumerations import EventTlvs
from core.emulator.enumerations import ExecuteTlvs
from core.emulator.enumerations import LinkTlvs
from core.emulator.enumerations import LinkTypes
from core.emulator.enumerations import MessageFlags
from core.emulator.enumerations import MessageTypes
from core.emulator.enumerations import NodeTypes, NodeTlvs
from core.nodes.ipaddress import Ipv4Prefix


def command_message(node, command):
    """
    Create an execute command TLV message.

    :param node: node to execute command for
    :param command: command to execute
    :return: packed execute message
    """
    tlv_data = CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node.id)
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
    tlv_data = coreapi.CoreLinkTlv.pack(LinkTlvs.N1_NUMBER.value, switch.id)
    tlv_data += coreapi.CoreLinkTlv.pack(LinkTlvs.N2_NUMBER.value, node.id)
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
    # tlv_data = CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node.id)
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
        print("received response message: %s" % message_type)
        if message_type == MessageTypes.EXECUTE.value:
            message = coreapi.CoreExecMessage(message_flags, message_header, message_data)
            result = message.get_tlv(ExecuteTlvs.RESULT.value)
            status = message.get_tlv(ExecuteTlvs.STATUS.value)
            break

    return result, status


class TestGui:
    @pytest.mark.parametrize("node_type, model", [
        (NodeTypes.DEFAULT, "PC"),
        (NodeTypes.EMANE, None),
        (NodeTypes.HUB, None),
        (NodeTypes.SWITCH, None),
        (NodeTypes.WIRELESS_LAN, None),
        (NodeTypes.TUNNEL, None),
        (NodeTypes.RJ45, None),
    ])
    def test_node_add(self, coreserver, node_type, model):
        node_id = 1
        message = coreapi.CoreNodeMessage.create(MessageFlags.ADD.value, [
            (NodeTlvs.NUMBER, node_id),
            (NodeTlvs.TYPE, node_type.value),
            (NodeTlvs.NAME, "n1"),
            (NodeTlvs.X_POSITION, 0),
            (NodeTlvs.Y_POSITION, 0),
            (NodeTlvs.MODEL, model),
        ])

        coreserver.request_handler.handle_message(message)

        assert coreserver.session.get_node(node_id) is not None

    def test_node_update(self, coreserver):
        node_id = 1
        coreserver.session.add_node(_id=node_id)
        x = 50
        y = 100
        message = coreapi.CoreNodeMessage.create(0, [
            (NodeTlvs.NUMBER, node_id),
            (NodeTlvs.X_POSITION, x),
            (NodeTlvs.Y_POSITION, y),
        ])

        coreserver.request_handler.handle_message(message)

        node = coreserver.session.get_node(node_id)
        assert node is not None
        assert node.position.x == x
        assert node.position.y == y

    def test_node_delete(self, coreserver):
        node_id = 1
        coreserver.session.add_node(_id=node_id)
        message = coreapi.CoreNodeMessage.create(MessageFlags.DELETE.value, [
            (NodeTlvs.NUMBER, node_id),
        ])

        coreserver.request_handler.handle_message(message)

        with pytest.raises(KeyError):
            coreserver.session.get_node(node_id)

    def test_link_add(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        coreserver.session.add_link(node_one, switch, interface_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])

        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

    def test_link_update(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1
        link = all_links[0]
        assert link.bandwidth is None

        bandwidth = 50000
        message = coreapi.CoreLinkMessage.create(0, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.BANDWIDTH, bandwidth),
        ])
        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1
        link = all_links[0]
        assert link.bandwidth == bandwidth

    def test_link_delete_node_to_node(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        node_two = 2
        coreserver.session.add_node(_id=node_two)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        interface_two = ip_prefix.addr(node_two)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, node_two),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
            (LinkTlvs.INTERFACE2_IP4, interface_two),
            (LinkTlvs.INTERFACE2_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        all_links = []
        for node_id in coreserver.session.nodes:
            node = coreserver.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(MessageFlags.DELETE.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, node_two),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE2_NUMBER, 0),
        ])
        coreserver.request_handler.handle_message(message)

        all_links = []
        for node_id in coreserver.session.nodes:
            node = coreserver.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 0

    def test_link_delete_node_to_net(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(MessageFlags.DELETE.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
        ])
        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 0

    def test_link_delete_net_to_node(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(MessageFlags.DELETE.value, [
            (LinkTlvs.N1_NUMBER, switch),
            (LinkTlvs.N2_NUMBER, node_one),
            (LinkTlvs.INTERFACE2_NUMBER, 0),
        ])
        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 0
