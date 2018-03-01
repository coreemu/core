"""
Unit test fixture module.
"""

import os

import pytest
from mock.mock import MagicMock

from core import services
from core.api.coreapi import CoreConfMessage
from core.api.coreapi import CoreEventMessage
from core.api.coreapi import CoreExecMessage
from core.api.coreapi import CoreLinkMessage
from core.api.coreapi import CoreNodeMessage
from core.corehandlers import CoreRequestHandler
from core.coreserver import CoreServer
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
from core.netns import nodes
from core.session import Session

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


class Core(object):
    def __init__(self, session, ip_prefix):
        self.session = session
        self.ip_prefix = ip_prefix
        self.current_ip = 1
        self.nodes = {}
        self.node_ips = {}

    def create_node(self, name, cls=nodes.CoreNode, objid=None, position=None, services=None, model="host"):
        node = self.session.add_object(cls=cls, name=name, objid=objid)
        node.type = model
        if position:
            node.setposition(*position)
        if services:
            self.session.services.addservicestonode(node, model, services)
        self.nodes[name] = node

    def add_interface(self, network, name):
        node_ip = self.ip_prefix.addr(self.current_ip)
        self.current_ip += 1
        self.node_ips[name] = node_ip
        node = self.nodes[name]
        interface_id = node.newnetif(network, ["%s/%s" % (node_ip, self.ip_prefix.prefixlen)])
        return node.netif(interface_id)

    def get_node(self, name):
        """
        Retrieve node from current session.

        :param str name: name of node to retrieve
        :return: core node
        :rtype: core.netns.nodes.CoreNode
        """
        return self.nodes[name]

    def get_ip(self, name):
        return self.node_ips[name]

    def link(self, network, from_interface, to_interface):
        network.link(from_interface, to_interface)

    def configure_link(self, network, interface_one, interface_two, values, unidirectional=False):
        network.linkconfig(netif=interface_one, netif2=interface_two, **values)

        if not unidirectional:
            network.linkconfig(netif=interface_two, netif2=interface_one, **values)

    def ping(self, from_name, to_name):
        from_node = self.nodes[from_name]
        to_ip = str(self.get_ip(to_name))
        return from_node.cmd(["ping", "-c", "3", to_ip])

    def ping_output(self, from_name, to_name):
        from_node = self.nodes[from_name]
        to_ip = str(self.get_ip(to_name))
        _, output = from_node.check_cmd(["ping", "-i", "0.05", "-c", "3", to_ip])
        return output

    def iperf(self, from_name, to_name):
        from_node = self.nodes[from_name]
        to_node = self.nodes[to_name]
        to_ip = str(self.get_ip(to_name))

        # run iperf server, run client, kill iperf server
        vcmd, stdin, stdout, stderr = to_node.client.popen(["iperf", "-s", "-u", "-y", "C"])
        from_node.cmd(["iperf", "-u", "-t", "5", "-c", to_ip])
        to_node.cmd(["killall", "-9", "iperf"])

        return stdout.read().strip()

    def assert_nodes(self):
        for node in self.nodes.itervalues():
            assert os.path.exists(node.nodedir)

    def create_link_network(self):
        # create switch
        ptp_node = self.session.add_object(cls=nodes.PtpNet)

        # create nodes
        self.create_node("n1")
        self.create_node("n2")

        # add interfaces
        interface_one = self.add_interface(ptp_node, "n1")
        interface_two = self.add_interface(ptp_node, "n2")

        # instantiate session
        self.session.instantiate()

        # assert node directories created
        self.assert_nodes()

        return ptp_node, interface_one, interface_two

    def set_emane_model(self, emane_node, emane_model):
        # set the emane model
        values = emane_model.getdefaultvalues()
        self.session.emane.setconfig(emane_node.objid, emane_model.name, values)


class CoreServerTest(object):
    def __init__(self):
        address = ("localhost", CORE_API_PORT)
        self.server = CoreServer(address, CoreRequestHandler, {
            "numthreads": 1,
            "daemonize": False,
        })

        self.distributed_server = "core2"
        self.prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
        self.session = None
        self.request_handler = None

    def setup(self, distributed_address):
        # validate address
        assert distributed_address, "distributed server address was not provided"

        # create session
        self.session = self.server.create_session(1)
        self.session.master = True

        # create request handler
        request_mock = MagicMock()
        request_mock.fileno = MagicMock(return_value=1)
        self.request_handler = CoreRequestHandler(request_mock, "", self.server)
        self.request_handler.session = self.session
        self.request_handler.add_session_handlers()
        self.session.broker.session_clients.append(self.request_handler)

        # have broker handle a configuration state change
        self.session.set_state(state=EventTypes.DEFINITION_STATE.value)
        message = state_message(EventTypes.CONFIGURATION_STATE)
        self.request_handler.handle_message(message)

        # add broker server for distributed core
        distributed = "%s:%s:%s" % (self.distributed_server, distributed_address, CORE_API_PORT)
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
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def session():
    # load default services
    services.load()

    # create and return session
    session_fixture = Session(1, persistent=True)
    session_fixture.master = True
    assert os.path.exists(session_fixture.session_dir)

    # set location
    # session_fixture.master = True
    session_fixture.location.setrefgeo(47.57917, -122.13232, 2.00000)
    session_fixture.location.refscale = 150.0

    # return session fixture
    yield session_fixture

    # cleanup
    print "shutting down session"
    session_fixture.shutdown()
    assert not os.path.exists(session_fixture.session_dir)


@pytest.fixture(scope="module")
def ip_prefix():
    return ipaddress.Ipv4Prefix("10.83.0.0/16")


@pytest.fixture()
def core(session, ip_prefix):
    return Core(session, ip_prefix)


@pytest.fixture()
def cored():
    # load default services
    services.load()

    # create and return server
    server = CoreServerTest()
    yield server

    # cleanup
    server.shutdown()


def pytest_addoption(parser):
    parser.addoption("--distributed", help="distributed server address")


def pytest_generate_tests(metafunc):
    distributed_param = "distributed_address"
    if distributed_param in metafunc.fixturenames:
        distributed_address = metafunc.config.getoption("distributed")
        metafunc.parametrize(distributed_param, [distributed_address])
