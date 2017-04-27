"""
Unit tests for testing with a CORE switch.
"""
from core.mobility import BasicRangeModel
from core.netns import nodes


class TestCore:
    def test_ptp(self, core):
        """
        Test ptp node network.

        :param conftest.Core core: core fixture to test with
        """

        # create switch
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

        # ping n2 from n1 and assert success
        status = core.ping("n1", "n2")
        assert not status

    def test_hub(self, core):
        """
        Test basic hub network.

        :param conftest.Core core: core fixture to test with
        """

        # create switch
        hub_node = core.session.add_object(cls=nodes.HubNode)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        core.add_interface(hub_node, "n1")
        core.add_interface(hub_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # ping n2 from n1 and assert success
        status = core.ping("n1", "n2")
        assert not status

    def test_switch(self, core):
        """
        Test basic switch network.

        :param conftest.Core core: core fixture to test with
        """

        # create switch
        switch_node = core.session.add_object(cls=nodes.SwitchNode)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        core.add_interface(switch_node, "n1")
        core.add_interface(switch_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # ping n2 from n1 and assert success
        status = core.ping("n1", "n2")
        assert not status

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
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        interface_one = core.add_interface(wlan_node, "n1")
        interface_two = core.add_interface(wlan_node, "n2")

        # link nodes in wlan
        core.link(wlan_node, interface_one, interface_two)

        # mark node position as together
        core.get_node("n1").setposition(0, 0)
        core.get_node("n2").setposition(0, 0)

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
        core.create_node("n1")
        core.create_node("n2")

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

        # ping n2 from n1 and assert failure
        import time
        time.sleep(1)
        status = core.ping("n1", "n2")
        assert status

    def test_link_bandwidth(self, core):
        """
        Test ptp node network with modifying link bandwidth.

        :param conftest.Core core: core fixture to test with
        """

        # create switch
        ptp_node = core.session.add_object(cls=nodes.PtpNet)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        interface_one = core.add_interface(ptp_node, "n1")
        interface_two = core.add_interface(ptp_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # output csv index
        bandwidth_index = 8

        # run iperf, validate normal bandwidth
        stdout = core.iperf("n1", "n2")
        assert stdout
        value = int(stdout.split(',')[bandwidth_index])
        print "bandwidth before: %s" % value
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

        # create switch
        ptp_node = core.session.add_object(cls=nodes.PtpNet)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        interface_one = core.add_interface(ptp_node, "n1")
        interface_two = core.add_interface(ptp_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

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
        assert 45 <= value <= 55

    def test_link_delay(self, core):
        """
        Test ptp node network with modifying link packet delay.

        :param conftest.Core core: core fixture to test with
        """

        # create switch
        ptp_node = core.session.add_object(cls=nodes.PtpNet)

        # create nodes
        core.create_node("n1")
        core.create_node("n2")

        # add interfaces
        interface_one = core.add_interface(ptp_node, "n1")
        interface_two = core.add_interface(ptp_node, "n2")

        # instantiate session
        core.session.instantiate()

        # assert node directories created
        core.assert_nodes()

        # run ping for delay information
        stdout = core.ping_output("n1", "n2")
        assert stdout
        rtt_line = stdout.split("\n")[-1]
        rtt_values = rtt_line.split("=")[1].split("ms")[0].strip()
        rtt_avg = float(rtt_values.split("/")[2])
        assert 0 <= rtt_avg <= 0.1

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
