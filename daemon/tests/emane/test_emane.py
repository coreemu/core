"""
Unit tests for testing CORE EMANE networks.
"""
from pathlib import Path
from tempfile import TemporaryFile
from typing import Type
from xml.etree import ElementTree

import pytest

from core import utils
from core.emane.emanemodel import EmaneModel
from core.emane.models.bypass import EmaneBypassModel
from core.emane.models.commeffect import EmaneCommEffectModel
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel
from core.emane.models.rfpipe import EmaneRfPipeModel
from core.emane.models.tdma import EmaneTdmaModel
from core.emane.nodes import EmaneNet
from core.emulator.data import IpPrefixes, NodeOptions
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
_DIR: Path = Path(__file__).resolve().parent
_SCHEDULE: Path = _DIR / "../../examples/tdma/schedule.xml"


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
    def test_two_emane_interfaces(self, session: Session):
        """
        Test nodes running multiple emane interfaces.

        :param core.emulator.coreemu.EmuSession session: session for test
        """
        # create emane node for networking the core nodes
        session.set_location(47.57917, -122.13232, 2.00000, 1.0)
        options = NodeOptions()
        options.set_position(80, 50)
        options.emane = EmaneIeee80211abgModel.name
        emane_net1 = session.add_node(EmaneNet, options=options)
        options.emane = EmaneRfPipeModel.name
        emane_net2 = session.add_node(EmaneNet, options=options)

        # create nodes
        options = NodeOptions(model="mdr")
        options.set_position(150, 150)
        node1 = session.add_node(CoreNode, options=options)
        options.set_position(300, 150)
        node2 = session.add_node(CoreNode, options=options)

        # create interfaces
        ip_prefix1 = IpPrefixes("10.0.0.0/24")
        ip_prefix2 = IpPrefixes("10.0.1.0/24")
        for i, node in enumerate([node1, node2]):
            node.setposition(x=150 * (i + 1), y=150)
            iface_data = ip_prefix1.create_iface(node)
            session.add_link(node.id, emane_net1.id, iface1_data=iface_data)
            iface_data = ip_prefix2.create_iface(node)
            session.add_link(node.id, emane_net2.id, iface1_data=iface_data)

        # instantiate session
        session.instantiate()

        # ping node2 from node1 on both interfaces and check success
        status = ping(node1, node2, ip_prefix1, count=5)
        assert not status
        status = ping(node1, node2, ip_prefix2, count=5)
        assert not status

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
        options = NodeOptions(emane=model.name)
        options.set_position(80, 50)
        emane_network = session.add_node(EmaneNet, options=options)

        # configure tdma
        if model == EmaneTdmaModel:
            session.emane.set_config(
                emane_network.id, EmaneTdmaModel.name, {"schedule": str(_SCHEDULE)}
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
        options = NodeOptions(emane=EmaneIeee80211abgModel.name)
        options.set_position(80, 50)
        emane_network = session.add_node(EmaneNet, options=options)
        config_key = "txpower"
        config_value = "10"
        session.emane.set_config(
            emane_network.id, EmaneIeee80211abgModel.name, {config_key: config_value}
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
        session.save_xml(Path(file_path))

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
        session.open_xml(Path(file_path), start=True)

        # retrieve configuration we set originally
        config = session.emane.get_config(emane_id, EmaneIeee80211abgModel.name)
        value = config[config_key]

        # verify nodes and configuration were restored
        assert session.get_node(node1_id, CoreNode)
        assert session.get_node(node2_id, CoreNode)
        assert session.get_node(emane_id, EmaneNet)
        assert value == config_value

    def test_xml_emane_node_config(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        # create nodes
        options = NodeOptions(model="mdr", x=50, y=50)
        node1 = session.add_node(CoreNode, options=options)
        iface1_data = ip_prefixes.create_iface(node1)
        node2 = session.add_node(CoreNode, options=options)
        iface2_data = ip_prefixes.create_iface(node2)

        # create emane node
        options = NodeOptions(model=None, emane=EmaneRfPipeModel.name)
        emane_node = session.add_node(EmaneNet, options=options)

        # create links
        session.add_link(node1.id, emane_node.id, iface1_data)
        session.add_link(node2.id, emane_node.id, iface2_data)

        # set node specific config
        datarate = "101"
        session.emane.set_config(
            node1.id, EmaneRfPipeModel.name, {"datarate": datarate}
        )

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(Path(file_path))

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # verify nodes have been removed from session
        with pytest.raises(CoreError):
            assert not session.get_node(node1.id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(node2.id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(emane_node.id, EmaneNet)

        # load saved xml
        session.open_xml(Path(file_path), start=True)

        # verify nodes have been recreated
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(node2.id, CoreNode)
        assert session.get_node(emane_node.id, EmaneNet)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.links()
        assert len(links) == 2
        config = session.emane.get_config(node1.id, EmaneRfPipeModel.name)
        assert config["datarate"] == datarate

    def test_xml_emane_interface_config(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        # create nodes
        options = NodeOptions(model="mdr", x=50, y=50)
        node1 = session.add_node(CoreNode, options=options)
        iface1_data = ip_prefixes.create_iface(node1)
        node2 = session.add_node(CoreNode, options=options)
        iface2_data = ip_prefixes.create_iface(node2)

        # create emane node
        options = NodeOptions(model=None, emane=EmaneRfPipeModel.name)
        emane_node = session.add_node(EmaneNet, options=options)

        # create links
        session.add_link(node1.id, emane_node.id, iface1_data)
        session.add_link(node2.id, emane_node.id, iface2_data)

        # set node specific conifg
        datarate = "101"
        config_id = utils.iface_config_id(node1.id, iface1_data.id)
        session.emane.set_config(
            config_id, EmaneRfPipeModel.name, {"datarate": datarate}
        )

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(Path(file_path))

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # verify nodes have been removed from session
        with pytest.raises(CoreError):
            assert not session.get_node(node1.id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(node2.id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(emane_node.id, EmaneNet)

        # load saved xml
        session.open_xml(Path(file_path), start=True)

        # verify nodes have been recreated
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(node2.id, CoreNode)
        assert session.get_node(emane_node.id, EmaneNet)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.links()
        assert len(links) == 2
        config = session.emane.get_config(config_id, EmaneRfPipeModel.name)
        assert config["datarate"] == datarate
