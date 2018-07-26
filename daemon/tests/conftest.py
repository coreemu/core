"""
Unit test fixture module.
"""

import os

import pytest
from mock.mock import MagicMock

from core.api.coreapi import CoreConfMessage
from core.api.coreapi import CoreEventMessage
from core.api.coreapi import CoreExecMessage
from core.api.coreapi import CoreLinkMessage
from core.api.coreapi import CoreNodeMessage
from core.corehandlers import CoreHandler
from core.coreserver import CoreServer
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
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
from core.misc.ipaddress import MacAddress
from core.service import ServiceManager

EMANE_SERVICES = "zebra|OSPFv3MDR|IPForward"


def node_message(objid, name, emulation_server=None, node_type=NodeTypes.DEFAULT, model=None):
    """
    Convenience method for creating a node TLV messages.

    :param int objid: node id
    :param str name: node name
    :param str emulation_server: distributed server name, if desired
    :param core.enumerations.NodeTypes node_type: node type
    :param str model: model for node
    :return: tlv message
    :rtype: core.api.coreapi.CoreNodeMessage
    """
    values = [
        (NodeTlvs.NUMBER, objid),
        (NodeTlvs.TYPE, node_type.value),
        (NodeTlvs.NAME, name),
        (NodeTlvs.EMULATION_SERVER, emulation_server),
    ]

    if model:
        values.append((NodeTlvs.MODEL, model))

    return CoreNodeMessage.create(MessageFlags.ADD.value, values)


def link_message(n1, n2, intf_one=None, address_one=None, intf_two=None, address_two=None, key=None):
    """
    Convenience method for creating link TLV messages.

    :param int n1: node one id
    :param int n2: node two id
    :param int intf_one: node one interface id
    :param core.misc.ipaddress.IpAddress address_one: node one ip4 address
    :param int intf_two: node two interface id
    :param core.misc.ipaddress.IpAddress address_two: node two ip4 address
    :param int key: tunnel key for link if needed
    :return: tlv mesage
    :rtype: core.api.coreapi.CoreLinkMessage
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
        (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        (LinkTlvs.INTERFACE1_MAC, mac_one),
        (LinkTlvs.INTERFACE2_NUMBER, intf_two),
        (LinkTlvs.INTERFACE2_IP4, address_two),
        (LinkTlvs.INTERFACE2_IP4_MASK, 24),
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
    :rtype: core.api.coreapi.CoreExecMessage
    """
    flags = MessageFlags.STRING.value | MessageFlags.TEXT.value
    return CoreExecMessage.create(flags, [
        (ExecuteTlvs.NODE, node.objid),
        (ExecuteTlvs.NUMBER, 1),
        (ExecuteTlvs.COMMAND, command)
    ])


def state_message(state):
    """
    Create a event TLV message for a new state.

    :param core.enumerations.EventTypes state: state to create message for
    :return: tlv message
    :rtype: core.api.coreapi.CoreEventMessage
    """
    return CoreEventMessage.create(0, [
        (EventTlvs.TYPE, state.value)
    ])


class CoreServerTest(object):
    def __init__(self, port=CORE_API_PORT):
        self.host = "localhost"
        self.port = port
        address = (self.host, self.port)
        self.server = CoreServer(address, CoreHandler, {
            "numthreads": 1,
            "daemonize": False,
        })

        self.distributed_server = "core2"
        self.prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
        self.session = None
        self.request_handler = None

    def setup(self, distributed_address, port):
        # validate address
        assert distributed_address, "distributed server address was not provided"

        # create session
        self.session = self.server.coreemu.create_session(1)
        self.session.master = True

        # create request handler
        request_mock = MagicMock()
        request_mock.fileno = MagicMock(return_value=1)
        self.request_handler = CoreHandler(request_mock, "", self.server)
        self.request_handler.session = self.session
        self.request_handler.add_session_handlers()
        self.session.broker.session_clients.append(self.request_handler)

        # have broker handle a configuration state change
        self.session.set_state(EventTypes.DEFINITION_STATE)
        message = state_message(EventTypes.CONFIGURATION_STATE)
        self.request_handler.handle_message(message)

        # add broker server for distributed core
        distributed = "%s:%s:%s" % (self.distributed_server, distributed_address, port)
        message = CoreConfMessage.create(0, [
            (ConfigTlvs.OBJECT, "broker"),
            (ConfigTlvs.TYPE, 0),
            (ConfigTlvs.DATA_TYPES, (10,)),
            (ConfigTlvs.VALUES, distributed)
        ])
        self.request_handler.handle_message(message)

        # set session location
        message = CoreConfMessage.create(0, [
            (ConfigTlvs.OBJECT, "location"),
            (ConfigTlvs.TYPE, 0),
            (ConfigTlvs.DATA_TYPES, (9, 9, 9, 9, 9, 9)),
            (ConfigTlvs.VALUES, "0|0| 47.5766974863|-122.125920191|0.0|150.0")
        ])
        self.request_handler.handle_message(message)

        # set services for host nodes
        message = CoreConfMessage.create(0, [
            (ConfigTlvs.SESSION, str(self.session.session_id)),
            (ConfigTlvs.OBJECT, "services"),
            (ConfigTlvs.TYPE, 0),
            (ConfigTlvs.DATA_TYPES, (10, 10, 10)),
            (ConfigTlvs.VALUES, "host|DefaultRoute|SSH")
        ])
        self.request_handler.handle_message(message)

    def shutdown(self):
        self.server.coreemu.shutdown()
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def session():
    # use coreemu and create a session
    coreemu = CoreEmu()
    session_fixture = coreemu.create_session()
    session_fixture.set_state(EventTypes.CONFIGURATION_STATE)
    assert os.path.exists(session_fixture.session_dir)

    # return created session
    yield session_fixture

    # clear session configurations
    session_fixture.location.reset()
    session_fixture.services.reset()
    session_fixture.mobility.config_reset()
    session_fixture.emane.config_reset()

    # shutdown coreemu
    coreemu.shutdown()

    # clear services, since they will be reloaded
    ServiceManager.services.clear()


@pytest.fixture(scope="module")
def ip_prefixes():
    return IpPrefixes(ip4_prefix="10.83.0.0/16")


@pytest.fixture()
def cored():
    # create and return server
    server = CoreServerTest()
    yield server

    # cleanup
    server.shutdown()

    #

    # cleanup services
    ServiceManager.services.clear()


def ping(from_node, to_node, ip_prefixes, count=3):
    address = ip_prefixes.ip4_address(to_node)
    return from_node.cmd(["ping", "-c", str(count), address])


def pytest_addoption(parser):
    parser.addoption("--distributed", help="distributed server address")


def pytest_generate_tests(metafunc):
    distributed_param = "distributed_address"
    if distributed_param in metafunc.fixturenames:
        distributed_address = metafunc.config.getoption("distributed")
        metafunc.parametrize(distributed_param, [distributed_address])
