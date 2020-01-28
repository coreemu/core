"""
EMANE Bypass model for CORE
"""
from typing import List

from core.config import ConfigGroup, Configuration
from core.emane import emanemodel
from core.emulator.enumerations import ConfigDataTypes


class EmaneBypassModel(emanemodel.EmaneModel):
    name = "emane_bypass"

    # values to ignore, when writing xml files
    config_ignore = {"none"}

    # mac definitions
    mac_library = "bypassmaclayer"
    mac_config = [
        Configuration(
            _id="none",
            _type=ConfigDataTypes.BOOL,
            default="0",
            label="There are no parameters for the bypass model.",
        )
    ]

    # phy definitions
    phy_library = "bypassphylayer"
    phy_config = []

    @classmethod
    def load(cls, emane_prefix: str) -> None:
        # ignore default logic
        pass

    # override config groups
    @classmethod
    def config_groups(cls) -> List[ConfigGroup]:
        return [ConfigGroup("Bypass Parameters", 1, 1)]
