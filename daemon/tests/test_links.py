from typing import Tuple

from core.emulator.data import IpPrefixes, LinkOptions
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
    iface1_data = ip_prefixes.create_iface(node1)
    iface2_data = ip_prefixes.create_iface(node2)
    session.add_link(node1.id, node2.id, iface1_data, iface2_data)

    # instantiate session
    session.instantiate()

    return node1, node2


class TestLinks:
    def test_add_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)

        # when
        session.add_link(node1.id, node2.id, iface1_data, iface2_data)

        # then
        assert node1.get_iface(iface1_data.id)
        assert node2.get_iface(iface2_data.id)

    def test_add_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        iface1_data = ip_prefixes.create_iface(node1)

        # when
        session.add_link(node1.id, node2.id, iface1_data=iface1_data)

        # then
        assert node2.all_link_data()
        assert node1.get_iface(iface1_data.id)

    def test_add_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        iface2_data = ip_prefixes.create_iface(node2)

        # when
        session.add_link(node1.id, node2.id, iface2_data=iface2_data)

        # then
        assert node1.all_link_data()
        assert node2.get_iface(iface2_data.id)

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
        loss = 25
        dup = 25
        jitter = 10
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        iface1_data = ip_prefixes.create_iface(node1)
        session.add_link(node1.id, node2.id, iface1_data)
        iface1 = node1.get_iface(iface1_data.id)
        assert iface1.getparam("delay") != delay
        assert iface1.getparam("bw") != bandwidth
        assert iface1.getparam("loss") != loss
        assert iface1.getparam("duplicate") != dup
        assert iface1.getparam("jitter") != jitter

        # when
        options = LinkOptions(
            delay=delay, bandwidth=bandwidth, loss=loss, dup=dup, jitter=jitter
        )
        session.update_link(
            node1.id, node2.id, iface1_id=iface1_data.id, options=options
        )

        # then
        assert iface1.getparam("delay") == delay
        assert iface1.getparam("bw") == bandwidth
        assert iface1.getparam("loss") == loss
        assert iface1.getparam("duplicate") == dup
        assert iface1.getparam("jitter") == jitter

    def test_update_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        loss = 25
        dup = 25
        jitter = 10
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        iface2_data = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface2_data=iface2_data)
        iface2 = node2.get_iface(iface2_data.id)
        assert iface2.getparam("delay") != delay
        assert iface2.getparam("bw") != bandwidth
        assert iface2.getparam("loss") != loss
        assert iface2.getparam("duplicate") != dup
        assert iface2.getparam("jitter") != jitter

        # when
        options = LinkOptions(
            delay=delay, bandwidth=bandwidth, loss=loss, dup=dup, jitter=jitter
        )
        session.update_link(
            node1.id, node2.id, iface2_id=iface2_data.id, options=options
        )

        # then
        assert iface2.getparam("delay") == delay
        assert iface2.getparam("bw") == bandwidth
        assert iface2.getparam("loss") == loss
        assert iface2.getparam("duplicate") == dup
        assert iface2.getparam("jitter") == jitter

    def test_update_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        delay = 50
        bandwidth = 5000000
        loss = 25
        dup = 25
        jitter = 10
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface1_data, iface2_data)
        iface1 = node1.get_iface(iface1_data.id)
        iface2 = node2.get_iface(iface2_data.id)
        assert iface1.getparam("delay") != delay
        assert iface1.getparam("bw") != bandwidth
        assert iface1.getparam("loss") != loss
        assert iface1.getparam("duplicate") != dup
        assert iface1.getparam("jitter") != jitter
        assert iface2.getparam("delay") != delay
        assert iface2.getparam("bw") != bandwidth
        assert iface2.getparam("loss") != loss
        assert iface2.getparam("duplicate") != dup
        assert iface2.getparam("jitter") != jitter

        # when
        options = LinkOptions(
            delay=delay, bandwidth=bandwidth, loss=loss, dup=dup, jitter=jitter
        )
        session.update_link(node1.id, node2.id, iface1_data.id, iface2_data.id, options)

        # then
        assert iface1.getparam("delay") == delay
        assert iface1.getparam("bw") == bandwidth
        assert iface1.getparam("loss") == loss
        assert iface1.getparam("duplicate") == dup
        assert iface1.getparam("jitter") == jitter
        assert iface2.getparam("delay") == delay
        assert iface2.getparam("bw") == bandwidth
        assert iface2.getparam("loss") == loss
        assert iface2.getparam("duplicate") == dup
        assert iface2.getparam("jitter") == jitter

    def test_delete_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface1_data, iface2_data)
        assert node1.get_iface(iface1_data.id)
        assert node2.get_iface(iface2_data.id)

        # when
        session.delete_link(node1.id, node2.id, iface1_data.id, iface2_data.id)

        # then
        assert iface1_data.id not in node1.ifaces
        assert iface2_data.id not in node2.ifaces

    def test_delete_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        iface1_data = ip_prefixes.create_iface(node1)
        session.add_link(node1.id, node2.id, iface1_data)
        assert node1.get_iface(iface1_data.id)

        # when
        session.delete_link(node1.id, node2.id, iface1_id=iface1_data.id)

        # then
        assert iface1_data.id not in node1.ifaces

    def test_delete_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        iface2_data = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface2_data=iface2_data)
        assert node2.get_iface(iface2_data.id)

        # when
        session.delete_link(node1.id, node2.id, iface2_id=iface2_data.id)

        # then
        assert iface2_data.id not in node2.ifaces
