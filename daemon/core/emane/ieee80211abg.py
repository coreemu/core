"""
ieee80211abg.py: EMANE IEEE 802.11abg model for CORE
"""
import os

from core.emane import emanemodel


class EmaneIeee80211abgModel(emanemodel.EmaneModel):
    # model name
    name = "emane_ieee80211abg"

    # mac configuration
    mac_library = "ieee80211abgmaclayer"
    mac_xml = "ieee80211abgmaclayer.xml"

    @classmethod
    def load(cls, emane_prefix):
        cls.mac_defaults["pcrcurveuri"] = os.path.join(
            emane_prefix, "share/emane/xml/models/mac/ieee80211abg/ieee80211pcr.xml"
        )
        super(EmaneIeee80211abgModel, cls).load(emane_prefix)
