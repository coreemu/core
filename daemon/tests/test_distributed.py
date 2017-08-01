"""
Unit tests for testing CORE with distributed networks.
"""

from mock.mock import MagicMock

from core.api.coreapi import CoreConfMessage
from core.api.coreapi import CoreConfigTlv
from core.api.coreapi import CoreEventMessage
from core.api.coreapi import CoreEventTlv
from core.api.coreapi import CoreExecMessage
from core.api.coreapi import CoreExecuteTlv
from core.api.coreapi import CoreLinkMessage
from core.api.coreapi import CoreLinkTlv
from core.api.coreapi import CoreNodeMessage
from core.api.coreapi import CoreNodeTlv
from core.corehandlers import CoreRequestHandler
from core.enumerations import CORE_API_PORT
from core.enumerations import ConfigTlvs
from core.enumerations import EventTlvs
from core.enumerations import EventTypes
from core.enumerations import ExecuteTlvs
from core.enumerations import LinkTlvs
from core.enumerations import LinkTypes
from core.enumerations import MessageFlags
from core.enumerations import NodeTlvs
from core.enumerations import NodeTypes
from core.misc import ipaddress
from core.misc import structutils
from core.misc.ipaddress import MacAddress


def node_message(objid, name, emulation_server=None, node_type=NodeTypes.DEFAULT):
    """
    Convenience method for creating a node TLV messages.

    :param int objid: node id
    :param str name: node name
    :param str emulation_server: distributed server name, if desired
    :param core.enumerations.NodeTypes node_type: node type
    :return: tlv message
    :rtype: core.api.coreapi.CoreNodeMessage
    """
    tlv_data = structutils.pack_values(CoreNodeTlv, [
        (NodeTlvs.NUMBER, objid),
        (NodeTlvs.TYPE, node_type.value),
        (NodeTlvs.NAME, name),
        (NodeTlvs.MODEL, "host"),
        (NodeTlvs.EMULATION_SERVER, emulation_server),
    ])
    packed = CoreNodeMessage.pack(MessageFlags.ADD.value, tlv_data)
    header_data = packed[:CoreNodeMessage.header_len]
    return CoreNodeMessage(MessageFlags.ADD.value, header_data, tlv_data)


def link_message(n1, n2, intf_one=None, address_one=None, intf_two=None, address_two=None):
    """
    Convenience method for creating link TLV messages.

    :param int n1: node one id
    :param int n2: node two id
    :param int intf_one: node one interface id
    :param core.misc.ipaddress.IpAddress address_one: node one ip4 address
    :param int intf_two: node two interface id
    :param core.misc.ipaddress.IpAddress address_two: node two ip4 address
    :return: tlv mesage
    :rtype: core.api.coreapi.CoreLinkMessage
    """
    mac_one, mac_two = None, None
    if address_one:
        mac_one = MacAddress.random()
    if address_two:
        mac_two = MacAddress.random()

    tlv_data = structutils.pack_values(CoreLinkTlv, [
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
        (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        (LinkTlvs.INTERFACE1_MAC, mac_one),
        (LinkTlvs.INTERFACE2_NUMBER, intf_two),
        (LinkTlvs.INTERFACE2_IP4, address_two),
        (LinkTlvs.INTERFACE2_IP4_MASK, 24),
        (LinkTlvs.INTERFACE2_MAC, mac_two),
    ])
    packed = CoreLinkMessage.pack(MessageFlags.ADD.value, tlv_data)
    header_data = packed[:CoreLinkMessage.header_len]
    return CoreLinkMessage(MessageFlags.ADD.value, header_data, tlv_data)


def command_message(node, command):
    """
    Create an execute command TLV message.

    :param node: node to execute command for
    :param command: command to execute
    :return: tlv message
    :rtype: core.api.coreapi.CoreExecMessage
    """
    tlv_data = CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node.objid)
    tlv_data += CoreExecuteTlv.pack(ExecuteTlvs.NUMBER.value, 1)
    tlv_data += CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, command)
    flags = MessageFlags.STRING.value | MessageFlags.TEXT.value
    packed = CoreExecMessage.pack(flags, tlv_data)
    header_data = packed[:CoreExecMessage.header_len]
    return CoreExecMessage(flags, header_data, tlv_data)


