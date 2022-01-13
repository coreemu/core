"""
Defines Emane Models used within CORE.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.config import ConfigBool, ConfigGroup, ConfigString, Configuration
from core.emane import emanemanifest
from core.emulator.data import LinkOptions
from core.errors import CoreError
from core.location.mobility import WirelessModel
from core.nodes.interface import CoreInterface
from core.xml import emanexml

logger = logging.getLogger(__name__)
DEFAULT_DEV: str = "ctrl0"
MANIFEST_PATH: str = "share/emane/manifest"


class EmaneModel(WirelessModel):
    """
    EMANE models inherit from this parent class, which takes care of
    handling configuration messages based on the list of
    configurable parameters. Helper functions also live here.
    """

    # default platform configuration settings
    platform_controlport: str = "controlportendpoint"
    platform_xml: str = "nemmanager.xml"
    platform_defaults: Dict[str, str] = {
        "eventservicedevice": DEFAULT_DEV,
        "eventservicegroup": "224.1.2.8:45703",
        "otamanagerdevice": DEFAULT_DEV,
        "otamanagergroup": "224.1.2.8:45702",
    }
    platform_config: List[Configuration] = []

    # default mac configuration settings
    mac_library: Optional[str] = None
    mac_xml: Optional[str] = None
    mac_defaults: Dict[str, str] = {}
    mac_config: List[Configuration] = []

    # default phy configuration settings, using the universal model
    phy_library: Optional[str] = None
    phy_xml: str = "emanephy.xml"
    phy_defaults: Dict[str, str] = {
        "subid": "1",
        "propagationmodel": "2ray",
        "noisemode": "none",
    }
    phy_config: List[Configuration] = []

    # support for external configurations
    external_config: List[Configuration] = [
        ConfigBool(id="external", default="0"),
        ConfigString(id="platformendpoint", default="127.0.0.1:40001"),
        ConfigString(id="transportendpoint", default="127.0.0.1:50002"),
    ]

    config_ignore: Set[str] = set()

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        """
        Called after being loaded within the EmaneManager. Provides configured
        emane_prefix for parsing xml files.

        :param emane_prefix: configured emane prefix path
        :return: nothing
        """
        cls._load_platform_config(emane_prefix)
        # load mac configuration
        mac_xml_path = emane_prefix / MANIFEST_PATH / cls.mac_xml
        cls.mac_config = emanemanifest.parse(mac_xml_path, cls.mac_defaults)
        # load phy configuration
        phy_xml_path = emane_prefix / MANIFEST_PATH / cls.phy_xml
        cls.phy_config = emanemanifest.parse(phy_xml_path, cls.phy_defaults)

    @classmethod
    def _load_platform_config(cls, emane_prefix: Path) -> None:
        platform_xml_path = emane_prefix / MANIFEST_PATH / cls.platform_xml
        cls.platform_config = emanemanifest.parse(
            platform_xml_path, cls.platform_defaults
        )
        # remove controlport configuration, since core will set this directly
        controlport_index = None
        for index, configuration in enumerate(cls.platform_config):
            if configuration.id == cls.platform_controlport:
                controlport_index = index
                break
        if controlport_index is not None:
            cls.platform_config.pop(controlport_index)

    @classmethod
    def configurations(cls) -> List[Configuration]:
        """
        Returns the combination all all configurations (mac, phy, and external).

        :return: all configurations
        """
        return (
            cls.platform_config + cls.mac_config + cls.phy_config + cls.external_config
        )

    @classmethod
    def config_groups(cls) -> List[ConfigGroup]:
        """
        Returns the defined configuration groups.

        :return: list of configuration groups.
        """
        platform_len = len(cls.platform_config)
        mac_len = len(cls.mac_config) + platform_len
        phy_len = len(cls.phy_config) + mac_len
        config_len = len(cls.configurations())
        return [
            ConfigGroup("Platform Parameters", 1, platform_len),
            ConfigGroup("MAC Parameters", platform_len + 1, mac_len),
            ConfigGroup("PHY Parameters", mac_len + 1, phy_len),
            ConfigGroup("External Parameters", phy_len + 1, config_len),
        ]

    def build_xml_files(self, config: Dict[str, str], iface: CoreInterface) -> None:
        """
        Builds xml files for this emane model. Creates a nem.xml file that points to
        both mac.xml and phy.xml definitions.

        :param config: emane model configuration for the node and interface
        :param iface: interface to run emane for
        :return: nothing
        """
        # create nem, mac, and phy xml files
        emanexml.create_nem_xml(self, iface, config)
        emanexml.create_mac_xml(self, iface, config)
        emanexml.create_phy_xml(self, iface, config)
        emanexml.create_transport_xml(iface, config)

    def post_startup(self, iface: CoreInterface) -> None:
        """
        Logic to execute after the emane manager is finished with startup.

        :param iface: interface for post startup
        :return: nothing
        """
        logger.debug("emane model(%s) has no post setup tasks", self.name)

    def update(self, moved_ifaces: List[CoreInterface]) -> None:
        """
        Invoked from MobilityModel when nodes are moved; this causes
        emane location events to be generated for the nodes in the moved
        list, making EmaneModels compatible with Ns2ScriptedMobility.

        :param moved_ifaces: interfaces that were moved
        :return: nothing
        """
        try:
            self.session.emane.set_nem_positions(moved_ifaces)
        except CoreError:
            logger.exception("error during update")

    def linkconfig(
        self, iface: CoreInterface, options: LinkOptions, iface2: CoreInterface = None
    ) -> None:
        """
        Invoked when a Link Message is received. Default is unimplemented.

        :param iface: interface one
        :param options: options for configuring link
        :param iface2: interface two
        :return: nothing
        """
        logger.warning("emane model(%s) does not support link config", self.name)
