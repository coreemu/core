"""
Tests for testing tlv message handling.
"""
import os
import time

import mock
import pytest
from mock import MagicMock

from core.api.tlv import coreapi
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.enumerations import (
    ConfigFlags,
    ConfigTlvs,
    EventTlvs,
    EventTypes,
    ExecuteTlvs,
    FileTlvs,
    LinkTlvs,
    MessageFlags,
    NodeTlvs,
    NodeTypes,
    RegisterTlvs,
    SessionTlvs,
)
from core.errors import CoreError
from core.location.mobility import BasicRangeModel
from core.nodes.ipaddress import Ipv4Prefix


def dict_to_str(values):
    return "|".join(f"{x}={values[x]}" for x in values)


class TestGui:
    @pytest.mark.parametrize(
        "node_type, model",
        [
            (NodeTypes.DEFAULT, "PC"),
            (NodeTypes.EMANE, None),
            (NodeTypes.HUB, None),
            (NodeTypes.SWITCH, None),
            (NodeTypes.WIRELESS_LAN, None),
            (NodeTypes.TUNNEL, None),
            (NodeTypes.RJ45, None),
        ],
    )
    def test_node_add(self, cored, node_type, model):
        node_id = 1
        message = coreapi.CoreNodeMessage.create(
            MessageFlags.ADD.value,
            [
                (NodeTlvs.NUMBER, node_id),
                (NodeTlvs.TYPE, node_type.value),
                (NodeTlvs.NAME, "n1"),
                (NodeTlvs.X_POSITION, 0),
                (NodeTlvs.Y_POSITION, 0),
                (NodeTlvs.MODEL, model),
            ],
        )

        cored.request_handler.handle_message(message)

        assert cored.session.get_node(node_id) is not None

    def test_node_update(self, cored):
        node_id = 1
        cored.session.add_node(_id=node_id)
        x = 50
        y = 100
        message = coreapi.CoreNodeMessage.create(
            0,
            [
                (NodeTlvs.NUMBER, node_id),
                (NodeTlvs.X_POSITION, x),
                (NodeTlvs.Y_POSITION, y),
            ],
        )

        cored.request_handler.handle_message(message)

        node = cored.session.get_node(node_id)
        assert node is not None
        assert node.position.x == x
        assert node.position.y == y

    def test_node_delete(self, cored):
        node_id = 1
        cored.session.add_node(_id=node_id)
        message = coreapi.CoreNodeMessage.create(
            MessageFlags.DELETE.value, [(NodeTlvs.NUMBER, node_id)]
        )

        cored.request_handler.handle_message(message)

        with pytest.raises(CoreError):
            cored.session.get_node(node_id)

    def test_link_add_node_to_net(self, cored):
        node_one = 1
        cored.session.add_node(_id=node_one)
        switch = 2
        cored.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, switch),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.INTERFACE1_IP4, interface_one),
                (LinkTlvs.INTERFACE1_IP4_MASK, 24),
            ],
        )

        cored.request_handler.handle_message(message)

        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

    def test_link_add_net_to_node(self, cored):
        node_one = 1
        cored.session.add_node(_id=node_one)
        switch = 2
        cored.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, switch),
                (LinkTlvs.N2_NUMBER, node_one),
                (LinkTlvs.INTERFACE2_NUMBER, 0),
                (LinkTlvs.INTERFACE2_IP4, interface_one),
                (LinkTlvs.INTERFACE2_IP4_MASK, 24),
            ],
        )

        cored.request_handler.handle_message(message)

        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

    def test_link_add_node_to_node(self, cored):
        node_one = 1
        cored.session.add_node(_id=node_one)
        node_two = 2
        cored.session.add_node(_id=node_two)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        interface_two = ip_prefix.addr(node_two)
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, node_two),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.INTERFACE1_IP4, interface_one),
                (LinkTlvs.INTERFACE1_IP4_MASK, 24),
                (LinkTlvs.INTERFACE2_NUMBER, 0),
                (LinkTlvs.INTERFACE2_IP4, interface_two),
                (LinkTlvs.INTERFACE2_IP4_MASK, 24),
            ],
        )

        cored.request_handler.handle_message(message)

        all_links = []
        for node_id in cored.session.nodes:
            node = cored.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 1

    def test_link_update(self, cored):
        node_one = 1
        cored.session.add_node(_id=node_one)
        switch = 2
        cored.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, switch),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.INTERFACE1_IP4, interface_one),
                (LinkTlvs.INTERFACE1_IP4_MASK, 24),
            ],
        )
        cored.request_handler.handle_message(message)
        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1
        link = all_links[0]
        assert link.bandwidth is None

        bandwidth = 50000
        message = coreapi.CoreLinkMessage.create(
            0,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, switch),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.BANDWIDTH, bandwidth),
            ],
        )
        cored.request_handler.handle_message(message)

        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1
        link = all_links[0]
        assert link.bandwidth == bandwidth

    def test_link_delete_node_to_node(self, cored):
        node_one = 1
        cored.session.add_node(_id=node_one)
        node_two = 2
        cored.session.add_node(_id=node_two)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        interface_two = ip_prefix.addr(node_two)
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, node_two),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.INTERFACE1_IP4, interface_one),
                (LinkTlvs.INTERFACE1_IP4_MASK, 24),
                (LinkTlvs.INTERFACE2_IP4, interface_two),
                (LinkTlvs.INTERFACE2_IP4_MASK, 24),
            ],
        )
        cored.request_handler.handle_message(message)
        all_links = []
        for node_id in cored.session.nodes:
            node = cored.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(
            MessageFlags.DELETE.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, node_two),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.INTERFACE2_NUMBER, 0),
            ],
        )
        cored.request_handler.handle_message(message)

        all_links = []
        for node_id in cored.session.nodes:
            node = cored.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 0

    def test_link_delete_node_to_net(self, cored):
        node_one = 1
        cored.session.add_node(_id=node_one)
        switch = 2
        cored.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, switch),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.INTERFACE1_IP4, interface_one),
                (LinkTlvs.INTERFACE1_IP4_MASK, 24),
            ],
        )
        cored.request_handler.handle_message(message)
        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(
            MessageFlags.DELETE.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, switch),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
            ],
        )
        cored.request_handler.handle_message(message)

        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 0

    def test_link_delete_net_to_node(self, cored):
        node_one = 1
        cored.session.add_node(_id=node_one)
        switch = 2
        cored.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node_one),
                (LinkTlvs.N2_NUMBER, switch),
                (LinkTlvs.INTERFACE1_NUMBER, 0),
                (LinkTlvs.INTERFACE1_IP4, interface_one),
                (LinkTlvs.INTERFACE1_IP4_MASK, 24),
            ],
        )
        cored.request_handler.handle_message(message)
        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(
            MessageFlags.DELETE.value,
            [
                (LinkTlvs.N1_NUMBER, switch),
                (LinkTlvs.N2_NUMBER, node_one),
                (LinkTlvs.INTERFACE2_NUMBER, 0),
            ],
        )
        cored.request_handler.handle_message(message)

        switch_node = cored.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 0

    def test_session_update(self, cored):
        session_id = cored.session.id
        name = "test"
        message = coreapi.CoreSessionMessage.create(
            0, [(SessionTlvs.NUMBER, str(session_id)), (SessionTlvs.NAME, name)]
        )

        cored.request_handler.handle_message(message)

        assert cored.session.name == name

    def test_session_query(self, cored):
        cored.request_handler.dispatch_replies = mock.MagicMock()
        message = coreapi.CoreSessionMessage.create(MessageFlags.STRING.value, [])

        cored.request_handler.handle_message(message)

        args, _ = cored.request_handler.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_session_join(self, cored):
        cored.request_handler.dispatch_replies = mock.MagicMock()
        session_id = cored.session.id
        message = coreapi.CoreSessionMessage.create(
            MessageFlags.ADD.value, [(SessionTlvs.NUMBER, str(session_id))]
        )

        cored.request_handler.handle_message(message)

        assert cored.request_handler.session.id == session_id

    def test_session_delete(self, cored):
        assert len(cored.server.coreemu.sessions) == 1
        session_id = cored.session.id
        message = coreapi.CoreSessionMessage.create(
            MessageFlags.DELETE.value, [(SessionTlvs.NUMBER, str(session_id))]
        )

        cored.request_handler.handle_message(message)

        assert len(cored.server.coreemu.sessions) == 0

    def test_file_hook_add(self, cored):
        state = EventTypes.DATACOLLECT_STATE.value
        assert cored.session._hooks.get(state) is None
        file_name = "test.sh"
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(
            MessageFlags.ADD.value,
            [
                (FileTlvs.TYPE, f"hook:{state}"),
                (FileTlvs.NAME, file_name),
                (FileTlvs.DATA, file_data),
            ],
        )

        cored.request_handler.handle_message(message)

        hooks = cored.session._hooks.get(state)
        assert len(hooks) == 1
        name, data = hooks[0]
        assert file_name == name
        assert file_data == data

    def test_file_service_file_set(self, cored):
        node = cored.session.add_node()
        service = "DefaultRoute"
        file_name = "defaultroute.sh"
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(
            MessageFlags.ADD.value,
            [
                (FileTlvs.NODE, node.id),
                (FileTlvs.TYPE, f"service:{service}"),
                (FileTlvs.NAME, file_name),
                (FileTlvs.DATA, file_data),
            ],
        )

        cored.request_handler.handle_message(message)

        service_file = cored.session.services.get_service_file(node, service, file_name)
        assert file_data == service_file.data

    def test_file_node_file_copy(self, request, cored):
        file_name = "/var/log/test/node.log"
        node = cored.session.add_node()
        node.makenodedir()
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(
            MessageFlags.ADD.value,
            [
                (FileTlvs.NODE, node.id),
                (FileTlvs.NAME, file_name),
                (FileTlvs.DATA, file_data),
            ],
        )

        cored.request_handler.handle_message(message)

        if not request.config.getoption("mock"):
            directory, basename = os.path.split(file_name)
            created_directory = directory[1:].replace("/", ".")
            create_path = os.path.join(node.nodedir, created_directory, basename)
            assert os.path.exists(create_path)

    def test_exec_node_tty(self, cored):
        cored.request_handler.dispatch_replies = mock.MagicMock()
        node = cored.session.add_node()
        message = coreapi.CoreExecMessage.create(
            MessageFlags.TTY.value,
            [
                (ExecuteTlvs.NODE, node.id),
                (ExecuteTlvs.NUMBER, 1),
                (ExecuteTlvs.COMMAND, "bash"),
            ],
        )

        cored.request_handler.handle_message(message)

        args, _ = cored.request_handler.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_exec_local_command(self, request, cored):
        if request.config.getoption("mock"):
            pytest.skip("mocking calls")

        cored.request_handler.dispatch_replies = mock.MagicMock()
        node = cored.session.add_node()
        cmd = "echo hello"
        message = coreapi.CoreExecMessage.create(
            MessageFlags.TEXT.value | MessageFlags.LOCAL.value,
            [
                (ExecuteTlvs.NODE, node.id),
                (ExecuteTlvs.NUMBER, 1),
                (ExecuteTlvs.COMMAND, cmd),
            ],
        )

        cored.request_handler.handle_message(message)

        args, _ = cored.request_handler.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_exec_node_command(self, cored):
        cored.request_handler.dispatch_replies = mock.MagicMock()
        node = cored.session.add_node()
        cmd = "echo hello"
        message = coreapi.CoreExecMessage.create(
            MessageFlags.TEXT.value,
            [
                (ExecuteTlvs.NODE, node.id),
                (ExecuteTlvs.NUMBER, 1),
                (ExecuteTlvs.COMMAND, cmd),
            ],
        )
        node.cmd = MagicMock(return_value="hello")

        cored.request_handler.handle_message(message)

        node.cmd.assert_called_with(cmd)

    @pytest.mark.parametrize(
        "state",
        [
            EventTypes.SHUTDOWN_STATE,
            EventTypes.RUNTIME_STATE,
            EventTypes.DATACOLLECT_STATE,
            EventTypes.CONFIGURATION_STATE,
            EventTypes.DEFINITION_STATE,
        ],
    )
    def test_event_state(self, cored, state):
        message = coreapi.CoreEventMessage.create(0, [(EventTlvs.TYPE, state.value)])

        cored.request_handler.handle_message(message)

        assert cored.session.state == state.value

    def test_event_schedule(self, cored):
        cored.session.add_event = mock.MagicMock()
        node = cored.session.add_node()
        message = coreapi.CoreEventMessage.create(
            MessageFlags.ADD.value,
            [
                (EventTlvs.TYPE, EventTypes.SCHEDULED.value),
                (EventTlvs.TIME, str(time.time() + 100)),
                (EventTlvs.NODE, node.id),
                (EventTlvs.NAME, "event"),
                (EventTlvs.DATA, "data"),
            ],
        )

        cored.request_handler.handle_message(message)

        cored.session.add_event.assert_called_once()

    def test_event_save_xml(self, cored, tmpdir):
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        cored.session.add_node()
        message = coreapi.CoreEventMessage.create(
            0,
            [(EventTlvs.TYPE, EventTypes.FILE_SAVE.value), (EventTlvs.NAME, file_path)],
        )

        cored.request_handler.handle_message(message)

        assert os.path.exists(file_path)

    def test_event_open_xml(self, cored, tmpdir):
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        node = cored.session.add_node()
        cored.session.save_xml(file_path)
        cored.session.delete_node(node.id)
        message = coreapi.CoreEventMessage.create(
            0,
            [(EventTlvs.TYPE, EventTypes.FILE_OPEN.value), (EventTlvs.NAME, file_path)],
        )

        cored.request_handler.handle_message(message)

        assert cored.session.get_node(node.id)

    @pytest.mark.parametrize(
        "state",
        [
            EventTypes.START,
            EventTypes.STOP,
            EventTypes.RESTART,
            EventTypes.PAUSE,
            EventTypes.RECONFIGURE,
        ],
    )
    def test_event_service(self, cored, state):
        cored.session.broadcast_event = mock.MagicMock()
        node = cored.session.add_node()
        node.startup()
        message = coreapi.CoreEventMessage.create(
            0,
            [
                (EventTlvs.TYPE, state.value),
                (EventTlvs.NODE, node.id),
                (EventTlvs.NAME, "service:DefaultRoute"),
            ],
        )

        cored.request_handler.handle_message(message)

        cored.session.broadcast_event.assert_called_once()

    @pytest.mark.parametrize(
        "state",
        [
            EventTypes.START,
            EventTypes.STOP,
            EventTypes.RESTART,
            EventTypes.PAUSE,
            EventTypes.RECONFIGURE,
        ],
    )
    def test_event_mobility(self, cored, state):
        message = coreapi.CoreEventMessage.create(
            0, [(EventTlvs.TYPE, state.value), (EventTlvs.NAME, "mobility:ns2script")]
        )

        cored.request_handler.handle_message(message)

    def test_register_gui(self, cored):
        cored.request_handler.master = False
        message = coreapi.CoreRegMessage.create(0, [(RegisterTlvs.GUI, "gui")])

        cored.request_handler.handle_message(message)

        assert cored.request_handler.master is True

    def test_register_xml(self, cored, tmpdir):
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        node = cored.session.add_node()
        cored.session.save_xml(file_path)
        cored.session.delete_node(node.id)
        message = coreapi.CoreRegMessage.create(
            0, [(RegisterTlvs.EXECUTE_SERVER, file_path)]
        )
        cored.session.instantiate()

        cored.request_handler.handle_message(message)

        assert cored.server.coreemu.sessions[2].get_node(node.id)

    def test_register_python(self, cored, tmpdir):
        xml_file = tmpdir.join("test.py")
        file_path = xml_file.strpath
        with open(file_path, "w") as f:
            f.write("coreemu = globals()['coreemu']\n")
            f.write("session = coreemu.sessions[1]\n")
            f.write("session.add_node()\n")
        message = coreapi.CoreRegMessage.create(
            0, [(RegisterTlvs.EXECUTE_SERVER, file_path)]
        )
        cored.session.instantiate()

        cored.request_handler.handle_message(message)

        assert len(cored.session.nodes) == 1

    def test_config_all(self, cored):
        node = cored.session.add_node()
        message = coreapi.CoreConfMessage.create(
            MessageFlags.ADD.value,
            [
                (ConfigTlvs.OBJECT, "all"),
                (ConfigTlvs.NODE, node.id),
                (ConfigTlvs.TYPE, ConfigFlags.RESET.value),
            ],
        )
        cored.session.location.refxyz = (10, 10, 10)

        cored.request_handler.handle_message(message)

        assert cored.session.location.refxyz == (0, 0, 0)

    def test_config_options_request(self, cored):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "session"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        cored.request_handler.handle_broadcast_config = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.request_handler.handle_broadcast_config.assert_called_once()

    def test_config_options_update(self, cored):
        test_key = "test"
        test_value = "test"
        values = {test_key: test_value}
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "session"),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, dict_to_str(values)),
            ],
        )

        cored.request_handler.handle_message(message)

        assert cored.session.options.get_config(test_key) == test_value

    def test_config_location_reset(self, cored):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "location"),
                (ConfigTlvs.TYPE, ConfigFlags.RESET.value),
            ],
        )
        cored.session.location.refxyz = (10, 10, 10)

        cored.request_handler.handle_message(message)

        assert cored.session.location.refxyz == (0, 0, 0)

    def test_config_location_update(self, cored):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "location"),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, "10|10|70|50|0|0.5"),
            ],
        )

        cored.request_handler.handle_message(message)

        assert cored.session.location.refxyz == (10, 10, 0.0)
        assert cored.session.location.refgeo == (70, 50, 0)
        assert cored.session.location.refscale == 0.5

    def test_config_metadata_request(self, cored):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "metadata"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        cored.request_handler.handle_broadcast_config = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.request_handler.handle_broadcast_config.assert_called_once()

    def test_config_metadata_update(self, cored):
        test_key = "test"
        test_value = "test"
        values = {test_key: test_value}
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "metadata"),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, dict_to_str(values)),
            ],
        )

        cored.request_handler.handle_message(message)

        assert cored.session.metadata.get_config(test_key) == test_value

    def test_config_broker_request(self, cored):
        server = "test"
        host = "10.0.0.1"
        port = 50000
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "broker"),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, f"{server}:{host}:{port}"),
            ],
        )
        cored.session.distributed.add_server = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.session.distributed.add_server.assert_called_once_with(server, host)

    def test_config_services_request_all(self, cored):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        cored.request_handler.handle_broadcast_config = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.request_handler.handle_broadcast_config.assert_called_once()

    def test_config_services_request_specific(self, cored):
        node = cored.session.add_node()
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, node.id),
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
                (ConfigTlvs.OPAQUE, "service:DefaultRoute"),
            ],
        )
        cored.request_handler.handle_broadcast_config = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.request_handler.handle_broadcast_config.assert_called_once()

    def test_config_services_request_specific_file(self, cored):
        node = cored.session.add_node()
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, node.id),
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
                (ConfigTlvs.OPAQUE, "service:DefaultRoute:defaultroute.sh"),
            ],
        )
        cored.session.broadcast_file = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.session.broadcast_file.assert_called_once()

    def test_config_services_reset(self, cored):
        node = cored.session.add_node()
        service = "DefaultRoute"
        cored.session.services.set_service(node.id, service)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.RESET.value),
            ],
        )
        assert cored.session.services.get_service(node.id, service) is not None

        cored.request_handler.handle_message(message)

        assert cored.session.services.get_service(node.id, service) is None

    def test_config_services_set(self, cored):
        node = cored.session.add_node()
        service = "DefaultRoute"
        values = {"meta": "metadata"}
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, node.id),
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.OPAQUE, f"service:{service}"),
                (ConfigTlvs.VALUES, dict_to_str(values)),
            ],
        )
        assert cored.session.services.get_service(node.id, service) is None

        cored.request_handler.handle_message(message)

        assert cored.session.services.get_service(node.id, service) is not None

    def test_config_mobility_reset(self, cored):
        wlan = cored.session.add_node(_type=NodeTypes.WIRELESS_LAN)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "MobilityManager"),
                (ConfigTlvs.TYPE, ConfigFlags.RESET.value),
            ],
        )
        cored.session.mobility.set_model_config(wlan.id, BasicRangeModel.name, {})
        assert len(cored.session.mobility.node_configurations) == 1

        cored.request_handler.handle_message(message)

        assert len(cored.session.mobility.node_configurations) == 0

    def test_config_mobility_model_request(self, cored):
        wlan = cored.session.add_node(_type=NodeTypes.WIRELESS_LAN)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, wlan.id),
                (ConfigTlvs.OBJECT, BasicRangeModel.name),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        cored.request_handler.handle_broadcast_config = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.request_handler.handle_broadcast_config.assert_called_once()

    def test_config_mobility_model_update(self, cored):
        wlan = cored.session.add_node(_type=NodeTypes.WIRELESS_LAN)
        config_key = "range"
        config_value = "1000"
        values = {config_key: config_value}
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, wlan.id),
                (ConfigTlvs.OBJECT, BasicRangeModel.name),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, dict_to_str(values)),
            ],
        )

        cored.request_handler.handle_message(message)

        config = cored.session.mobility.get_model_config(wlan.id, BasicRangeModel.name)
        assert config[config_key] == config_value

    def test_config_emane_model_request(self, cored):
        wlan = cored.session.add_node(_type=NodeTypes.WIRELESS_LAN)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, wlan.id),
                (ConfigTlvs.OBJECT, EmaneIeee80211abgModel.name),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        cored.request_handler.handle_broadcast_config = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.request_handler.handle_broadcast_config.assert_called_once()

    def test_config_emane_model_update(self, cored):
        wlan = cored.session.add_node(_type=NodeTypes.WIRELESS_LAN)
        config_key = "distance"
        config_value = "50051"
        values = {config_key: config_value}
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, wlan.id),
                (ConfigTlvs.OBJECT, EmaneIeee80211abgModel.name),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, dict_to_str(values)),
            ],
        )

        cored.request_handler.handle_message(message)

        config = cored.session.emane.get_model_config(
            wlan.id, EmaneIeee80211abgModel.name
        )
        assert config[config_key] == config_value

    def test_config_emane_request(self, cored):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "emane"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        cored.request_handler.handle_broadcast_config = mock.MagicMock()

        cored.request_handler.handle_message(message)

        cored.request_handler.handle_broadcast_config.assert_called_once()

    def test_config_emane_update(self, cored):
        config_key = "eventservicedevice"
        config_value = "eth4"
        values = {config_key: config_value}
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "emane"),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, dict_to_str(values)),
            ],
        )

        cored.request_handler.handle_message(message)

        config = cored.session.emane.get_configs()
        assert config[config_key] == config_value
