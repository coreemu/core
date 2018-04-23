import os
import time

import pytest

from core.data import NodeData, LinkData
from core.enumerations import NodeTypes, EventTypes
from core.future.coreemu import CoreEmu, FutureIpv4Prefix
from core.misc import utils


@pytest.fixture
def future_session():
    # use coreemu and create a session
    coreemu = CoreEmu()
    session = coreemu.create_session(master=True)
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
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value, model=model)

        # when
        node_id = future_session.node_add(node_data)

        # give time for node services to boot
        time.sleep(1)

        # then
        node = future_session.get_object(node_id)
        assert node
        assert os.path.exists(node.nodedir)
        assert node.alive()
        assert node.up
        assert node.check_cmd(["ip", "addr", "show", "lo"])
        node.validate()

    def test_node_update(self, future_session):
        # given
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_id = future_session.node_add(node_data)
        position_value = 100
        update_data = NodeData(
            id=node_id,
            x_position=position_value,
            y_position=position_value
        )

        # when
        future_session.node_update(update_data)

        # then
        node = future_session.get_object(node_id)
        assert node.position.x == position_value
        assert node.position.y == position_value

    def test_node_delete(self, future_session):
        # given
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_id = future_session.node_add(node_data)

        # when
        future_session.node_delete(node_id)

        # then
        with pytest.raises(KeyError):
            future_session.get_object(node_id)

    @pytest.mark.parametrize("net_type", NET_TYPES)
    def test_net(self, future_session, net_type):
        # given
        node_data = NodeData(node_type=net_type.value)

        # when
        node_id = future_session.node_add(node_data)

        # then
        node = future_session.get_object(node_id)
        assert node
        assert node.up
        assert utils.check_cmd(["brctl", "show", node.brname])

    def test_ptp(self, future_session):
        # given
        prefix = FutureIpv4Prefix("10.83.0.0/16")
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_one_id = future_session.node_add(node_data)
        node_two_id = future_session.node_add(node_data)

        node_one = future_session.get_object(node_one_id)
        inteface_one_index = node_one.newifindex()
        address_one = prefix.addr(node_one_id)

        node_two = future_session.get_object(node_two_id)
        inteface_two_index = node_two.newifindex()
        address_two = prefix.addr(node_two_id)

        link_data = LinkData(
            node1_id=node_one_id,
            node2_id=node_two_id,
            interface1_id=inteface_one_index,
            interface1_ip4=str(address_one),
            interface1_ip4_mask=prefix.prefixlen,
            interface2_id=inteface_two_index,
            interface2_ip4=str(address_two),
            interface2_ip4_mask=prefix.prefixlen,
        )

        # when
        future_session.link_add(link_data)

        # then
        assert node_one.netif(inteface_one_index)
        assert node_two.netif(inteface_two_index)

    def test_node_to_net(self, future_session):
        # given
        prefix = FutureIpv4Prefix("10.83.0.0/16")

        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_one = future_session.node_add(node_data)
        node_data = NodeData(node_type=NodeTypes.SWITCH.value)
        node_two = future_session.node_add(node_data)

        node = future_session.get_object(node_one)
        inteface_index = node.newifindex()
        address = prefix.addr(node_one)

        link_data = LinkData(
            node1_id=node_one,
            node2_id=node_two,
            interface1_id=inteface_index,
            interface1_ip4=str(address),
            interface1_ip4_mask=prefix.prefixlen,
        )

        # when
        future_session.link_add(link_data)

        # then
        node_two = future_session.get_object(node_two)
        assert node_two.all_link_data(0)
        assert node.netif(inteface_index)

    def test_net_to_node(self, future_session):
        # given
        prefix = FutureIpv4Prefix("10.83.0.0/16")

        node_data = NodeData(node_type=NodeTypes.SWITCH.value)
        node_one = future_session.node_add(node_data)
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_two = future_session.node_add(node_data)

        node = future_session.get_object(node_two)
        inteface_index = node.newifindex()
        address = prefix.addr(node_two)

        link_data = LinkData(
            node1_id=node_one,
            node2_id=node_two,
            interface2_id=inteface_index,
            interface2_ip4=str(address),
            interface2_ip4_mask=prefix.prefixlen,
        )

        # when
        future_session.link_add(link_data)

        # then
        node_one = future_session.get_object(node_one)
        assert node_one.all_link_data(0)
        assert node.netif(inteface_index)

    def test_net_to_net(self, future_session):
        # given
        node_data = NodeData(node_type=NodeTypes.SWITCH.value)
        node_one = future_session.node_add(node_data)
        node_data = NodeData(node_type=NodeTypes.SWITCH.value)
        node_two = future_session.node_add(node_data)

        link_data = LinkData(
            node1_id=node_one,
            node2_id=node_two,
        )

        # when
        future_session.link_add(link_data)

        # then
        node_one = future_session.get_object(node_one)
        assert node_one.all_link_data(0)

    def test_link_update(self, future_session):
        # given
        prefix = FutureIpv4Prefix("10.83.0.0/16")
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_one = future_session.node_add(node_data)
        node_data = NodeData(node_type=NodeTypes.SWITCH.value)
        node_two = future_session.node_add(node_data)
        node = future_session.get_object(node_one)
        inteface_index = node.newifindex()
        address = prefix.addr(node_one)
        link_data = LinkData(
            node1_id=node_one,
            node2_id=node_two,
            interface1_id=inteface_index,
            interface1_ip4=str(address),
            interface1_ip4_mask=prefix.prefixlen,
        )
        future_session.link_add(link_data)
        update_data = LinkData(
            node1_id=node_one,
            node2_id=node_two,
            interface1_id=inteface_index,
            delay=50,
            bandwidth=5000000,
            per=25,
            dup=25
        )
        interface = node.netif(inteface_index)
        output = utils.check_cmd(["tc", "qdisc", "show", "dev", interface.localname])
        assert "delay" not in output
        assert "rate" not in output
        assert "loss" not in output
        assert "duplicate" not in output

        # when
        future_session.link_update(update_data)

        # then
        output = utils.check_cmd(["tc", "qdisc", "show", "dev", interface.localname])
        assert "delay" in output
        assert "rate" in output
        assert "loss" in output
        assert "duplicate" in output

    def test_link_delete(self, future_session):
        # given
        prefix = FutureIpv4Prefix("10.83.0.0/16")
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_one_id = future_session.node_add(node_data)
        node_two_id = future_session.node_add(node_data)
        node_one = future_session.get_object(node_one_id)
        inteface_one_index = node_one.newifindex()
        address_one = prefix.addr(node_one_id)
        node_two = future_session.get_object(node_two_id)
        inteface_two_index = node_two.newifindex()
        address_two = prefix.addr(node_two_id)
        link_data = LinkData(
            node1_id=node_one_id,
            node2_id=node_two_id,
            interface1_id=inteface_one_index,
            interface1_ip4=str(address_one),
            interface1_ip4_mask=prefix.prefixlen,
            interface2_id=inteface_two_index,
            interface2_ip4=str(address_two),
            interface2_ip4_mask=prefix.prefixlen,
        )
        future_session.link_add(link_data)
        assert node_one.netif(inteface_one_index)
        assert node_two.netif(inteface_two_index)
        assert future_session.get_node_count() == 3

        # when
        future_session.link_delete(link_data)

        # then
        assert not node_one.netif(inteface_one_index)
        assert not node_two.netif(inteface_two_index)
        assert future_session.get_node_count() == 2
