from typing import Optional

from core.config import ConfigBool, ConfigInt, ConfigString, Configuration
from core.errors import CoreError
from core.plugins.sdt import Sdt


class SessionConfig:
    """
    Provides session configuration.
    """

    options: list[Configuration] = [
        ConfigString(id="controlnet", label="Control Network"),
        ConfigString(id="controlnet0", label="Control Network 0"),
        ConfigString(id="controlnet1", label="Control Network 1"),
        ConfigString(id="controlnet2", label="Control Network 2"),
        ConfigString(id="controlnet3", label="Control Network 3"),
        ConfigString(id="controlnet_updown_script", label="Control Network Script"),
        ConfigBool(id="enablerj45", default="1", label="Enable RJ45s"),
        ConfigBool(id="preservedir", default="0", label="Preserve session dir"),
        ConfigBool(id="enablesdt", default="0", label="Enable SDT3D output"),
        ConfigString(id="sdturl", default=Sdt.DEFAULT_SDT_URL, label="SDT3D URL"),
        ConfigBool(id="ovs", default="0", label="Enable OVS"),
        ConfigInt(id="platform_id_start", default="1", label="EMANE Platform ID Start"),
        ConfigInt(id="nem_id_start", default="1", label="EMANE NEM ID Start"),
        ConfigBool(id="link_enabled", default="1", label="EMANE Links?"),
        ConfigInt(
            id="loss_threshold", default="30", label="EMANE Link Loss Threshold (%)"
        ),
        ConfigInt(
            id="link_interval", default="1", label="EMANE Link Check Interval (sec)"
        ),
        ConfigInt(id="link_timeout", default="4", label="EMANE Link Timeout (sec)"),
        ConfigInt(id="mtu", default="0", label="MTU for All Devices"),
    ]

    def __init__(self, config: dict[str, str] = None) -> None:
        """
        Create a SessionConfig instance.

        :param config: configuration to initialize with
        """
        self._config: dict[str, str] = {x.id: x.default for x in self.options}
        self._config.update(config or {})

    def update(self, config: dict[str, str]) -> None:
        """
        Update current configuration with provided values.

        :param config: configuration to update with
        :return: nothing
        """
        self._config.update(config)

    def set(self, name: str, value: str) -> None:
        """
        Set a configuration value.

        :param name: name of configuration to set
        :param value: value to set
        :return: nothing
        """
        self._config[name] = value

    def get(self, name: str, default: str = None) -> Optional[str]:
        """
        Retrieve configuration value.

        :param name: name of configuration to get
        :param default: value to return as default
        :return: return found configuration value or default
        """
        return self._config.get(name, default)

    def all(self) -> dict[str, str]:
        """
        Retrieve all configuration options.

        :return: configuration value dict
        """
        return self._config

    def get_bool(self, name: str, default: bool = None) -> bool:
        """
        Get configuration value as a boolean.

        :param name: configuration name
        :param default: default value if not found
        :return: boolean for configuration value
        """
        value = self._config.get(name)
        if value is None and default is None:
            raise CoreError(f"missing session options for {name}")
        if value is None:
            return default
        else:
            return value.lower() == "true"

    def get_int(self, name: str, default: int = None) -> int:
        """
        Get configuration value as int.

        :param name: configuration name
        :param default: default value if not found
        :return: int for configuration value
        """
        value = self._config.get(name)
        if value is None and default is None:
            raise CoreError(f"missing session options for {name}")
        if value is None:
            return default
        else:
            return int(value)
