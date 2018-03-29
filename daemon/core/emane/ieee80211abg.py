"""
ieee80211abg.py: EMANE IEEE 802.11abg model for CORE
"""

from core.emane import emanemodel
from core.enumerations import ConfigDataTypes


class EmaneIeee80211abgModel(emanemodel.EmaneModel):
    # model name
    name = "emane_ieee80211abg"
    library = "ieee80211abgmaclayer"

    # mac configuration
    _80211rates = "1 1 Mbps,2 2 Mbps,3 5.5 Mbps,4 11 Mbps,5 6 Mbps," + \
                  "6 9 Mbps,7 12 Mbps,8 18 Mbps,9 24 Mbps,10 36 Mbps,11 48 Mbps," + \
                  "12 54 Mbps"
    xml_path = "/usr/share/emane/xml/models/mac/ieee80211abg"
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

    config_matrix = _config_mac + emanemodel.EmaneModel._config_phy
    config_groups = emanemodel.create_config_groups(_config_mac, config_matrix)

    def create_mac_doc(self, emane_manager, values):
        names = self.getnames()
        mac_names = names[:len(self._config_mac)]
        mac_document = emane_manager.xmldoc("mac")
        mac_element = mac_document.getElementsByTagName("mac").pop()
        mac_element.setAttribute("name", "%s MAC" % self.name)
        mac_element.setAttribute("library", self.library)
        for name in mac_names:
            mac9xnvpairlist = self.get9xmacparamequivalent(name, values)
            for nvpair in mac9xnvpairlist:
                param = emane_manager.xmlparam(mac_document, nvpair[0], nvpair[1])
                mac_element.appendChild(param)
        return mac_document

    def get9xmacparamequivalent(self, mac_name, values):
        """
        This accounts for current config values labeled value0, value1, value2, etc.

        Generate a list of 80211abg mac parameters in 0.9.x layout for a given mac parameter
        in 8.x layout.For mac category parameters, the list returned will contain the four
        equivalent 9.x parameter and value pairs. Otherwise, the list returned will only
        contain a single name and value pair.
        """
        nvpairlist = []
        macparmval = self.valueof(mac_name, values)

        if mac_name in ["queuesize", "aifs", "cwmin", "cwmax", "txop", "retrylimit", "msdu"]:
            for catval in macparmval.split():
                idx_and_val = catval.split(":")
                idx = int(idx_and_val[0])
                val = idx_and_val[1]
                # aifs and tx are in microseconds. Convert to seconds.
                if mac_name in ["aifs", "txop"]:
                    val = "%f" % (float(val) * 1e-6)
                name9x = "%s%d" % (mac_name, idx)
                nvpairlist.append([name9x, val])
        else:
            nvpairlist.append([mac_name, macparmval])

        return nvpairlist
