"""
Unit tests for testing basic CORE networks.
"""

import os
import stat
import threading
from xml.etree import ElementTree

import pytest
from mock import MagicMock

from core.emulator.emudata import NodeOptions
from core.enumerations import MessageFlags, NodeTypes
from core.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.netns.vnodeclient import VnodeClient
from core.service import ServiceManager

_PATH = os.path.abspath(os.path.dirname(__file__))
_SERVICES_PATH = os.path.join(_PATH, "myservices")
_MOBILITY_FILE = os.path.join(_PATH, "mobility.scen")
_XML_VERSIONS = [
    "0.0",
    "1.0"
]
_WIRED = [
    NodeTypes.PEER_TO_PEER,
    NodeTypes.HUB,
    NodeTypes.SWITCH
]


def createclients(sessiondir, clientcls=VnodeClient, cmdchnlfilterfunc=None):
    """
    Create clients

    :param str sessiondir: session directory to create clients
    :param class clientcls: class to create clients from
    :param func cmdchnlfilterfunc: command channel filter function
    :return: list of created clients
    :rtype: list
    """
    direntries = map(lambda x: os.path.join(sessiondir, x), os.listdir(sessiondir))
    cmdchnls = filter(lambda x: stat.S_ISSOCK(os.stat(x).st_mode), direntries)
    if cmdchnlfilterfunc:
        cmdchnls = filter(cmdchnlfilterfunc, cmdchnls)
    cmdchnls.sort()
    return map(lambda x: clientcls(os.path.basename(x), x), cmdchnls)


def ping(from_node, to_node, ip_prefixes):
    address = ip_prefixes.ip4_address(to_node)
    return from_node.cmd(["ping", "-c", "3", address])


class TestCore:
    def test_import_service(self):
        """
        Test importing a custom service.

        :param conftest.Core core: core fixture to test with
        """
        ServiceManager.add_services(_SERVICES_PATH)
        assert ServiceManager.get("MyService")
        assert ServiceManager.get("MyService2")

    @pytest.mark.parametrize("net_type", _WIRED)
    def test_wired_ping(self, session, net_type, ip_prefixes):
        """
        Test ptp node network.

        :param session: session for test
        :param core.enumerations.NodeTypes net_type: type of net node to create
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create net node
        net_node = session.add_node(_type=net_type)

        # create nodes
        node_one = session.add_node()
        node_two = session.add_node()

        # link nodes to net node
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, net_node.objid, interface_one=interface)

        # instantiate session
        session.instantiate()

        # ping n2 from n1 and assert success
        status = ping(node_one, node_two, ip_prefixes)
        assert not status

    @pytest.mark.parametrize("version", _XML_VERSIONS)
    def test_xml(self, session, tmpdir, version, ip_prefixes):
        """
        Test xml client methods.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param str version: xml version to write and parse
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create ptp
        ptp_node = session.add_node(_type=NodeTypes.PEER_TO_PEER)

        # create nodes
        node_one = session.add_node()
        node_two = session.add_node()

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, ptp_node.objid, interface_one=interface)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        n1_id = node_one.objid
        n2_id = node_two.objid

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(file_path, version)

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # verify nodes have been removed from session
        with pytest.raises(KeyError):
            assert not session.get_object(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_object(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_object(n1_id)
        assert session.get_object(n2_id)

    def test_vnode_client(self, session, ip_prefixes):
        """
        Test vnode client methods.

        :param session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create ptp
        ptp_node = session.add_node(_type=NodeTypes.PEER_TO_PEER)

        # create nodes
        node_one = session.add_node()
        node_two = session.add_node()

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, ptp_node.objid, interface_one=interface)

        # get node client for testing
        client = node_one.client

        # instantiate session
        session.instantiate()

        # check we are connected
        assert client.connected()

        # check various command using vcmd module
        command = ["ls"]
        assert not client.cmd(command)
        status, output = client.cmd_output(command)
        assert not status
        p, stdin, stdout, stderr = client.popen(command)
        assert not p.status()
        assert not client.icmd(command)
        assert not client.redircmd(MagicMock(), MagicMock(), MagicMock(), command)
        assert not client.shcmd(command[0])

        # check various command using command line
        assert not client.cmd(command)
        status, output = client.cmd_output(command)
        assert not status
        p, stdin, stdout, stderr = client.popen(command)
        assert not p.wait()
        assert not client.icmd(command)
        assert not client.shcmd(command[0])

        # check module methods
        assert createclients(session.session_dir)

        # check convenience methods for interface information
        assert client.getaddr("eth0")
        assert client.netifstats()

    def test_netif(self, session, ip_prefixes):
        """
        Test netif methods.

        :param session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create ptp
        ptp_node = session.add_node(_type=NodeTypes.PEER_TO_PEER)

        # create nodes
        node_one = session.add_node()
        node_two = session.add_node()

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, ptp_node.objid, interface_one=interface)

        # instantiate session
        session.instantiate()

        # check link data gets generated
        assert ptp_node.all_link_data(MessageFlags.ADD.value)

        # check common nets exist between linked nodes
        assert node_one.commonnets(node_two)
        assert node_two.commonnets(node_one)

        # check we can retrieve netif index
        assert node_one.getifindex(0)
        assert node_two.getifindex(0)

        # check interface parameters
        interface = node_one.netif(0)
        interface.setparam("test", 1)
        assert interface.getparam("test") == 1
        assert interface.getparams()

        # delete netif and test that if no longer exists
        node_one.delnetif(0)
        assert not node_one.netif(0)

    def test_wlan_ping(self, session, ip_prefixes):
        """
        Test basic wlan network.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create wlan
        wlan_node = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        wlan_node.setmodel(BasicRangeModel)

        # create nodes
        node_options = NodeOptions()
        node_options.set_position(0, 0)
        node_one = session.create_wireless_node(node_options=node_options)
        node_two = session.create_wireless_node(node_options=node_options)

        # link nodes
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, wlan_node.objid, interface_one=interface)

        # link nodes in wlan
        session.wireless_link_all(wlan_node, [node_one, node_two])

        # instantiate session
        session.instantiate()

        # ping n2 from n1 and assert success
        status = ping(node_one, node_two, ip_prefixes)
        assert not status

    def test_mobility(self, session, ip_prefixes):
        """
        Test basic wlan network.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create wlan
        wlan_node = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        wlan_node.setmodel(BasicRangeModel)

        # create nodes
        node_options = NodeOptions()
        node_options.set_position(0, 0)
        node_one = session.create_wireless_node(node_options=node_options)
        node_two = session.create_wireless_node(node_options=node_options)

        # link nodes
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, wlan_node.objid, interface_one=interface)

        # link nodes in wlan
        session.wireless_link_all(wlan_node, [node_one, node_two])

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
        wlan_node.setmodel(Ns2ScriptedMobility, config)

        # add handler for receiving node updates
        event = threading.Event()

        def node_update(_):
            event.set()

        session.node_handlers.append(node_update)

        # instantiate session
        session.instantiate()

        # validate we receive a node message for updating its location
        assert event.wait(5)
