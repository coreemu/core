from pathlib import Path
from tempfile import TemporaryFile
from xml.etree import ElementTree

import pytest

from core.emulator.data import IpPrefixes, LinkOptions
from core.emulator.enumerations import EventTypes
from core.emulator.session import Session
from core.errors import CoreError
from core.location.mobility import BasicRangeModel
from core.nodes.base import CoreNode
from core.nodes.network import SwitchNode, WlanNode
from core.services.utility import SshService


class TestXml:
    def test_xml_hooks(self, session: Session, tmpdir: TemporaryFile):
        """
        Test save/load hooks in xml.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        """
        # create hooks
        file_name = "runtime_hook.sh"
        data = "#!/bin/sh\necho hello"
        state = EventTypes.RUNTIME_STATE
        session.add_hook(state, file_name, data)

        file_name = "instantiation_hook.sh"
        data = "#!/bin/sh\necho hello"
        state = EventTypes.INSTANTIATION_STATE
        session.add_hook(state, file_name, data)

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        runtime_hooks = session.hooks.get(state)
        assert runtime_hooks
        runtime_hook = runtime_hooks[0]
        assert file_name == runtime_hook[0]
        assert data == runtime_hook[1]

    def test_xml_ptp(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)

        # link nodes
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface1_data, iface2_data)

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

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
        # verify no links are known
        assert len(session.link_manager.links()) == 0

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(node2.id, CoreNode)
        assert len(session.link_manager.links()) == 1

    def test_xml_ptp_services(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for a ptp neetwork.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node1 = session.add_node(CoreNode)
        node2 = session.add_node(CoreNode)

        # link nodes to ptp net
        iface1_data = ip_prefixes.create_iface(node1)
        iface2_data = ip_prefixes.create_iface(node2)
        session.add_link(node1.id, node2.id, iface1_data, iface2_data)

        # set custom values for node service
        session.services.set_service(node1.id, SshService.name)
        service_file = SshService.configs[0]
        file_data = "# test"
        session.services.set_service_file(
            node1.id, SshService.name, service_file, file_data
        )

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

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

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve custom service
        service = session.services.get_service(node1.id, SshService.name)

        # verify nodes have been recreated
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(node2.id, CoreNode)
        assert service.config_data.get(service_file) == file_data

    def test_xml_mobility(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for mobility.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create wlan
        wlan = session.add_node(WlanNode)
        session.mobility.set_model(wlan, BasicRangeModel, {"test": "1"})

        # create nodes
        options = CoreNode.create_options()
        options.model = "mdr"
        node1 = session.add_node(CoreNode, options=options)
        node2 = session.add_node(CoreNode, options=options)

        # link nodes
        for node in [node1, node2]:
            iface_data = ip_prefixes.create_iface(node)
            session.add_link(node.id, wlan.id, iface1_data=iface_data)

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

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

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(session.mobility.get_config("test", wlan.id, BasicRangeModel.name))

        # verify nodes and configuration were restored
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(node2.id, CoreNode)
        assert session.get_node(wlan.id, WlanNode)
        assert value == "1"

    def test_network_to_network(self, session: Session, tmpdir: TemporaryFile):
        """
        Test xml generation when dealing with network to network nodes.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        """
        # create nodes
        switch1 = session.add_node(SwitchNode)
        switch2 = session.add_node(SwitchNode)

        # link nodes
        session.add_link(switch1.id, switch2.id)

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # verify nodes have been removed from session
        with pytest.raises(CoreError):
            assert not session.get_node(switch1.id, SwitchNode)
        with pytest.raises(CoreError):
            assert not session.get_node(switch2.id, SwitchNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        switch1 = session.get_node(switch1.id, SwitchNode)
        switch2 = session.get_node(switch2.id, SwitchNode)
        assert switch1
        assert switch2
        assert len(session.link_manager.links()) == 1

    def test_link_options(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node1 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        switch = session.add_node(SwitchNode)

        # create link
        options = LinkOptions()
        options.loss = 10.5
        options.bandwidth = 50000
        options.jitter = 10
        options.delay = 30
        options.dup = 5
        options.buffer = 100
        session.add_link(node1.id, switch.id, iface1_data, options=options)

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # verify nodes have been removed from session
        with pytest.raises(CoreError):
            assert not session.get_node(node1.id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(switch.id, SwitchNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(switch.id, SwitchNode)
        assert len(session.link_manager.links()) == 1
        link = list(session.link_manager.links())[0]
        link_options = link.options()
        assert options.loss == link_options.loss
        assert options.bandwidth == link_options.bandwidth
        assert options.jitter == link_options.jitter
        assert options.delay == link_options.delay
        assert options.dup == link_options.dup
        assert options.buffer == link_options.buffer

    def test_link_options_ptp(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node1 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        node2 = session.add_node(CoreNode)
        iface2_data = ip_prefixes.create_iface(node2)

        # create link
        options = LinkOptions()
        options.loss = 10.5
        options.bandwidth = 50000
        options.jitter = 10
        options.delay = 30
        options.dup = 5
        options.buffer = 100
        session.add_link(node1.id, node2.id, iface1_data, iface2_data, options)

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

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

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(node2.id, CoreNode)
        assert len(session.link_manager.links()) == 1
        link = list(session.link_manager.links())[0]
        link_options = link.options()
        assert options.loss == link_options.loss
        assert options.bandwidth == link_options.bandwidth
        assert options.jitter == link_options.jitter
        assert options.delay == link_options.delay
        assert options.dup == link_options.dup
        assert options.buffer == link_options.buffer

    def test_link_options_bidirectional(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node1 = session.add_node(CoreNode)
        iface1_data = ip_prefixes.create_iface(node1)
        node2 = session.add_node(CoreNode)
        iface2_data = ip_prefixes.create_iface(node2)

        # create link
        options1 = LinkOptions()
        options1.unidirectional = 1
        options1.bandwidth = 5000
        options1.delay = 10
        options1.loss = 10.5
        options1.dup = 5
        options1.jitter = 5
        options1.buffer = 50
        iface1, iface2 = session.add_link(
            node1.id, node2.id, iface1_data, iface2_data, options1
        )
        options2 = LinkOptions()
        options2.unidirectional = 1
        options2.bandwidth = 10000
        options2.delay = 20
        options2.loss = 10
        options2.dup = 10
        options2.jitter = 10
        options2.buffer = 100
        session.update_link(node2.id, node1.id, iface2.id, iface1.id, options2)

        # instantiate session
        session.instantiate()

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = Path(xml_file.strpath)
        session.save_xml(file_path)

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

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(node1.id, CoreNode)
        assert session.get_node(node2.id, CoreNode)
        assert len(session.link_manager.links()) == 1
        assert options1.bandwidth == iface1.options.bandwidth
        assert options1.delay == iface1.options.delay
        assert options1.loss == iface1.options.loss
        assert options1.dup == iface1.options.dup
        assert options1.jitter == iface1.options.jitter
        assert options1.buffer == iface1.options.buffer
        assert options2.bandwidth == iface2.options.bandwidth
        assert options2.delay == iface2.options.delay
        assert options2.loss == iface2.options.loss
        assert options2.dup == iface2.options.dup
        assert options2.jitter == iface2.options.jitter
        assert options2.buffer == iface2.options.buffer
