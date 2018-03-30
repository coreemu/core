

from core.emane import emanemanifest
from core.emane import emanemodel

## Custom EMANE Model
class ExampleModel(emanemodel.EmaneModel):
    ### MAC Definition

    # Defines the emane model name that will show up in the GUI.
    name = "emane_example"

    # Defines that mac library that the model will reference.
    mac_library = "rfpipemaclayer"
    # Defines the mac manifest file that will be parsed to obtain configuration options, that will be displayed
    # within the GUI.
    mac_xml = "/usr/share/emane/manifest/rfpipemaclayer.xml"
    # Allows you to override options that are maintained within the manifest file above.
    mac_defaults = {
        "pcrcurveuri": "/usr/share/emane/xml/models/mac/rfpipe/rfpipepcr.xml",
    }
    # Parses the manifest file and converts configurations into core supported formats.
    mac_config = emanemanifest.parse(mac_xml, mac_defaults)

    ### PHY Definition
    # **NOTE: phy configuration will default to the universal model as seen below and the below section does not
    # have to be included.**

    # Defines that phy library that the model will reference, used if you need to provide a custom phy.
    phy_library = None
    # Defines the phy manifest file that will be parsed to obtain configuration options, that will be displayed
    # within the GUI.
    phy_xml = "/usr/share/emane/manifest/emanephy.xml"
    # Allows you to override options that are maintained within the manifest file above or for the default universal
    # model.
    phy_defaults = {
        "subid": "1",
        "propagationmodel": "2ray",
        "noisemode": "none"
    }
    # Parses the manifest file and converts configurations into core supported formats.
    phy_config = emanemanifest.parse(phy_xml, phy_defaults)

    ### Custom override options
    # **NOTE: these options default to what's seen below and do not have to be included.**

    # Allows you to ignore options within phy/mac, used typically if you needed to add a custom option for display
    # within the gui.
    config_ignore = set()
    # Allows you to override how options are displayed with the GUI, using the GUI format of
    # "name:1-2|othername:3-4". This will be parsed into tabs, split by "|" and account for items based on the indexed
    # numbers after ":" for including values in each tab.
    config_groups_override = None
    # Allows you to override the default config matrix list. This value by default is the mac_config + phy_config, in
    # that order.
    config_matrix_override = None
