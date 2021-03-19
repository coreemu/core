"""
ieee80211abg.py: EMANE IEEE 802.11abg model for CORE
"""
from pathlib import Path

from core.emane import emanemodel


class EmaneIeee80211abgModel(emanemodel.EmaneModel):
    # model name
    name: str = "emane_ieee80211abg"

    # mac configuration
    mac_library: str = "ieee80211abgmaclayer"
    mac_xml: str = "ieee80211abgmaclayer.xml"

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        cls.mac_defaults["pcrcurveuri"] = str(
            emane_prefix / "share/emane/xml/models/mac/ieee80211abg/ieee80211pcr.xml"
        )
        super().load(emane_prefix)
