"""
Unit tests for testing CORE EMANE networks.
"""
import os
from xml.etree import ElementTree

import pytest

from core.emane.bypass import EmaneBypassModel
from core.emane.commeffect import EmaneCommEffectModel
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emane.rfpipe import EmaneRfPipeModel
from core.emane.tdma import EmaneTdmaModel
from core.emulator.emudata import NodeOptions
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError, CoreError

_EMANE_MODELS = [
    EmaneIeee80211abgModel,
    EmaneRfPipeModel,
    EmaneBypassModel,
    EmaneCommEffectModel,
    EmaneTdmaModel,
]
_DIR = os.path.dirname(os.path.abspath(__file__))


def ping(from_node, to_node, ip_prefixes, count=3):
    address = ip_prefixes.ip4_address(to_node)
    try:
        from_node.cmd(f"ping -c {count} {address}")
        status = 0
    except CoreCommandError as e:
        status = e.returncode
    return status


class TestEmane:
    @pytest.mark.parametrize("model", _EMANE_MODELS)
    def test_models(self, session, model, ip_prefixes):
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
        emane_network = session.add_node(_type=NodeTypes.EMANE, options=options)
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
        node_one = session.add_node(options=options)
        options.set_position(300, 150)
        node_two = session.add_node(options=options)

        for i, node in enumerate([node_one, node_two]):
            node.setposition(x=150 * (i + 1), y=150)
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, emane_network.id, interface_one=interface)

        # instantiate session
        session.instantiate()

        # ping n2 from n1 and assert success
        status = ping(node_one, node_two, ip_prefixes, count=5)
        assert not status

    def test_xml_emane(self, session, tmpdir, ip_prefixes):
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
        emane_network = session.add_node(_type=NodeTypes.EMANE, options=options)
        session.emane.set_model(emane_network, EmaneIeee80211abgModel, {"test": "1"})

        # create nodes
        options = NodeOptions(model="mdr")
        options.set_position(150, 150)
        node_one = session.add_node(options=options)
        options.set_position(300, 150)
        node_two = session.add_node(options=options)

        for i, node in enumerate([node_one, node_two]):
            node.setposition(x=150 * (i + 1), y=150)
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, emane_network.id, interface_one=interface)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        emane_id = emane_network.id
        n1_id = node_one.id
        n2_id = node_two.id

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
            assert not session.get_node(n1_id)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(
            session.emane.get_config("test", emane_id, EmaneIeee80211abgModel.name)
        )

        # verify nodes and configuration were restored
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)
        assert session.get_node(emane_id)
        assert value == "1"
