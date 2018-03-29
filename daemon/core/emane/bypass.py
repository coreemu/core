"""
EMANE Bypass model for CORE
"""

from core.emane import emanemodel
from core.enumerations import ConfigDataTypes


class EmaneBypassModel(emanemodel.EmaneModel):
    name = "emane_bypass"
    library = "bypassmaclayer"

    config_ignore = {"none"}
    _config_mac = [
        ("none", ConfigDataTypes.BOOL.value, "0", "True,False",
         "There are no parameters for the bypass model."),
    ]
    _config_phy = []
    config_matrix = _config_mac + _config_phy
    config_groups = "Bypass Parameters:1-1"

    def create_phy_doc(self, emane_manager, values):
        phy_document = emane_manager.xmldoc("phy")
        phy_element = phy_document.getElementsByTagName("phy").pop()
        phy_element.setAttribute("name", "%s PHY" % self.name)
        phy_element.setAttribute("library", "bypassphylayer")
        return phy_document
