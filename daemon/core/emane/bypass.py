"""
bypass.py: EMANE Bypass model for CORE
"""

from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes


class EmaneBypassModel(EmaneModel):
    name = "emane_bypass"
    config_matrix = [
        ("none", ConfigDataTypes.BOOL.value, "0",
         "True,False", "There are no parameters for the bypass model."),
    ]

    # value groupings
    config_groups = "Bypass Parameters:1-1"

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    def buildnemxmlfiles(self, e, ifc):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide nXXemane_bypassnem.xml,
        nXXemane_bypassmac.xml, nXXemane_bypassphy.xml are used.
        """
        values = e.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), ifc)
        if values is None:
            return
        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "BYPASS NEM")
        e.appendtransporttonem(nemdoc, nem, self.object_id, ifc)
        mactag = nemdoc.createElement("mac")
        mactag.setAttribute("definition", self.macxmlname(ifc))
        nem.appendChild(mactag)
        phytag = nemdoc.createElement("phy")
        phytag.setAttribute("definition", self.phyxmlname(ifc))
        nem.appendChild(phytag)
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "BYPASS MAC")
        mac.setAttribute("library", "bypassmaclayer")
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = e.xmldoc("phy")
        phy = phydoc.getElementsByTagName("phy").pop()
        phy.setAttribute("name", "BYPASS PHY")
        phy.setAttribute("library", "bypassphylayer")
        e.xmlwrite(phydoc, self.phyxmlname(ifc))
