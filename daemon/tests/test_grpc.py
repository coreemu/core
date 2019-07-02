import time

import grpc
import pytest
from builtins import int
from queue import Queue

from core.api.grpc import core_pb2
from core.api.grpc.client import CoreGrpcClient
from core.config import ConfigShim
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.data import EventData
from core.emulator.emudata import NodeOptions
from core.emulator.enumerations import NodeTypes, EventTypes, ConfigFlags, ExceptionLevels
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility


class TestGrpc:
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
        assert session.state == response.state
        if session_id is not None:
            assert response.session_id == session_id
            assert session.id == session_id

    @pytest.mark.parametrize("session_id, expected", [
        (None, True),
        (6013, False)
    ])
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
        assert len(response.groups) > 0

    def test_get_session_location(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_session_location(session.id)

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
                session.id,
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
            response = client.set_session_options(session.id, {option: value})

        # then
        assert response.result is True
        assert session.options.get_config(option) == value
        config = session.options.get_configs()
        assert len(config) > 0

    def test_set_session_state(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.set_session_state(session.id, core_pb2.SessionState.DEFINITION)

        # then
        assert response.result is True
        assert session.state == core_pb2.SessionState.DEFINITION

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

    @pytest.mark.parametrize("node_id, expected", [
        (1, True),
        (2, False)
    ])
    def test_edit_node(self, grpc_server, node_id, expected):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()

        # then
        x, y = 10, 10
        with client.context_connect():
            position = core_pb2.Position(x=x, y=y)
            response = client.edit_node(session.id, node_id, position)

        # then
        assert response.result is expected
        if expected is True:
            assert node.position.x == x
            assert node.position.y == y

    @pytest.mark.parametrize("node_id, expected", [
        (1, True),
        (2, False)
    ])
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
            with pytest.raises(KeyError):
                assert session.get_node(node.id)

    def test_node_command(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        node_options = NodeOptions(model="Host")
        node = session.add_node(node_options=node_options)
        session.instantiate()
        output = "hello world"

        # then
        command = "echo %s" % output
        with client.context_connect():
            response = client.node_command(session.id, node.id, command)

        # then
        assert response.output == output

    def test_get_node_terminal(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        node_options = NodeOptions(model="Host")
        node = session.add_node(node_options=node_options)
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
        session.add_hook(EventTypes.RUNTIME_STATE.value, file_name, None, file_data)

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
            response = client.add_hook(session.id, core_pb2.SessionState.RUNTIME, file_name, file_data)

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
            response = client.edit_link(session.id, node.id, switch.id, options, interface_one_id=interface.id)

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
                session.id, node_one.id, node_two.id, interface_one.id, interface_two.id)

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
        assert len(response.groups) > 0

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
            response = client.set_wlan_config(session.id, wlan.id, {
                range_key: range_value,
                "delay": "0",
                "loss": "0",
                "bandwidth": "50000",
                "error": "0",
                "jitter": "0"
            })

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
        assert len(response.groups) > 0

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
        emane_network = session.create_emane_network(
            model=EmaneIeee80211abgModel,
            geo_reference=(47.57917, -122.13232, 2.00000)
        )
        config_key = "platform_id_start"
        config_value = "2"
        session.emane.set_model_config(emane_network.id, EmaneIeee80211abgModel.name, {config_key: config_value})

        # then
        with client.context_connect():
            response = client.get_emane_model_configs(session.id)

        # then
        assert len(response.configs) == 1
        assert emane_network.id in response.configs

    def test_set_emane_model_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        emane_network = session.create_emane_network(
            model=EmaneIeee80211abgModel,
            geo_reference=(47.57917, -122.13232, 2.00000)
        )
        config_key = "bandwidth"
        config_value = "900000"

        # then
        with client.context_connect():
            response = client.set_emane_model_config(
                session.id, emane_network.id, EmaneIeee80211abgModel.name, {config_key: config_value})

        # then
        assert response.result is True
        config = session.emane.get_model_config(emane_network.id, EmaneIeee80211abgModel.name)
        assert config[config_key] == config_value

    def test_get_emane_model_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        emane_network = session.create_emane_network(
            model=EmaneIeee80211abgModel,
            geo_reference=(47.57917, -122.13232, 2.00000)
        )

        # then
        with client.context_connect():
            response = client.get_emane_model_config(
                session.id, emane_network.id, EmaneIeee80211abgModel.name)

        # then
        assert len(response.groups) > 0

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
        assert len(response.groups) > 0

    def test_set_mobility_config(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        config_key = "refresh_ms"
        config_value = "60"

        # then
        with client.context_connect():
            response = client.set_mobility_config(session.id, wlan.id, {config_key: config_value})

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
            response = client.mobility_action(session.id, wlan.id, core_pb2.MobilityAction.STOP)

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
            response = client.get_node_service_file(session.id, node.id, "DefaultRoute", "defaultroute.sh")

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
            response = client.set_node_service(session.id, node.id, service_name, [], validate, [])

        # then
        assert response.result is True
        service = session.services.get_service(node.id, service_name, default_service=True)
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
            response = client.set_node_service_file(session.id, node.id, service_name, file_name, file_data)

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
            response = client.service_action(session.id, node.id, service_name, core_pb2.ServiceAction.STOP)

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
            assert event_data.HasField("link_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session.broadcast_link(link_data)

            # then
            queue.get(timeout=5)

    def test_throughputs(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()

        def handle_event(event_data):
            queue.put(event_data)

        # then
        with client.context_connect():
            client.throughputs(handle_event)
            time.sleep(0.1)

            # then
            queue.get(timeout=5)

    def test_session_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.HasField("session_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            event = EventData(event_type=EventTypes.RUNTIME_STATE.value, time="%s" % time.time())
            session.broadcast_event(event)

            # then
            queue.get(timeout=5)

    def test_config_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.HasField("config_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session_config = session.options.get_configs()
            config_data = ConfigShim.config_data(0, None, ConfigFlags.UPDATE.value, session.options, session_config)
            session.broadcast_config(config_data)

            # then
            queue.get(timeout=5)

    def test_exception_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.HasField("exception_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session.exception(ExceptionLevels.FATAL, "test", None, "exception message")

            # then
            queue.get(timeout=5)

    def test_file_events(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node()
        queue = Queue()

        def handle_event(event_data):
            assert event_data.HasField("file_event")
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            file_data = session.services.get_service_file(node, "DefaultRoute", "defaultroute.sh")
            session.broadcast_file(file_data)

            # then
            queue.get(timeout=5)
