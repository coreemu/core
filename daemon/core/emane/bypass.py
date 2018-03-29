"""
EMANE Bypass model for CORE
"""

from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes


class EmaneBypassModel(EmaneModel):
    name = "emane_bypass"
    library = "bypassmaclayer"

    config_ignore = {"none"}
    _config_mac = [
        ("none", ConfigDataTypes.BOOL.value, "0", "True,False",
         "There are no parameters for the bypass model."),
    ]
    _config_phy = []

    @property
    def config_groups(self):
        return "Bypass Parameters:1-1"
