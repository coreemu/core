"""
Tests for testing tlv message handling.
"""
import time
from pathlib import Path
from typing import Optional

import mock
import netaddr
import pytest
from mock import MagicMock

from core.api.tlv import coreapi
from core.api.tlv.corehandlers import CoreHandler
from core.api.tlv.enumerations import (
    ConfigFlags,
    ConfigTlvs,
    EventTlvs,
    ExecuteTlvs,
    FileTlvs,
    LinkTlvs,
    NodeTlvs,
    SessionTlvs,
)
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.enumerations import EventTypes, MessageFlags, NodeTypes, RegisterTlvs
from core.errors import CoreError
from core.location.mobility import BasicRangeModel
from core.nodes.base import CoreNode, NodeBase
from core.nodes.network import SwitchNode, WlanNode


def dict_to_str(values) -> str:
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
        ],
    )
    def test_node_add(
        self, coretlv: CoreHandler, node_type: NodeTypes, model: Optional[str]
    ):
        node_id = 1
        name = "node1"
        message = coreapi.CoreNodeMessage.create(
            MessageFlags.ADD.value,
            [
                (NodeTlvs.NUMBER, node_id),
                (NodeTlvs.TYPE, node_type.value),
                (NodeTlvs.NAME, name),
                (NodeTlvs.X_POSITION, 0),
                (NodeTlvs.Y_POSITION, 0),
                (NodeTlvs.MODEL, model),
            ],
        )

        coretlv.handle_message(message)
        node = coretlv.session.get_node(node_id, NodeBase)
        assert node
        assert node.name == name

    def test_node_update(self, coretlv: CoreHandler):
        node_id = 1
        coretlv.session.add_node(CoreNode, _id=node_id)
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

        coretlv.handle_message(message)

        node = coretlv.session.get_node(node_id, NodeBase)
        assert node is not None
        assert node.position.x == x
        assert node.position.y == y

    def test_node_delete(self, coretlv: CoreHandler):
        node_id = 1
        coretlv.session.add_node(CoreNode, _id=node_id)
        message = coreapi.CoreNodeMessage.create(
            MessageFlags.DELETE.value, [(NodeTlvs.NUMBER, node_id)]
        )

        coretlv.handle_message(message)

        with pytest.raises(CoreError):
            coretlv.session.get_node(node_id, NodeBase)

    def test_link_add_node_to_net(self, coretlv: CoreHandler):
        node1_id = 1
        coretlv.session.add_node(CoreNode, _id=node1_id)
        switch_id = 2
        coretlv.session.add_node(SwitchNode, _id=switch_id)
        ip_prefix = netaddr.IPNetwork("10.0.0.0/24")
        iface1_ip4 = str(ip_prefix[node1_id])
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, switch_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.IFACE1_IP4, iface1_ip4),
                (LinkTlvs.IFACE1_IP4_MASK, 24),
            ],
        )

        coretlv.handle_message(message)

        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 1

    def test_link_add_net_to_node(self, coretlv: CoreHandler):
        node1_id = 1
        coretlv.session.add_node(CoreNode, _id=node1_id)
        switch_id = 2
        coretlv.session.add_node(SwitchNode, _id=switch_id)
        ip_prefix = netaddr.IPNetwork("10.0.0.0/24")
        iface2_ip4 = str(ip_prefix[node1_id])
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, switch_id),
                (LinkTlvs.N2_NUMBER, node1_id),
                (LinkTlvs.IFACE2_NUMBER, 0),
                (LinkTlvs.IFACE2_IP4, iface2_ip4),
                (LinkTlvs.IFACE2_IP4_MASK, 24),
            ],
        )

        coretlv.handle_message(message)

        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 1

    def test_link_add_node_to_node(self, coretlv: CoreHandler):
        node1_id = 1
        coretlv.session.add_node(CoreNode, _id=node1_id)
        node2_id = 2
        coretlv.session.add_node(CoreNode, _id=node2_id)
        ip_prefix = netaddr.IPNetwork("10.0.0.0/24")
        iface1_ip4 = str(ip_prefix[node1_id])
        iface2_ip4 = str(ip_prefix[node2_id])
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, node2_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.IFACE1_IP4, iface1_ip4),
                (LinkTlvs.IFACE1_IP4_MASK, 24),
                (LinkTlvs.IFACE2_NUMBER, 0),
                (LinkTlvs.IFACE2_IP4, iface2_ip4),
                (LinkTlvs.IFACE2_IP4_MASK, 24),
            ],
        )

        coretlv.handle_message(message)

        all_links = []
        for node_id in coretlv.session.nodes:
            node = coretlv.session.nodes[node_id]
            all_links += node.links()
        assert len(all_links) == 1

    def test_link_update(self, coretlv: CoreHandler):
        node1_id = 1
        coretlv.session.add_node(CoreNode, _id=node1_id)
        switch_id = 2
        coretlv.session.add_node(SwitchNode, _id=switch_id)
        ip_prefix = netaddr.IPNetwork("10.0.0.0/24")
        iface1_ip4 = str(ip_prefix[node1_id])
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, switch_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.IFACE1_IP4, iface1_ip4),
                (LinkTlvs.IFACE1_IP4_MASK, 24),
            ],
        )
        coretlv.handle_message(message)
        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 1
        link = all_links[0]
        assert link.options.bandwidth is None

        bandwidth = 50000
        message = coreapi.CoreLinkMessage.create(
            0,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, switch_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.BANDWIDTH, bandwidth),
            ],
        )
        coretlv.handle_message(message)

        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 1
        link = all_links[0]
        assert link.options.bandwidth == bandwidth

    def test_link_delete_node_to_node(self, coretlv: CoreHandler):
        node1_id = 1
        coretlv.session.add_node(CoreNode, _id=node1_id)
        node2_id = 2
        coretlv.session.add_node(CoreNode, _id=node2_id)
        ip_prefix = netaddr.IPNetwork("10.0.0.0/24")
        iface1_ip4 = str(ip_prefix[node1_id])
        iface2_ip4 = str(ip_prefix[node2_id])
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, node2_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.IFACE1_IP4, iface1_ip4),
                (LinkTlvs.IFACE1_IP4_MASK, 24),
                (LinkTlvs.IFACE2_IP4, iface2_ip4),
                (LinkTlvs.IFACE2_IP4_MASK, 24),
            ],
        )
        coretlv.handle_message(message)
        all_links = []
        for node_id in coretlv.session.nodes:
            node = coretlv.session.nodes[node_id]
            all_links += node.links()
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(
            MessageFlags.DELETE.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, node2_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.IFACE2_NUMBER, 0),
            ],
        )
        coretlv.handle_message(message)

        all_links = []
        for node_id in coretlv.session.nodes:
            node = coretlv.session.nodes[node_id]
            all_links += node.links()
        assert len(all_links) == 0

    def test_link_delete_node_to_net(self, coretlv: CoreHandler):
        node1_id = 1
        coretlv.session.add_node(CoreNode, _id=node1_id)
        switch_id = 2
        coretlv.session.add_node(SwitchNode, _id=switch_id)
        ip_prefix = netaddr.IPNetwork("10.0.0.0/24")
        iface1_ip4 = str(ip_prefix[node1_id])
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, switch_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.IFACE1_IP4, iface1_ip4),
                (LinkTlvs.IFACE1_IP4_MASK, 24),
            ],
        )
        coretlv.handle_message(message)
        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(
            MessageFlags.DELETE.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, switch_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
            ],
        )
        coretlv.handle_message(message)

        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 0

    def test_link_delete_net_to_node(self, coretlv: CoreHandler):
        node1_id = 1
        coretlv.session.add_node(CoreNode, _id=node1_id)
        switch_id = 2
        coretlv.session.add_node(SwitchNode, _id=switch_id)
        ip_prefix = netaddr.IPNetwork("10.0.0.0/24")
        iface1_ip4 = str(ip_prefix[node1_id])
        message = coreapi.CoreLinkMessage.create(
            MessageFlags.ADD.value,
            [
                (LinkTlvs.N1_NUMBER, node1_id),
                (LinkTlvs.N2_NUMBER, switch_id),
                (LinkTlvs.IFACE1_NUMBER, 0),
                (LinkTlvs.IFACE1_IP4, iface1_ip4),
                (LinkTlvs.IFACE1_IP4_MASK, 24),
            ],
        )
        coretlv.handle_message(message)
        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 1

        message = coreapi.CoreLinkMessage.create(
            MessageFlags.DELETE.value,
            [
                (LinkTlvs.N1_NUMBER, switch_id),
                (LinkTlvs.N2_NUMBER, node1_id),
                (LinkTlvs.IFACE2_NUMBER, 0),
            ],
        )
        coretlv.handle_message(message)

        switch_node = coretlv.session.get_node(switch_id, SwitchNode)
        all_links = switch_node.links()
        assert len(all_links) == 0

    def test_session_update(self, coretlv: CoreHandler):
        session_id = coretlv.session.id
        name = "test"
        message = coreapi.CoreSessionMessage.create(
            0, [(SessionTlvs.NUMBER, str(session_id)), (SessionTlvs.NAME, name)]
        )

        coretlv.handle_message(message)

        assert coretlv.session.name == name

    def test_session_query(self, coretlv: CoreHandler):
        coretlv.dispatch_replies = mock.MagicMock()
        message = coreapi.CoreSessionMessage.create(MessageFlags.STRING.value, [])

        coretlv.handle_message(message)

        args, _ = coretlv.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_session_join(self, coretlv: CoreHandler):
        coretlv.dispatch_replies = mock.MagicMock()
        session_id = coretlv.session.id
        message = coreapi.CoreSessionMessage.create(
            MessageFlags.ADD.value, [(SessionTlvs.NUMBER, str(session_id))]
        )

        coretlv.handle_message(message)

        assert coretlv.session.id == session_id

    def test_session_delete(self, coretlv: CoreHandler):
        assert len(coretlv.coreemu.sessions) == 1
        session_id = coretlv.session.id
        message = coreapi.CoreSessionMessage.create(
            MessageFlags.DELETE.value, [(SessionTlvs.NUMBER, str(session_id))]
        )

        coretlv.handle_message(message)

        assert len(coretlv.coreemu.sessions) == 0

    def test_file_hook_add(self, coretlv: CoreHandler):
        state = EventTypes.DATACOLLECT_STATE
        assert coretlv.session.hooks.get(state) is None
        file_name = "test.sh"
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(
            MessageFlags.ADD.value,
            [
                (FileTlvs.TYPE, f"hook:{state.value}"),
                (FileTlvs.NAME, file_name),
                (FileTlvs.DATA, file_data),
            ],
        )

        coretlv.handle_message(message)

        hooks = coretlv.session.hooks.get(state)
        assert len(hooks) == 1
        name, data = hooks[0]
        assert file_name == name
        assert file_data == data

    def test_file_service_file_set(self, coretlv: CoreHandler):
        node = coretlv.session.add_node(CoreNode)
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

        coretlv.handle_message(message)

        service_file = coretlv.session.services.get_service_file(
            node, service, file_name
        )
        assert file_data == service_file.data

    def test_file_node_file_copy(self, request, coretlv: CoreHandler):
        file_path = Path("/var/log/test/node.log")
        node = coretlv.session.add_node(CoreNode)
        node.makenodedir()
        file_data = "echo hello"
        message = coreapi.CoreFileMessage.create(
            MessageFlags.ADD.value,
            [
                (FileTlvs.NODE, node.id),
                (FileTlvs.NAME, str(file_path)),
                (FileTlvs.DATA, file_data),
            ],
        )

        coretlv.handle_message(message)

        if not request.config.getoption("mock"):
            expected_path = node.directory / "var.log/test" / file_path.name
            assert expected_path.exists()

    def test_exec_node_tty(self, coretlv: CoreHandler):
        coretlv.dispatch_replies = mock.MagicMock()
        node = coretlv.session.add_node(CoreNode)
        message = coreapi.CoreExecMessage.create(
            MessageFlags.TTY.value,
            [
                (ExecuteTlvs.NODE, node.id),
                (ExecuteTlvs.NUMBER, 1),
                (ExecuteTlvs.COMMAND, "bash"),
            ],
        )

        coretlv.handle_message(message)

        args, _ = coretlv.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_exec_local_command(self, request, coretlv: CoreHandler):
        if request.config.getoption("mock"):
            pytest.skip("mocking calls")

        coretlv.dispatch_replies = mock.MagicMock()
        node = coretlv.session.add_node(CoreNode)
        cmd = "echo hello"
        message = coreapi.CoreExecMessage.create(
            MessageFlags.TEXT.value | MessageFlags.LOCAL.value,
            [
                (ExecuteTlvs.NODE, node.id),
                (ExecuteTlvs.NUMBER, 1),
                (ExecuteTlvs.COMMAND, cmd),
            ],
        )

        coretlv.handle_message(message)

        args, _ = coretlv.dispatch_replies.call_args
        replies = args[0]
        assert len(replies) == 1

    def test_exec_node_command(self, coretlv: CoreHandler):
        coretlv.dispatch_replies = mock.MagicMock()
        node = coretlv.session.add_node(CoreNode)
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

        coretlv.handle_message(message)

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
    def test_event_state(self, coretlv: CoreHandler, state: EventTypes):
        message = coreapi.CoreEventMessage.create(0, [(EventTlvs.TYPE, state.value)])

        coretlv.handle_message(message)

        assert coretlv.session.state == state

    def test_event_schedule(self, coretlv: CoreHandler):
        coretlv.session.add_event = mock.MagicMock()
        node = coretlv.session.add_node(CoreNode)
        message = coreapi.CoreEventMessage.create(
            MessageFlags.ADD.value,
            [
                (EventTlvs.TYPE, EventTypes.SCHEDULED.value),
                (EventTlvs.TIME, str(time.monotonic() + 100)),
                (EventTlvs.NODE, node.id),
                (EventTlvs.NAME, "event"),
                (EventTlvs.DATA, "data"),
            ],
        )

        coretlv.handle_message(message)

        coretlv.session.add_event.assert_called_once()

    def test_event_save_xml(self, coretlv: CoreHandler, tmpdir):
        xml_file = tmpdir.join("coretlv.session.xml")
        file_path = xml_file.strpath
        coretlv.session.add_node(CoreNode)
        message = coreapi.CoreEventMessage.create(
            0,
            [(EventTlvs.TYPE, EventTypes.FILE_SAVE.value), (EventTlvs.NAME, file_path)],
        )
        coretlv.handle_message(message)
        assert Path(file_path).exists()

    def test_event_open_xml(self, coretlv: CoreHandler, tmpdir):
        xml_file = tmpdir.join("coretlv.session.xml")
        file_path = Path(xml_file.strpath)
        node = coretlv.session.add_node(CoreNode)
        coretlv.session.save_xml(file_path)
        coretlv.session.delete_node(node.id)
        message = coreapi.CoreEventMessage.create(
            0,
            [
                (EventTlvs.TYPE, EventTypes.FILE_OPEN.value),
                (EventTlvs.NAME, str(file_path)),
            ],
        )

        coretlv.handle_message(message)
        assert coretlv.session.get_node(node.id, NodeBase)

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
    def test_event_service(self, coretlv: CoreHandler, state: EventTypes):
        coretlv.session.broadcast_event = mock.MagicMock()
        node = coretlv.session.add_node(CoreNode)
        message = coreapi.CoreEventMessage.create(
            0,
            [
                (EventTlvs.TYPE, state.value),
                (EventTlvs.NODE, node.id),
                (EventTlvs.NAME, "service:DefaultRoute"),
            ],
        )

        coretlv.handle_message(message)

        coretlv.session.broadcast_event.assert_called_once()

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
    def test_event_mobility(self, coretlv: CoreHandler, state: EventTypes):
        message = coreapi.CoreEventMessage.create(
            0, [(EventTlvs.TYPE, state.value), (EventTlvs.NAME, "mobility:ns2script")]
        )

        coretlv.handle_message(message)

    def test_register_gui(self, coretlv: CoreHandler):
        message = coreapi.CoreRegMessage.create(0, [(RegisterTlvs.GUI, "gui")])
        coretlv.handle_message(message)

    def test_register_xml(self, coretlv: CoreHandler, tmpdir):
        xml_file = tmpdir.join("coretlv.session.xml")
        file_path = xml_file.strpath
        node = coretlv.session.add_node(CoreNode)
        coretlv.session.save_xml(file_path)
        coretlv.session.delete_node(node.id)
        message = coreapi.CoreRegMessage.create(
            0, [(RegisterTlvs.EXECUTE_SERVER, file_path)]
        )
        coretlv.session.instantiate()

        coretlv.handle_message(message)

        assert coretlv.coreemu.sessions[1].get_node(node.id, CoreNode)

    def test_register_python(self, coretlv: CoreHandler, tmpdir):
        xml_file = tmpdir.join("test.py")
        file_path = xml_file.strpath
        with open(file_path, "w") as f:
            f.write("from core.nodes.base import CoreNode\n")
            f.write("coreemu = globals()['coreemu']\n")
            f.write(f"session = coreemu.sessions[{coretlv.session.id}]\n")
            f.write("session.add_node(CoreNode)\n")
        message = coreapi.CoreRegMessage.create(
            0, [(RegisterTlvs.EXECUTE_SERVER, file_path)]
        )
        coretlv.session.instantiate()

        coretlv.handle_message(message)

        assert len(coretlv.session.nodes) == 1

    def test_config_all(self, coretlv: CoreHandler):
        message = coreapi.CoreConfMessage.create(
            MessageFlags.ADD.value,
            [(ConfigTlvs.OBJECT, "all"), (ConfigTlvs.TYPE, ConfigFlags.RESET.value)],
        )
        coretlv.session.location.refxyz = (10, 10, 10)

        coretlv.handle_message(message)

        assert coretlv.session.location.refxyz == (0, 0, 0)

    def test_config_options_request(self, coretlv: CoreHandler):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "session"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        coretlv.handle_broadcast_config = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.handle_broadcast_config.assert_called_once()

    def test_config_options_update(self, coretlv: CoreHandler):
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

        coretlv.handle_message(message)

        assert coretlv.session.options.get_config(test_key) == test_value

    def test_config_location_reset(self, coretlv: CoreHandler):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "location"),
                (ConfigTlvs.TYPE, ConfigFlags.RESET.value),
            ],
        )
        coretlv.session.location.refxyz = (10, 10, 10)

        coretlv.handle_message(message)

        assert coretlv.session.location.refxyz == (0, 0, 0)

    def test_config_location_update(self, coretlv: CoreHandler):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "location"),
                (ConfigTlvs.TYPE, ConfigFlags.UPDATE.value),
                (ConfigTlvs.VALUES, "10|10|70|50|0|0.5"),
            ],
        )

        coretlv.handle_message(message)

        assert coretlv.session.location.refxyz == (10, 10, 0.0)
        assert coretlv.session.location.refgeo == (70, 50, 0)
        assert coretlv.session.location.refscale == 0.5

    def test_config_metadata_request(self, coretlv: CoreHandler):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "metadata"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        coretlv.handle_broadcast_config = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.handle_broadcast_config.assert_called_once()

    def test_config_metadata_update(self, coretlv: CoreHandler):
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

        coretlv.handle_message(message)

        assert coretlv.session.metadata[test_key] == test_value

    def test_config_broker_request(self, coretlv: CoreHandler):
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
        coretlv.session.distributed.add_server = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.session.distributed.add_server.assert_called_once_with(server, host)

    def test_config_services_request_all(self, coretlv: CoreHandler):
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        coretlv.handle_broadcast_config = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.handle_broadcast_config.assert_called_once()

    def test_config_services_request_specific(self, coretlv: CoreHandler):
        node = coretlv.session.add_node(CoreNode)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, node.id),
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
                (ConfigTlvs.OPAQUE, "service:DefaultRoute"),
            ],
        )
        coretlv.handle_broadcast_config = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.handle_broadcast_config.assert_called_once()

    def test_config_services_request_specific_file(self, coretlv: CoreHandler):
        node = coretlv.session.add_node(CoreNode)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, node.id),
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
                (ConfigTlvs.OPAQUE, "service:DefaultRoute:defaultroute.sh"),
            ],
        )
        coretlv.session.broadcast_file = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.session.broadcast_file.assert_called_once()

    def test_config_services_reset(self, coretlv: CoreHandler):
        node = coretlv.session.add_node(CoreNode)
        service = "DefaultRoute"
        coretlv.session.services.set_service(node.id, service)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, ConfigFlags.RESET.value),
            ],
        )
        assert coretlv.session.services.get_service(node.id, service) is not None

        coretlv.handle_message(message)

        assert coretlv.session.services.get_service(node.id, service) is None

    def test_config_services_set(self, coretlv: CoreHandler):
        node = coretlv.session.add_node(CoreNode)
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
        assert coretlv.session.services.get_service(node.id, service) is None

        coretlv.handle_message(message)

        assert coretlv.session.services.get_service(node.id, service) is not None

    def test_config_mobility_reset(self, coretlv: CoreHandler):
        wlan = coretlv.session.add_node(WlanNode)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "MobilityManager"),
                (ConfigTlvs.TYPE, ConfigFlags.RESET.value),
            ],
        )
        coretlv.session.mobility.set_model_config(wlan.id, BasicRangeModel.name, {})
        assert len(coretlv.session.mobility.node_configurations) == 1

        coretlv.handle_message(message)

        assert len(coretlv.session.mobility.node_configurations) == 0

    def test_config_mobility_model_request(self, coretlv: CoreHandler):
        wlan = coretlv.session.add_node(WlanNode)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, wlan.id),
                (ConfigTlvs.OBJECT, BasicRangeModel.name),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        coretlv.handle_broadcast_config = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.handle_broadcast_config.assert_called_once()

    def test_config_mobility_model_update(self, coretlv: CoreHandler):
        wlan = coretlv.session.add_node(WlanNode)
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

        coretlv.handle_message(message)

        config = coretlv.session.mobility.get_model_config(
            wlan.id, BasicRangeModel.name
        )
        assert config[config_key] == config_value

    def test_config_emane_model_request(self, coretlv: CoreHandler):
        wlan = coretlv.session.add_node(WlanNode)
        message = coreapi.CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.NODE, wlan.id),
                (ConfigTlvs.OBJECT, EmaneIeee80211abgModel.name),
                (ConfigTlvs.TYPE, ConfigFlags.REQUEST.value),
            ],
        )
        coretlv.handle_broadcast_config = mock.MagicMock()

        coretlv.handle_message(message)

        coretlv.handle_broadcast_config.assert_called_once()

    def test_config_emane_model_update(self, coretlv: CoreHandler):
        wlan = coretlv.session.add_node(WlanNode)
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

        coretlv.handle_message(message)

        config = coretlv.session.emane.get_config(wlan.id, EmaneIeee80211abgModel.name)
        assert config[config_key] == config_value
