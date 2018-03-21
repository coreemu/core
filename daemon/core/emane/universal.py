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
    config_matrix = [
        ("bandwidth", ConfigDataTypes.UINT64.value, "1M", "", "rf bandwidth (Hz)"),
        ("fading.model", ConfigDataTypes.STRING.value, "none", "none,event,nakagami", "Defines fading model"),
        ("fading.nakagami.distance0", ConfigDataTypes.FLOAT.value, "100.0", "",
         "Nakagami D0: distance lower bound in meters"),
        ("fading.nakagami.distance1", ConfigDataTypes.FLOAT.value, "250.0", "",
         "Nakagami D1: distance upper bound in meters"),
        ("fading.nakagami.m0", ConfigDataTypes.FLOAT.value, "0.75", "", "Nakagami M0: shape factor for distance < D0"),
        ("fading.nakagami.m1", ConfigDataTypes.FLOAT.value, "1.0", "",
         "Nakagami M1: shape factor for distance >= D0 < D1"),
        ("fading.nakagami.m2", ConfigDataTypes.FLOAT.value, "200.0", "",
         "Nakagami M2: shape factor for distance >= D1"),
        ("fixedantennagain", ConfigDataTypes.FLOAT.value, "0.0", "", "antenna gain (dBi)"),
        ("fixedantennagainenable", ConfigDataTypes.BOOL.value, "1", "On,Off", "enable fixed antenna gain"),
        ("frequency", ConfigDataTypes.UINT64.value, "2.347G", "", "frequency (Hz)"),
        ("frequencyofinterest", ConfigDataTypes.UINT64.value, "2.347G", "", "frequency of interest (Hz)"),
        ("noisebinsize", ConfigDataTypes.UINT64.value, "20", "", "noise bin size in microseconds"),
        ("noisemaxclampenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "Noise max clamp enable"),
        ("noisemaxmessagepropagation", ConfigDataTypes.UINT64.value, "200000", "",
         "Noise maximum message propagation in microsecond"),
        ("noisemaxsegmentduration", ConfigDataTypes.UINT64.value, "1000000", "",
         "Noise maximum segment duration in microseconds"),
        ("noisemaxsegmentoffset", ConfigDataTypes.UINT64.value, "300000", "",
         "Noise maximum segment offset in microseconds"),
        ("noisemode", ConfigDataTypes.STRING.value, "none", "none,all,outofband", "noise processing mode"),
        ("propagationmodel", ConfigDataTypes.STRING.value, "2ray", "precomputed,2ray,freespace", "path loss mode"),
        ("subid", ConfigDataTypes.UINT16.value, "1", "", "subid"),
        ("systemnoisefigure", ConfigDataTypes.FLOAT.value, "4.0", "", "system noise figure (dB)"),
        ("timesyncthreshold", ConfigDataTypes.UINT64.value, "10000", "", "Time sync threshold"),
        ("txpower", ConfigDataTypes.FLOAT.value, "0.0", "", "transmit power (dBm)"),
    ]

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
