"""
Unit tests for testing basic CORE networks.
"""

import os
import threading
import time

import pytest

from xml.etree import ElementTree

from mock import MagicMock

from conftest import EMANE_SERVICES
from core.data import ConfigData
from core.enumerations import MessageFlags
from core.mobility import BasicRangeModel
from core.netns import nodes
from core.netns import vnodeclient
from core.phys.pnodes import PhysicalNode
from core.xml import xmlsession

_PATH = os.path.abspath(os.path.dirname(__file__))
_MOBILITY_FILE = os.path.join(_PATH, "mobility.scen")
_XML_VERSIONS = ["0.0", "1.0"]
_NODE_CLASSES = [nodes.PtpNet, nodes.HubNode, nodes.SwitchNode]


class TestCore:
    @pytest.mark.parametrize("cls", _NODE_CLASSES)
    def test_nodes(self, core, cls):
        """
        Test ptp node network.

        :param conftest.Core core: core fixture to test with
        :param cls: node classes that work within a simple network
        """

        # create ptp
        network_node = core.session.add_object(cls=cls)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        core.add_interface(network_node, "n1")
        core.add_interface(network_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # ping n2 from n1 and assert success
        status = core.ping("n1", "n2")
        assert not status

    @pytest.mark.parametrize("version", _XML_VERSIONS)
    def test_xml(self, core, tmpdir, version):
        """
        Test xml client methods.

        :param conftest.Core core: core fixture to test with
        :param str version: xml version to write and parse
        """

        # create ptp
        ptp_node = core.session.add_object(cls=nodes.PtpNet)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        core.add_interface(ptp_node, "n1")
        core.add_interface(ptp_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # get ids for nodes
        n1_id = core.get_node("n1").objid
        n2_id = core.get_node("n2").objid

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        xmlsession.save_session_xml(core.session, file_path, version)

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        core.session.shutdown()

        # verify nodes have been removed from session
        with pytest.raises(KeyError):
            assert not core.session.get_object_by_name(n1_id)
        with pytest.raises(KeyError):
            assert not core.session.get_object(n2_id)

        # load saved xml
        xmlsession.open_session_xml(core.session, file_path, start=True)

        # verify nodes have been recreated
        assert core.session.get_object(n1_id)
        assert core.session.get_object(n2_id)

    def test_vnode_client(self, core):
        """
        Test vnode client methods.

        :param conftest.Core core: core fixture to test with
        """

        # create ptp
        ptp_node = core.session.add_object(cls=nodes.PtpNet)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        core.add_interface(ptp_node, "n1")
        core.add_interface(ptp_node, "n2")

        # get node client for testing
        n1 = core.get_node("n1")
        client = n1.vnodeclient

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # check we are connected
        assert client.connected()

        # check various command using vcmd module
        command = ["ls"]
        assert not client.cmd(command)
        status, output = client.cmdresult(command)
        assert not status
        p, stdin, stdout, stderr = client.popen(command)
        assert not p.status()
        assert not client.icmd(command)
        assert not client.redircmd(MagicMock(), MagicMock(), MagicMock(), command)
        assert not client.shcmd(command[0])

        # check various command using command line
        vnodeclient.USE_VCMD_MODULE = False
        assert not client.cmd(command)
        status, output = client.cmdresult(command)
        assert not status
        p, stdin, stdout, stderr = client.popen(command)
        assert not p.wait()
        assert not client.icmd(command)
        assert not client.shcmd(command[0])

        # check module methods
        assert vnodeclient.createclients(core.session.session_dir)

        # check convenience methods for interface information
        assert client.getaddr("eth0")
        assert client.netifstats()

    def test_netif(self, core):
        """
        Test netif methods.

        :param conftest.Core core: core fixture to test with
        """

        # create ptp
        ptp_node = core.session.add_object(cls=nodes.PtpNet)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        n1_interface = core.add_interface(ptp_node, "n1")
        n2_interface = core.add_interface(ptp_node, "n2")

        # get nodes
        n1 = core.get_node("n1")
        n2 = core.get_node("n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # check link data gets generated
        assert ptp_node.all_link_data(MessageFlags.ADD.value)

        # check common nets exist between linked nodes
        assert n1.commonnets(n2)
        assert n2.commonnets(n1)

        # check we can retrieve netif index
        assert n1.getifindex(n1_interface) == 0
        assert n2.getifindex(n2_interface) == 0

        # check interface parameters
        n1_interface.setparam("test", 1)
        assert n1_interface.getparam("test") == 1
        assert n1_interface.getparams()

        # delete netif and test that if no longer exists
        n1.delnetif(0)
        assert not n1.netif(0)

    def test_physical(self, core):
        """
        Test physical node network.

        :param conftest.Core core: core fixture to test with
        """

        # create switch node
        switch_node = core.session.add_object(cls=nodes.SwitchNode)

        # create a physical node
        core.create_node(cls=PhysicalNode, name="p1")

        # mock method that will not work
        physical_node = core.get_node("p1")
        physical_node.newnetif = MagicMock(return_value=0)

        # create regular node
        core.create_node("n1")

        # add interface
        core.add_interface(switch_node, "n1")
        core.add_interface(switch_node, "p1")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

    def test_wlan_basic_range_good(self, core):
        """
        Test basic wlan network.

        :param conftest.Core core: core fixture to test with
        """

        # create wlan
        wlan_node = core.session.add_object(cls=nodes.WlanNode)
        values = BasicRangeModel.getdefaultvalues()
        wlan_node.setmodel(BasicRangeModel, values)

        # create nodes
        core.create_node("n1", position=(0, 0), services=EMANE_SERVICES, model="mdr")
        core.create_node("n2", position=(0, 0), services=EMANE_SERVICES, model="mdr")

        # add interfaces
        interface_one = core.add_interface(wlan_node, "n1")
        interface_two = core.add_interface(wlan_node, "n2")

        # link nodes in wlan
        core.link(wlan_node, interface_one, interface_two)

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # ping n2 from n1 and assert success
        status = core.ping("n1", "n2")
        assert not status

    def test_wlan_basic_range_bad(self, core):
        """
        Test basic wlan network with leveraging basic range model.

        :param conftest.Core core: core fixture to test with
        """

        # create wlan
        wlan_node = core.session.add_object(cls=nodes.WlanNode)
        values = BasicRangeModel.getdefaultvalues()
        wlan_node.setmodel(BasicRangeModel, values)

        # create nodes
        core.create_node("n1", position=(0, 0), services=EMANE_SERVICES, model="mdr")
        core.create_node("n2", position=(0, 0), services=EMANE_SERVICES, model="mdr")

        # add interfaces
        interface_one = core.add_interface(wlan_node, "n1")
        interface_two = core.add_interface(wlan_node, "n2")

        # link nodes in wlan
        core.link(wlan_node, interface_one, interface_two)

        # move nodes out of range, default range check is 275
        core.get_node("n1").setposition(0, 0)
        core.get_node("n2").setposition(500, 500)

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # ping n2 from n1 and assert failure        )
        time.sleep(3)
        status = core.ping("n1", "n2")
        assert status

    def test_mobility(self, core):
        """
        Test basic wlan network.

        :param conftest.Core core: core fixture to test with
        """

        # create wlan
        wlan_node = core.session.add_object(cls=nodes.WlanNode)
        values = BasicRangeModel.getdefaultvalues()
        wlan_node.setmodel(BasicRangeModel, values)

        # create nodes
        core.create_node("n1", objid=1, position=(0, 0), services=EMANE_SERVICES, model="mdr")
        core.create_node("n2", objid=2, position=(0, 0), services=EMANE_SERVICES, model="mdr")

        # add interfaces
        interface_one = core.add_interface(wlan_node, "n1")
        interface_two = core.add_interface(wlan_node, "n2")

        # link nodes in wlan
        core.link(wlan_node, interface_one, interface_two)

        # configure mobility script for session
        config = ConfigData(
            node=wlan_node.objid,
            object="ns2script",
            type=0,
            data_types=(10, 3, 11, 10, 10, 10, 10, 10, 0),
            data_values="file=%s|refresh_ms=50|loop=1|autostart=0.0|"
                        "map=|script_start=|script_pause=|script_stop=" % _MOBILITY_FILE
        )
        core.session.config_object(config)

        # add handler for receiving node updates
        event = threading.Event()

        def node_update(_):
            event.set()

        core.session.node_handlers.append(node_update)

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # validate we receive a node message for updating its location
        assert event.wait(5)

    def test_link_bandwidth(self, core):
        """
        Test ptp node network with modifying link bandwidth.

        :param conftest.Core core: core fixture to test with
        """

        # create link network
        ptp_node, interface_one, interface_two = core.create_link_network()

        # output csv index
        bandwidth_index = 8

        # run iperf, validate normal bandwidth
        stdout = core.iperf("n1", "n2")
        assert stdout
        value = int(stdout.split(',')[bandwidth_index])
        assert 900000 <= value <= 1100000

        # change bandwidth in bits per second
        bandwidth = 500000
        core.configure_link(ptp_node, interface_one, interface_two, {
            "bw": bandwidth
        })

        # run iperf again
        stdout = core.iperf("n1", "n2")
        assert stdout
        value = int(stdout.split(',')[bandwidth_index])
        assert 400000 <= value <= 600000

    def test_link_loss(self, core):
        """
        Test ptp node network with modifying link packet loss.

        :param conftest.Core core: core fixture to test with
        """

        # create link network
        ptp_node, interface_one, interface_two = core.create_link_network()

        # output csv index
        loss_index = -2

        # run iperf, validate normal bandwidth
        stdout = core.iperf("n1", "n2")
        assert stdout
        value = float(stdout.split(',')[loss_index])
        assert 0 <= value <= 0.5

        # change bandwidth in bits per second
        loss = 50
        core.configure_link(ptp_node, interface_one, interface_two, {
            "loss": loss
        })

        # run iperf again
        stdout = core.iperf("n1", "n2")
        assert stdout
        value = float(stdout.split(',')[loss_index])
        assert 40 <= value <= 60

    def test_link_delay(self, core):
        """
        Test ptp node network with modifying link packet delay.

        :param conftest.Core core: core fixture to test with
        """

        # create link network
        ptp_node, interface_one, interface_two = core.create_link_network()

        # run ping for delay information
        stdout = core.ping_output("n1", "n2")
        assert stdout
        rtt_line = stdout.split("\n")[-1]
        rtt_values = rtt_line.split("=")[1].split("ms")[0].strip()
        rtt_avg = float(rtt_values.split("/")[2])
        assert 0 <= rtt_avg <= 0.2

        # change delay in microseconds
        delay = 1000000
        core.configure_link(ptp_node, interface_one, interface_two, {
            "delay": delay
        })

        # run ping for delay information again
        stdout = core.ping_output("n1", "n2")
        assert stdout
        rtt_line = stdout.split("\n")[-1]
        rtt_values = rtt_line.split("=")[1].split("ms")[0].strip()
        rtt_avg = float(rtt_values.split("/")[2])
        assert 1800 <= rtt_avg <= 2200

    def test_link_jitter(self, core):
        """
        Test ptp node network with modifying link packet jitter.

        :param conftest.Core core: core fixture to test with
        """

        # create link network
        ptp_node, interface_one, interface_two = core.create_link_network()

        # output csv index
        jitter_index = 9

        # run iperf
        stdout = core.iperf("n1", "n2")
        assert stdout
        value = float(stdout.split(",")[jitter_index])
        assert -0.5 <= value <= 0.05

        # change jitter in microseconds
        jitter = 1000000
        core.configure_link(ptp_node, interface_one, interface_two, {
            "jitter": jitter
        })

        # run iperf again
        stdout = core.iperf("n1", "n2")
        assert stdout
        value = float(stdout.split(",")[jitter_index])
        assert 200 <= value <= 500
