from typing import Any, List

from core.config import ConfigurableManager, ConfigurableOptions, Configuration
from core.emulator.enumerations import ConfigDataTypes, RegisterTlvs
from core.plugins.sdt import Sdt


class SessionConfig(ConfigurableManager, ConfigurableOptions):
    """
    Provides session configuration.
    """

    name: str = "session"
    options: List[Configuration] = [
        Configuration(
            _id="controlnet", _type=ConfigDataTypes.STRING, label="Control Network"
        ),
        Configuration(
            _id="controlnet0", _type=ConfigDataTypes.STRING, label="Control Network 0"
        ),
        Configuration(
            _id="controlnet1", _type=ConfigDataTypes.STRING, label="Control Network 1"
        ),
        Configuration(
            _id="controlnet2", _type=ConfigDataTypes.STRING, label="Control Network 2"
        ),
        Configuration(
            _id="controlnet3", _type=ConfigDataTypes.STRING, label="Control Network 3"
        ),
        Configuration(
            _id="controlnet_updown_script",
            _type=ConfigDataTypes.STRING,
            label="Control Network Script",
        ),
        Configuration(
            _id="enablerj45",
            _type=ConfigDataTypes.BOOL,
            default="1",
            label="Enable RJ45s",
        ),
        Configuration(
            _id="preservedir",
            _type=ConfigDataTypes.BOOL,
            default="0",
            label="Preserve session dir",
        ),
        Configuration(
            _id="enablesdt",
            _type=ConfigDataTypes.BOOL,
            default="0",
            label="Enable SDT3D output",
        ),
        Configuration(
            _id="sdturl",
            _type=ConfigDataTypes.STRING,
            default=Sdt.DEFAULT_SDT_URL,
            label="SDT3D URL",
        ),
        Configuration(
            _id="ovs", _type=ConfigDataTypes.BOOL, default="0", label="Enable OVS"
        ),
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
