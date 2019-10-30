"""
rfpipe.py: EMANE RF-PIPE model for CORE
"""
import os

from core.emane import emanemodel


class EmaneRfPipeModel(emanemodel.EmaneModel):
    # model name
    name = "emane_rfpipe"

    # mac configuration
    mac_library = "rfpipemaclayer"
    mac_xml = "rfpipemaclayer.xml"

    @classmethod
    def load(cls, emane_prefix):
        cls.mac_defaults["pcrcurveuri"] = os.path.join(
            emane_prefix, "share/emane/xml/models/mac/rfpipe/rfpipepcr.xml"
        )
        super().load(emane_prefix)
