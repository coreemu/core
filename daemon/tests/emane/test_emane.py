"""
Unit tests for testing CORE EMANE networks.
"""
import os
from tempfile import TemporaryFile
from typing import Type
from xml.etree import ElementTree

import pytest

from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.emanemodel import EmaneModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNet
from core.emane.rfpipe import EmaneRfPipeModel
from core.emane.tdma import EmaneTdmaModel
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.session import Session
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNode

_EMANE_MODELS = [
    EmaneIeee80211abgModel,
    EmaneRfPipeModel,
    EmaneBypassModel,
    EmaneCommEffectModel,
    EmaneTdmaModel,
]
_DIR = os.path.dirname(os.path.abspath(__file__))


def ping(
    from_node: CoreNode, to_node: CoreNode, ip_prefixes: IpPrefixes, count: int = 3
):
    address = ip_prefixes.ip4_address(to_node.id)
    try:
        from_node.cmd(f"ping -c {count} {address}")
        status = 0
    except CoreCommandError as e:
        status = e.returncode
    return status


class TestEmane:
    @pytest.mark.parametrize("model", _EMANE_MODELS)
    def test_models(
        self, session: Session, model: Type[EmaneModel], ip_prefixes: IpPrefixes
    ):
        """
        Test emane models within a basic network.

        :param core.emulator.coreemu.EmuSession session: session for test
        :param model: emane model to test
        :param ip_prefixes: generates ip addresses for nodes
        """

        # create emane node for networking the core nodes
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions()
        options.set_position(80, 50)
        emane_network = session.add_node(EmaneNet, options=options)
        session.emane.set_model(emane_network, model)

        # configure tdma
        if model == EmaneTdmaModel:
            session.emane.set_model_config(
                emane_network.id,
                EmaneTdmaModel.name,
                {"schedule": os.path.join(_DIR, "../../examples/tdma/schedule.xml")},
            )

        # create nodes
        options = NodeOptions(model="mdr")
        options.set_position(150, 150)
        node1 = session.add_node(CoreNode, options=options)
        options.set_position(300, 150)
        node2 = session.add_node(CoreNode, options=options)

        for i, node in enumerate([node1, node2]):
            node.setposition(x=150 * (i + 1), y=150)
            iface_data = ip_prefixes.create_iface(node)
            session.add_link(node.id, emane_network.id, iface1_data=iface_data)

        # instantiate session
        session.instantiate()

        # ping node2 from node1 and assert success
        status = ping(node1, node2, ip_prefixes, count=5)
        assert not status

    def test_xml_emane(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for emane.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create emane node for networking the core nodes
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions()
        options.set_position(80, 50)
        emane_network = session.add_node(EmaneNet, options=options)
        config_key = "txpower"
        config_value = "10"
        session.emane.set_model(
            emane_network, EmaneIeee80211abgModel, {config_key: config_value}
        )

        # create nodes
        options = NodeOptions(model="mdr")
        options.set_position(150, 150)
        node1 = session.add_node(CoreNode, options=options)
        options.set_position(300, 150)
        node2 = session.add_node(CoreNode, options=options)

        for i, node in enumerate([node1, node2]):
            node.setposition(x=150 * (i + 1), y=150)
            iface_data = ip_prefixes.create_iface(node)
            session.add_link(node.id, emane_network.id, iface1_data=iface_data)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        emane_id = emane_network.id
        node1_id = node1.id
        node2_id = node2.id

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(file_path)

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # verify nodes have been removed from session
        with pytest.raises(CoreError):
            assert not session.get_node(node1_id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(node2_id, CoreNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(
            session.emane.get_config(config_key, emane_id, EmaneIeee80211abgModel.name)
        )

        # verify nodes and configuration were restored
        assert session.get_node(node1_id, CoreNode)
        assert session.get_node(node2_id, CoreNode)
        assert session.get_node(emane_id, EmaneNet)
        assert value == config_value
