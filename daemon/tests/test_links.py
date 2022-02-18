from typing import Tuple

import pytest

from core.emulator.data import IpPrefixes, LinkOptions
from core.emulator.session import Session
from core.errors import CoreError
from core.nodes.base import CoreNode
from core.nodes.network import SwitchNode

INVALID_ID: int = 100
LINK_OPTIONS: LinkOptions = LinkOptions(
    delay=50, bandwidth=5000000, loss=25, dup=25, jitter=10, buffer=100
)


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
    def test_add_node_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)

        # when
        iface1, iface2 = session.add_link(
            node1.id, node2.id, iface1_data, iface2_data, options=LINK_OPTIONS
        )

        # then
        assert node1.get_iface(iface1_data.id)
        assert node2.get_iface(iface2_data.id)
        assert iface1 is not None
        assert iface2 is not None
        assert iface1.local_options == LINK_OPTIONS
        assert iface1.has_local_netem
        assert iface2.local_options == LINK_OPTIONS
        assert iface2.has_local_netem

    def test_add_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        iface1_data = ip_prefixes.create_iface(node1)

        # when
        iface, _ = session.add_link(
            node1.id, node2.id, iface1_data=iface1_data, options=LINK_OPTIONS
        )

        # then
        assert node2.links()
        assert node1.get_iface(iface1_data.id)
        assert iface is not None
        assert iface.local_options == LINK_OPTIONS
        assert iface.has_local_netem

    def test_add_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        iface2_data = ip_prefixes.create_iface(node2)

        # when
        _, iface = session.add_link(
            node1.id, node2.id, iface2_data=iface2_data, options=LINK_OPTIONS
        )

        # then
        assert node1.links()
        assert node2.get_iface(iface2_data.id)
        assert iface is not None
        assert iface.local_options == LINK_OPTIONS
        assert iface.has_local_netem

    def test_add_net_to_net(self, session):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(SwitchNode)

        # when
        iface, _ = session.add_link(node1.id, node2.id, options=LINK_OPTIONS)

        # then
        assert node1.links()
        assert iface is not None
        assert iface.local_options == LINK_OPTIONS
        assert iface.options == LINK_OPTIONS
        assert iface.has_local_netem
        assert iface.has_netem

    def test_add_node_to_node_uni(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        link_options1 = LinkOptions(
            delay=50,
            bandwidth=5000000,
            loss=25,
            dup=25,
            jitter=10,
            buffer=100,
            unidirectional=True,
        )
        link_options2 = LinkOptions(
            delay=51,
            bandwidth=5000001,
            loss=26,
            dup=26,
            jitter=11,
            buffer=101,
            unidirectional=True,
        )

        # when
        iface1, iface2 = session.add_link(
            node1.id, node2.id, iface1_data, iface2_data, link_options1
        )
        session.update_link(
            node2.id, node1.id, iface2_data.id, iface1_data.id, link_options2
        )

        # then
        assert node1.get_iface(iface1_data.id)
        assert node2.get_iface(iface2_data.id)
        assert iface1 is not None
        assert iface2 is not None
        assert iface1.local_options == link_options1
        assert iface1.has_local_netem
        assert iface2.local_options == link_options2
        assert iface2.has_local_netem

    def test_update_node_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface1, _ = session.add_link(node1.id, node2.id, iface1_data)
        assert iface1.local_options != LINK_OPTIONS

        # when
        session.update_link(
            node1.id, node2.id, iface1_id=iface1_data.id, options=LINK_OPTIONS
        )

        # then
        assert iface1.local_options == LINK_OPTIONS
        assert iface1.has_local_netem

    def test_update_net_to_node(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        iface2_data = ip_prefixes.create_iface(node2)
        _, iface2 = session.add_link(node1.id, node2.id, iface2_data=iface2_data)
        assert iface2.local_options != LINK_OPTIONS

        # when
        session.update_link(
            node1.id, node2.id, iface2_id=iface2_data.id, options=LINK_OPTIONS
        )

        # then
        assert iface2.local_options == LINK_OPTIONS
        assert iface2.has_local_netem

    def test_update_ptp(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        iface1, iface2 = session.add_link(node1.id, node2.id, iface1_data, iface2_data)
        assert iface1.local_options != LINK_OPTIONS
        assert iface2.local_options != LINK_OPTIONS

        # when
        session.update_link(
            node1.id, node2.id, iface1_data.id, iface2_data.id, LINK_OPTIONS
        )

        # then
        assert iface1.local_options == LINK_OPTIONS
        assert iface1.has_local_netem
        assert iface2.local_options == LINK_OPTIONS
        assert iface2.has_local_netem

    def test_update_net_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(SwitchNode)
        iface1, _ = session.add_link(node1.id, node2.id)
        assert iface1.local_options != LINK_OPTIONS

        # when
        session.update_link(node1.id, node2.id, options=LINK_OPTIONS)

        # then
        assert iface1.local_options == LINK_OPTIONS
        assert iface1.has_local_netem
        assert iface1.options == LINK_OPTIONS
        assert iface1.has_netem

    def test_clear_net_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(SwitchNode)
        iface1, _ = session.add_link(node1.id, node2.id, options=LINK_OPTIONS)
        assert iface1.local_options == LINK_OPTIONS
        assert iface1.has_local_netem
        assert iface1.options == LINK_OPTIONS
        assert iface1.has_netem

        # when
        options = LinkOptions(delay=0, bandwidth=0, loss=0.0, dup=0, jitter=0, buffer=0)
        session.update_link(node1.id, node2.id, options=options)

        # then
        assert iface1.local_options.is_clear()
        assert not iface1.has_local_netem
        assert iface1.options.is_clear()
        assert not iface1.has_netem

    def test_delete_node_to_node(self, session: Session, ip_prefixes: IpPrefixes):
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

    def test_delete_net_to_net(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(SwitchNode)
        session.add_link(node1.id, node2.id)
        assert node1.get_linked_iface(node2)

        # when
        session.delete_link(node1.id, node2.id)

        # then
        assert not node1.get_linked_iface(node2)

    def test_delete_node_error(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(SwitchNode)
        session.add_link(node1.id, node2.id)
        assert node1.get_linked_iface(node2)

        # when
        with pytest.raises(CoreError):
            session.delete_link(node1.id, INVALID_ID)
        with pytest.raises(CoreError):
            session.delete_link(INVALID_ID, node2.id)

    def test_delete_net_to_net_error(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(SwitchNode)
        node3 = session.add_node(SwitchNode)
        session.add_link(node1.id, node2.id)
        assert node1.get_linked_iface(node2)

        # when
        with pytest.raises(CoreError):
            session.delete_link(node1.id, node3.id)

    def test_delete_node_to_net_error(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(SwitchNode)
        node3 = session.add_node(SwitchNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface1, _ = session.add_link(node1.id, node2.id, iface1_data)
        assert iface1

        # when
        with pytest.raises(CoreError):
            session.delete_link(node1.id, node3.id)

    def test_delete_net_to_node_error(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(SwitchNode)
        node2 = session.add_node(CoreNode)
        node3 = session.add_node(SwitchNode)
        iface2_data = ip_prefixes.create_iface(node2)
        _, iface2 = session.add_link(node1.id, node2.id, iface2_data=iface2_data)
        assert iface2

        # when
        with pytest.raises(CoreError):
            session.delete_link(node1.id, node3.id)

    def test_delete_node_to_node_error(self, session: Session, ip_prefixes: IpPrefixes):
        # given
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)
        node3 = session.add_node(SwitchNode)
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        iface1, iface2 = session.add_link(node1.id, node2.id, iface1_data, iface2_data)
        assert iface1
        assert iface2

        # when
        with pytest.raises(CoreError):
            session.delete_link(node1.id, node3.id)
