from typing import Tuple

from core.emulator.emudata import IpPrefixes, LinkOptions
from core.emulator.session import Session
from core.nodes.base import CoreNode
from core.nodes.network import SwitchNode


def create_ptp_network(
    session: Session, ip_prefixes: IpPrefixes
) -> Tuple[CoreNode, CoreNode]:
    # create nodes
    node_one = session.add_node(CoreNode)
    node_two = session.add_node(CoreNode)

    # link nodes to net node
    interface_one = ip_prefixes.create_interface(node_one)
    interface_two = ip_prefixes.create_interface(node_two)
    session.add_link(node_one.id, node_two.id, interface_one, interface_two)

    # instantiate session
    session.instantiate()

    return node_one, node_two


class TestLinks:
    def test_add_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(CoreNode)
        interface_one = ip_prefixes.create_interface(node_one)
        interface_two = ip_prefixes.create_interface(node_two)

        # when
        session.add_link(node_one.id, node_two.id, interface_one, interface_two)

        # then
        assert node_one.netif(interface_one.id)
        assert node_two.netif(interface_two.id)

    def test_add_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(SwitchNode)
        interface_one = ip_prefixes.create_interface(node_one)

        # when
        session.add_link(node_one.id, node_two.id, interface_one=interface_one)

        # then
        assert node_two.all_link_data()
        assert node_one.netif(interface_one.id)

    def test_add_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node_one = session.add_node(SwitchNode)
        node_two = session.add_node(CoreNode)
        interface_two = ip_prefixes.create_interface(node_two)

        # when
        session.add_link(node_one.id, node_two.id, interface_two=interface_two)

        # then
        assert node_one.all_link_data()
        assert node_two.netif(interface_two.id)

    def test_add_net_to_net(self, session):
        # given
        node_one = session.add_node(SwitchNode)
        node_two = session.add_node(SwitchNode)

        # when
        session.add_link(node_one.id, node_two.id)

        # then
        assert node_one.all_link_data()

    def test_update_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        per = 25
        dup = 25
        jitter = 10
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(SwitchNode)
        interface_one_data = ip_prefixes.create_interface(node_one)
        session.add_link(node_one.id, node_two.id, interface_one_data)
        interface_one = node_one.netif(interface_one_data.id)
        assert interface_one.getparam("delay") != delay
        assert interface_one.getparam("bw") != bandwidth
        assert interface_one.getparam("loss") != per
        assert interface_one.getparam("duplicate") != dup
        assert interface_one.getparam("jitter") != jitter

        # when
        link_options = LinkOptions(
            delay=delay, bandwidth=bandwidth, per=per, dup=dup, jitter=jitter
        )
        session.update_link(
            node_one.id,
            node_two.id,
            interface_one_id=interface_one_data.id,
            options=link_options,
        )

        # then
        assert interface_one.getparam("delay") == delay
        assert interface_one.getparam("bw") == bandwidth
        assert interface_one.getparam("loss") == per
        assert interface_one.getparam("duplicate") == dup
        assert interface_one.getparam("jitter") == jitter

    def test_update_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        per = 25
        dup = 25
        jitter = 10
        node_one = session.add_node(SwitchNode)
        node_two = session.add_node(CoreNode)
        interface_two_data = ip_prefixes.create_interface(node_two)
        session.add_link(node_one.id, node_two.id, interface_two=interface_two_data)
        interface_two = node_two.netif(interface_two_data.id)
        assert interface_two.getparam("delay") != delay
        assert interface_two.getparam("bw") != bandwidth
        assert interface_two.getparam("loss") != per
        assert interface_two.getparam("duplicate") != dup
        assert interface_two.getparam("jitter") != jitter

        # when
        link_options = LinkOptions(
            delay=delay, bandwidth=bandwidth, per=per, dup=dup, jitter=jitter
        )
        session.update_link(
            node_one.id,
            node_two.id,
            interface_two_id=interface_two_data.id,
            options=link_options,
        )

        # then
        assert interface_two.getparam("delay") == delay
        assert interface_two.getparam("bw") == bandwidth
        assert interface_two.getparam("loss") == per
        assert interface_two.getparam("duplicate") == dup
        assert interface_two.getparam("jitter") == jitter

    def test_update_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        per = 25
        dup = 25
        jitter = 10
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(CoreNode)
        interface_one_data = ip_prefixes.create_interface(node_one)
        interface_two_data = ip_prefixes.create_interface(node_two)
        session.add_link(
            node_one.id, node_two.id, interface_one_data, interface_two_data
        )
        interface_one = node_one.netif(interface_one_data.id)
        interface_two = node_two.netif(interface_two_data.id)
        assert interface_one.getparam("delay") != delay
        assert interface_one.getparam("bw") != bandwidth
        assert interface_one.getparam("loss") != per
        assert interface_one.getparam("duplicate") != dup
        assert interface_one.getparam("jitter") != jitter
        assert interface_two.getparam("delay") != delay
        assert interface_two.getparam("bw") != bandwidth
        assert interface_two.getparam("loss") != per
        assert interface_two.getparam("duplicate") != dup
        assert interface_two.getparam("jitter") != jitter

        # when
        link_options = LinkOptions(
            delay=delay, bandwidth=bandwidth, per=per, dup=dup, jitter=jitter
        )
        session.update_link(
            node_one.id,
            node_two.id,
            interface_one_data.id,
            interface_two_data.id,
            link_options,
        )

        # then
        assert interface_one.getparam("delay") == delay
        assert interface_one.getparam("bw") == bandwidth
        assert interface_one.getparam("loss") == per
        assert interface_one.getparam("duplicate") == dup
        assert interface_one.getparam("jitter") == jitter
        assert interface_two.getparam("delay") == delay
        assert interface_two.getparam("bw") == bandwidth
        assert interface_two.getparam("loss") == per
        assert interface_two.getparam("duplicate") == dup
        assert interface_two.getparam("jitter") == jitter

    def test_delete_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(CoreNode)
        interface_one = ip_prefixes.create_interface(node_one)
        interface_two = ip_prefixes.create_interface(node_two)
        session.add_link(node_one.id, node_two.id, interface_one, interface_two)
        assert node_one.netif(interface_one.id)
        assert node_two.netif(interface_two.id)

        # when
        session.delete_link(
            node_one.id, node_two.id, interface_one.id, interface_two.id
        )

        # then
        assert not node_one.netif(interface_one.id)
        assert not node_two.netif(interface_two.id)

    def test_delete_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(SwitchNode)
        interface_one = ip_prefixes.create_interface(node_one)
        session.add_link(node_one.id, node_two.id, interface_one)
        assert node_one.netif(interface_one.id)

        # when
        session.delete_link(node_one.id, node_two.id, interface_one_id=interface_one.id)

        # then
        assert not node_one.netif(interface_one.id)

    def test_delete_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node_one = session.add_node(SwitchNode)
        node_two = session.add_node(CoreNode)
        interface_two = ip_prefixes.create_interface(node_two)
        session.add_link(node_one.id, node_two.id, interface_two=interface_two)
        assert node_two.netif(interface_two.id)

        # when
        session.delete_link(node_one.id, node_two.id, interface_two_id=interface_two.id)

        # then
        assert not node_two.netif(interface_two.id)
