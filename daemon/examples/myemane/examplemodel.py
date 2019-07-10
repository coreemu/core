"""
Example custom emane model.
"""

from core.emane import emanemanifest
from core.emane import emanemodel


class ExampleModel(emanemodel.EmaneModel):
    """
    Custom emane model.

    :var str name: defines the emane model name that will show up in the GUI

    Mac Definition:
    :var str mac_library: defines that mac library that the model will reference
    :var str mac_xml: defines the mac manifest file that will be parsed to obtain configuration options,
        that will be displayed within the GUI
    :var dict mac_mac_defaults: allows you to override options that are maintained within the manifest file above
    :var list mac_mac_config: parses the manifest file and converts configurations into core supported formats

    Phy Definition:
    NOTE: phy configuration will default to the universal model as seen below and the below section does not
    have to be included
    :var str phy_library: defines that phy library that the model will reference, used if you need to
        provide a custom phy
    :var str phy_xml: defines the phy manifest file that will be parsed to obtain configuration options,
        that will be displayed within the GUI
    :var dict phy_defaults: allows you to override options that are maintained within the manifest file above
        or for the default universal model
    :var list phy_config: parses the manifest file and converts configurations into core supported formats

    Custom Override Options:
    NOTE: these options default to what's seen below and do not have to be included
    :var set config_ignore: allows you to ignore options within phy/mac, used typically if you needed to add
        a custom option for display within the gui
    """

    name = "emane_example"
    mac_library = "rfpipemaclayer"
    mac_xml = "/usr/share/emane/manifest/rfpipemaclayer.xml"
    mac_defaults = {
        "pcrcurveuri": "/usr/share/emane/xml/models/mac/rfpipe/rfpipepcr.xml",
    }
    mac_config = emanemanifest.parse(mac_xml, mac_defaults)
    phy_library = None
    phy_xml = "/usr/share/emane/manifest/emanephy.xml"
    phy_defaults = {
        "subid": "1",
        "propagationmodel": "2ray",
        "noisemode": "none"
    }
    phy_config = emanemanifest.parse(phy_xml, phy_defaults)
    config_ignore = set()
