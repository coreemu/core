from xml.etree import ElementTree

import pytest

from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.emudata import NodeOptions
from core.enumerations import NodeTypes
from core.mobility import BasicRangeModel
from core.services.utility import SshService

_XML_VERSIONS = [
    "0.0",
    "1.0"
]


class TestXml:
    @pytest.mark.parametrize("version", _XML_VERSIONS)
    def test_xml_ptp(self, session, tmpdir, version, ip_prefixes):
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
        node_one = session.add_node()
        node_two = session.add_node()

        # link nodes to ptp net
        for node in [node_one, node_two]:
            interface = ip_prefixes.create_interface(node)
            session.add_link(node.objid, ptp_node.objid, interface_one=interface)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        n1_id = node_one.objid
        n2_id = node_two.objid

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(file_path, version)

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

    @pytest.mark.parametrize("version", _XML_VERSIONS)
    def test_xml_ptp_services(self, session, tmpdir, version, ip_prefixes):
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
            session.add_link(node.objid, ptp_node.objid, interface_one=interface)

        # set custom values for node service\
        custom_start = 50
        session.services.setcustomservice(node_one.objid, SshService.name)
        service = session.services.getcustomservice(node_one.objid, SshService.name)
        service.startindex = custom_start
        service_file = SshService.configs[0]
        file_data = "# test"
        session.services.setservicefile(node_one.objid, SshService.name, service_file, file_data)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        n1_id = node_one.objid
        n2_id = node_two.objid

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(file_path, version)

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
        service = session.services.getcustomservice(node_one.objid, SshService.name)

        # verify nodes have been recreated
        assert session.get_object(n1_id)
        assert session.get_object(n2_id)
        assert service.startindex == custom_start
        assert service.configtxt.get(service_file) == file_data

    @pytest.mark.parametrize("version", _XML_VERSIONS)
    def test_xml_mobility(self, session, tmpdir, version, ip_prefixes):
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
            session.add_link(node.objid, wlan_node.objid, interface_one=interface)

        # link nodes in wlan
        session.wireless_link_all(wlan_node, [node_one, node_two])

        # instantiate session
        session.instantiate()

        # get ids for nodes
        wlan_id = wlan_node.objid
        n1_id = node_one.objid
        n2_id = node_two.objid

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(file_path, version)

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

    @pytest.mark.parametrize("version", ["1.0"])
    def test_xml_emane(self, session, tmpdir, version, ip_prefixes):
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
            session.add_link(node.objid, emane_network.objid, interface_one=interface)

        # instantiate session
        session.instantiate()

        # get ids for nodes
        emane_id = emane_network.objid
        n1_id = node_one.objid
        n2_id = node_two.objid

        # save xml
        xml_file = tmpdir.join("session.xml")
        file_path = xml_file.strpath
        session.save_xml(file_path, version)

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
