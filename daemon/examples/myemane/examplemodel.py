"""
Example custom emane model.
"""
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.config import Configuration
from core.emane import emanemanifest, emanemodel


class ExampleModel(emanemodel.EmaneModel):
    """
    Custom emane model.

    :cvar name: defines the emane model name that will show up in the GUI

    Mac Definition:
    :cvar mac_library: defines that mac library that the model will reference
    :cvar mac_xml: defines the mac manifest file that will be parsed to obtain configuration options,
        that will be displayed within the GUI
    :cvar mac_defaults: allows you to override options that are maintained within the manifest file above
    :cvar mac_config: parses the manifest file and converts configurations into core supported formats

    Phy Definition:
    NOTE: phy configuration will default to the universal model as seen below and the below section does not
    have to be included
    :cvar phy_library: defines that phy library that the model will reference, used if you need to
        provide a custom phy
    :cvar phy_xml: defines the phy manifest file that will be parsed to obtain configuration options,
        that will be displayed within the GUI
    :cvar phy_defaults: allows you to override options that are maintained within the manifest file above
        or for the default universal model
    :cvar phy_config: parses the manifest file and converts configurations into core supported formats

    Custom Override Options:
    NOTE: these options default to what's seen below and do not have to be included
    :cvar config_ignore: allows you to ignore options within phy/mac, used typically if you needed to add
        a custom option for display within the gui
    """

    name: str = "emane_example"
    mac_library: str = "rfpipemaclayer"
    mac_xml: str = "rfpipemaclayer.xml"
    mac_defaults: Dict[str, str] = {
        "pcrcurveuri": "/usr/share/emane/xml/models/mac/rfpipe/rfpipepcr.xml"
    }
    mac_config: List[Configuration] = []
    phy_library: Optional[str] = None
    phy_xml: str = "emanephy.xml"
    phy_defaults: Dict[str, str] = {
        "subid": "1",
        "propagationmodel": "2ray",
        "noisemode": "none",
    }
    phy_config: List[Configuration] = []
    config_ignore: Set[str] = set()

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        """
        Called after being loaded within the EmaneManager. Provides configured
        emane_prefix for parsing xml files.

        :param emane_prefix: configured emane prefix path
        :return: nothing
        """
        manifest_path = "share/emane/manifest"
        # load mac configuration
        mac_xml_path = emane_prefix / manifest_path / cls.mac_xml
        cls.mac_config = emanemanifest.parse(mac_xml_path, cls.mac_defaults)
        # load phy configuration
        phy_xml_path = emane_prefix / manifest_path / cls.phy_xml
        cls.phy_config = emanemanifest.parse(phy_xml_path, cls.phy_defaults)
