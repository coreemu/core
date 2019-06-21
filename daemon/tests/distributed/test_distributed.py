"""
Unit tests for testing CORE with distributed networks.
"""
from core.emane.ieee80211abg import EmaneIeee80211abgModel

from core.api.tlv.coreapi import CoreExecMessage, CoreNodeMessage, CoreLinkMessage, CoreEventMessage, CoreConfMessage
from core.emulator.enumerations import EventTypes, NodeTlvs, LinkTlvs, LinkTypes, EventTlvs, ConfigTlvs, ConfigFlags
from core.emulator.enumerations import ExecuteTlvs
from core.emulator.enumerations import MessageFlags
from core.emulator.enumerations import NodeTypes
from core.nodes.ipaddress import IpAddress, MacAddress, Ipv4Prefix


def set_emane_model(node_id, model):
    return CoreConfMessage.create(0, [
        (ConfigTlvs.NODE, node_id),
        (ConfigTlvs.OBJECT, model),
        (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
    ])


def node_message(_id, name, emulation_server=None, node_type=NodeTypes.DEFAULT, model=None):
    """
    Convenience method for creating a node TLV messages.

    :param int _id: node id
    :param str name: node name
    :param str emulation_server: distributed server name, if desired
    :param core.emulator.enumerations.NodeTypes node_type: node type
    :param str model: model for node
    :return: tlv message
    :rtype: core.api.tlv.coreapi.CoreNodeMessage
    """
    values = [
        (NodeTlvs.NUMBER, _id),
        (NodeTlvs.TYPE, node_type.value),
        (NodeTlvs.NAME, name),
        (NodeTlvs.EMULATION_SERVER, emulation_server),
        (NodeTlvs.X_POSITION, 0),
        (NodeTlvs.Y_POSITION, 0),
    ]

    if model:
        values.append((NodeTlvs.MODEL, model))

    return CoreNodeMessage.create(MessageFlags.ADD.value, values)


def link_message(n1, n2, intf_one=None, address_one=None, intf_two=None, address_two=None, key=None, mask=24):
    """
    Convenience method for creating link TLV messages.

    :param int n1: node one id
    :param int n2: node two id
    :param int intf_one: node one interface id
    :param core.nodes.ipaddress.IpAddress address_one: node one ip4 address
    :param int intf_two: node two interface id
    :param core.nodes.ipaddress.IpAddress address_two: node two ip4 address
    :param int key: tunnel key for link if needed
    :param int mask: ip4 mask to use for link
    :return: tlv mesage
    :rtype: core.api.tlv.coreapi.CoreLinkMessage
    """
    mac_one, mac_two = None, None
    if address_one:
        mac_one = MacAddress.random()
    if address_two:
        mac_two = MacAddress.random()

    values = [
        (LinkTlvs.N1_NUMBER, n1),
        (LinkTlvs.N2_NUMBER, n2),
        (LinkTlvs.DELAY, 0),
        (LinkTlvs.BANDWIDTH, 0),
        (LinkTlvs.PER, "0"),
        (LinkTlvs.DUP, "0"),
        (LinkTlvs.JITTER, 0),
        (LinkTlvs.TYPE, LinkTypes.WIRED.value),
        (LinkTlvs.INTERFACE1_NUMBER, intf_one),
        (LinkTlvs.INTERFACE1_IP4, address_one),
        (LinkTlvs.INTERFACE1_IP4_MASK, mask),
        (LinkTlvs.INTERFACE1_MAC, mac_one),
        (LinkTlvs.INTERFACE2_NUMBER, intf_two),
        (LinkTlvs.INTERFACE2_IP4, address_two),
        (LinkTlvs.INTERFACE2_IP4_MASK, mask),
        (LinkTlvs.INTERFACE2_MAC, mac_two),
    ]

    if key:
        values.append((LinkTlvs.KEY, key))

    return CoreLinkMessage.create(MessageFlags.ADD.value, values)


def command_message(node, command):
    """
    Create an execute command TLV message.

    :param node: node to execute command for
    :param command: command to execute
    :return: tlv message
    :rtype: core.api.tlv.coreapi.CoreExecMessage
    """
    flags = MessageFlags.STRING.value | MessageFlags.TEXT.value
    return CoreExecMessage.create(flags, [
        (ExecuteTlvs.NODE, node.id),
        (ExecuteTlvs.NUMBER, 1),
        (ExecuteTlvs.COMMAND, command)
    ])


def state_message(state):
    """
    Create a event TLV message for a new state.

    :param core.enumerations.EventTypes state: state to create message for
    :return: tlv message
    :rtype: core.api.tlv.coreapi.CoreEventMessage
    """
    return CoreEventMessage.create(0, [
        (EventTlvs.TYPE, state.value)
    ])


def validate_response(replies, _):
    """
    Patch method for handling dispatch replies within a CoreRequestHandler to validate a response.

    :param tuple replies: replies to handle
    :param _: nothing
    :return: nothing
    """
    response = replies[0]
    header = response[:CoreExecMessage.header_len]
    tlv_data = response[CoreExecMessage.header_len:]
    response = CoreExecMessage(MessageFlags.TEXT, header, tlv_data)
    assert not response.get_tlv(ExecuteTlvs.STATUS.value)


class TestDistributed:
    def test_switch(self, cored, distributed_address):
        """
        Test creating a distributed switch network.

        :param core.api.tlv.coreserver.CoreServer conftest.Core cored: core daemon server to test with
        :param str distributed_address: distributed server to test against
        """
        # initialize server for testing
        cored.setup(distributed_address)

        # create local node
        message = node_message(
            _id=1,
            name="n1",
            model="host"
        )
        cored.request_handler.handle_message(message)

        # create distributed node and assign to distributed server
        message = node_message(
            _id=2,
            name="n2",
            emulation_server=cored.distributed_server,
            model="host"
        )
        cored.request_handler.handle_message(message)

        # create distributed switch and assign to distributed server
        message = node_message(
            _id=3,
            name="n3",
            node_type=NodeTypes.SWITCH
        )
        cored.request_handler.handle_message(message)

        # link message one
        ip4_address = cored.prefix.addr(1)
        message = link_message(
            n1=1,
            n2=3,
            intf_one=0,
            address_one=ip4_address
        )
        cored.request_handler.handle_message(message)

        # link message two
        ip4_address = cored.prefix.addr(2)
        message = link_message(
            n1=3,
            n2=2,
            intf_two=0,
            address_two=ip4_address
        )
        cored.request_handler.handle_message(message)

        # change session to instantiation state
        message = state_message(EventTypes.INSTANTIATION_STATE)
        cored.request_handler.handle_message(message)

        # test a ping command
        node_one = cored.session.get_node(1)
        message = command_message(node_one, "ping -c 5 %s" % ip4_address)
        cored.request_handler.dispatch_replies = validate_response
        cored.request_handler.handle_message(message)

    def test_emane(self, cored, distributed_address):
        """
        Test creating a distributed emane network.

        :param core.api.tlv.coreserver.CoreServer conftest.Core cored: core daemon server to test with
        :param str distributed_address: distributed server to test against
        """
        # initialize server for testing
        cored.setup(distributed_address)

        # configure required controlnet
        cored.session.options.set_config("controlnet", "core1:172.16.1.0/24 core2:172.16.2.0/24")

        # create local node
        message = node_message(
            _id=1,
            name="n1",
            model="mdr"
        )
        cored.request_handler.handle_message(message)

        # create distributed node and assign to distributed server
        message = node_message(
            _id=2,
            name="n2",
            emulation_server=cored.distributed_server,
            model="mdr"
        )
        cored.request_handler.handle_message(message)

        # create distributed switch and assign to distributed server
        message = node_message(
            _id=3,
            name="n3",
            node_type=NodeTypes.EMANE
        )
        cored.request_handler.handle_message(message)

        # set emane model
        message = set_emane_model(3, EmaneIeee80211abgModel.name)
        cored.request_handler.handle_message(message)

        # link message one
        ip4_address = cored.prefix.addr(1)
        message = link_message(
            n1=1,
            n2=3,
            intf_one=0,
            address_one=ip4_address,
            mask=32
        )
        cored.request_handler.handle_message(message)

        # link message two
        ip4_address = cored.prefix.addr(2)
        message = link_message(
            n1=2,
            n2=3,
            intf_one=0,
            address_one=ip4_address,
            mask=32
        )
        cored.request_handler.handle_message(message)

        # change session to instantiation state
        message = state_message(EventTypes.INSTANTIATION_STATE)
        cored.request_handler.handle_message(message)

        # test a ping command
        node_one = cored.session.get_node(1)
        message = command_message(node_one, "ping -c 5 %s" % ip4_address)
        cored.request_handler.dispatch_replies = validate_response
        cored.request_handler.handle_message(message)

    def test_prouter(self, cored, distributed_address):
        """
        Test creating a distributed prouter node.

        :param core.coreserver.CoreServer Core cored: core daemon server to test with
        :param str distributed_address: distributed server to test against
        """
        # initialize server for testing
        cored.setup(distributed_address)

        # create local node
        message = node_message(
            _id=1,
            name="n1",
            model="host"
        )
        cored.request_handler.handle_message(message)

        # create distributed node and assign to distributed server
        message = node_message(
            _id=2,
            name="n2",
            emulation_server=cored.distributed_server,
            node_type=NodeTypes.PHYSICAL,
            model="prouter"
        )
        cored.request_handler.handle_message(message)

        # create distributed switch and assign to distributed server
        message = node_message(
            _id=3,
            name="n3",
            node_type=NodeTypes.SWITCH
        )
        cored.request_handler.handle_message(message)

        # link message one
        ip4_address = cored.prefix.addr(1)
        message = link_message(
            n1=1,
            n2=3,
            intf_one=0,
            address_one=ip4_address
        )
        cored.request_handler.handle_message(message)

        # link message two
        ip4_address = cored.prefix.addr(2)
        message = link_message(
            n1=3,
            n2=2,
            intf_two=0,
            address_two=ip4_address
        )
        cored.request_handler.handle_message(message)

        # change session to instantiation state
        message = state_message(EventTypes.INSTANTIATION_STATE)
        cored.request_handler.handle_message(message)

        # test a ping command
        node_one = cored.session.get_node(1)
        message = command_message(node_one, "ping -c 5 %s" % ip4_address)
        cored.request_handler.dispatch_replies = validate_response
        cored.request_handler.handle_message(message)
        cored.request_handler.handle_message(message)

    def test_tunnel(self, cored, distributed_address):
        """
        Test session broker creation.

        :param core.coreserver.CoreServer Core cored: core daemon server to test with
        :param str distributed_address: distributed server to test against
        """
        # initialize server for testing
        cored.setup(distributed_address)

        # create local node
        message = node_message(
            _id=1,
            name="n1",
            model="host"
        )
        cored.request_handler.handle_message(message)

        # create distributed node and assign to distributed server
        message = node_message(
            _id=2,
            name=distributed_address,
            emulation_server=cored.distributed_server,
            node_type=NodeTypes.TUNNEL
        )
        cored.request_handler.handle_message(message)

        # link message one
        ip4_address = cored.prefix.addr(1)
        address_two = IpAddress.from_string(distributed_address)
        message = link_message(
            n1=1,
            n2=2,
            intf_one=0,
            address_one=ip4_address,
            intf_two=0,
            address_two=address_two,
            key=1
        )
        cored.request_handler.handle_message(message)

        # change session to instantiation state
        message = state_message(EventTypes.INSTANTIATION_STATE)
        cored.request_handler.handle_message(message)
