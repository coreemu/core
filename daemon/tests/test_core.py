"""
Unit tests for testing basic CORE networks.
"""

import os
import threading

import pytest

from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import MessageFlags
from core.emulator.session import Session
from core.errors import CoreCommandError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import CoreNode
from core.nodes.network import HubNode, PtpNet, SwitchNode, WlanNode

_PATH = os.path.abspath(os.path.dirname(__file__))
_MOBILITY_FILE = os.path.join(_PATH, "mobility.scen")
_WIRED = [PtpNet, HubNode, SwitchNode]


def ping(from_node, to_node, ip_prefixes):
    address = ip_prefixes.ip4_address(to_node)
    try:
        from_node.cmd(f"ping -c 1 {address}")
        status = 0
    except CoreCommandError as e:
        status = e.returncode
    return status


class TestCore:
    @pytest.mark.parametrize("net_type", _WIRED)
    def test_wired_ping(self, session, net_type, ip_prefixes):
        """
        Test ptp node network.

        :param session: session for test
        :param core.enumerations.NodeTypes net_type: type of net node to create
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create net node
        net_node = session.add_node(net_type)

        # create nodes
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(CoreNode)

        # link nodes to net node
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, net_node.id, interface_one=interface)

        # instantiate session
        session.instantiate()

        # ping n2 from n1 and assert success
        status = ping(node_one, node_two, ip_prefixes)
        assert not status

    def test_vnode_client(self, request, session: Session, ip_prefixes: IpPrefixes):
        """
        Test vnode client methods.

        :param request: pytest request
        :param session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create ptp
        ptp_node = session.add_node(PtpNet)

        # create nodes
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(CoreNode)

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, ptp_node.id, interface_one=interface)

        # get node client for testing
        client = node_one.client

        # instantiate session
        session.instantiate()

        # check we are connected
        assert client.connected()

        # validate command
        if not request.config.getoption("mock"):
            assert client.check_cmd("echo hello") == "hello"

    def test_netif(self, session: Session, ip_prefixes: IpPrefixes):
        """
        Test netif methods.

        :param session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create ptp
        ptp_node = session.add_node(PtpNet)

        # create nodes
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(CoreNode)

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, ptp_node.id, interface_one=interface)

        # instantiate session
        session.instantiate()

        # check link data gets generated
        assert ptp_node.all_link_data(MessageFlags.ADD)

        # check common nets exist between linked nodes
        assert node_one.commonnets(node_two)
        assert node_two.commonnets(node_one)

        # check we can retrieve netif index
        assert node_one.ifname(0)
        assert node_two.ifname(0)

        # check interface parameters
        interface = node_one.netif(0)
        interface.setparam("test", 1)
        assert interface.getparam("test") == 1
        assert interface.getparams()

        # delete netif and test that if no longer exists
        node_one.delnetif(0)
        assert not node_one.netif(0)

    def test_wlan_ping(self, session: Session, ip_prefixes: IpPrefixes):
        """
        Test basic wlan network.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create wlan
        wlan_node = session.add_node(WlanNode)
        session.mobility.set_model(wlan_node, BasicRangeModel)

        # create nodes
        options = NodeOptions(model="mdr")
        options.set_position(0, 0)
        node_one = session.add_node(CoreNode, options=options)
        node_two = session.add_node(CoreNode, options=options)

        # link nodes
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, wlan_node.id, interface_one=interface)

        # instantiate session
        session.instantiate()

        # ping n2 from n1 and assert success
        status = ping(node_one, node_two, ip_prefixes)
        assert not status

    def test_mobility(self, session: Session, ip_prefixes: IpPrefixes):
        """
        Test basic wlan network.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create wlan
        wlan_node = session.add_node(WlanNode)
        session.mobility.set_model(wlan_node, BasicRangeModel)

        # create nodes
        options = NodeOptions(model="mdr")
        options.set_position(0, 0)
        node_one = session.add_node(CoreNode, options=options)
        node_two = session.add_node(CoreNode, options=options)

        # link nodes
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, wlan_node.id, interface_one=interface)

        # configure mobility script for session
        config = {
            "file": _MOBILITY_FILE,
            "refresh_ms": "50",
            "loop": "1",
            "autostart": "0.0",
            "map": "",
            "script_start": "",
            "script_pause": "",
            "script_stop": "",
        }
        session.mobility.set_model(wlan_node, Ns2ScriptedMobility, config)

        # add handler for receiving node updates
        event = threading.Event()

        def node_update(_):
            event.set()

        session.node_handlers.append(node_update)

        # instantiate session
        session.instantiate()

        # validate we receive a node message for updating its location
        assert event.wait(5)
