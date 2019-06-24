"""
Tests for testing tlv message handling.
"""
import os
import time

import mock
import pytest

from core.api.tlv import coreapi
from core.emulator.enumerations import EventTlvs, SessionTlvs, EventTypes, FileTlvs, RegisterTlvs
from core.emulator.enumerations import ExecuteTlvs
from core.emulator.enumerations import LinkTlvs
from core.emulator.enumerations import MessageFlags
from core.emulator.enumerations import NodeTypes, NodeTlvs
from core.nodes.ipaddress import Ipv4Prefix


class TestGui:
    @pytest.mark.parametrize("node_type, model", [
        (NodeTypes.DEFAULT, "PC"),
        (NodeTypes.EMANE, None),
        (NodeTypes.HUB, None),
        (NodeTypes.SWITCH, None),
        (NodeTypes.WIRELESS_LAN, None),
        (NodeTypes.TUNNEL, None),
        (NodeTypes.RJ45, None),
    ])
    def test_node_add(self, coreserver, node_type, model):
        node_id = 1
        message = coreapi.CoreNodeMessage.create(MessageFlags.ADD.value, [
            (NodeTlvs.NUMBER, node_id),
            (NodeTlvs.TYPE, node_type.value),
            (NodeTlvs.NAME, "n1"),
            (NodeTlvs.X_POSITION, 0),
            (NodeTlvs.Y_POSITION, 0),
            (NodeTlvs.MODEL, model),
        ])

        coreserver.request_handler.handle_message(message)

        assert coreserver.session.get_node(node_id) is not None

    def test_node_update(self, coreserver):
        node_id = 1
        coreserver.session.add_node(_id=node_id)
        x = 50
        y = 100
        message = coreapi.CoreNodeMessage.create(0, [
            (NodeTlvs.NUMBER, node_id),
            (NodeTlvs.X_POSITION, x),
            (NodeTlvs.Y_POSITION, y),
        ])

        coreserver.request_handler.handle_message(message)

        node = coreserver.session.get_node(node_id)
        assert node is not None
        assert node.position.x == x
        assert node.position.y == y

    def test_node_delete(self, coreserver):
        node_id = 1
        coreserver.session.add_node(_id=node_id)
        message = coreapi.CoreNodeMessage.create(MessageFlags.DELETE.value, [
            (NodeTlvs.NUMBER, node_id),
        ])

        coreserver.request_handler.handle_message(message)

        with pytest.raises(KeyError):
            coreserver.session.get_node(node_id)

    def test_link_add_node_to_net(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])

        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

    def test_link_add_net_to_node(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, switch),
            (LinkTlvs.N2_NUMBER, node_one),
            (LinkTlvs.INTERFACE2_NUMBER, 0),
            (LinkTlvs.INTERFACE2_IP4, interface_one),
            (LinkTlvs.INTERFACE2_IP4_MASK, 24),
        ])

        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

    def test_link_add_node_to_node(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        node_two = 2
        coreserver.session.add_node(_id=node_two)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        interface_two = ip_prefix.addr(node_two)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, node_two),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
            (LinkTlvs.INTERFACE2_NUMBER, 0),
            (LinkTlvs.INTERFACE2_IP4, interface_two),
            (LinkTlvs.INTERFACE2_IP4_MASK, 24),
        ])

        coreserver.request_handler.handle_message(message)

        all_links = []
        for node_id in coreserver.session.nodes:
            node = coreserver.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 1

    def test_link_update(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1
        link = all_links[0]
        assert link.bandwidth is None

        bandwidth = 50000
        message = coreapi.CoreLinkMessage.create(0, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.BANDWIDTH, bandwidth),
        ])
        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1
        link = all_links[0]
        assert link.bandwidth == bandwidth

    def test_link_delete_node_to_node(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        node_two = 2
        coreserver.session.add_node(_id=node_two)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        interface_two = ip_prefix.addr(node_two)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, node_two),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
            (LinkTlvs.INTERFACE2_IP4, interface_two),
            (LinkTlvs.INTERFACE2_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        all_links = []
        for node_id in coreserver.session.nodes:
            node = coreserver.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(MessageFlags.DELETE.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, node_two),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE2_NUMBER, 0),
        ])
        coreserver.request_handler.handle_message(message)

        all_links = []
        for node_id in coreserver.session.nodes:
            node = coreserver.session.nodes[node_id]
            all_links += node.all_link_data(0)
        assert len(all_links) == 0

    def test_link_delete_node_to_net(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(MessageFlags.DELETE.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
        ])
        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 0

    def test_link_delete_net_to_node(self, coreserver):
        node_one = 1
        coreserver.session.add_node(_id=node_one)
        switch = 2
        coreserver.session.add_node(_id=switch, _type=NodeTypes.SWITCH)
        ip_prefix = Ipv4Prefix("10.0.0.0/24")
        interface_one = ip_prefix.addr(node_one)
        message = coreapi.CoreLinkMessage.create(MessageFlags.ADD.value, [
            (LinkTlvs.N1_NUMBER, node_one),
            (LinkTlvs.N2_NUMBER, switch),
            (LinkTlvs.INTERFACE1_NUMBER, 0),
            (LinkTlvs.INTERFACE1_IP4, interface_one),
            (LinkTlvs.INTERFACE1_IP4_MASK, 24),
        ])
        coreserver.request_handler.handle_message(message)
        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(MessageFlags.DELETE.value, [
            (LinkTlvs.N1_NUMBER, switch),
            (LinkTlvs.N2_NUMBER, node_one),
            (LinkTlvs.INTERFACE2_NUMBER, 0),
        ])
        coreserver.request_handler.handle_message(message)

        switch_node = coreserver.session.get_node(switch)
        all_links = switch_node.all_link_data(0)
        assert len(all_links) == 0

    def test_session_update(self, coreserver):
        session_id = coreserver.session.id
        name = "test"
        message = coreapi.CoreSessionMessage.create(0, [
            (SessionTlvs.NUMBER, str(session_id)),
            (SessionTlvs.NAME, name),
        ])

        coreserver.request_handler.handle_message(message)

        assert coreserver.session.name == name

    def test_session_query(self, coreserver):
        coreserver.request_handler.dispatch_replies = mock.MagicMock()
        message = coreapi.CoreSessionMessage.create(MessageFlags.STRING.value, [])

        coreserver.request_handler.handle_message(message)

        args, _ = coreserver.request_handler.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_session_join(self, coreserver):
        coreserver.request_handler.dispatch_replies = mock.MagicMock()
        session_id = coreserver.session.id
        message = coreapi.CoreSessionMessage.create(MessageFlags.ADD.value, [
            (SessionTlvs.NUMBER, str(session_id)),
        ])

        coreserver.request_handler.handle_message(message)

        assert coreserver.request_handler.session.id == session_id

    def test_session_delete(self, coreserver):
        assert len(coreserver.server.coreemu.sessions) == 1
        session_id = coreserver.session.id
        message = coreapi.CoreSessionMessage.create(MessageFlags.DELETE.value, [
            (SessionTlvs.NUMBER, str(session_id)),
        ])

        coreserver.request_handler.handle_message(message)

        assert len(coreserver.server.coreemu.sessions) == 0

    def test_file_hook_add(self, coreserver):
        state = EventTypes.DATACOLLECT_STATE.value
        assert coreserver.session._hooks.get(state) is None
        file_name = "test.sh"
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(MessageFlags.ADD.value, [
            (FileTlvs.TYPE, "hook:%s" % state),
            (FileTlvs.NAME, file_name),
            (FileTlvs.DATA, file_data),
        ])

        coreserver.request_handler.handle_message(message)

        hooks = coreserver.session._hooks.get(state)
        assert len(hooks) == 1
        name, data = hooks[0]
        assert file_name == name
        assert file_data == data

    def test_file_service_file_set(self, coreserver):
        node = coreserver.session.add_node()
        service = "DefaultRoute"
        file_name = "defaultroute.sh"
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(MessageFlags.ADD.value, [
            (FileTlvs.NODE, node.id),
            (FileTlvs.TYPE, "service:%s" % service),
            (FileTlvs.NAME, file_name),
            (FileTlvs.DATA, file_data),
        ])

        coreserver.request_handler.handle_message(message)

        service_file = coreserver.session.services.get_service_file(node, service, file_name)
        assert file_data == service_file.data

    def test_file_node_file_copy(self, coreserver):
        file_name = "/var/log/test/node.log"
        node = coreserver.session.add_node()
        node.makenodedir()
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(MessageFlags.ADD.value, [
            (FileTlvs.NODE, node.id),
            (FileTlvs.NAME, file_name),
            (FileTlvs.DATA, file_data),
        ])

        coreserver.request_handler.handle_message(message)

        directory, basename = os.path.split(file_name)
        created_directory = directory[1:].replace("/", ".")
        create_path = os.path.join(node.nodedir, created_directory, basename)
        assert os.path.exists(create_path)

    def test_exec_node_tty(self, coreserver):
        coreserver.request_handler.dispatch_replies = mock.MagicMock()
        node = coreserver.session.add_node()
        node.startup()
        message = coreapi.CoreExecMessage.create(MessageFlags.TTY.value, [
            (ExecuteTlvs.NODE, node.id),
            (ExecuteTlvs.NUMBER, 1),
            (ExecuteTlvs.COMMAND, "bash")
        ])

        coreserver.request_handler.handle_message(message)

        args, _ = coreserver.request_handler.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_exec_local_command(self, coreserver):
        coreserver.request_handler.dispatch_replies = mock.MagicMock()
        node = coreserver.session.add_node()
        node.startup()
        message = coreapi.CoreExecMessage.create(
            MessageFlags.TEXT.value | MessageFlags.LOCAL.value, [
                (ExecuteTlvs.NODE, node.id),
                (ExecuteTlvs.NUMBER, 1),
                (ExecuteTlvs.COMMAND, "echo hello")
            ])

        coreserver.request_handler.handle_message(message)

        args, _ = coreserver.request_handler.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_exec_node_command(self, coreserver):
        coreserver.request_handler.dispatch_replies = mock.MagicMock()
        node = coreserver.session.add_node()
        node.startup()
        message = coreapi.CoreExecMessage.create(
            MessageFlags.TEXT.value, [
                (ExecuteTlvs.NODE, node.id),
                (ExecuteTlvs.NUMBER, 1),
                (ExecuteTlvs.COMMAND, "echo hello")
            ])

        coreserver.request_handler.handle_message(message)

        args, _ = coreserver.request_handler.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    @pytest.mark.parametrize("state", [
        EventTypes.SHUTDOWN_STATE,
        EventTypes.RUNTIME_STATE,
        EventTypes.DATACOLLECT_STATE,
        EventTypes.CONFIGURATION_STATE,
        EventTypes.DEFINITION_STATE
    ])
    def test_event_state(self, coreserver, state):
        message = coreapi.CoreEventMessage.create(0, [
            (EventTlvs.TYPE, state.value),
        ])

        coreserver.request_handler.handle_message(message)

        assert coreserver.session.state == state.value

    def test_event_schedule(self, coreserver):
        coreserver.session.add_event = mock.MagicMock()
        node = coreserver.session.add_node()
        message = coreapi.CoreEventMessage.create(MessageFlags.ADD.value, [
            (EventTlvs.TYPE, EventTypes.SCHEDULED.value),
            (EventTlvs.TIME, str(time.time() + 100)),
            (EventTlvs.NODE, node.id),
            (EventTlvs.NAME, "event"),
            (EventTlvs.DATA, "data"),
        ])

        coreserver.request_handler.handle_message(message)

        coreserver.session.add_event.assert_called_once()

    def test_event_save_xml(self, coreserver, tmpdir):
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        coreserver.session.add_node()
        message = coreapi.CoreEventMessage.create(0, [
            (EventTlvs.TYPE, EventTypes.FILE_SAVE.value),
            (EventTlvs.NAME, file_path),
        ])

        coreserver.request_handler.handle_message(message)

        assert os.path.exists(file_path)

    def test_event_open_xml(self, coreserver, tmpdir):
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        node = coreserver.session.add_node()
        coreserver.session.save_xml(file_path)
        coreserver.session.delete_node(node.id)
        message = coreapi.CoreEventMessage.create(0, [
            (EventTlvs.TYPE, EventTypes.FILE_OPEN.value),
            (EventTlvs.NAME, file_path),
        ])

        coreserver.request_handler.handle_message(message)

        assert coreserver.session.get_node(node.id)

    @pytest.mark.parametrize("state", [
        EventTypes.START,
        EventTypes.STOP,
        EventTypes.RESTART,
        EventTypes.PAUSE,
        EventTypes.RECONFIGURE
    ])
    def test_event_service(self, coreserver, state):
        coreserver.session.broadcast_event = mock.MagicMock()
        node = coreserver.session.add_node()
        node.startup()
        message = coreapi.CoreEventMessage.create(0, [
            (EventTlvs.TYPE, state.value),
            (EventTlvs.NODE, node.id),
            (EventTlvs.NAME, "service:DefaultRoute"),
        ])

        coreserver.request_handler.handle_message(message)

        coreserver.session.broadcast_event.assert_called_once()

    @pytest.mark.parametrize("state", [
        EventTypes.START,
        EventTypes.STOP,
        EventTypes.RESTART,
        EventTypes.PAUSE,
        EventTypes.RECONFIGURE
    ])
    def test_event_mobility(self, coreserver, state):
        coreserver.session.broadcast_event = mock.MagicMock()
        message = coreapi.CoreEventMessage.create(0, [
            (EventTlvs.TYPE, state.value),
            (EventTlvs.NAME, "mobility:ns2script"),
        ])

        coreserver.request_handler.handle_message(message)

    def test_register_gui(self, coreserver):
        coreserver.request_handler.master = False
        message = coreapi.CoreRegMessage.create(0, [
            (RegisterTlvs.GUI, "gui"),
        ])

        coreserver.request_handler.handle_message(message)

        assert coreserver.request_handler.master is True

    def test_register_xml(self, coreserver, tmpdir):
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        node = coreserver.session.add_node()
        coreserver.session.save_xml(file_path)
        coreserver.session.delete_node(node.id)
        message = coreapi.CoreRegMessage.create(0, [
            (RegisterTlvs.EXECUTE_SERVER, file_path),
        ])
        coreserver.session.instantiate()

        coreserver.request_handler.handle_message(message)

        assert coreserver.server.coreemu.sessions[2].get_node(node.id)

    def test_register_python(self, coreserver, tmpdir):
        xml_file = tmpdir.join("test.py")
        file_path = xml_file.strpath
        with open(file_path, "w") as f:
            f.write("coreemu = globals()['coreemu']\n")
            f.write("session = coreemu.sessions[1]\n")
            f.write("session.add_node()\n")
        message = coreapi.CoreRegMessage.create(0, [
            (RegisterTlvs.EXECUTE_SERVER, file_path),
        ])
        coreserver.session.instantiate()

        coreserver.request_handler.handle_message(message)

        assert len(coreserver.session.nodes) == 1
