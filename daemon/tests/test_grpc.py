import time
from queue import Queue

import grpc
import pytest
from mock import patch

from core.api.grpc import core_pb2
from core.api.grpc.client import CoreGrpcClient, InterfaceHelper
from core.config import ConfigShim
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.data import EventData
from core.emulator.emudata import NodeOptions
from core.emulator.enumerations import (
    ConfigFlags,
    EventTypes,
    ExceptionLevels,
    NodeTypes,
)
from core.errors import CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.xml.corexml import CoreXmlWriter


class TestGrpc:
    def test_start_session(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        position = core_pb2.Position(x=50, y=100)
        node_one = core_pb2.Node(id=1, position=position, model="PC")
        position = core_pb2.Position(x=100, y=100)
        node_two = core_pb2.Node(id=2, position=position, model="PC")
        position = core_pb2.Position(x=200, y=200)
        wlan_node = core_pb2.Node(
            id=3, type=NodeTypes.WIRELESS_LAN.value, position=position
        )
        nodes = [node_one, node_two, wlan_node]
        interface_helper = InterfaceHelper(ip4_prefix="10.83.0.0/16")
        interface_one = interface_helper.create_interface(node_one.id, 0)
        interface_two = interface_helper.create_interface(node_two.id, 0)
        link = core_pb2.Link(
            type=core_pb2.LinkType.WIRED,
            node_one_id=node_one.id,
            node_two_id=node_two.id,
            interface_one=interface_one,
            interface_two=interface_two,
        )
        links = [link]
        hook = core_pb2.Hook(
            state=core_pb2.SessionState.RUNTIME, file="echo.sh", data="echo hello"
        )
        hooks = [hook]
        location_x = 5
        location_y = 10
        location_z = 15
        location_lat = 20
        location_lon = 30
        location_alt = 40
        location_scale = 5
        location = core_pb2.SessionLocation(
            x=location_x,
            y=location_y,
            z=location_z,
            lat=location_lat,
            lon=location_lon,
            alt=location_alt,
            scale=location_scale,
        )
        emane_config_key = "platform_id_start"
        emane_config_value = "2"
        emane_config = {emane_config_key: emane_config_value}
        model_node_id = 20
        model_config_key = "bandwidth"
        model_config_value = "500000"
        model_config = core_pb2.EmaneModelConfig(
            node_id=model_node_id,
            interface_id=-1,
            model=EmaneIeee80211abgModel.name,
            config={model_config_key: model_config_value},
        )
        model_configs = [model_config]
        wlan_config_key = "range"
        wlan_config_value = "333"
        wlan_config = core_pb2.WlanConfig(
            node_id=wlan_node.id, config={wlan_config_key: wlan_config_value}
        )
        wlan_configs = [wlan_config]
        mobility_config_key = "refresh_ms"
        mobility_config_value = "60"
        mobility_config = core_pb2.MobilityConfig(
            node_id=wlan_node.id, config={mobility_config_key: mobility_config_value}
        )
        mobility_configs = [mobility_config]
        service_config = core_pb2.ServiceConfig(
            node_id=node_one.id, service="DefaultRoute", validate=["echo hello"]
        )
        service_configs = [service_config]
        service_file_config = core_pb2.ServiceFileConfig(
            node_id=node_one.id,
            service="DefaultRoute",
            file="defaultroute.sh",
            data="echo hello",
        )
        service_file_configs = [service_file_config]

        # when
        with patch.object(CoreXmlWriter, "write"):
            with client.context_connect():
                client.start_session(
                    session.id,
                    nodes,
                    links,
                    location,
                    hooks,
                    emane_config,
                    model_configs,
                    wlan_configs,
                    mobility_configs,
                    service_configs,
                    service_file_configs,
                )

        # then
        assert node_one.id in session.nodes
        assert node_two.id in session.nodes
        assert wlan_node.id in session.nodes
        assert session.nodes[node_one.id].netif(0) is not None
        assert session.nodes[node_two.id].netif(0) is not None
        hook_file, hook_data = session._hooks[EventTypes.RUNTIME_STATE][0]
        assert hook_file == hook.file
        assert hook_data == hook.data
        assert session.location.refxyz == (location_x, location_y, location_z)
        assert session.location.refgeo == (location_lat, location_lon, location_alt)
        assert session.location.refscale == location_scale
        assert session.emane.get_config(emane_config_key) == emane_config_value
        set_wlan_config = session.mobility.get_model_config(
            wlan_node.id, BasicRangeModel.name
        )
        assert set_wlan_config[wlan_config_key] == wlan_config_value
        set_mobility_config = session.mobility.get_model_config(
            wlan_node.id, Ns2ScriptedMobility.name
        )
        assert set_mobility_config[mobility_config_key] == mobility_config_value
        set_model_config = session.emane.get_model_config(
            model_node_id, EmaneIeee80211abgModel.name
        )
        assert set_model_config[model_config_key] == model_config_value
        service = session.services.get_service(
            node_one.id, service_config.service, default_service=True
        )
        assert service.validate == tuple(service_config.validate)
        service_file = session.services.get_service_file(
            node_one, service_file_config.service, service_file_config.file
        )
        assert service_file.data == service_file_config.data

    @pytest.mark.parametrize("session_id", [None, 6013])
    def test_create_session(self, grpc_server, session_id):
        # given
        client = CoreGrpcClient()

        # when
        with client.context_connect():
            response = client.create_session(session_id)

        # then
        assert isinstance(response.session_id, int)
        assert isinstance(response.state, int)
        session = grpc_server.coreemu.sessions.get(response.session_id)
        assert session is not None
        assert session.state == EventTypes(response.state)
        if session_id is not None:
            assert response.session_id == session_id
            assert session.id == session_id

    @pytest.mark.parametrize("session_id, expected", [(None, True), (6013, False)])
    def test_delete_session(self, grpc_server, session_id, expected):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        if session_id is None:
            session_id = session.id

        # then
        with client.context_connect():
            response = client.delete_session(session_id)

        # then
        assert response.result is expected
        assert grpc_server.coreemu.sessions.get(session_id) is None

    def test_get_session(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.add_node()
        session.set_state(EventTypes.DEFINITION_STATE)

        # then
        with client.context_connect():
            response = client.get_session(session.id)

        # then
        assert response.session.state == core_pb2.SessionState.DEFINITION
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
            if current_session.id == session.id:
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
            response = client.get_session_options(session.id)

        # then
        assert len(response.config) > 0

    def test_get_session_location(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_session_location(session.id)

        # then
        assert response.location.scale == 1.0
        assert response.location.x == 0
        assert response.location.y == 0
        assert response.location.z == 0
        assert response.location.lat == 0
        assert response.location.lon == 0
        assert response.location.alt == 0

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
                session.id,
                x=xyz[0],
                y=xyz[1],
                z=xyz[2],
                lat=lat_lon_alt[0],
                lon=lat_lon_alt[1],
                alt=lat_lon_alt[2],
                scale=scale,
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
            response = client.set_session_options(session.id, {option: value})

        # then
        assert response.result is True
        assert session.options.get_config(option) == value
        config = session.options.get_configs()
        assert len(config) > 0

    def test_set_session_metadata(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        key = "meta1"
        value = "value1"
        with client.context_connect():
            response = client.set_session_metadata(session.id, {key: value})

        # then
        assert response.result is True
        assert session.metadata[key] == value

    def test_get_session_metadata(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        key = "meta1"
        value = "value1"
        session.metadata[key] = value

        # then
        with client.context_connect():
            response = client.get_session_metadata(session.id)

        # then
        assert response.config[key] == value

    def test_set_session_state(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.set_session_state(
                session.id, core_pb2.SessionState.DEFINITION
            )

        # then
        assert response.result is True
        assert session.state == EventTypes.DEFINITION_STATE

    def test_add_node(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            node = core_pb2.Node()
            response = client.add_node(session.id, node)

        # then
        assert response.node_id is not None
        assert session.get_node(response.node_id) is not None

    def test_get_node(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        with client.context_connect():
            response = client.get_node(session.id, node.id)

        # then
        assert response.node.id == node.id

    def test_edit_node(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        x, y = 10, 10
        with client.context_connect():
            position = core_pb2.Position(x=x, y=y)
            response = client.edit_node(session.id, node.id, position)

        # then
        assert response.result is True
        assert node.position.x == x
        assert node.position.y == y

    @pytest.mark.parametrize("node_id, expected", [(1, True), (2, False)])
    def test_delete_node(self, grpc_server, node_id, expected):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        with client.context_connect():
            response = client.delete_node(session.id, node_id)

        # then
        assert response.result is expected
        if expected is True:
            with pytest.raises(CoreError):
                assert session.get_node(node.id)

    def test_node_command(self, request, grpc_server):
        if request.config.getoption("mock"):
            pytest.skip("mocking calls")

        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        options = NodeOptions(model="Host")
        node = session.add_node(options=options)
        session.instantiate()
        output = "hello world"

        # then
        command = f"echo {output}"
        with client.context_connect():
            response = client.node_command(session.id, node.id, command)

        # then
        assert response.output == output

    def test_get_node_terminal(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        options = NodeOptions(model="Host")
        node = session.add_node(options=options)
        session.instantiate()

        # then
        with client.context_connect():
            response = client.get_node_terminal(session.id, node.id)

        # then
        assert response.terminal is not None

    def test_get_hooks(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        file_name = "test"
        file_data = "echo hello"
        session.add_hook(EventTypes.RUNTIME_STATE, file_name, None, file_data)

        # then
        with client.context_connect():
            response = client.get_hooks(session.id)

        # then
        assert len(response.hooks) == 1
        hook = response.hooks[0]
        assert hook.state == core_pb2.SessionState.RUNTIME
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
            response = client.add_hook(
                session.id, core_pb2.SessionState.RUNTIME, file_name, file_data
            )

        # then
        assert response.result is True

    def test_save_xml(self, grpc_server, tmpdir):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        tmp = tmpdir.join("text.xml")

        # then
        with client.context_connect():
            client.save_xml(session.id, str(tmp))

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
        assert response.session_id is not None

    def test_get_node_links(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(_type=NodeTypes.SWITCH)
        node = session.add_node()
        interface = ip_prefixes.create_interface(node)
        session.add_link(node.id, switch.id, interface)

        # then
        with client.context_connect():
            response = client.get_node_links(session.id, switch.id)

        # then
        assert len(response.links) == 1

    def test_get_node_links_exception(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(_type=NodeTypes.SWITCH)
        node = session.add_node()
        interface = ip_prefixes.create_interface(node)
        session.add_link(node.id, switch.id, interface)

        # then
        with pytest.raises(grpc.RpcError):
            with client.context_connect():
                client.get_node_links(session.id, 3)

    def test_add_link(self, grpc_server, interface_helper):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(_type=NodeTypes.SWITCH)
        node = session.add_node()
        assert len(switch.all_link_data(0)) == 0

        # then
        interface = interface_helper.create_interface(node.id, 0)
        with client.context_connect():
            response = client.add_link(session.id, node.id, switch.id, interface)

        # then
        assert response.result is True
        assert len(switch.all_link_data(0)) == 1

    def test_add_link_exception(self, grpc_server, interface_helper):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        interface = interface_helper.create_interface(node.id, 0)
        with pytest.raises(grpc.RpcError):
            with client.context_connect():
                client.add_link(session.id, 1, 3, interface)

    def test_edit_link(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(_type=NodeTypes.SWITCH)
        node = session.add_node()
        interface = ip_prefixes.create_interface(node)
        session.add_link(node.id, switch.id, interface)
        options = core_pb2.LinkOptions(bandwidth=30000)
        link = switch.all_link_data(0)[0]
        assert options.bandwidth != link.bandwidth

        # then
        with client.context_connect():
            response = client.edit_link(
                session.id, node.id, switch.id, options, interface_one_id=interface.id
            )

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
        session.add_link(node_one.id, node_two.id, interface_one, interface_two)
        link_node = None
        for node_id in session.nodes:
            node = session.nodes[node_id]
            if node.id not in {node_one.id, node_two.id}:
                link_node = node
                break
        assert len(link_node.all_link_data(0)) == 1

        # then
        with client.context_connect():
            response = client.delete_link(
                session.id, node_one.id, node_two.id, interface_one.id, interface_two.id
            )

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
            response = client.get_wlan_config(session.id, wlan.id)

        # then
        assert len(response.config) > 0

    def test_set_wlan_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        wlan.setmodel(BasicRangeModel, BasicRangeModel.default_values())
        session.instantiate()
        range_key = "range"
        range_value = "50"

        # then
        with client.context_connect():
            response = client.set_wlan_config(
                session.id,
                wlan.id,
                {
                    range_key: range_value,
                    "delay": "0",
                    "loss": "0",
                    "bandwidth": "50000",
                    "error": "0",
                    "jitter": "0",
                },
            )

        # then
        assert response.result is True
        config = session.mobility.get_model_config(wlan.id, BasicRangeModel.name)
        assert config[range_key] == range_value
        assert wlan.model.range == int(range_value)

    def test_get_emane_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_emane_config(session.id)

        # then
        assert len(response.config) > 0

    def test_set_emane_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        config_key = "platform_id_start"
        config_value = "2"

        # then
        with client.context_connect():
            response = client.set_emane_config(session.id, {config_key: config_value})

        # then
        assert response.result is True
        config = session.emane.get_configs()
        assert len(config) > 1
        assert config[config_key] == config_value

    def test_get_emane_model_configs(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions()
        options.emane = EmaneIeee80211abgModel.name
        emane_network = session.add_node(_type=NodeTypes.EMANE, options=options)
        session.emane.set_model(emane_network, EmaneIeee80211abgModel)
        config_key = "platform_id_start"
        config_value = "2"
        session.emane.set_model_config(
            emane_network.id, EmaneIeee80211abgModel.name, {config_key: config_value}
        )

        # then
        with client.context_connect():
            response = client.get_emane_model_configs(session.id)

        # then
        assert len(response.configs) == 1
        model_config = response.configs[0]
        assert emane_network.id == model_config.node_id
        assert model_config.model == EmaneIeee80211abgModel.name
        assert len(model_config.config) > 0
        assert model_config.interface == -1

    def test_set_emane_model_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions()
        options.emane = EmaneIeee80211abgModel.name
        emane_network = session.add_node(_type=NodeTypes.EMANE, options=options)
        session.emane.set_model(emane_network, EmaneIeee80211abgModel)
        config_key = "bandwidth"
        config_value = "900000"

        # then
        with client.context_connect():
            response = client.set_emane_model_config(
                session.id,
                emane_network.id,
                EmaneIeee80211abgModel.name,
                {config_key: config_value},
            )

        # then
        assert response.result is True
        config = session.emane.get_model_config(
            emane_network.id, EmaneIeee80211abgModel.name
        )
        assert config[config_key] == config_value

    def test_get_emane_model_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions()
        options.emane = EmaneIeee80211abgModel.name
        emane_network = session.add_node(_type=NodeTypes.EMANE, options=options)
        session.emane.set_model(emane_network, EmaneIeee80211abgModel)

        # then
        with client.context_connect():
            response = client.get_emane_model_config(
                session.id, emane_network.id, EmaneIeee80211abgModel.name
            )

        # then
        assert len(response.config) > 0

    def test_get_emane_models(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_emane_models(session.id)

        # then
        assert len(response.models) > 0

    def test_get_mobility_configs(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        session.mobility.set_model_config(wlan.id, Ns2ScriptedMobility.name, {})

        # then
        with client.context_connect():
            response = client.get_mobility_configs(session.id)

        # then
        assert len(response.configs) > 0
        assert wlan.id in response.configs
        mapped_config = response.configs[wlan.id]
        assert len(mapped_config.config) > 0

    def test_get_mobility_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        session.mobility.set_model_config(wlan.id, Ns2ScriptedMobility.name, {})

        # then
        with client.context_connect():
            response = client.get_mobility_config(session.id, wlan.id)

        # then
        assert len(response.config) > 0

    def test_set_mobility_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        config_key = "refresh_ms"
        config_value = "60"

        # then
        with client.context_connect():
            response = client.set_mobility_config(
                session.id, wlan.id, {config_key: config_value}
            )

        # then
        assert response.result is True
        config = session.mobility.get_model_config(wlan.id, Ns2ScriptedMobility.name)
        assert config[config_key] == config_value

    def test_mobility_action(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        session.mobility.set_model_config(wlan.id, Ns2ScriptedMobility.name, {})
        session.instantiate()

        # then
        with client.context_connect():
            response = client.mobility_action(
                session.id, wlan.id, core_pb2.MobilityAction.STOP
            )

        # then
        assert response.result is True

    def test_get_services(self, grpc_server):
        # given
        client = CoreGrpcClient()

        # then
        with client.context_connect():
            response = client.get_services()

        # then
        assert len(response.services) > 0

    def test_get_service_defaults(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_service_defaults(session.id)

        # then
        assert len(response.defaults) > 0

    def test_set_service_defaults(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node_type = "test"
        services = ["SSH"]

        # then
        with client.context_connect():
            response = client.set_service_defaults(session.id, {node_type: services})

        # then
        assert response.result is True
        assert session.services.default_services[node_type] == services

    def test_get_node_service_configs(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()
        service_name = "DefaultRoute"
        session.services.set_service(node.id, service_name)

        # then
        with client.context_connect():
            response = client.get_node_service_configs(session.id)

        # then
        assert len(response.configs) == 1
        service_config = response.configs[0]
        assert service_config.node_id == node.id
        assert service_config.service == service_name

    def test_get_node_service(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        with client.context_connect():
            response = client.get_node_service(session.id, node.id, "DefaultRoute")

        # then
        assert len(response.service.configs) > 0

    def test_get_node_service_file(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        with client.context_connect():
            response = client.get_node_service_file(
                session.id, node.id, "DefaultRoute", "defaultroute.sh"
            )

        # then
        assert response.data is not None

    def test_set_node_service(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()
        service_name = "DefaultRoute"
        validate = ["echo hello"]

        # then
        with client.context_connect():
            response = client.set_node_service(
                session.id, node.id, service_name, validate=validate
            )

        # then
        assert response.result is True
        service = session.services.get_service(
            node.id, service_name, default_service=True
        )
        assert service.validate == tuple(validate)

    def test_set_node_service_file(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()
        service_name = "DefaultRoute"
        file_name = "defaultroute.sh"
        file_data = "echo hello"

        # then
        with client.context_connect():
            response = client.set_node_service_file(
                session.id, node.id, service_name, file_name, file_data
            )

        # then
        assert response.result is True
        service_file = session.services.get_service_file(node, service_name, file_name)
        assert service_file.data == file_data

    def test_service_action(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()
        service_name = "DefaultRoute"

        # then
        with client.context_connect():
            response = client.service_action(
                session.id, node.id, service_name, core_pb2.ServiceAction.STOP
            )

        # then
        assert response.result is True

    def test_node_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()
        node_data = node.data(message_type=0)
        queue = Queue()

        def handle_event(event_data):
            assert event_data.session_id == session.id
            assert event_data.HasField("node_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session.broadcast_node(node_data)

            # then
            queue.get(timeout=5)

    def test_link_events(self, grpc_server, ip_prefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        node = session.add_node()
        interface = ip_prefixes.create_interface(node)
        session.add_link(node.id, wlan.id, interface)
        link_data = wlan.all_link_data(0)[0]
        queue = Queue()

        def handle_event(event_data):
            assert event_data.session_id == session.id
            assert event_data.HasField("link_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session.broadcast_link(link_data)

            # then
            queue.get(timeout=5)

    def test_throughputs(self, request, grpc_server):
        if request.config.getoption("mock"):
            pytest.skip("mocking calls")

        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.session_id == session.id
            queue.put(event_data)

        # then
        with client.context_connect():
            client.throughputs(session.id, handle_event)
            time.sleep(0.1)

            # then
            queue.get(timeout=5)

    def test_session_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.session_id == session.id
            assert event_data.HasField("session_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            event = EventData(
                event_type=EventTypes.RUNTIME_STATE, time=str(time.monotonic())
            )
            session.broadcast_event(event)

            # then
            queue.get(timeout=5)

    def test_config_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.session_id == session.id
            assert event_data.HasField("config_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session_config = session.options.get_configs()
            config_data = ConfigShim.config_data(
                0, None, ConfigFlags.UPDATE.value, session.options, session_config
            )
            session.broadcast_config(config_data)

            # then
            queue.get(timeout=5)

    def test_exception_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()
        exception_level = ExceptionLevels.FATAL
        source = "test"
        node_id = None
        text = "exception message"

        def handle_event(event_data):
            assert event_data.session_id == session.id
            assert event_data.HasField("exception_event")
            exception_event = event_data.exception_event
            assert exception_event.level == exception_level.value
            assert exception_event.node_id == 0
            assert exception_event.source == source
            assert exception_event.text == text
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session.exception(exception_level, source, node_id, text)

            # then
            queue.get(timeout=5)

    def test_file_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.session_id == session.id
            assert event_data.HasField("file_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            file_data = session.services.get_service_file(
                node, "DefaultRoute", "defaultroute.sh"
            )
            session.broadcast_file(file_data)

            # then
            queue.get(timeout=5)
