import pytest

from core.emulator.emudata import NodeOptions
from core.emulator.enumerations import NodeTypes
from core.errors import CoreError

MODELS = ["router", "host", "PC", "mdr"]
NET_TYPES = [NodeTypes.SWITCH, NodeTypes.HUB, NodeTypes.WIRELESS_LAN]


class TestNodes:
    @pytest.mark.parametrize("model", MODELS)
    def test_node_add(self, session, model):
        # given
        options = NodeOptions(model=model)

        # when
        node = session.add_node(options=options)

        # then
        assert node
        assert node.alive()
        assert node.up

    def test_node_update(self, session):
        # given
        node = session.add_node()
        position_value = 100
        update_options = NodeOptions()
        update_options.set_position(x=position_value, y=position_value)

        # when
        session.edit_node(node.id, update_options)

        # then
        assert node.position.x == position_value
        assert node.position.y == position_value

    def test_node_delete(self, session):
        # given
        node = session.add_node()

        # when
        session.delete_node(node.id)

        # then
        with pytest.raises(CoreError):
            session.get_node(node.id)

    @pytest.mark.parametrize("net_type", NET_TYPES)
    def test_net(self, session, net_type):
        # given

        # when
        node = session.add_node(_type=net_type)

        # then
        assert node
        assert node.up
