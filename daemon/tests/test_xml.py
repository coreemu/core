from xml.etree import ElementTree

import pytest
from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.emudata import LinkOptions, NodeOptions
from core.emulator.enumerations import NodeTypes
from core.location.mobility import BasicRangeModel
from core.services.utility import SshService


class TestXml:
    def test_xml_hooks(self, session, tmpdir):
        """
        Test save/load hooks in xml.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        """
        # create hook
        file_name = "runtime_hook.sh"
        data = "#!/bin/sh\necho hello"
        session.set_hook("hook:4", file_name, None, data)

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
        runtime_hooks = session._hooks.get(4)
        assert runtime_hooks
        runtime_hook = runtime_hooks[0]
        assert file_name == runtime_hook[0]
        assert data == runtime_hook[1]

    def test_xml_ptp(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create ptp
        ptp_node = session.add_node(_type=NodeTypes.PEER_TO_PEER)

        # create nodes
        node_one = session.add_node()
        node_two = session.add_node()

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)

    def test_xml_ptp_services(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for a ptp neetwork.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create ptp
        ptp_node = session.add_node(_type=NodeTypes.PEER_TO_PEER)

        # create nodes
        node_options = NodeOptions(model="host")
        node_one = session.add_node(node_options=node_options)
        node_two = session.add_node()

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.id, ptp_node.id, interface_one=interface)

        # set custom values for node service
        session.services.set_service(node_one.id, SshService.name)
        service_file = SshService.configs[0]
        file_data = "# test"
        session.services.set_service_file(node_one.id, SshService.name, service_file, file_data)

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve custom service
        service = session.services.get_service(node_one.id, SshService.name)

        # verify nodes have been recreated
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)
        assert service.config_data.get(service_file) == file_data

    def test_xml_mobility(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for mobility.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create wlan
        wlan_node = session.add_node(_type=NodeTypes.WIRELESS_LAN)
        session.mobility.set_model(wlan_node, BasicRangeModel, {"test": "1"})

        # create nodes
        node_options = NodeOptions()
        node_options.set_position(0, 0)
        node_one = session.create_wireless_node(node_options=node_options)
        node_two = session.create_wireless_node(node_options=node_options)

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(session.mobility.get_config("test", wlan_id, BasicRangeModel.name))

        # verify nodes and configuration were restored
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)
        assert session.get_node(wlan_id)
        assert value == "1"

    def test_xml_emane(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for emane.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create emane node for networking the core nodes
        emane_network = session.create_emane_network(
            EmaneIeee80211abgModel,
            geo_reference=(47.57917, -122.13232, 2.00000),
            config={"test": "1"}
        )
        emane_network.setposition(x=80, y=50)

        # create nodes
        node_options = NodeOptions()
        node_options.set_position(150, 150)
        node_one = session.create_wireless_node(node_options=node_options)
        node_options.set_position(300, 150)
        node_two = session.create_wireless_node(node_options=node_options)

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(session.emane.get_config("test", emane_id, EmaneIeee80211abgModel.name))

        # verify nodes and configuration were restored
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)
        assert session.get_node(emane_id)
        assert value == "1"

    def test_network_to_network(self, session, tmpdir):
        """
        Test xml generation when dealing with network to network nodes.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        """
        # create nodes
        switch_one = session.add_node(_type=NodeTypes.SWITCH)
        switch_two = session.add_node(_type=NodeTypes.SWITCH)

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        switch_one = session.get_node(n1_id)
        switch_two = session.get_node(n2_id)
        assert switch_one
        assert switch_two
        assert len(switch_one.all_link_data(0) + switch_two.all_link_data(0)) == 1

    def test_link_options(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node_one = session.add_node()
        interface_one = ip_prefixes.create_interface(node_one)
        switch = session.add_node(_type=NodeTypes.SWITCH)

        # create link
        link_options = LinkOptions()
        link_options.per = 10.5
        link_options.bandwidth = 50000
        link_options.jitter = 10
        link_options.delay = 30
        link_options.dup = 5
        session.add_link(node_one.id, switch.id, interface_one, link_options=link_options)

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.all_link_data(0)
        link = links[0]
        assert link_options.per == link.per
        assert link_options.bandwidth == link.bandwidth
        assert link_options.jitter == link.jitter
        assert link_options.delay == link.delay
        assert link_options.dup == link.dup

    def test_link_options_ptp(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node_one = session.add_node()
        interface_one = ip_prefixes.create_interface(node_one)
        node_two = session.add_node()
        interface_two = ip_prefixes.create_interface(node_two)

        # create link
        link_options = LinkOptions()
        link_options.per = 10.5
        link_options.bandwidth = 50000
        link_options.jitter = 10
        link_options.delay = 30
        link_options.dup = 5
        session.add_link(node_one.id, node_two.id, interface_one, interface_two, link_options)

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.all_link_data(0)
        link = links[0]
        assert link_options.per == link.per
        assert link_options.bandwidth == link.bandwidth
        assert link_options.jitter == link.jitter
        assert link_options.delay == link.delay
        assert link_options.dup == link.dup

    def test_link_options_bidirectional(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for a ptp network.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param ip_prefixes: generates ip addresses for nodes
        """
        # create nodes
        node_one = session.add_node()
        interface_one = ip_prefixes.create_interface(node_one)
        node_two = session.add_node()
        interface_two = ip_prefixes.create_interface(node_two)

        # create link
        link_options_one = LinkOptions()
        link_options_one.unidirectional = 1
        link_options_one.bandwidth = 5000
        link_options_one.delay = 10
        link_options_one.per = 10.5
        link_options_one.dup = 5
        link_options_one.jitter = 5
        session.add_link(node_one.id, node_two.id, interface_one, interface_two, link_options_one)
        link_options_two = LinkOptions()
        link_options_two.unidirectional = 1
        link_options_two.bandwidth = 10000
        link_options_two.delay = 20
        link_options_two.per = 10
        link_options_two.dup = 10
        link_options_two.jitter = 10
        session.update_link(node_two.id, node_one.id, interface_two.id, interface_one.id, link_options_two)

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
        with pytest.raises(KeyError):
            assert not session.get_node(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_node(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_node(n1_id)
        assert session.get_node(n2_id)
        links = []
        for node_id in session.nodes:
            node = session.nodes[node_id]
            links += node.all_link_data(0)
        assert len(links) == 2
        link_one = links[0]
        link_two = links[1]
        assert link_options_one.bandwidth == link_one.bandwidth
        assert link_options_one.delay == link_one.delay
        assert link_options_one.per == link_one.per
        assert link_options_one.dup == link_one.dup
        assert link_options_one.jitter == link_one.jitter
        assert link_options_two.bandwidth == link_two.bandwidth
        assert link_options_two.delay == link_two.delay
        assert link_options_two.per == link_two.per
        assert link_options_two.dup == link_two.dup
        assert link_options_two.jitter == link_two.jitter
