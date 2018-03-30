"""
rfpipe.py: EMANE RF-PIPE model for CORE
"""

from core.emane import emanemanifest
from core.emane import emanemodel


class EmaneRfPipeModel(emanemodel.EmaneModel):
    # model name
    name = "emane_rfpipe"

    # mac configuration
    mac_library = "rfpipemaclayer"
    mac_xml = "/usr/share/emane/manifest/rfpipemaclayer.xml"
    mac_defaults = {
        "pcrcurveuri": "/usr/share/emane/xml/models/mac/rfpipe/rfpipepcr.xml",
    }
    config_mac = emanemanifest.parse(mac_xml, mac_defaults)

    # defines overall config
    config_matrix = config_mac + emanemodel.EmaneModel.config_phy

    # gui display tabs
    config_groups = emanemodel.create_config_groups(config_mac, config_matrix)
