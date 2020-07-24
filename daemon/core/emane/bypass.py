"""
EMANE Bypass model for CORE
"""
from typing import List, Set

from core.config import Configuration
from core.emane import emanemodel
from core.emulator.enumerations import ConfigDataTypes


class EmaneBypassModel(emanemodel.EmaneModel):
    name: str = "emane_bypass"

    # values to ignore, when writing xml files
    config_ignore: Set[str] = {"none"}

    # mac definitions
    mac_library: str = "bypassmaclayer"
    mac_config: List[Configuration] = [
        Configuration(
            _id="none",
            _type=ConfigDataTypes.BOOL,
            default="0",
            label="There are no parameters for the bypass model.",
        )
    ]

    # phy definitions
    phy_library: str = "bypassphylayer"
    phy_config: List[Configuration] = []

    @classmethod
    def load(cls, emane_prefix: str) -> None:
        # ignore default logic
        pass
