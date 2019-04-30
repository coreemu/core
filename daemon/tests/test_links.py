from core.emulator.emudata import LinkOptions
from core.emulator.enumerations import NodeTypes
from core import utils


def create_ptp_network(session, ip_prefixes):
    # create nodes
    node_one = session.add_node()
    node_two = session.add_node()

    # link nodes to net node
    interface_one = ip_prefixes.create_interface(node_one)
    interface_two = ip_prefixes.create_interface(node_two)
    session.add_link(node_one.id, node_two.id, interface_one, interface_two)

    # instantiate session
    session.instantiate()

    return node_one, node_two


def ping_output(from_node, to_node, ip_prefixes):
    address = ip_prefixes.ip4_address(to_node)
    output = from_node.check_cmd(["ping", "-i", "0.05", "-c", "3", address])
    return output


def iperf(from_node, to_node, ip_prefixes):
    # run iperf server, run client, kill iperf server
    address = ip_prefixes.ip4_address(to_node)
    vcmd, stdin, stdout, stderr = to_node.client.popen(["iperf", "-s", "-u", "-y", "C"])
    from_node.cmd(["iperf", "-u", "-t", "5", "-c", address])
    to_node.cmd(["killall", "-9", "iperf"])
    return stdout.read().strip()


class TestLinks:
    def test_ptp(self, session, ip_prefixes):
        # given
        node_one = session.add_node()
        node_two = session.add_node()
        interface_one = ip_prefixes.create_interface(node_one)
        inteface_two = ip_prefixes.create_interface(node_two)

        # when
        session.add_link(node_one.id, node_two.id, interface_one, inteface_two)

        # then
        assert node_one.netif(interface_one.id)
        assert node_two.netif(inteface_two.id)

    def test_node_to_net(self, session, ip_prefixes):
        # given
        node_one = session.add_node()
        node_two = session.add_node(_type=NodeTypes.SWITCH)
        interface_one = ip_prefixes.create_interface(node_one)

        # when
        session.add_link(node_one.id, node_two.id, interface_one)

        # then
        assert node_two.all_link_data(0)
        assert node_one.netif(interface_one.id)

    def test_net_to_node(self, session, ip_prefixes):
        # given
        node_one = session.add_node(_type=NodeTypes.SWITCH)
        node_two = session.add_node()
        interface_two = ip_prefixes.create_interface(node_two)

        # when
        session.add_link(node_one.id, node_two.id, interface_two=interface_two)

        # then
        assert node_one.all_link_data(0)
        assert node_two.netif(interface_two.id)

    def test_net_to_net(self, session):
        # given
        node_one = session.add_node(_type=NodeTypes.SWITCH)
        node_two = session.add_node(_type=NodeTypes.SWITCH)

        # when
        session.add_link(node_one.id, node_two.id)

        # then
        assert node_one.all_link_data(0)

    def test_link_update(self, session, ip_prefixes):
        # given
        node_one = session.add_node()
        node_two = session.add_node(_type=NodeTypes.SWITCH)
        interface_one = ip_prefixes.create_interface(node_one)
        session.add_link(node_one.id, node_two.id, interface_one)
        interface = node_one.netif(interface_one.id)
        output = utils.check_cmd(["tc", "qdisc", "show", "dev", interface.localname])
        assert "delay" not in output
        assert "rate" not in output
        assert "loss" not in output
        assert "duplicate" not in output

        # when
        link_options = LinkOptions()
        link_options.delay = 50
        link_options.bandwidth = 5000000
        link_options.per = 25
        link_options.dup = 25
        session.update_link(node_one.id, node_two.id,
                            interface_one_id=interface_one.id, link_options=link_options)

        # then
        output = utils.check_cmd(["tc", "qdisc", "show", "dev", interface.localname])
        assert "delay" in output
        assert "rate" in output
        assert "loss" in output
        assert "duplicate" in output

    def test_link_delete(self, session, ip_prefixes):
        # given
        node_one = session.add_node()
        node_two = session.add_node()
        interface_one = ip_prefixes.create_interface(node_one)
        interface_two = ip_prefixes.create_interface(node_two)
        session.add_link(node_one.id, node_two.id, interface_one, interface_two)
        assert node_one.netif(interface_one.id)
        assert node_two.netif(interface_two.id)

        # when
        session.delete_link(node_one.id, node_two.id, interface_one.id, interface_two.id)

        # then
        assert not node_one.netif(interface_one.id)
        assert not node_two.netif(interface_two.id)

    def test_link_bandwidth(self, session, ip_prefixes):
        """
        Test ptp node network with modifying link bandwidth.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create link network
        node_one, node_two = create_ptp_network(session, ip_prefixes)

        # output csv index
        bandwidth_index = 8

        # run iperf, validate normal bandwidth
        stdout = iperf(node_one, node_two, ip_prefixes)
        assert stdout
        value = int(stdout.split(',')[bandwidth_index])
        assert 900000 <= value <= 1100000

        # change bandwidth in bits per second
        link_options = LinkOptions()
        link_options.bandwidth = 500000
        session.update_link(node_one.id, node_two.id, link_options=link_options)

        # run iperf again
        stdout = iperf(node_one, node_two, ip_prefixes)
        assert stdout
        value = int(stdout.split(',')[bandwidth_index])
        assert 400000 <= value <= 600000

    def test_link_loss(self, session, ip_prefixes):
        """
        Test ptp node network with modifying link packet loss.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create link network
        node_one, node_two = create_ptp_network(session, ip_prefixes)

        # output csv index
        loss_index = -2

        # run iperf, validate normal bandwidth
        stdout = iperf(node_one, node_two, ip_prefixes)
        assert stdout
        value = float(stdout.split(',')[loss_index])
        assert 0 <= value <= 0.5

        # change bandwidth in bits per second
        link_options = LinkOptions()
        link_options.per = 50
        session.update_link(node_one.id, node_two.id, link_options=link_options)

        # run iperf again
        stdout = iperf(node_one, node_two, ip_prefixes)
        assert stdout
        value = float(stdout.split(',')[loss_index])
        assert 40 <= value <= 60

    def test_link_delay(self, session, ip_prefixes):
        """
        Test ptp node network with modifying link packet delay.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create link network
        node_one, node_two = create_ptp_network(session, ip_prefixes)

        # run ping for delay information
        stdout = ping_output(node_one, node_two, ip_prefixes)
        assert stdout
        rtt_line = stdout.split("\n")[-1]
        rtt_values = rtt_line.split("=")[1].split("ms")[0].strip()
        rtt_avg = float(rtt_values.split("/")[2])
        assert 0 <= rtt_avg <= 0.2

        # change delay in microseconds
        link_options = LinkOptions()
        link_options.delay = 1000000
        session.update_link(node_one.id, node_two.id, link_options=link_options)

        # run ping for delay information again
        stdout = ping_output(node_one, node_two, ip_prefixes)
        assert stdout
        rtt_line = stdout.split("\n")[-1]
        rtt_values = rtt_line.split("=")[1].split("ms")[0].strip()
        rtt_avg = float(rtt_values.split("/")[2])
        assert 1800 <= rtt_avg <= 2200

    def test_link_jitter(self, session, ip_prefixes):
        """
        Test ptp node network with modifying link packet jitter.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create link network
        node_one, node_two = create_ptp_network(session, ip_prefixes)

        # output csv index
        jitter_index = 9

        # run iperf
        stdout = iperf(node_one, node_two, ip_prefixes)
        assert stdout
        value = float(stdout.split(",")[jitter_index])
        assert -0.5 <= value <= 0.05

        # change jitter in microseconds
        link_options = LinkOptions()
        link_options.jitter = 1000000
        session.update_link(node_one.id, node_two.id, link_options=link_options)

        # run iperf again
        stdout = iperf(node_one, node_two, ip_prefixes)
        assert stdout
        value = float(stdout.split(",")[jitter_index])
        assert 200 <= value <= 500
