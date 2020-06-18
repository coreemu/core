import time
from queue import Queue
from tempfile import TemporaryFile
from typing import Optional

import grpc
import pytest
from mock import patch

from core.api.grpc import core_pb2
from core.api.grpc.client import CoreGrpcClient, InterfaceHelper
from core.api.grpc.emane_pb2 import EmaneModelConfig
from core.api.grpc.mobility_pb2 import MobilityAction, MobilityConfig
from core.api.grpc.server import CoreGrpcServer
from core.api.grpc.services_pb2 import ServiceAction, ServiceConfig, ServiceFileConfig
from core.api.grpc.wlan_pb2 import WlanConfig
from core.api.tlv.dataconversion import ConfigShim
from core.api.tlv.enumerations import ConfigFlags
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNet
from core.emulator.data import EventData, IpPrefixes, NodeData, NodeOptions
from core.emulator.enumerations import EventTypes, ExceptionLevels, NodeTypes
from core.errors import CoreError
from core.location.mobility import BasicRangeModel, Ns2ScriptedMobility
from core.nodes.base import CoreNode
from core.nodes.network import SwitchNode, WlanNode
from core.xml.corexml import CoreXmlWriter


class TestGrpc:
    def test_start_session(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        position = core_pb2.Position(x=50, y=100)
        node1 = core_pb2.Node(id=1, position=position, model="PC")
        position = core_pb2.Position(x=100, y=100)
        node2 = core_pb2.Node(id=2, position=position, model="PC")
        position = core_pb2.Position(x=200, y=200)
        wlan_node = core_pb2.Node(
            id=3, type=NodeTypes.WIRELESS_LAN.value, position=position
        )
        nodes = [node1, node2, wlan_node]
        iface_helper = InterfaceHelper(ip4_prefix="10.83.0.0/16")
        iface1_id = 0
        iface1 = iface_helper.create_iface(node1.id, iface1_id)
        iface2_id = 0
        iface2 = iface_helper.create_iface(node2.id, iface2_id)
        link = core_pb2.Link(
            type=core_pb2.LinkType.WIRED,
            node1_id=node1.id,
            node2_id=node2.id,
            iface1=iface1,
            iface2=iface2,
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
        model_config = EmaneModelConfig(
            node_id=model_node_id,
            iface_id=-1,
            model=EmaneIeee80211abgModel.name,
            config={model_config_key: model_config_value},
        )
        model_configs = [model_config]
        wlan_config_key = "range"
        wlan_config_value = "333"
        wlan_config = WlanConfig(
            node_id=wlan_node.id, config={wlan_config_key: wlan_config_value}
        )
        wlan_configs = [wlan_config]
        mobility_config_key = "refresh_ms"
        mobility_config_value = "60"
        mobility_config = MobilityConfig(
            node_id=wlan_node.id, config={mobility_config_key: mobility_config_value}
        )
        mobility_configs = [mobility_config]
        service_config = ServiceConfig(
            node_id=node1.id, service="DefaultRoute", validate=["echo hello"]
        )
        service_configs = [service_config]
        service_file_config = ServiceFileConfig(
            node_id=node1.id,
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
        assert node1.id in session.nodes
        assert node2.id in session.nodes
        assert wlan_node.id in session.nodes
        assert iface1_id in session.nodes[node1.id].ifaces
        assert iface2_id in session.nodes[node2.id].ifaces
        hook_file, hook_data = session.hooks[EventTypes.RUNTIME_STATE][0]
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
            node1.id, service_config.service, default_service=True
        )
        assert service.validate == tuple(service_config.validate)
        service_file = session.services.get_service_file(
            node1, service_file_config.service, service_file_config.file
        )
        assert service_file.data == service_file_config.data

    @pytest.mark.parametrize("session_id", [None, 6013])
    def test_create_session(
        self, grpc_server: CoreGrpcServer, session_id: Optional[int]
    ):
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
    def test_delete_session(
        self, grpc_server: CoreGrpcServer, session_id: Optional[int], expected: bool
    ):
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

    def test_get_session(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.add_node(CoreNode)
        session.set_state(EventTypes.DEFINITION_STATE)

        # then
        with client.context_connect():
            response = client.get_session(session.id)

        # then
        assert response.session.state == core_pb2.SessionState.DEFINITION
        assert len(response.session.nodes) == 1
        assert len(response.session.links) == 0

    def test_get_sessions(self, grpc_server: CoreGrpcServer):
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

    def test_get_session_options(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_session_options(session.id)

        # then
        assert len(response.config) > 0

    def test_get_session_location(self, grpc_server: CoreGrpcServer):
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

    def test_set_session_location(self, grpc_server: CoreGrpcServer):
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

    def test_set_session_options(self, grpc_server: CoreGrpcServer):
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

    def test_set_session_metadata(self, grpc_server: CoreGrpcServer):
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

    def test_get_session_metadata(self, grpc_server: CoreGrpcServer):
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

    def test_set_session_state(self, grpc_server: CoreGrpcServer):
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

    def test_add_node(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            node = core_pb2.Node()
            response = client.add_node(session.id, node)

        # then
        assert response.node_id is not None
        assert session.get_node(response.node_id, CoreNode) is not None

    def test_get_node(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)

        # then
        with client.context_connect():
            response = client.get_node(session.id, node.id)

        # then
        assert response.node.id == node.id

    def test_edit_node(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)

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
    def test_delete_node(
        self, grpc_server: CoreGrpcServer, node_id: int, expected: bool
    ):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)

        # then
        with client.context_connect():
            response = client.delete_node(session.id, node_id)

        # then
        assert response.result is expected
        if expected is True:
            with pytest.raises(CoreError):
                assert session.get_node(node.id, CoreNode)

    def test_node_command(self, request, grpc_server: CoreGrpcServer):
        if request.config.getoption("mock"):
            pytest.skip("mocking calls")

        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        options = NodeOptions(model="Host")
        node = session.add_node(CoreNode, options=options)
        session.instantiate()
        output = "hello world"

        # then
        command = f"echo {output}"
        with client.context_connect():
            response = client.node_command(session.id, node.id, command)

        # then
        assert response.output == output

    def test_get_node_terminal(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        options = NodeOptions(model="Host")
        node = session.add_node(CoreNode, options=options)
        session.instantiate()

        # then
        with client.context_connect():
            response = client.get_node_terminal(session.id, node.id)

        # then
        assert response.terminal is not None

    def test_get_hooks(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        file_name = "test"
        file_data = "echo hello"
        session.add_hook(EventTypes.RUNTIME_STATE, file_name, file_data)

        # then
        with client.context_connect():
            response = client.get_hooks(session.id)

        # then
        assert len(response.hooks) == 1
        hook = response.hooks[0]
        assert hook.state == core_pb2.SessionState.RUNTIME
        assert hook.file == file_name
        assert hook.data == file_data

    def test_add_hook(self, grpc_server: CoreGrpcServer):
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

    def test_save_xml(self, grpc_server: CoreGrpcServer, tmpdir: TemporaryFile):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        tmp = tmpdir.join("text.xml")

        # then
        with client.context_connect():
            client.save_xml(session.id, str(tmp))

        # then
        assert tmp.exists()

    def test_open_xml_hook(self, grpc_server: CoreGrpcServer, tmpdir: TemporaryFile):
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

    def test_get_node_links(self, grpc_server: CoreGrpcServer, ip_prefixes: IpPrefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(SwitchNode)
        node = session.add_node(CoreNode)
        iface_data = ip_prefixes.create_iface(node)
        session.add_link(node.id, switch.id, iface_data)

        # then
        with client.context_connect():
            response = client.get_node_links(session.id, switch.id)

        # then
        assert len(response.links) == 1

    def test_get_node_links_exception(
        self, grpc_server: CoreGrpcServer, ip_prefixes: IpPrefixes
    ):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(SwitchNode)
        node = session.add_node(CoreNode)
        iface_data = ip_prefixes.create_iface(node)
        session.add_link(node.id, switch.id, iface_data)

        # then
        with pytest.raises(grpc.RpcError):
            with client.context_connect():
                client.get_node_links(session.id, 3)

    def test_add_link(self, grpc_server: CoreGrpcServer, iface_helper: InterfaceHelper):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(SwitchNode)
        node = session.add_node(CoreNode)
        assert len(switch.all_link_data()) == 0

        # then
        iface = iface_helper.create_iface(node.id, 0)
        with client.context_connect():
            response = client.add_link(session.id, node.id, switch.id, iface)

        # then
        assert response.result is True
        assert len(switch.all_link_data()) == 1

    def test_add_link_exception(
        self, grpc_server: CoreGrpcServer, iface_helper: InterfaceHelper
    ):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)

        # then
        iface = iface_helper.create_iface(node.id, 0)
        with pytest.raises(grpc.RpcError):
            with client.context_connect():
                client.add_link(session.id, 1, 3, iface)

    def test_edit_link(self, grpc_server: CoreGrpcServer, ip_prefixes: IpPrefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        switch = session.add_node(SwitchNode)
        node = session.add_node(CoreNode)
        iface = ip_prefixes.create_iface(node)
        session.add_link(node.id, switch.id, iface)
        options = core_pb2.LinkOptions(bandwidth=30000)
        link = switch.all_link_data()[0]
        assert options.bandwidth != link.options.bandwidth

        # then
        with client.context_connect():
            response = client.edit_link(
                session.id, node.id, switch.id, options, iface1_id=iface.id
            )

        # then
        assert response.result is True
        link = switch.all_link_data()[0]
        assert options.bandwidth == link.options.bandwidth

    def test_delete_link(self, grpc_server: CoreGrpcServer, ip_prefixes: IpPrefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node1 = session.add_node(CoreNode)
        iface1 = ip_prefixes.create_iface(node1)
        node2 = session.add_node(CoreNode)
        iface2 = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface1, iface2)
        link_node = None
        for node_id in session.nodes:
            node = session.nodes[node_id]
            if node.id not in {node1.id, node2.id}:
                link_node = node
                break
        assert len(link_node.all_link_data()) == 1

        # then
        with client.context_connect():
            response = client.delete_link(
                session.id, node1.id, node2.id, iface1.id, iface2.id
            )

        # then
        assert response.result is True
        assert len(link_node.all_link_data()) == 0

    def test_get_wlan_config(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(WlanNode)

        # then
        with client.context_connect():
            response = client.get_wlan_config(session.id, wlan.id)

        # then
        assert len(response.config) > 0

    def test_set_wlan_config(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_state(EventTypes.CONFIGURATION_STATE)
        wlan = session.add_node(WlanNode)
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

    def test_get_emane_config(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_emane_config(session.id)

        # then
        assert len(response.config) > 0

    def test_set_emane_config(self, grpc_server: CoreGrpcServer):
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

    def test_get_emane_model_configs(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions(emane=EmaneIeee80211abgModel.name)
        emane_network = session.add_node(EmaneNet, options=options)
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
        assert model_config.iface_id == -1

    def test_set_emane_model_config(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions(emane=EmaneIeee80211abgModel.name)
        emane_network = session.add_node(EmaneNet, options=options)
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

    def test_get_emane_model_config(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions(emane=EmaneIeee80211abgModel.name)
        emane_network = session.add_node(EmaneNet, options=options)
        session.emane.set_model(emane_network, EmaneIeee80211abgModel)

        # then
        with client.context_connect():
            response = client.get_emane_model_config(
                session.id, emane_network.id, EmaneIeee80211abgModel.name
            )

        # then
        assert len(response.config) > 0

    def test_get_emane_models(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_emane_models(session.id)

        # then
        assert len(response.models) > 0

    def test_get_mobility_configs(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(WlanNode)
        session.mobility.set_model_config(wlan.id, Ns2ScriptedMobility.name, {})

        # then
        with client.context_connect():
            response = client.get_mobility_configs(session.id)

        # then
        assert len(response.configs) > 0
        assert wlan.id in response.configs
        mapped_config = response.configs[wlan.id]
        assert len(mapped_config.config) > 0

    def test_get_mobility_config(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(WlanNode)
        session.mobility.set_model_config(wlan.id, Ns2ScriptedMobility.name, {})

        # then
        with client.context_connect():
            response = client.get_mobility_config(session.id, wlan.id)

        # then
        assert len(response.config) > 0

    def test_set_mobility_config(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(WlanNode)
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

    def test_mobility_action(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(WlanNode)
        session.mobility.set_model_config(wlan.id, Ns2ScriptedMobility.name, {})
        session.instantiate()

        # then
        with client.context_connect():
            response = client.mobility_action(session.id, wlan.id, MobilityAction.STOP)

        # then
        assert response.result is True

    def test_get_services(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()

        # then
        with client.context_connect():
            response = client.get_services()

        # then
        assert len(response.services) > 0

    def test_get_service_defaults(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_service_defaults(session.id)

        # then
        assert len(response.defaults) > 0

    def test_set_service_defaults(self, grpc_server: CoreGrpcServer):
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

    def test_get_node_service_configs(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
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

    def test_get_node_service(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)

        # then
        with client.context_connect():
            response = client.get_node_service(session.id, node.id, "DefaultRoute")

        # then
        assert len(response.service.configs) > 0

    def test_get_node_service_file(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)

        # then
        with client.context_connect():
            response = client.get_node_service_file(
                session.id, node.id, "DefaultRoute", "defaultroute.sh"
            )

        # then
        assert response.data is not None

    def test_set_node_service(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
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

    def test_set_node_service_file(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
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

    def test_service_action(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
        service_name = "DefaultRoute"

        # then
        with client.context_connect():
            response = client.service_action(
                session.id, node.id, service_name, ServiceAction.STOP
            )

        # then
        assert response.result is True

    def test_node_events(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
        node.position.lat = 10.0
        node.position.lon = 20.0
        node.position.alt = 5.0
        queue = Queue()

        def handle_event(event_data):
            assert event_data.session_id == session.id
            assert event_data.HasField("node_event")
            event_node = event_data.node_event.node
            assert event_node.geo.lat == node.position.lat
            assert event_node.geo.lon == node.position.lon
            assert event_node.geo.alt == node.position.alt
            queue.put(event_data)

        # then
        with client.context_connect():
            client.events(session.id, handle_event)
            time.sleep(0.1)
            session.broadcast_node(node)

            # then
            queue.get(timeout=5)

    def test_link_events(self, grpc_server: CoreGrpcServer, ip_prefixes: IpPrefixes):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        wlan = session.add_node(WlanNode)
        node = session.add_node(CoreNode)
        iface = ip_prefixes.create_iface(node)
        session.add_link(node.id, wlan.id, iface)
        link_data = wlan.all_link_data()[0]
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

    def test_throughputs(self, request, grpc_server: CoreGrpcServer):
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

    def test_session_events(self, grpc_server: CoreGrpcServer):
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

    def test_config_events(self, grpc_server: CoreGrpcServer):
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

    def test_exception_events(self, grpc_server: CoreGrpcServer):
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
            session.exception(exception_level, source, text, node_id)

            # then
            queue.get(timeout=5)

    def test_file_events(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
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

    def test_move_nodes(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
        x, y = 10.0, 15.0

        def move_iter():
            yield core_pb2.MoveNodesRequest(
                session_id=session.id,
                node_id=node.id,
                position=core_pb2.Position(x=x, y=y),
            )

        # then
        with client.context_connect():
            client.move_nodes(move_iter())

        # assert
        assert node.position.x == x
        assert node.position.y == y

    def test_move_nodes_geo(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        node = session.add_node(CoreNode)
        lon, lat, alt = 10.0, 15.0, 5.0
        queue = Queue()

        def node_handler(node_data: NodeData):
            n = node_data.node
            assert n.position.lon == lon
            assert n.position.lat == lat
            assert n.position.alt == alt
            queue.put(node_data)

        session.node_handlers.append(node_handler)

        def move_iter():
            yield core_pb2.MoveNodesRequest(
                session_id=session.id,
                node_id=node.id,
                geo=core_pb2.Geo(lon=lon, lat=lat, alt=alt),
            )

        # then
        with client.context_connect():
            client.move_nodes(move_iter())

        # assert
        assert node.position.lon == lon
        assert node.position.lat == lat
        assert node.position.alt == alt
        assert queue.get(timeout=5)

    def test_move_nodes_exception(self, grpc_server: CoreGrpcServer):
        # given
        client = CoreGrpcClient()
        grpc_server.coreemu.create_session()

        def move_iter():
            yield core_pb2.MoveNodesRequest()

        # then
        with pytest.raises(grpc.RpcError):
            with client.context_connect():
                client.move_nodes(move_iter())
