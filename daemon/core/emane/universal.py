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

    name = "emane_universal"

    # universal PHY parameters
    _xmlname = "universalphy"
    _xmllibrary = "universalphylayer"
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

    def __init__(self, session, object_id=None):
        raise NotImplemented("Cannot use this class directly")

    @classmethod
    def get_phy_doc(cls, emane_manager, emane_model, values, phy_names):
        """
        Create a phy doc for a model based on the universal model.

        :param core.emane.emanemanager.EmaneManager emane_manager: core emane manager
        :param core.emane.emanemodel.EmaneModel emane_model: model to create phy doc for
        :param tuple values: emane model configuration values
        :param phy_names: names for phy configuration values
        :return:
        """
        phy_document = emane_manager.xmldoc("phy")
        phy_element = phy_document.getElementsByTagName("phy").pop()
        phy_element.setAttribute("name", cls._xmlname)

        name = "frequencyofinterest"
        value = emane_model.valueof(name, values)
        frequencies = cls.value_to_params(phy_document, name, value)
        if frequencies:
            phy_names = list(phy_names)
            phy_names.remove("frequencyofinterest")

        # append all PHY options to phydoc
        for name in phy_names:
            value = emane_model.valueof(name, values)
            param = emane_manager.xmlparam(phy_document, name, value)
            phy_element.appendChild(param)

        if frequencies:
            phy_element.appendChild(frequencies)

        return phy_document
