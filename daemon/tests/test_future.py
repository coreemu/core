import os
import time

import pytest

from core.enumerations import NodeTypes, EventTypes
from core.future.coreemu import CoreEmu
from core.future.futuredata import IpPrefixes, NodeOptions, LinkOptions
from core.misc import utils


@pytest.fixture
def future_session():
    # use coreemu and create a session
    coreemu = CoreEmu()
    session = coreemu.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE.value)

    # return created session
    yield session

    # shutdown coreemu
    coreemu.shutdown()


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


class TestFuture:
    @pytest.mark.parametrize("model", MODELS)
    def test_node_add(self, future_session, model):
        # given
        node_options = NodeOptions(_type=NodeTypes.DEFAULT, model=model)

        # when
        node = future_session.add_node(node_options)

        # give time for node services to boot
        time.sleep(1)

        # then
        assert node
        assert os.path.exists(node.nodedir)
        assert node.alive()
        assert node.up
        assert node.check_cmd(["ip", "addr", "show", "lo"])
        node.validate()

    def test_node_update(self, future_session):
        # given
        node_options = NodeOptions(_type=NodeTypes.DEFAULT)
        node = future_session.add_node(node_options)
        position_value = 100
        update_options = NodeOptions(_id=node.objid)
        update_options.set_position(x=position_value, y=position_value)

        # when
        future_session.update_node(update_options)

        # then
        assert node.position.x == position_value
        assert node.position.y == position_value

    def test_node_delete(self, future_session):
        # given
        node_options = NodeOptions(_type=NodeTypes.DEFAULT)
        node = future_session.add_node(node_options)

        # when
        future_session.delete_node(node.objid)

        # then
        with pytest.raises(KeyError):
            future_session.get_object(node.objid)

    @pytest.mark.parametrize("net_type", NET_TYPES)
    def test_net(self, future_session, net_type):
        # given
        node_options = NodeOptions(_type=net_type)

        # when
        node = future_session.add_node(node_options)

        # then
        assert node
        assert node.up
        assert utils.check_cmd(["brctl", "show", node.brname])

    def test_ptp(self, future_session):
        # given
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
        node_options = NodeOptions(_type=NodeTypes.DEFAULT)
        node_one = future_session.add_node(node_options)
        node_two = future_session.add_node(node_options)
        interface_one = prefixes.create_interface(node_one)
        inteface_two = prefixes.create_interface(node_two)

        # when
        future_session.add_link(node_one.objid, node_two.objid, interface_one, inteface_two)

        # then
        assert node_one.netif(interface_one.id)
        assert node_two.netif(inteface_two.id)

    def test_node_to_net(self, future_session):
        # given
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
        node_options = NodeOptions(_type=NodeTypes.DEFAULT)
        node_one = future_session.add_node(node_options)
        node_options = NodeOptions(_type=NodeTypes.SWITCH)
        node_two = future_session.add_node(node_options)
        interface_one = prefixes.create_interface(node_one)

        # when
        future_session.add_link(node_one.objid, node_two.objid, interface_one)

        # then
        assert node_two.all_link_data(0)
        assert node_one.netif(interface_one.id)

    def test_net_to_node(self, future_session):
        # given
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

        node_options = NodeOptions(_type=NodeTypes.SWITCH)
        node_one = future_session.add_node(node_options)
        node_options = NodeOptions(_type=NodeTypes.DEFAULT)
        node_two = future_session.add_node(node_options)
        interface_two = prefixes.create_interface(node_two)

        # when
        future_session.add_link(node_one.objid, node_two.objid, interface_two=interface_two)

        # then
        assert node_one.all_link_data(0)
        assert node_two.netif(interface_two.id)

    def test_net_to_net(self, future_session):
        # given
        node_options = NodeOptions(_type=NodeTypes.SWITCH)
        node_one = future_session.add_node(node_options)
        node_options = NodeOptions(_type=NodeTypes.SWITCH)
        node_two = future_session.add_node(node_options)

        # when
        future_session.add_link(node_one.objid, node_two.objid)

        # then
        assert node_one.all_link_data(0)

    def test_link_update(self, future_session):
        # given
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
        node_options = NodeOptions(_type=NodeTypes.DEFAULT)
        node_one = future_session.add_node(node_options)
        node_options = NodeOptions(_type=NodeTypes.SWITCH)
        node_two = future_session.add_node(node_options)
        interface_one = prefixes.create_interface(node_one)
        future_session.add_link(node_one.objid, node_two.objid, interface_one)
        interface = node_one.netif(interface_one.id)
        output = utils.check_cmd(["tc", "qdisc", "show", "dev", interface.localname])
        assert "delay" not in output
        assert "rate" not in output
        assert "loss" not in output
        assert "duplicate" not in output

        # when
        link_options = LinkOptions()
        link_options.delay = 50
        link_options.bandwidth = 5000000
        link_options.per = 25
        link_options.dup = 25
        future_session.update_link(node_one.objid, node_two.objid,
                                   interface_one_id=interface_one.id, link_options=link_options)

        # then
        output = utils.check_cmd(["tc", "qdisc", "show", "dev", interface.localname])
        assert "delay" in output
        assert "rate" in output
        assert "loss" in output
        assert "duplicate" in output

    def test_link_delete(self, future_session):
        # given
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
        node_options = NodeOptions(_type=NodeTypes.DEFAULT)
        node_one = future_session.add_node(node_options)
        node_two = future_session.add_node(node_options)
        interface_one = prefixes.create_interface(node_one)
        interface_two = prefixes.create_interface(node_two)
        future_session.add_link(node_one.objid, node_two.objid, interface_one, interface_two)
        assert node_one.netif(interface_one.id)
        assert node_two.netif(interface_two.id)
        assert future_session.get_node_count() == 3

        # when
        future_session.delete_link(node_one.objid, node_two.objid, interface_one.id, interface_two.id)

        # then
        assert not node_one.netif(interface_one.id)
        assert not node_two.netif(interface_two.id)
        assert future_session.get_node_count() == 2
