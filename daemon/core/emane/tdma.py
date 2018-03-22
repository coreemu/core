"""
tdma.py: EMANE TDMA model bindings for CORE
"""

from core.emane.emanemodel import EmaneModel
from core.emane.universal import EmaneUniversalModel
from core.enumerations import ConfigDataTypes


class EmaneTdmaModel(EmaneModel):
    # model name
    name = "emane_tdma"
    xml_path = "/usr/share/emane/xml/models/mac/tdmaeventscheduler"

    # MAC parameters
    _confmatrix_mac = [
        ("enablepromiscuousmode", ConfigDataTypes.BOOL.value, "0", "True,False", "enable promiscuous mode"),
        ("flowcontrolenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "enable traffic flow control"),
        ("flowcontroltokens", ConfigDataTypes.UINT16.value, "10", "", "number of flow control tokens"),
        ("fragmentcheckthreshold", ConfigDataTypes.UINT16.value, "2", "",
         "rate in seconds for check if fragment reassembly efforts should be abandoned"),
        ("fragmenttimeoutthreshold", ConfigDataTypes.UINT16.value, "5", "",
         "threshold in seconds to wait for another packet fragment for reassembly"),
        ("neighbormetricdeletetime", ConfigDataTypes.FLOAT.value, "60.0", "",
         "neighbor RF reception timeout for removal from neighbor table (sec)"),
        ("neighbormetricupdateinterval", ConfigDataTypes.FLOAT.value, "1.0", "",
         "neighbor table update interval (sec)"),
        ("pcrcurveuri", ConfigDataTypes.STRING.value, "%s/tdmabasemodelpcr.xml" % xml_path, "", "SINR/PCR curve file"),
        ("queue.aggregationenable", ConfigDataTypes.BOOL.value, "1", "On,Off", "enable transmit packet aggregation"),
        ("queue.aggregationslotthreshold", ConfigDataTypes.FLOAT.value, "90.0", "",
         "percentage of a slot that must be filled in order to conclude aggregation"),
        ("queue.depth", ConfigDataTypes.UINT16.value, "256", "",
         "size of the per service class downstream packet queues (packets)"),
        ("queue.fragmentationenable", ConfigDataTypes.BOOL.value, "1", "On,Off",
         "enable packet fragmentation (over multiple slots)"),
        ("queue.strictdequeueenable", ConfigDataTypes.BOOL.value, "0", "On,Off",
         "enable strict dequeueing to specified queues  only"),
    ]

    # PHY parameters from Universal PHY
    _confmatrix_phy = EmaneUniversalModel.config_matrix

    config_matrix = _confmatrix_mac + _confmatrix_phy

    # value groupings
    config_groups = "TDMA MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" % (
        len(_confmatrix_mac), len(_confmatrix_mac) + 1, len(config_matrix))

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    def buildnemxmlfiles(self, e, ifc):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide nXXemane_tdmanem.xml,
        nXXemane_tdmamac.xml, nXXemane_tdmaphy.xml are used.
        """
        values = e.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), ifc)
        if values is None:
            return

        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "TDMA NEM")
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
        # make any changes to the mac/phy names here to e.g. exclude them from
        # the XML output

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "TDMA MAC")
        mac.setAttribute("library", "tdmaeventschedulerradiomodel")
        # append MAC options to macdoc
        map(lambda n: mac.appendChild(e.xmlparam(macdoc, n, self.valueof(n, values))), macnames)
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = EmaneUniversalModel.getphydoc(e, self, values, phynames)
        e.xmlwrite(phydoc, self.phyxmlname(ifc))