def state_message(state):
    """
    Create a event TLV message for a new state.

    :param core.enumerations.EventTypes state: state to create message for
    :return: tlv message
    :rtype: core.api.coreapi.CoreEventMessage
    """
    tlv_data = CoreEventTlv.pack(EventTlvs.TYPE.value, state.value)
    packed = CoreEventMessage.pack(0, tlv_data)
    header_data = packed[:CoreEventMessage.header_len]
    return CoreEventMessage(0, header_data, tlv_data)


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
    def test_distributed(self, cored):
        """
        Test session broker creation.

        :param conftest.Core core: core fixture to test with
        """

        # create session
        session = cored.create_session(1)
        session.master = True

        # create request handler
        request_mock = MagicMock()
        request_mock.fileno = MagicMock(return_value=1)
        request_handler = CoreRequestHandler(request_mock, "", cored)
        request_handler.session = session
        request_handler.add_session_handlers()
        session.broker.session_clients.append(request_handler)

        # ip prefix for nodes
        prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")

        # add and setup server
        distributed_server = "core2"
        session.broker.addserver(distributed_server, "10.50.184.152", CORE_API_PORT)
        session.broker.setupserver(distributed_server)

        # have broker handle a configuration state change
        session.set_state(state=EventTypes.DEFINITION_STATE.value)
        message = state_message(EventTypes.CONFIGURATION_STATE)
        request_handler.handle_message(message)

        # add broker server for distributed core
        tlv_data = structutils.pack_values(CoreConfigTlv, [
            # (ConfigTlvs.SESSION, str(session.session_id)),
            (ConfigTlvs.OBJECT, "broker"),
            (ConfigTlvs.TYPE, 0),
            (ConfigTlvs.DATA_TYPES, (10,)),
            (ConfigTlvs.VALUES, "core2:10.50.184.152:4038"),
        ])
        packed = CoreConfMessage.pack(0, tlv_data)
        header = packed[:CoreConfMessage.header_len]
        message = CoreConfMessage(0, header, tlv_data)
        request_handler.handle_message(message)

        # set session location
        tlv_data = structutils.pack_values(CoreConfigTlv, [
            # (ConfigTlvs.SESSION, str(session.session_id)),
            (ConfigTlvs.OBJECT, "location"),
            (ConfigTlvs.TYPE, 0),
            (ConfigTlvs.DATA_TYPES, (9, 9, 9, 9, 9, 9)),
            (ConfigTlvs.VALUES, "0|0| 47.5766974863|-122.125920191|0.0|150.0"),
        ])
        packed = CoreConfMessage.pack(0, tlv_data)
        header = packed[:CoreConfMessage.header_len]
        message = CoreConfMessage(0, header, tlv_data)
        request_handler.handle_message(message)

        # set services for host nodes
        tlv_data = structutils.pack_values(CoreConfigTlv, [
            (ConfigTlvs.SESSION, str(session.session_id)),
            (ConfigTlvs.OBJECT, "services"),
            (ConfigTlvs.TYPE, 0),
            (ConfigTlvs.DATA_TYPES, (10, 10, 10)),
            (ConfigTlvs.VALUES, "host|DefaultRoute|SSH"),
        ])
        packed = CoreConfMessage.pack(0, tlv_data)
        header = packed[:CoreConfMessage.header_len]
        message = CoreConfMessage(0, header, tlv_data)
        request_handler.handle_message(message)

        # create local node
        message = node_message(1, "n1")
        request_handler.handle_message(message)

        # create distributed node and give to broker
        message = node_message(2, "n2", emulation_server=distributed_server)
        request_handler.handle_message(message)

        # create distributed switch and give to broker
        message = node_message(3, "n3", emulation_server=distributed_server, node_type=NodeTypes.SWITCH)
        request_handler.handle_message(message)

        # link message one
        ip4_address = prefix.addr(1)
        message = link_message(1, 3, intf_one=0, address_one=ip4_address)
        request_handler.handle_message(message)

        # link message two
        ip4_address = prefix.addr(2)
        message = link_message(3, 2, intf_two=0, address_two=ip4_address)
        request_handler.handle_message(message)

        # change session to instantiation state
        message = state_message(EventTypes.INSTANTIATION_STATE)
        request_handler.handle_message(message)

        # test a ping command
        node_one = session.get_object(1)
        message = command_message(node_one, "ping -c 5 %s" % ip4_address)
        request_handler.dispatch_replies = validate_response
        request_handler.handle_message(message)
