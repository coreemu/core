import pytest

from core.emulator.data import IpPrefixes, LinkOptions
from core.emulator.session import Session
from core.errors import CoreCommandError
from core.nodes.base import CoreNode


class TestPing:
    def test_success(self, session: Session, ip_prefixes: IpPrefixes):
        # create nodes
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)

        # link nodes together
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface1_data, iface2_data)

        # ping node, expect a successful command
        node1.cmd(f"ping -c 1 {iface2_data.ip4}")

    def test_failure(self, session: Session, ip_prefixes: IpPrefixes):
        # create nodes
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)

        # link nodes together
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        options = LinkOptions(loss=100.0)
        session.add_link(node1.id, node2.id, iface1_data, iface2_data, options)

        # ping node, expect command to fail and raise exception due to 100% loss
        with pytest.raises(CoreCommandError):
            node1.cmd(f"ping -c 1 {iface2_data.ip4}")
