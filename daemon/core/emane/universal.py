"""
universal.py: EMANE Universal PHY model for CORE. Enumerates configuration items
used for the Universal PHY.
"""

from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes


class EmaneUniversalModel(EmaneModel):
    """
    This Univeral PHY model is meant to be imported by other models,
    not instantiated.
    """

    def __init__(self, session, object_id=None):
        raise NotImplemented("Cannot use this class directly")

    name = "emane_universal"
    _xmlname = "universalphy"
    _xmllibrary = "universalphylayer"

    # universal PHY parameters
    _confmatrix_base = [
        ("bandwidth", ConfigDataTypes.UINT64.value, "1M",
         "", "rf bandwidth (hz)"),
        ("frequency", ConfigDataTypes.UINT64.value, "2.347G",
         "", "frequency (Hz)"),
        ("frequencyofinterest", ConfigDataTypes.UINT64.value, "2.347G",
         "", "frequency of interest (Hz)"),
        ("subid", ConfigDataTypes.UINT16.value, "1",
         "", "subid"),
        ("systemnoisefigure", ConfigDataTypes.FLOAT.value, "4.0",
         "", "system noise figure (dB)"),
        ("txpower", ConfigDataTypes.FLOAT.value, "0.0",
         "", "transmit power (dBm)"),
    ]
    _confmatrix_091 = [
        ("fixedantennagain", ConfigDataTypes.FLOAT.value, "0.0",
         "", "antenna gain (dBi)"),
        ("fixedantennagainenable", ConfigDataTypes.BOOL.value, "1",
         "On,Off", "enable fixed antenna gain"),
        ("noisemode", ConfigDataTypes.STRING.value, "none",
         "none,all,outofband", "noise processing mode"),
        ("noisebinsize", ConfigDataTypes.UINT64.value, "20",
         "", "noise bin size in microseconds"),
        ("propagationmodel", ConfigDataTypes.STRING.value, "2ray",
         "precomputed,2ray,freespace", "path loss mode"),
    ]
    config_matrix = _confmatrix_base + _confmatrix_091

    @classmethod
    def getphydoc(cls, e, mac, values, phynames):
        phydoc = e.xmldoc("phy")
        phy = phydoc.getElementsByTagName("phy").pop()
        phy.setAttribute("name", cls._xmlname)

        name = "frequencyofinterest"
        value = mac.valueof(name, values)
        frequencies = cls.valuestrtoparamlist(phydoc, name, value)
        if frequencies:
            phynames = list(phynames)
            phynames.remove("frequencyofinterest")

        # append all PHY options to phydoc
        map(lambda n: phy.appendChild(e.xmlparam(phydoc, n, mac.valueof(n, values))), phynames)
        if frequencies:
            phy.appendChild(frequencies)

        return phydoc
