import pytest

from core.emulator.data import InterfaceData, NodeOptions
from core.emulator.session import Session
from core.errors import CoreError
from core.nodes.base import CoreNode
from core.nodes.network import HubNode, SwitchNode, WlanNode

MODELS = ["router", "host", "PC", "mdr"]
NET_TYPES = [SwitchNode, HubNode, WlanNode]


class TestNodes:
    @pytest.mark.parametrize("model", MODELS)
    def test_node_add(self, session: Session, model: str):
        # given
        options = NodeOptions(model=model)

        # when
        node = session.add_node(CoreNode, options=options)

        # then
        assert node
        assert node.alive()
        assert node.up

    def test_node_update(self, session: Session):
        # given
        node = session.add_node(CoreNode)
        position_value = 100
        update_options = NodeOptions()
        update_options.set_position(x=position_value, y=position_value)

        # when
        session.edit_node(node.id, update_options)

        # then
        assert node.position.x == position_value
        assert node.position.y == position_value

    def test_node_delete(self, session: Session):
        # given
        node = session.add_node(CoreNode)

        # when
        session.delete_node(node.id)

        # then
        with pytest.raises(CoreError):
            session.get_node(node.id, CoreNode)

    def test_node_set_mac(self, session: Session):
        # given
        node = session.add_node(CoreNode)
        switch = session.add_node(SwitchNode)
        iface_data = InterfaceData()
        iface = node.new_iface(switch, iface_data)
        mac = "aa:aa:aa:ff:ff:ff"

        # when
        node.set_mac(iface.node_id, mac)

        # then
        assert iface.mac == mac

    def test_node_set_mac_exception(self, session: Session):
        # given
        node = session.add_node(CoreNode)
        switch = session.add_node(SwitchNode)
        iface_data = InterfaceData()
        iface = node.new_iface(switch, iface_data)
        mac = "aa:aa:aa:ff:ff:fff"

        # when
        with pytest.raises(CoreError):
            node.set_mac(iface.node_id, mac)

    def test_node_addaddr(self, session: Session):
        # given
        node = session.add_node(CoreNode)
        switch = session.add_node(SwitchNode)
        iface_data = InterfaceData()
        iface = node.new_iface(switch, iface_data)
        addr = "192.168.0.1/24"

        # when
        node.addaddr(iface.node_id, addr)

        # then
        assert iface.addrlist[0] == addr

    def test_node_addaddr_exception(self, session):
        # given
        node = session.add_node(CoreNode)
        switch = session.add_node(SwitchNode)
        iface_data = InterfaceData()
        iface = node.new_iface(switch, iface_data)
        addr = "256.168.0.1/24"

        # when
        with pytest.raises(CoreError):
            node.addaddr(iface.node_id, addr)

    @pytest.mark.parametrize("net_type", NET_TYPES)
    def test_net(self, session, net_type):
        # given

        # when
        node = session.add_node(net_type)

        # then
        assert node
        assert node.up
