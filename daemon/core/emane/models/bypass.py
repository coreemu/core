"""
EMANE Bypass model for CORE
"""
from pathlib import Path
from typing import List, Set

from core.config import ConfigBool, Configuration
from core.emane import emanemodel


class EmaneBypassModel(emanemodel.EmaneModel):
    name: str = "emane_bypass"

    # values to ignore, when writing xml files
    config_ignore: Set[str] = {"none"}

    # mac definitions
    mac_library: str = "bypassmaclayer"
    mac_config: List[Configuration] = [
        ConfigBool(
            id="none",
            default="0",
            label="There are no parameters for the bypass model.",
        )
    ]

    # phy definitions
    phy_library: str = "bypassphylayer"
    phy_config: List[Configuration] = []

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        cls._load_platform_config(emane_prefix)
