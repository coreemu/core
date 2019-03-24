import os
import time

import pytest

from core.emulator.emudata import NodeOptions, LinkOptions
from core.grpc import core_pb2
from core.enumerations import NodeTypes, EventTypes
from core.grpc.client import CoreGrpcClient
from core.mobility import BasicRangeModel

MODELS = [
    "router",
    "host",
    "PC",
    "mdr",
]

NET_TYPES = [
    NodeTypes.SWITCH,
    NodeTypes.HUB,
    NodeTypes.WIRELESS_LAN
]


class TestGrpc:
    @pytest.mark.parametrize("session_id", [None, 6013])
    def test_create_session(self, grpc_server, session_id):
        # given
        client = CoreGrpcClient()

        # when
        with client.context_connect():
            response = client.create_session(session_id)

        # then
        assert isinstance(response.id, int)
        assert isinstance(response.state, int)
        session = grpc_server.coreemu.sessions.get(response.id)
        assert session is not None
        assert session.state == response.state
        if session_id is not None:
            assert response.id == session_id
            assert session.session_id == session_id

    def test_delete_session(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.delete_session(session.session_id)

        # then
        assert response.result is True
        assert grpc_server.coreemu.sessions.get(session.session_id) is None

    def test_get_session(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.add_node()
        session.set_state(EventTypes.DEFINITION_STATE)

        # then
        with client.context_connect():
            response = client.get_session(session.session_id)

        # then
        assert response.session.state == core_pb2.DEFINITION
        assert len(response.session.nodes) == 1
        assert len(response.session.links) == 0

    def test_get_sessions(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_sessions()

        # then
        found_session = None
        for current_session in response.sessions:
            if current_session.id == session.session_id:
                found_session = current_session
                break
        assert len(response.sessions) == 1
        assert found_session is not None

    def test_get_session_options(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_session_options(session.session_id)

        # then
        assert len(response.groups) > 0

    def test_get_session_location(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_session_location(session.session_id)

        # then
        assert response.scale == 1.0
        assert response.position.x == 0
        assert response.position.y == 0
        assert response.position.z == 0
        assert response.position.lat == 0
        assert response.position.lon == 0
        assert response.position.alt == 0

    def test_set_session_location(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        scale = 2
        xyz = (1, 1, 1)
        lat_lon_alt = (1, 1, 1)
        with client.context_connect():
            response = client.set_session_location(
                session.session_id,
                x=xyz[0], y=xyz[1], z=xyz[2],
                lat=lat_lon_alt[0], lon=lat_lon_alt[1], alt=lat_lon_alt[2],
                scale=scale
            )

        # then
        assert response.result is True
        assert session.location.refxyz == xyz
        assert session.location.refscale == scale
        assert session.location.refgeo == lat_lon_alt

    def test_set_session_options(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        option = "enablerj45"
        value = "1"
        with client.context_connect():
            response = client.set_session_options(session.session_id, {option: value})

        # then
        assert response.result is True
        assert session.options.get_config(option) == value

    def test_set_session_state(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.set_session_state(session.session_id, EventTypes.DEFINITION_STATE)

        # then
        assert response.result is True
        assert session.state == EventTypes.DEFINITION_STATE.value

    def test_add_node(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.add_node(session.session_id)

        # then
        assert response.id is not None
        assert session.get_object(response.id) is not None

    def test_get_node(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        with client.context_connect():
            response = client.get_node(session.session_id, node.objid)

        # then
        assert response.node.id == node.objid

    def test_edit_node(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        x, y = 10, 10
        with client.context_connect():
            node_options = NodeOptions()
            node_options.set_position(x, y)
            response = client.edit_node(session.session_id, node.objid, node_options)

        # then
        assert response.result is True
        assert node.position.x == x
        assert node.position.y == y

    def test_delete_node(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        with client.context_connect():
            response = client.delete_node(session.session_id, node.objid)

        # then
        assert response.result is True
        with pytest.raises(KeyError):
            assert session.get_object(node.objid)

    def test_get_hooks(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        file_name = "test"
        file_data = "echo hello"
        session.add_hook(EventTypes.RUNTIME_STATE.value, file_name, None, file_data)

        # then
        with client.context_connect():
            response = client.get_hooks(session.session_id)

        # then
        assert len(response.hooks) == 1
        hook = response.hooks[0]
        assert hook.state == EventTypes.RUNTIME_STATE.value
        assert hook.file == file_name
        assert hook.data == file_data

    def test_add_hook(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        file_name = "test"
        file_data = "echo hello"
        with client.context_connect():
            response = client.add_hook(session.session_id, EventTypes.RUNTIME_STATE, file_name, file_data)

        # then
        assert response.result is True

    def test_save_xml(self, grpc_server, tmpdir):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        tmp = tmpdir.join("text.xml")

        # then
        with client.context_connect():
            response = client.save_xml(session.session_id, str(tmp))

        # then
        assert tmp.exists()

    def test_open_xml_hook(self, grpc_server, tmpdir):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        tmp = tmpdir.join("text.xml")
        session.save_xml(str(tmp))

        # then
        with client.context_connect():
            response = client.open_xml(str(tmp))

        # then
        assert response.result is True
        assert response.session is not None

    def test_get_node_links(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(_type=NodeTypes.SWITCH)
        node = session.add_node()
        interface = ip_prefixes.create_interface(node)
        session.add_link(node.objid, switch.objid, interface)

        # then
        with client.context_connect():
            response = client.get_node_links(session.session_id, switch.objid)

        # then
        assert len(response.links) == 1

    def test_add_link(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(_type=NodeTypes.SWITCH)
        node = session.add_node()
        assert len(switch.all_link_data(0)) == 0

        # then
        interface = ip_prefixes.create_interface(node)
        with client.context_connect():
            response = client.add_link(session.session_id, node.objid, switch.objid, interface)

        # then
        assert response.result is True
        assert len(switch.all_link_data(0)) == 1

    def test_edit_link(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(_type=NodeTypes.SWITCH)
        node = session.add_node()
        interface = ip_prefixes.create_interface(node)
        session.add_link(node.objid, switch.objid, interface)
        options = LinkOptions()
        options.bandwidth = 30000
        link = switch.all_link_data(0)[0]
        assert options.bandwidth != link.bandwidth

        # then
        with client.context_connect():
            response = client.edit_link(session.session_id, node.objid, switch.objid, options)

        # then
        assert response.result is True
        link = switch.all_link_data(0)[0]
        assert options.bandwidth == link.bandwidth

    def test_delete_link(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node_one = session.add_node()
        interface_one = ip_prefixes.create_interface(node_one)
        node_two = session.add_node()
        interface_two = ip_prefixes.create_interface(node_two)
        session.add_link(node_one.objid, node_two.objid, interface_one, interface_two)
        link_node = None
        for node_id in session.objects:
            node = session.objects[node_id]
            if node.objid not in {node_one.objid, node_two.objid}:
                link_node = node
                break
        assert len(link_node.all_link_data(0)) == 1

        # then
        with client.context_connect():
            response = client.delete_link(
                session.session_id, node_one.objid, node_two.objid, interface_one.id, interface_two.id)

        # then
        assert response.result is True
        assert len(link_node.all_link_data(0)) == 0

    def test_get_wlan_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)

        # then
        with client.context_connect():
            response = client.get_wlan_config(session.session_id, wlan.objid)

        # then
        assert len(response.groups) > 0

    def test_set_wlan_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        range_key = "range"
        range_value = "300"

        # then
        with client.context_connect():
            response = client.set_wlan_config(session.session_id, wlan.objid, {range_key: range_value})

        # then
        assert response.result is True
        config = session.mobility.get_model_config(wlan.objid, BasicRangeModel.name)
        assert config[range_key] == range_value
