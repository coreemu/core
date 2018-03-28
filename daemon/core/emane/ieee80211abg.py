"""
ieee80211abg.py: EMANE IEEE 802.11abg model for CORE
"""

from core.emane.emanemodel import EmaneModel
from core.emane.universal import EmaneUniversalModel
from core.enumerations import ConfigDataTypes


class EmaneIeee80211abgModel(EmaneModel):
    # model name
    name = "emane_ieee80211abg"
    _80211rates = "1 1 Mbps,2 2 Mbps,3 5.5 Mbps,4 11 Mbps,5 6 Mbps," + \
                  "6 9 Mbps,7 12 Mbps,8 18 Mbps,9 24 Mbps,10 36 Mbps,11 48 Mbps," + \
                  "12 54 Mbps"
    xml_path = "/usr/share/emane/xml/models/mac/ieee80211abg"

    # MAC parameters
    _config_mac = [
        ("aifs", ConfigDataTypes.STRING.value, "0:2 1:2 2:2 3:1", "", "arbitration inter frame space (0-4:aifs)"),
        ("channelactivityestimationtimer", ConfigDataTypes.FLOAT.value, "0.1", "",
         "Defines channel activity estimation timer in seconds"),
        ("cwmax", ConfigDataTypes.STRING.value, "0:1024 1:1024 2:64 3:16", "", "max contention window (0-4:maxw)"),
        ("cwmin", ConfigDataTypes.STRING.value, "0:32 1:32 2:16 3:8", "", "min contention window (0-4:minw)"),
        ("distance", ConfigDataTypes.UINT32.value, "1000", "", "max distance (m)"),
        ("enablepromiscuousmode", ConfigDataTypes.BOOL.value, "0", "On,Off", "enable promiscuous mode"),
        ("flowcontrolenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "enable traffic flow control"),
        ("flowcontroltokens", ConfigDataTypes.UINT16.value, "10", "", "number of flow control tokens"),
        ("mode", ConfigDataTypes.UINT8.value, "0", "0 802.11b (DSSS only),1 802.11b (DSSS only)," +
         "2 802.11a or g (OFDM),3 802.11b/g (DSSS and OFDM)", "mode"),
        ("multicastrate", ConfigDataTypes.UINT8.value, "1", _80211rates, "multicast rate (Mbps)"),
        ("msdu", ConfigDataTypes.UINT16.value, "0:65535 1:65535 2:65535 3:65535", "", "MSDU categories (0-4:size)"),
        ("neighbormetricdeletetime", ConfigDataTypes.FLOAT.value, "60.0", "",
         "R2RI neighbor table inactivity time (sec)"),
        ("neighbortimeout", ConfigDataTypes.FLOAT.value, "30.0", "", "Neighbor timeout in seconds for estimation"),
        ("pcrcurveuri", ConfigDataTypes.STRING.value, "%s/ieee80211pcr.xml" % xml_path, "", "SINR/PCR curve file"),
        ("queuesize", ConfigDataTypes.STRING.value, "0:255 1:255 2:255 3:255", "", "queue size (0-4:size)"),
        ("radiometricenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "report radio metrics via R2RI"),
        ("radiometricreportinterval", ConfigDataTypes.FLOAT.value, "1.0", "",
         "R2RI radio metric report interval (sec)"),
        ("retrylimit", ConfigDataTypes.STRING.value, "0:3 1:3 2:3 3:3", "", "retry limit (0-4:numretries)"),
        ("rtsthreshold", ConfigDataTypes.UINT16.value, "0", "", "RTS threshold (bytes)"),
        ("txop", ConfigDataTypes.STRING.value, "0:0 1:0 2:0 3:0", "", "txop (0-4:usec)"),
        ("unicastrate", ConfigDataTypes.UINT8.value, "4", _80211rates, "unicast rate (Mbps)"),
        ("wmmenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "WiFi Multimedia (WMM)"),
    ]

    # PHY parameters from Universal PHY
    _config_phy = EmaneUniversalModel.config_matrix

    config_matrix = _config_mac + _config_phy
    # value groupings
    config_groups = "802.11 MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" % (
        len(_config_mac), len(_config_mac) + 1, len(config_matrix))

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    def build_xml_files(self, emane_manager, interface):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide
        nXXemane_ieee80211abgnem.xml, nXXemane_ieee80211abgemac.xml,
        nXXemane_ieee80211abgphy.xml are used.

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
        nem_element.setAttribute("name", "ieee80211abg NEM")
        emane_manager.appendtransporttonem(nem_document, nem_element, self.object_id, interface)

        mac_element = nem_document.createElement("mac")
        mac_element.setAttribute("definition", mac_name)
        nem_element.appendChild(mac_element)

        phy_element = nem_document.createElement("phy")
        phy_element.setAttribute("definition", phy_name)
        nem_element.appendChild(phy_element)

        emane_manager.xmlwrite(nem_document, nem_name)

        names = self.getnames()
        mac_names = names[:len(self._config_mac)]
        phy_names = names[len(self._config_mac):]

        mac_document = emane_manager.xmldoc("mac")
        mac_element = mac_document.getElementsByTagName("mac").pop()
        mac_element.setAttribute("name", "ieee80211abg MAC")
        mac_element.setAttribute("library", "ieee80211abgmaclayer")
        for name in mac_names:
            mac9xnvpairlist = self.get9xmacparamequivalent(name, values)
            for nvpair in mac9xnvpairlist:
                param = emane_manager.xmlparam(mac_document, nvpair[0], nvpair[1])
                mac_element.appendChild(param)
        emane_manager.xmlwrite(mac_document, mac_name)

        phy_document = EmaneUniversalModel.get_phy_doc(emane_manager, self, values, phy_names)
        emane_manager.xmlwrite(phy_document, phy_name)

    #
    # TEMP HACK: Account for parameter convention change in EMANE 9.x
    # This allows CORE to preserve the entry layout for the mac "category" parameters
    # and work with EMANE 9.x onwards.
    #
    def get9xmacparamequivalent(self, macname, values):
        """
        Generate a list of 80211abg mac parameters in 0.9.x layout for a given mac parameter
        in 8.x layout.For mac category parameters, the list returned will contain the four
        equivalent 9.x parameter and value pairs. Otherwise, the list returned will only
        contain a single name and value pair.
        """
        nvpairlist = []
        macparmval = self.valueof(macname, values)

        if macname in ["queuesize", "aifs", "cwmin", "cwmax", "txop", "retrylimit", "msdu"]:
            for catval in macparmval.split():
                idx_and_val = catval.split(":")
                idx = int(idx_and_val[0])
                val = idx_and_val[1]
                # aifs and tx are in microseconds. Convert to seconds.
                if macname in ["aifs", "txop"]:
                    val = "%f" % (float(val) * 1e-6)
                name9x = "%s%d" % (macname, idx)
                nvpairlist.append([name9x, val])
        else:
            nvpairlist.append([macname, macparmval])

        return nvpairlist
