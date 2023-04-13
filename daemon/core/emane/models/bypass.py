"""
EMANE Bypass model for CORE
"""
from pathlib import Path

from core.config import ConfigBool, Configuration
from core.emane import emanemodel


class EmaneBypassModel(emanemodel.EmaneModel):
    name: str = "emane_bypass"

    # values to ignore, when writing xml files
    config_ignore: set[str] = {"none"}

    # mac definitions
    mac_library: str = "bypassmaclayer"
    mac_config: list[Configuration] = [
        ConfigBool(
            id="none",
            default="0",
            label="There are no parameters for the bypass model.",
        )
    ]

    # phy definitions
    phy_library: str = "bypassphylayer"
    phy_config: list[Configuration] = []

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        cls._load_platform_config(emane_prefix)
