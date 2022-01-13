"""
rfpipe.py: EMANE RF-PIPE model for CORE
"""
from pathlib import Path

from core.emane import emanemodel


class EmaneRfPipeModel(emanemodel.EmaneModel):
    # model name
    name: str = "emane_rfpipe"

    # mac configuration
    mac_library: str = "rfpipemaclayer"
    mac_xml: str = "rfpipemaclayer.xml"

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        cls.mac_defaults["pcrcurveuri"] = str(
            emane_prefix / "share/emane/xml/models/mac/rfpipe/rfpipepcr.xml"
        )
        super().load(emane_prefix)
