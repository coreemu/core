from tempfile import TemporaryFile
from xml.etree import ElementTree

import pytest

from core.emulator.emudata import IpPrefixes, LinkOptions, NodeOptions
from core.emulator.enumerations import EventTypes
from core.emulator.session import Session
from core.errors import CoreError
from core.location.mobility import BasicRangeModel
from core.nodes.base import CoreNode
from core.nodes.network import PtpNet, SwitchNode, WlanNode
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
        file_path = xml_file.strpath
        session.save_xml(file_path)

        # verify xml file was created and can be parsed
        assert xml_file.isfile()
        assert ElementTree.parse(file_path)

        # stop current session, clearing data
        session.shutdown()

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        runtime_hooks = session._hooks.get(state)
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
        # create ptp
        ptp_node = session.add_node(PtpNet)

        # create nodes
        node_one = session.add_node(CoreNode)
        node_two = session.add_node(CoreNode)

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, ptp_node.id, interface_one=interface)

        # instantiate session
        session.instantiate()

        # get ids for nodes
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
            assert not session.get_node(n1_id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id, CoreNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id, CoreNode)
        assert session.get_node(n2_id, CoreNode)

    def test_xml_ptp_services(
        self, session: Session, tmpdir: TemporaryFile, ip_prefixes: IpPrefixes
    ):
        """
        Test xml client methods for a ptp neetwork.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create ptp
        ptp_node = session.add_node(PtpNet)

        # create nodes
        options = NodeOptions(model="host")
        node_one = session.add_node(CoreNode, options=options)
        node_two = session.add_node(CoreNode)

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, ptp_node.id, interface_one=interface)

        # set custom values for node service
        session.services.set_service(node_one.id, SshService.name)
        service_file = SshService.configs[0]
        file_data = "# test"
        session.services.set_service_file(
            node_one.id, SshService.name, service_file, file_data
        )

        # instantiate session
        session.instantiate()

        # get ids for nodes
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
            assert not session.get_node(n1_id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id, CoreNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve custom service
        service = session.services.get_service(node_one.id, SshService.name)

        # verify nodes have been recreated
        assert session.get_node(n1_id, CoreNode)
        assert session.get_node(n2_id, CoreNode)
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
        wlan_node = session.add_node(WlanNode)
        session.mobility.set_model(wlan_node, BasicRangeModel, {"test": "1"})

        # create nodes
        options = NodeOptions(model="mdr")
        options.set_position(0, 0)
        node_one = session.add_node(CoreNode, options=options)
        node_two = session.add_node(CoreNode, options=options)

        # link nodes
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, wlan_node.id, interface_one=interface)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        wlan_id = wlan_node.id
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
            assert not session.get_node(n1_id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id, CoreNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(session.mobility.get_config("test", wlan_id, BasicRangeModel.name))

        # verify nodes and configuration were restored
        assert session.get_node(n1_id, CoreNode)
        assert session.get_node(n2_id, CoreNode)
        assert session.get_node(wlan_id, WlanNode)
        assert value == "1"

    def test_network_to_network(self, session: Session, tmpdir: TemporaryFile):
        """
        Test xml generation when dealing with network to network nodes.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        """
        # create nodes
        switch_one = session.add_node(SwitchNode)
        switch_two = session.add_node(SwitchNode)

        # link nodes
        session.add_link(switch_one.id, switch_two.id)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        n1_id = switch_one.id
        n2_id = switch_two.id

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
            assert not session.get_node(n1_id, SwitchNode)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id, SwitchNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        switch_one = session.get_node(n1_id, SwitchNode)
        switch_two = session.get_node(n2_id, SwitchNode)
        assert switch_one
        assert switch_two
        assert len(switch_one.all_link_data() + switch_two.all_link_data()) == 1

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
        node_one = session.add_node(CoreNode)
        interface_one = ip_prefixes.create_interface(node_one)
        switch = session.add_node(SwitchNode)

        # create link
        link_options = LinkOptions()
        link_options.loss = 10.5
        link_options.bandwidth = 50000
        link_options.jitter = 10
        link_options.delay = 30
        link_options.dup = 5
        session.add_link(node_one.id, switch.id, interface_one, options=link_options)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        n1_id = node_one.id
        n2_id = switch.id

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
            assert not session.get_node(n1_id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id, SwitchNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id, CoreNode)
        assert session.get_node(n2_id, SwitchNode)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.all_link_data()
        link = links[0]
        assert link_options.loss == link.loss
        assert link_options.bandwidth == link.bandwidth
        assert link_options.jitter == link.jitter
        assert link_options.delay == link.delay
        assert link_options.dup == link.dup

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
        node_one = session.add_node(CoreNode)
        interface_one = ip_prefixes.create_interface(node_one)
        node_two = session.add_node(CoreNode)
        interface_two = ip_prefixes.create_interface(node_two)

        # create link
        link_options = LinkOptions()
        link_options.loss = 10.5
        link_options.bandwidth = 50000
        link_options.jitter = 10
        link_options.delay = 30
        link_options.dup = 5
        session.add_link(
            node_one.id, node_two.id, interface_one, interface_two, link_options
        )

        # instantiate session
        session.instantiate()

        # get ids for nodes
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
            assert not session.get_node(n1_id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id, CoreNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id, CoreNode)
        assert session.get_node(n2_id, CoreNode)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.all_link_data()
        link = links[0]
        assert link_options.loss == link.loss
        assert link_options.bandwidth == link.bandwidth
        assert link_options.jitter == link.jitter
        assert link_options.delay == link.delay
        assert link_options.dup == link.dup

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
        node_one = session.add_node(CoreNode)
        interface_one = ip_prefixes.create_interface(node_one)
        node_two = session.add_node(CoreNode)
        interface_two = ip_prefixes.create_interface(node_two)

        # create link
        link_options_one = LinkOptions()
        link_options_one.unidirectional = 1
        link_options_one.bandwidth = 5000
        link_options_one.delay = 10
        link_options_one.loss = 10.5
        link_options_one.dup = 5
        link_options_one.jitter = 5
        session.add_link(
            node_one.id, node_two.id, interface_one, interface_two, link_options_one
        )
        link_options_two = LinkOptions()
        link_options_two.unidirectional = 1
        link_options_two.bandwidth = 10000
        link_options_two.delay = 20
        link_options_two.loss = 10
        link_options_two.dup = 10
        link_options_two.jitter = 10
        session.update_link(
            node_two.id,
            node_one.id,
            interface_two.id,
            interface_one.id,
            link_options_two,
        )

        # instantiate session
        session.instantiate()

        # get ids for nodes
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
            assert not session.get_node(n1_id, CoreNode)
        with pytest.raises(CoreError):
            assert not session.get_node(n2_id, CoreNode)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id, CoreNode)
        assert session.get_node(n2_id, CoreNode)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.all_link_data()
        assert len(links) == 2
        link_one = links[0]
        link_two = links[1]
        assert link_options_one.bandwidth == link_one.bandwidth
        assert link_options_one.delay == link_one.delay
        assert link_options_one.loss == link_one.loss
        assert link_options_one.dup == link_one.dup
        assert link_options_one.jitter == link_one.jitter
        assert link_options_two.bandwidth == link_two.bandwidth
        assert link_options_two.delay == link_two.delay
        assert link_options_two.loss == link_two.loss
        assert link_options_two.dup == link_two.dup
        assert link_options_two.jitter == link_two.jitter
