"""
universal.py: EMANE Universal PHY model for CORE. Enumerates configuration items
used for the Universal PHY.
"""

from core import emane
from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes
from core.misc import log

logger = log.get_logger(__name__)


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
    _confmatrix_081 = [
        ("antennagain", ConfigDataTypes.FLOAT.value, "0.0",
         "", "antenna gain (dBi)"),
        ("antennaazimuth", ConfigDataTypes.FLOAT.value, "0.0",
         "", "antenna azimuth (deg)"),
        ("antennaelevation", ConfigDataTypes.FLOAT.value, "0.0",
         "", "antenna elevation (deg)"),
        ("antennaprofileid", ConfigDataTypes.STRING.value, "1",
         "", "antenna profile ID"),
        ("antennaprofilemanifesturi", ConfigDataTypes.STRING.value, "",
         "", "antenna profile manifest URI"),
        ("antennaprofileenable", ConfigDataTypes.BOOL.value, "0",
         "On,Off", "antenna profile mode"),
        ("defaultconnectivitymode", ConfigDataTypes.BOOL.value, "1",
         "On,Off", "default connectivity"),
        ("frequencyofinterestfilterenable", ConfigDataTypes.BOOL.value, "1",
         "On,Off", "frequency of interest filter enable"),
        ("noiseprocessingmode", ConfigDataTypes.BOOL.value, "0",
         "On,Off", "enable noise processing"),
        ("pathlossmode", ConfigDataTypes.STRING.value, "2ray",
         "pathloss,2ray,freespace", "path loss mode"),
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
    if emane.VERSION >= emane.EMANE091:
        config_matrix = _confmatrix_base + _confmatrix_091
    else:
        config_matrix = _confmatrix_base + _confmatrix_081

    # old parameters
    _confmatrix_ver074 = [
        ("antennaazimuthbeamwidth", ConfigDataTypes.FLOAT.value, "360.0",
         "", "azimith beam width (deg)"),
        ("antennaelevationbeamwidth", ConfigDataTypes.FLOAT.value, "180.0",
         "", "elevation beam width (deg)"),
        ("antennatype", ConfigDataTypes.STRING.value, "omnidirectional",
         "omnidirectional,unidirectional", "antenna type"),
    ]

    # parameters that require unit conversion for 0.7.4
    _update_ver074 = ("bandwidth", "frequency", "frequencyofinterest")
    # parameters that should be removed for 0.7.4
    _remove_ver074 = ("antennaprofileenable", "antennaprofileid",
                      "antennaprofilemanifesturi",
                      "frequencyofinterestfilterenable")

    @classmethod
    def getphydoc(cls, e, mac, values, phynames):
        phydoc = e.xmldoc("phy")
        phy = phydoc.getElementsByTagName("phy").pop()
        phy.setAttribute("name", cls._xmlname)
        if emane.VERSION < emane.EMANE091:
            phy.setAttribute("library", cls._xmllibrary)
        # EMANE 0.7.4 suppport - to be removed when 0.7.4 support is deprecated
        if emane.VERSION == emane.EMANE074:
            names = mac.getnames()
            values = list(values)
            phynames = list(phynames)
            # update units for some parameters
            for p in cls._update_ver074:
                i = names.index(p)
                # these all happen to be KHz, so 1000 is used
                values[i] = cls.emane074_fixup(values[i], 1000)
            # remove new incompatible options
            for p in cls._remove_ver074:
                phynames.remove(p)
            # insert old options with their default values
            for old in cls._confmatrix_ver074:
                phy.appendChild(e.xmlparam(phydoc, old[0], old[2]))

        frequencies = None
        if emane.VERSION >= emane.EMANE091:
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
