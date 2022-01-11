from typing import Any, List

from core.config import (
    ConfigBool,
    ConfigInt,
    ConfigString,
    ConfigurableManager,
    ConfigurableOptions,
    Configuration,
)
from core.emulator.enumerations import RegisterTlvs
from core.plugins.sdt import Sdt


class SessionConfig(ConfigurableManager, ConfigurableOptions):
    """
    Provides session configuration.
    """

    name: str = "session"
    options: List[Configuration] = [
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
    config_type: RegisterTlvs = RegisterTlvs.UTILITY

    def __init__(self) -> None:
        super().__init__()
        self.set_configs(self.default_values())

    def get_config(
        self,
        _id: str,
        node_id: int = ConfigurableManager._default_node,
        config_type: str = ConfigurableManager._default_type,
        default: Any = None,
    ) -> str:
        """
        Retrieves a specific configuration for a node and configuration type.

        :param _id: specific configuration to retrieve
        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :param default: default value to return when value is not found
        :return: configuration value
        """
        value = super().get_config(_id, node_id, config_type, default)
        if value == "":
            value = default
        return value

    def get_config_bool(self, name: str, default: Any = None) -> bool:
        """
        Get configuration value as a boolean.

        :param name: configuration name
        :param default: default value if not found
        :return: boolean for configuration value
        """
        value = self.get_config(name)
        if value is None:
            return default
        return value.lower() == "true"

    def get_config_int(self, name: str, default: Any = None) -> int:
        """
        Get configuration value as int.

        :param name: configuration name
        :param default: default value if not found
        :return: int for configuration value
        """
        value = self.get_config(name, default=default)
        if value is not None:
            value = int(value)
        return value

    def config_reset(self, node_id: int = None) -> None:
        """
        Clear prior configuration files and reset to default values.

        :param node_id: node id to store configuration for
        :return: nothing
        """
        super().config_reset(node_id)
        self.set_configs(self.default_values())
