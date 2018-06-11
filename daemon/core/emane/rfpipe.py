"""
rfpipe.py: EMANE RF-PIPE model for CORE
"""

from core.emane import emanemanifest
from core.emane import emanemodel


class EmaneRfPipeModel(emanemodel.EmaneModel):
    # model name
    name = "emane_rfpipe"
    configuration_maps = {}

    # mac configuration
    mac_library = "rfpipemaclayer"
    mac_xml = "/usr/share/emane/manifest/rfpipemaclayer.xml"
    mac_defaults = {
        "pcrcurveuri": "/usr/share/emane/xml/models/mac/rfpipe/rfpipepcr.xml",
    }
    mac_config = emanemanifest.parse(mac_xml, mac_defaults)
