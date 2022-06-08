from core.emulator.session import Session
from core.nodes.base import CoreNode
from core.nodes.network import HubNode


class TestDistributed:
    def test_remote_node(self, session: Session):
        # given
        server_name = "core2"
        host = "127.0.0.1"

        # when
        session.distributed.add_server(server_name, host)
        node = session.add_node(CoreNode, server=server_name)
        session.instantiate()

        # then
        assert node.server is not None
        assert node.server.name == server_name
        assert node.server.host == host

    def test_remote_bridge(self, session: Session):
        # given
        server_name = "core2"
        host = "127.0.0.1"
        session.distributed.address = host

        # when
        session.distributed.add_server(server_name, host)
        node1 = session.add_node(HubNode)
        node2 = session.add_node(HubNode, server=server_name)
        session.add_link(node1.id, node2.id)
        session.instantiate()

        # then
        assert node2.server is not None
        assert node2.server.name == server_name
        assert node2.server.host == host
        assert len(session.distributed.tunnels) == 1
