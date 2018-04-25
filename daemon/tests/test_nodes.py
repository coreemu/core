import os
import time

import pytest

from core.enumerations import NodeTypes
from core.future.futuredata import NodeOptions
from core.misc import utils

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


class TestNodes:
    @pytest.mark.parametrize("model", MODELS)
    def test_node_add(self, session, model):
        # given
        node_options = NodeOptions(model=model)

        # when
        node = session.add_node(node_options=node_options)

        # give time for node services to boot
        time.sleep(1)

        # then
        assert node
        assert os.path.exists(node.nodedir)
        assert node.alive()
        assert node.up
        assert node.check_cmd(["ip", "addr", "show", "lo"])
        node.validate()

    def test_node_update(self, session):
        # given
        node = session.add_node()
        position_value = 100
        update_options = NodeOptions()
        update_options.set_position(x=position_value, y=position_value)

        # when
        session.update_node(node.objid, update_options)

        # then
        assert node.position.x == position_value
        assert node.position.y == position_value

    def test_node_delete(self, session):
        # given
        node = session.add_node()

        # when
        session.delete_node(node.objid)

        # then
        with pytest.raises(KeyError):
            session.get_object(node.objid)

    @pytest.mark.parametrize("net_type", NET_TYPES)
    def test_net(self, session, net_type):
        # given

        # when
        node = session.add_node(_type=net_type)

        # then
        assert node
        assert node.up
        assert utils.check_cmd(["brctl", "show", node.brname])
