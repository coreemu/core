"""
Unit tests for testing CORE with distributed networks.
"""

import conftest

from core.api.coreapi import CoreExecMessage
from core.enumerations import EventTypes
from core.enumerations import ExecuteTlvs
from core.enumerations import MessageFlags
from core.enumerations import NodeTypes


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
    def test_distributed(self, cored, distributed_address):
        """
        Test session broker creation.

        :param core.coreserver.CoreServer conftest.Core cored: core daemon server to test with
        :param str distributed_address: distributed server to test against
        """

        assert distributed_address, "distributed server address was not provided"

        # initialize server for testing
        cored.setup(distributed_address)

        # create local node
        message = conftest.node_message(1, "n1", model="host")
        cored.request_handler.handle_message(message)

        # create distributed node and assign to distributed server
        message = conftest.node_message(
            2,
            "n2",
            emulation_server=cored.distributed_server,
            model="host"
        )
        cored.request_handler.handle_message(message)

        # create distributed switch and assign to distributed server
        message = conftest.node_message(
            3,
            "n3",
            emulation_server=cored.distributed_server,
            node_type=NodeTypes.SWITCH
        )
        cored.request_handler.handle_message(message)

        # link message one
        ip4_address = cored.prefix.addr(1)
        message = conftest.link_message(1, 3, intf_one=0, address_one=ip4_address)
        cored.request_handler.handle_message(message)

        # link message two
        ip4_address = cored.prefix.addr(2)
        message = conftest.link_message(3, 2, intf_two=0, address_two=ip4_address)
        cored.request_handler.handle_message(message)

        # change session to instantiation state
        message = conftest.state_message(EventTypes.INSTANTIATION_STATE)
        cored.request_handler.handle_message(message)

        # test a ping command
        node_one = cored.session.get_object(1)
        message = conftest.command_message(node_one, "ping -c 5 %s" % ip4_address)
        cored.request_handler.dispatch_replies = validate_response
        cored.request_handler.handle_message(message)

    def test_prouter(self, cored, distributed_address):
        """
        Test session broker creation.

        :param core.coreserver.CoreServer conftest.Core cored: core daemon server to test with
        :param str distributed_address: distributed server to test against
        """

        assert distributed_address, "distributed server address was not provided"

        # initialize server for testing
        cored.setup(distributed_address)

        # create local node
        message = conftest.node_message(1, "n1", model="host")
        cored.request_handler.handle_message(message)

        # create distributed node and assign to distributed server
        message = conftest.node_message(
            2,
            "n2",
            emulation_server=cored.distributed_server,
            node_type=NodeTypes.PHYSICAL,
            model="prouter"
        )
        cored.request_handler.handle_message(message)

        # create distributed switch and assign to distributed server
        message = conftest.node_message(
            3,
            "n3",
            node_type=NodeTypes.SWITCH
        )
        cored.request_handler.handle_message(message)

        # link message one
        ip4_address = cored.prefix.addr(1)
        message = conftest.link_message(1, 3, intf_one=0, address_one=ip4_address)
        cored.request_handler.handle_message(message)

        # link message two
        ip4_address = cored.prefix.addr(2)
        message = conftest.link_message(3, 2, intf_two=0, address_two=ip4_address)
        cored.request_handler.handle_message(message)

        # change session to instantiation state
        message = conftest.state_message(EventTypes.INSTANTIATION_STATE)
        cored.request_handler.handle_message(message)

        # test a ping command
        node_one = cored.session.get_object(1)
        message = conftest.command_message(node_one, "ping -c 5 %s" % ip4_address)
        cored.request_handler.dispatch_replies = validate_response
        cored.request_handler.handle_message(message)
        cored.request_handler.handle_message(message)
