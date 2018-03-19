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
    _confmatrix_mac_base = [
        ("enablepromiscuousmode", ConfigDataTypes.BOOL.value, "0", "True,False", "enable promiscuous mode"),
        ("datarate", ConfigDataTypes.UINT32.value, "1M", "", "data rate (bps)"),
        ("flowcontrolenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "enable traffic flow control"),
        ("flowcontroltokens", ConfigDataTypes.UINT16.value, "10", "", "number of flow control tokens"),
        ("pcrcurveuri", ConfigDataTypes.STRING.value, "%s/rfpipepcr.xml" % xml_path, "", "SINR/PCR curve file"),
    ]
    _confmatrix_mac_091 = [
        ("jitter", ConfigDataTypes.FLOAT.value, "0.0", "", "transmission jitter (sec)"),
        ("delay", ConfigDataTypes.FLOAT.value, "0.0", "", "transmission delay (sec)"),
        ("radiometricenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "report radio metrics via R2RI"),
        ("radiometricreportinterval", ConfigDataTypes.FLOAT.value, "1.0", "",
         "R2RI radio metric report interval (sec)"),
        ("neighbormetricdeletetime", ConfigDataTypes.FLOAT.value, "60.0", "",
         "R2RI neighbor table inactivity time (sec)"),
    ]
    _confmatrix_mac = _confmatrix_mac_base + _confmatrix_mac_091

    # PHY parameters from Universal PHY
    _confmatrix_phy = EmaneUniversalModel.config_matrix

    config_matrix = _confmatrix_mac + _confmatrix_phy

    # value groupings
    config_groups = "RF-PIPE MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" % (
        len(_confmatrix_mac), len(_confmatrix_mac) + 1, len(config_matrix))

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    def buildnemxmlfiles(self, e, ifc):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide nXXemane_rfpipenem.xml,
        nXXemane_rfpipemac.xml, nXXemane_rfpipephy.xml are used.
        """
        values = e.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), ifc)
        if values is None:
            return

        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "RF-PIPE NEM")
        e.appendtransporttonem(nemdoc, nem, self.object_id, ifc)
        mactag = nemdoc.createElement("mac")
        mactag.setAttribute("definition", self.macxmlname(ifc))
        nem.appendChild(mactag)
        phytag = nemdoc.createElement("phy")
        phytag.setAttribute("definition", self.phyxmlname(ifc))
        nem.appendChild(phytag)
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

        names = list(self.getnames())
        macnames = names[:len(self._confmatrix_mac)]
        phynames = names[len(self._confmatrix_mac):]

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "RF-PIPE MAC")
        mac.setAttribute("library", "rfpipemaclayer")
        if self.valueof("transmissioncontrolmap", values) is "":
            macnames.remove("transmissioncontrolmap")

        # append MAC options to macdoc
        map(lambda n: mac.appendChild(e.xmlparam(macdoc, n, self.valueof(n, values))), macnames)
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = EmaneUniversalModel.getphydoc(e, self, values, phynames)
        e.xmlwrite(phydoc, self.phyxmlname(ifc))
