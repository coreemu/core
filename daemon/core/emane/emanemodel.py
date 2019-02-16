"""
Defines Emane Models used within CORE.
"""
import logging
import os

from core.conf import ConfigGroup
from core.conf import Configuration
from core.emane import emanemanifest
from core.enumerations import ConfigDataTypes
from core.mobility import WirelessModel
from core.xml import emanexml


class EmaneModel(WirelessModel):
    """
    EMANE models inherit from this parent class, which takes care of
    handling configuration messages based on the list of
    configurable parameters. Helper functions also live here.
    """
    # default mac configuration settings
    mac_library = None
    mac_xml = None
    mac_defaults = {}
    mac_config = []

    # default phy configuration settings, using the universal model
    phy_library = None
    phy_xml = "/usr/share/emane/manifest/emanephy.xml"
    phy_defaults = {
        "subid": "1",
        "propagationmodel": "2ray",
        "noisemode": "none"
    }
    phy_config = emanemanifest.parse(phy_xml, phy_defaults)

    # support for external configurations
    external_config = [
        Configuration("external", ConfigDataTypes.BOOL, default="0"),
        Configuration("platformendpoint", ConfigDataTypes.STRING, default="127.0.0.1:40001"),
        Configuration("transportendpoint", ConfigDataTypes.STRING, default="127.0.0.1:50002")
    ]

    config_ignore = set()

    @classmethod
    def configurations(cls):
        return cls.mac_config + cls.phy_config + cls.external_config

    @classmethod
    def config_groups(cls):
        mac_len = len(cls.mac_config)
        phy_len = len(cls.phy_config) + mac_len
        config_len = len(cls.configurations())
        return [
            ConfigGroup("MAC Parameters", 1, mac_len),
            ConfigGroup("PHY Parameters", mac_len + 1, phy_len),
            ConfigGroup("External Parameters", phy_len + 1, config_len)
        ]

    def build_xml_files(self, config, interface=None):
        """
        Builds xml files for this emane model. Creates a nem.xml file that points to both mac.xml and phy.xml
        definitions.

        :param dict config: emane model configuration for the node and interface
        :param interface: interface for the emane node
        :return: nothing
        """
        nem_name = emanexml.nem_file_name(self, interface)
        mac_name = emanexml.mac_file_name(self, interface)
        phy_name = emanexml.phy_file_name(self, interface)

        # check if this is external
        transport_type = "virtual"
        if interface and interface.transport_type == "raw":
            transport_type = "raw"
        transport_name = emanexml.transport_file_name(self.object_id, transport_type)

        # create nem xml file
        nem_file = os.path.join(self.session.session_dir, nem_name)
        emanexml.create_nem_xml(self, config, nem_file, transport_name, mac_name, phy_name)

        # create mac xml file
        mac_file = os.path.join(self.session.session_dir, mac_name)
        emanexml.create_mac_xml(self, config, mac_file)

        # create phy xml file
        phy_file = os.path.join(self.session.session_dir, phy_name)
        emanexml.create_phy_xml(self, config, phy_file)

    def post_startup(self):
        """
        Logic to execute after the emane manager is finished with startup.

        :return: nothing
        """
        logging.info("emane model(%s) has no post setup tasks", self.name)

    def update(self, moved, moved_netifs):
        """
        Invoked from MobilityModel when nodes are moved; this causes
        emane location events to be generated for the nodes in the moved
        list, making EmaneModels compatible with Ns2ScriptedMobility.

        :param bool moved: were nodes moved
        :param list moved_netifs: interfaces that were moved
        :return:
        """
        try:
            wlan = self.session.get_object(self.object_id)
            wlan.setnempositions(moved_netifs)
        except KeyError:
            logging.exception("error during update")

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None, jitter=None, netif2=None):
        """
        Invoked when a Link Message is received. Default is unimplemented.

        :param core.netns.vif.Veth netif: interface one
        :param bw: bandwidth to set to
        :param delay: packet delay to set to
        :param loss: packet loss to set to
        :param duplicate: duplicate percentage to set to
        :param jitter: jitter to set to
        :param core.netns.vif.Veth netif2: interface two
        :return: nothing
        """
        logging.warn("emane model(%s) does not support link configuration", self.name)
