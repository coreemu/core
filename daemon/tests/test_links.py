from typing import Tuple

from core.emulator.emudata import IpPrefixes, LinkOptions
from core.emulator.session import Session
from core.nodes.base import CoreNode
from core.nodes.network import SwitchNode


def create_ptp_network(
    session: Session, ip_prefixes: IpPrefixes
) -> Tuple[CoreNode, CoreNode]:
    # create nodes
    node1 = session.add_node(CoreNode)
    node2 = session.add_node(CoreNode)

    # link nodes to net node
    interface1_data = ip_prefixes.create_interface(node1)
    interface2_data = ip_prefixes.create_interface(node2)
    session.add_link(node1.id, node2.id, interface1_data, interface2_data)

    # instantiate session
    session.instantiate()

    return node1, node2


class TestLinks:
    def test_add_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        interface1_data = ip_prefixes.create_interface(node1)
        interface2_data = ip_prefixes.create_interface(node2)

        # when
        session.add_link(node1.id, node2.id, interface1_data, interface2_data)

        # then
        assert node1.netif(interface1_data.id)
        assert node2.netif(interface2_data.id)

    def test_add_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        interface1_data = ip_prefixes.create_interface(node1)

        # when
        session.add_link(node1.id, node2.id, interface1_data=interface1_data)

        # then
        assert node2.all_link_data()
        assert node1.netif(interface1_data.id)

    def test_add_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        interface2_data = ip_prefixes.create_interface(node2)

        # when
        session.add_link(node1.id, node2.id, interface2_data=interface2_data)

        # then
        assert node1.all_link_data()
        assert node2.netif(interface2_data.id)

    def test_add_net_to_net(self, session):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(SwitchNode)

        # when
        session.add_link(node1.id, node2.id)

        # then
        assert node1.all_link_data()

    def test_update_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        per = 25
        dup = 25
        jitter = 10
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        interface1_data = ip_prefixes.create_interface(node1)
        session.add_link(node1.id, node2.id, interface1_data)
        interface1 = node1.netif(interface1_data.id)
        assert interface1.getparam("delay") != delay
        assert interface1.getparam("bw") != bandwidth
        assert interface1.getparam("loss") != per
        assert interface1.getparam("duplicate") != dup
        assert interface1.getparam("jitter") != jitter

        # when
        options = LinkOptions(
            delay=delay, bandwidth=bandwidth, per=per, dup=dup, jitter=jitter
        )
        session.update_link(
            node1.id, node2.id, interface1_id=interface1_data.id, options=options
        )

        # then
        assert interface1.getparam("delay") == delay
        assert interface1.getparam("bw") == bandwidth
        assert interface1.getparam("loss") == per
        assert interface1.getparam("duplicate") == dup
        assert interface1.getparam("jitter") == jitter

    def test_update_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        per = 25
        dup = 25
        jitter = 10
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        interface2_data = ip_prefixes.create_interface(node2)
        session.add_link(node1.id, node2.id, interface2_data=interface2_data)
        interface2 = node2.netif(interface2_data.id)
        assert interface2.getparam("delay") != delay
        assert interface2.getparam("bw") != bandwidth
        assert interface2.getparam("loss") != per
        assert interface2.getparam("duplicate") != dup
        assert interface2.getparam("jitter") != jitter

        # when
        options = LinkOptions(
            delay=delay, bandwidth=bandwidth, per=per, dup=dup, jitter=jitter
        )
        session.update_link(
            node1.id, node2.id, interface2_id=interface2_data.id, options=options
        )

        # then
        assert interface2.getparam("delay") == delay
        assert interface2.getparam("bw") == bandwidth
        assert interface2.getparam("loss") == per
        assert interface2.getparam("duplicate") == dup
        assert interface2.getparam("jitter") == jitter

    def test_update_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        per = 25
        dup = 25
        jitter = 10
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        interface1_data = ip_prefixes.create_interface(node1)
        interface2_data = ip_prefixes.create_interface(node2)
        session.add_link(node1.id, node2.id, interface1_data, interface2_data)
        interface1 = node1.netif(interface1_data.id)
        interface2 = node2.netif(interface2_data.id)
        assert interface1.getparam("delay") != delay
        assert interface1.getparam("bw") != bandwidth
        assert interface1.getparam("loss") != per
        assert interface1.getparam("duplicate") != dup
        assert interface1.getparam("jitter") != jitter
        assert interface2.getparam("delay") != delay
        assert interface2.getparam("bw") != bandwidth
        assert interface2.getparam("loss") != per
        assert interface2.getparam("duplicate") != dup
        assert interface2.getparam("jitter") != jitter

        # when
        options = LinkOptions(
            delay=delay, bandwidth=bandwidth, per=per, dup=dup, jitter=jitter
        )
        session.update_link(
            node1.id, node2.id, interface1_data.id, interface2_data.id, options
        )

        # then
        assert interface1.getparam("delay") == delay
        assert interface1.getparam("bw") == bandwidth
        assert interface1.getparam("loss") == per
        assert interface1.getparam("duplicate") == dup
        assert interface1.getparam("jitter") == jitter
        assert interface2.getparam("delay") == delay
        assert interface2.getparam("bw") == bandwidth
        assert interface2.getparam("loss") == per
        assert interface2.getparam("duplicate") == dup
        assert interface2.getparam("jitter") == jitter

    def test_delete_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        interface1_data = ip_prefixes.create_interface(node1)
        interface2_data = ip_prefixes.create_interface(node2)
        session.add_link(node1.id, node2.id, interface1_data, interface2_data)
        assert node1.netif(interface1_data.id)
        assert node2.netif(interface2_data.id)

        # when
        session.delete_link(node1.id, node2.id, interface1_data.id, interface2_data.id)

        # then
        assert not node1.netif(interface1_data.id)
        assert not node2.netif(interface2_data.id)

    def test_delete_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        interface1_data = ip_prefixes.create_interface(node1)
        session.add_link(node1.id, node2.id, interface1_data)
        assert node1.netif(interface1_data.id)

        # when
        session.delete_link(node1.id, node2.id, interface1_id=interface1_data.id)

        # then
        assert not node1.netif(interface1_data.id)

    def test_delete_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        interface2_data = ip_prefixes.create_interface(node2)
        session.add_link(node1.id, node2.id, interface2_data=interface2_data)
        assert node2.netif(interface2_data.id)

        # when
        session.delete_link(node1.id, node2.id, interface2_id=interface2_data.id)

        # then
        assert not node2.netif(interface2_data.id)
