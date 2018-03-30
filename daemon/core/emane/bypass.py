"""
EMANE Bypass model for CORE
"""

from core.emane import emanemodel
from core.enumerations import ConfigDataTypes


class EmaneBypassModel(emanemodel.EmaneModel):
    name = "emane_bypass"

    # values to ignore, when writing xml files
    config_ignore = {"none"}

    # mac definitions
    mac_library = "bypassmaclayer"
    config_mac = [
        ("none", ConfigDataTypes.BOOL.value, "0", "True,False",
         "There are no parameters for the bypass model."),
    ]

    # phy definitions
    phy_library = "bypassphylayer"
    config_phy = []

    # defines overall config
    config_matrix = config_mac + config_phy

    # gui display tabs
    config_groups = "Bypass Parameters:1-1"
