"""
rfpipe.py: EMANE RF-PIPE model for CORE
"""

from core.emane.emanemodel import EmaneModel
from core.emane.universal import EmaneUniversalModel
from core.enumerations import ConfigDataTypes


class EmaneRfPipeModel(EmaneModel):
    # model name
    name = "emane_rfpipe"
    xml_path = "/usr/share/emane/xml/models/mac/rfpipe"

    # configuration parameters are
    #  ( "name", "type", "default", "possible-value-list", "caption")
    # MAC parameters
    _config_mac = [
        ("datarate", ConfigDataTypes.UINT64.value, "1M", "", "data rate (bps)"),
        ("delay", ConfigDataTypes.FLOAT.value, "0.0", "", "transmission delay (sec)"),
        ("enablepromiscuousmode", ConfigDataTypes.BOOL.value, "0", "True,False", "enable promiscuous mode"),
        ("flowcontrolenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "enable traffic flow control"),
        ("flowcontroltokens", ConfigDataTypes.UINT16.value, "10", "", "number of flow control tokens"),
        ("jitter", ConfigDataTypes.FLOAT.value, "0.0", "", "transmission jitter (sec)"),
        ("neighbormetricdeletetime", ConfigDataTypes.FLOAT.value, "60.0", "",
         "R2RI neighbor table inactivity time (sec)"),
        ("pcrcurveuri", ConfigDataTypes.STRING.value, "%s/rfpipepcr.xml" % xml_path, "", "SINR/PCR curve file"),
        ("radiometricenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "report radio metrics via R2RI"),
        ("radiometricreportinterval", ConfigDataTypes.FLOAT.value, "1.0", "",
         "R2RI radio metric report interval (sec)"),
    ]

    # PHY parameters from Universal PHY
    _config_phy = EmaneUniversalModel.config_matrix

    config_matrix = _config_mac + _config_phy

    # value groupings
    config_groups = "RF-PIPE MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" % (
        len(_config_mac), len(_config_mac) + 1, len(config_matrix))

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    def build_xml_files(self, emane_manager, interface):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide nXXemane_rfpipenem.xml,
        nXXemane_rfpipemac.xml, nXXemane_rfpipephy.xml are used.

        :param core.emane.emanemanager.EmaneManager emane_manager: core emane manager
        :param interface: interface for the emane node
        :return: nothing
        """
        values = emane_manager.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), interface)
        if values is None:
            return

        # retrieve xml names
        nem_name = self.nem_name(interface)
        mac_name = self.mac_name(interface)
        phy_name = self.phy_name(interface)

        nem_document = emane_manager.xmldoc("nem")
        nem_element = nem_document.getElementsByTagName("nem").pop()
        nem_element.setAttribute("name", "RF-PIPE NEM")
        emane_manager.appendtransporttonem(nem_document, nem_element, self.object_id, interface)

        mac_element = nem_document.createElement("mac")
        mac_element.setAttribute("definition", mac_name)
        nem_element.appendChild(mac_element)

        phy_element = nem_document.createElement("phy")
        phy_element.setAttribute("definition", phy_name)
        nem_element.appendChild(phy_element)

        emane_manager.xmlwrite(nem_document, nem_name)

        names = list(self.getnames())
        mac_name = names[:len(self._config_mac)]
        phy_names = names[len(self._config_mac):]

        mac_document = emane_manager.xmldoc("mac")
        mac_element = mac_document.getElementsByTagName("mac").pop()
        mac_element.setAttribute("name", "RF-PIPE MAC")
        mac_element.setAttribute("library", "rfpipemaclayer")
        for name in mac_name:
            value = self.valueof(name, values)
            param = emane_manager.xmlparam(mac_document, name, value)
            mac_element.appendChild(param)
        emane_manager.xmlwrite(mac_document, mac_name)

        phy_document = EmaneUniversalModel.get_phy_doc(emane_manager, self, values, phy_names)
        emane_manager.xmlwrite(phy_document, phy_name)
