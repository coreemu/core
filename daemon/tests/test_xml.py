from xml.etree import ElementTree

import pytest

from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.emudata import NodeOptions
from core.enumerations import NodeTypes
from core.mobility import BasicRangeModel
from core.services.utility import SshService


class TestXml:
    def test_xml_hooks(self, session, tmpdir):
        """
        Test save/load hooks in xml.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param str version: xml version to write and parse
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
        :param str version: xml version to write and parse
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
            assert not session.get_object(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_object(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # verify nodes have been recreated
        assert session.get_object(n1_id)
        assert session.get_object(n2_id)

    def test_xml_ptp_services(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for a ptp neetwork.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param str version: xml version to write and parse
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
            assert not session.get_object(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_object(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve custom service
        service = session.services.get_service(node_one.id, SshService.name)

        # verify nodes have been recreated
        assert session.get_object(n1_id)
        assert session.get_object(n2_id)
        assert service.config_data.get(service_file) == file_data

    def test_xml_mobility(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for mobility.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param str version: xml version to write and parse
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
            assert not session.get_object(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_object(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(session.mobility.get_config("test", wlan_id, BasicRangeModel.name))

        # verify nodes and configuration were restored
        assert session.get_object(n1_id)
        assert session.get_object(n2_id)
        assert session.get_object(wlan_id)
        assert value == "1"

    def test_xml_emane(self, session, tmpdir, ip_prefixes):
        """
        Test xml client methods for emane.

        :param session: session for test
        :param tmpdir: tmpdir to create data in
        :param str version: xml version to write and parse
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
            assert not session.get_object(n1_id)
        with pytest.raises(KeyError):
            assert not session.get_object(n2_id)

        # load saved xml
        session.open_xml(file_path, start=True)

        # retrieve configuration we set originally
        value = str(session.emane.get_config("test", emane_id, EmaneIeee80211abgModel.name))

        # verify nodes and configuration were restored
        assert session.get_object(n1_id)
        assert session.get_object(n2_id)
        assert session.get_object(emane_id)
        assert value == "1"
