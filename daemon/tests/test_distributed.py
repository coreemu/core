from core.emulator.emudata import NodeOptions
from core.emulator.enumerations import NodeTypes


class TestDistributed:
    def test_remote_node(self, session):
        # given
        server_name = "core2"
        host = "127.0.0.1"

        # when
        session.distributed.add_server(server_name, host)
        options = NodeOptions()
        options.server = server_name
        node = session.add_node(options=options)
        session.instantiate()

        # then
        assert node.server is not None
        assert node.server.name == server_name
        assert node.server.host == host

    def test_remote_bridge(self, session):
        # given
        server_name = "core2"
        host = "127.0.0.1"
        session.distributed.address = host

        # when
        session.distributed.add_server(server_name, host)
        options = NodeOptions()
        options.server = server_name
        node = session.add_node(_type=NodeTypes.HUB, options=options)
        session.instantiate()

        # then
        assert node.server is not None
        assert node.server.name == server_name
        assert node.server.host == host
        assert len(session.distributed.tunnels) > 0
