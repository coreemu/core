"""
Defines Emane Models used within CORE.
"""
import logging
import os
from typing import Dict, List

from core.config import ConfigGroup, Configuration
from core.emane import emanemanifest
from core.emane.nodes import EmaneNet
from core.emulator.enumerations import ConfigDataTypes
from core.errors import CoreError
from core.location.mobility import WirelessModel
from core.nodes.interface import CoreInterface
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
    phy_xml = "emanephy.xml"
    phy_defaults = {"subid": "1", "propagationmodel": "2ray", "noisemode": "none"}
    phy_config = []

    # support for external configurations
    external_config = [
        Configuration("external", ConfigDataTypes.BOOL, default="0"),
        Configuration(
            "platformendpoint", ConfigDataTypes.STRING, default="127.0.0.1:40001"
        ),
        Configuration(
            "transportendpoint", ConfigDataTypes.STRING, default="127.0.0.1:50002"
        ),
    ]

    config_ignore = set()

    @classmethod
    def load(cls, emane_prefix: str) -> None:
        """
        Called after being loaded within the EmaneManager. Provides configured emane_prefix for
        parsing xml files.

        :param emane_prefix: configured emane prefix path
        :return: nothing
        """
        manifest_path = "share/emane/manifest"
        # load mac configuration
        mac_xml_path = os.path.join(emane_prefix, manifest_path, cls.mac_xml)
        cls.mac_config = emanemanifest.parse(mac_xml_path, cls.mac_defaults)

        # load phy configuration
        phy_xml_path = os.path.join(emane_prefix, manifest_path, cls.phy_xml)
        cls.phy_config = emanemanifest.parse(phy_xml_path, cls.phy_defaults)

    @classmethod
    def configurations(cls) -> List[Configuration]:
        """
        Returns the combination all all configurations (mac, phy, and external).

        :return: all configurations
        """
        return cls.mac_config + cls.phy_config + cls.external_config

    @classmethod
    def config_groups(cls) -> List[ConfigGroup]:
        """
        Returns the defined configuration groups.

        :return: list of configuration groups.
        """
        mac_len = len(cls.mac_config)
        phy_len = len(cls.phy_config) + mac_len
        config_len = len(cls.configurations())
        return [
            ConfigGroup("MAC Parameters", 1, mac_len),
            ConfigGroup("PHY Parameters", mac_len + 1, phy_len),
            ConfigGroup("External Parameters", phy_len + 1, config_len),
        ]

    def build_xml_files(
        self, config: Dict[str, str], interface: CoreInterface = None
    ) -> None:
        """
        Builds xml files for this emane model. Creates a nem.xml file that points to
        both mac.xml and phy.xml definitions.

        :param config: emane model configuration for the node and interface
        :param interface: interface for the emane node
        :return: nothing
        """
        nem_name = emanexml.nem_file_name(self, interface)
        mac_name = emanexml.mac_file_name(self, interface)
        phy_name = emanexml.phy_file_name(self, interface)

        # remote server for file
        server = None
        if interface is not None:
            server = interface.node.server

        # check if this is external
        transport_type = "virtual"
        if interface and interface.transport_type == "raw":
            transport_type = "raw"
        transport_name = emanexml.transport_file_name(self.id, transport_type)

        # create nem xml file
        nem_file = os.path.join(self.session.session_dir, nem_name)
        emanexml.create_nem_xml(
            self, config, nem_file, transport_name, mac_name, phy_name, server
        )

        # create mac xml file
        mac_file = os.path.join(self.session.session_dir, mac_name)
        emanexml.create_mac_xml(self, config, mac_file, server)

        # create phy xml file
        phy_file = os.path.join(self.session.session_dir, phy_name)
        emanexml.create_phy_xml(self, config, phy_file, server)

    def post_startup(self) -> None:
        """
        Logic to execute after the emane manager is finished with startup.

        :return: nothing
        """
        logging.debug("emane model(%s) has no post setup tasks", self.name)

    def update(self, moved: bool, moved_netifs: List[CoreInterface]) -> None:
        """
        Invoked from MobilityModel when nodes are moved; this causes
        emane location events to be generated for the nodes in the moved
        list, making EmaneModels compatible with Ns2ScriptedMobility.

        :param moved: were nodes moved
        :param moved_netifs: interfaces that were moved
        :return: nothing
        """
        try:
            wlan = self.session.get_node(self.id, EmaneNet)
            wlan.setnempositions(moved_netifs)
        except CoreError:
            logging.exception("error during update")

    def linkconfig(
        self,
        netif: CoreInterface,
        bw: float = None,
        delay: float = None,
        loss: float = None,
        duplicate: float = None,
        jitter: float = None,
        netif2: CoreInterface = None,
        devname: str = None,
    ) -> None:
        """
        Invoked when a Link Message is received. Default is unimplemented.

        :param netif: interface one
        :param bw: bandwidth to set to
        :param delay: packet delay to set to
        :param loss: packet loss to set to
        :param duplicate: duplicate percentage to set to
        :param jitter: jitter to set to
        :param netif2: interface two
        :param devname: device name
        :return: nothing
        """
        logging.warning(
            "emane model(%s) does not support link configuration", self.name
        )
