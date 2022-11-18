"""
Unit tests for testing basic CORE networks.
"""

import threading
from pathlib import Path
from typing import List, Type

import pytest

from core.emulator.data import IpPrefixes
from core.emulator.session import Session
from core.errors import CoreCommandError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import CoreNode, NodeBase
from core.nodes.network import HubNode, PtpNet, SwitchNode, WlanNode

_PATH: Path = Path(__file__).resolve().parent
_MOBILITY_FILE: Path = _PATH / "mobility.scen"
_WIRED: List = [PtpNet, HubNode, SwitchNode]


def ping(from_node: CoreNode, to_node: CoreNode, ip_prefixes: IpPrefixes):
    address = ip_prefixes.ip4_address(to_node.id)
    try:
        from_node.cmd(f"ping -c 1 {address}")
        status = 0
    except CoreCommandError as e:
        status = e.returncode
    return status


class TestCore:
    @pytest.mark.parametrize("net_type", _WIRED)
    def test_wired_ping(
        self, session: Session, net_type: Type[NodeBase], ip_prefixes: IpPrefixes
    ):
        """
        Test ptp node network.

        :param session: session for test
        :param core.enumerations.NodeTypes net_type: type of net node to create
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create net node
        net_node = session.add_node(net_type)

        # create nodes
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)

        # link nodes to net node
        for node in [node1, node2]:
            iface_data = ip_prefixes.create_iface(node)
            session.add_link(node.id, net_node.id, iface1_data=iface_data)

        # instantiate session
        session.instantiate()

        # ping node2 from node1 and assert success
        status = ping(node1, node2, ip_prefixes)
        assert not status

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
        options = CoreNode.create_options()
        options.model = "mdr"
        node1 = session.add_node(CoreNode, options=options)
        node2 = session.add_node(CoreNode, options=options)

        # link nodes
        for node in [node1, node2]:
            iface_id = ip_prefixes.create_iface(node)
            session.add_link(node.id, wlan_node.id, iface1_data=iface_id)

        # instantiate session
        session.instantiate()

        # ping node2 from node1 and assert success
        status = ping(node1, node2, ip_prefixes)
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
        options = CoreNode.create_options()
        options.model = "mdr"
        node1 = session.add_node(CoreNode, options=options)
        node2 = session.add_node(CoreNode, options=options)

        # link nodes
        for node in [node1, node2]:
            iface_id = ip_prefixes.create_iface(node)
            session.add_link(node.id, wlan_node.id, iface1_data=iface_id)

        # configure mobility script for session
        config = {
            "file": str(_MOBILITY_FILE),
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
