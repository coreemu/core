"""
Common support for configurable CORE objects.
"""

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Type, Union

from core.emane.nodes import EmaneNet
from core.emulator.enumerations import ConfigDataTypes
from core.errors import CoreConfigError
from core.nodes.network import WlanNode

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.location.mobility import WirelessModel

    WirelessModelType = Type[WirelessModel]

_BOOL_OPTIONS: Set[str] = {"0", "1"}


@dataclass
class ConfigGroup:
    """
    Defines configuration group tabs used for display by ConfigurationOptions.
    """

    name: str
    start: int
    stop: int


@dataclass
class Configuration:
    """
    Represents a configuration option.
    """

    id: str
    type: ConfigDataTypes
    label: str = None
    default: str = ""
    options: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.label = self.label if self.label else self.id
        if self.type == ConfigDataTypes.BOOL:
            if self.default and self.default not in _BOOL_OPTIONS:
                raise CoreConfigError(
                    f"{self.id} bool value must be one of: {_BOOL_OPTIONS}: "
                    f"{self.default}"
                )
        elif self.type == ConfigDataTypes.FLOAT:
            if self.default:
                try:
                    float(self.default)
                except ValueError:
                    raise CoreConfigError(
                        f"{self.id} is not a valid float: {self.default}"
                    )
        elif self.type != ConfigDataTypes.STRING:
            if self.default:
                try:
                    int(self.default)
                except ValueError:
                    raise CoreConfigError(
                        f"{self.id} is not a valid int: {self.default}"
                    )


@dataclass
class ConfigBool(Configuration):
    """
    Represents a boolean configuration option.
    """

    type: ConfigDataTypes = ConfigDataTypes.BOOL


@dataclass
class ConfigFloat(Configuration):
    """
    Represents a float configuration option.
    """

    type: ConfigDataTypes = ConfigDataTypes.FLOAT


@dataclass
class ConfigInt(Configuration):
    """
    Represents an integer configuration option.
    """

    type: ConfigDataTypes = ConfigDataTypes.INT32


@dataclass
class ConfigString(Configuration):
    """
    Represents a string configuration option.
    """

    type: ConfigDataTypes = ConfigDataTypes.STRING


class ConfigurableOptions:
    """
    Provides a base for defining configuration options within CORE.
    """

    name: Optional[str] = None
    bitmap: Optional[str] = None
    options: List[Configuration] = []

    @classmethod
    def configurations(cls) -> List[Configuration]:
        """
        Provides the configurations for this class.

        :return: configurations
        """
        return cls.options

    @classmethod
    def config_groups(cls) -> List[ConfigGroup]:
        """
        Defines how configurations are grouped.

        :return: configuration group definition
        """
        return [ConfigGroup("Options", 1, len(cls.configurations()))]

    @classmethod
    def default_values(cls) -> Dict[str, str]:
        """
        Provides an ordered mapping of configuration keys to default values.

        :return: ordered configuration mapping default values
        """
        return OrderedDict(
            [(config.id, config.default) for config in cls.configurations()]
        )


class ConfigurableManager:
    """
    Provides convenience methods for storing and retrieving configuration options for
    nodes.
    """

    _default_node: int = -1
    _default_type: int = _default_node

    def __init__(self) -> None:
        """
        Creates a ConfigurableManager object.
        """
        self.node_configurations = {}

    def nodes(self) -> List[int]:
        """
        Retrieves the ids of all node configurations known by this manager.

        :return: list of node ids
        """
        return [x for x in self.node_configurations if x != self._default_node]

    def config_reset(self, node_id: int = None) -> None:
        """
        Clears all configurations or configuration for a specific node.

        :param node_id: node id to clear configurations for, default is None and clears
            all configurations
        :return: nothing
        """
        if not node_id:
            self.node_configurations.clear()
        elif node_id in self.node_configurations:
            self.node_configurations.pop(node_id)

    def set_config(
        self,
        _id: str,
        value: str,
        node_id: int = _default_node,
        config_type: str = _default_type,
    ) -> None:
        """
        Set a specific configuration value for a node and configuration type.

        :param _id: configuration key
        :param value: configuration value
        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :return: nothing
        """
        node_configs = self.node_configurations.setdefault(node_id, OrderedDict())
        node_type_configs = node_configs.setdefault(config_type, OrderedDict())
        node_type_configs[_id] = value

    def set_configs(
        self,
        config: Dict[str, str],
        node_id: int = _default_node,
        config_type: str = _default_type,
    ) -> None:
        """
        Set configurations for a node and configuration type.

        :param config: configurations to set
        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :return: nothing
        """
        logger.debug(
            "setting config for node(%s) type(%s): %s", node_id, config_type, config
        )
        node_configs = self.node_configurations.setdefault(node_id, OrderedDict())
        node_configs[config_type] = config

    def get_config(
        self,
        _id: str,
        node_id: int = _default_node,
        config_type: str = _default_type,
        default: str = None,
    ) -> str:
        """
        Retrieves a specific configuration for a node and configuration type.

        :param _id: specific configuration to retrieve
        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :param default: default value to return when value is not found
        :return: configuration value
        """
        result = default
        node_type_configs = self.get_configs(node_id, config_type)
        if node_type_configs:
            result = node_type_configs.get(_id, default)
        return result

    def get_configs(
        self, node_id: int = _default_node, config_type: str = _default_type
    ) -> Optional[Dict[str, str]]:
        """
        Retrieve configurations for a node and configuration type.

        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :return: configurations
        """
        result = None
        node_configs = self.node_configurations.get(node_id)
        if node_configs:
            result = node_configs.get(config_type)
        return result

    def get_all_configs(self, node_id: int = _default_node) -> Dict[str, Any]:
        """
        Retrieve all current configuration types for a node.

        :param node_id: node id to retrieve configurations for
        :return: all configuration types for a node
        """
        return self.node_configurations.get(node_id)


class ModelManager(ConfigurableManager):
    """
    Helps handle setting models for nodes and managing their model configurations.
    """

    def __init__(self) -> None:
        """
        Creates a ModelManager object.
        """
        super().__init__()
        self.models: Dict[str, Any] = {}
        self.node_models: Dict[int, str] = {}

    def set_model_config(
        self, node_id: int, model_name: str, config: Dict[str, str] = None
    ) -> None:
        """
        Set configuration data for a model.

        :param node_id: node id to set model configuration for
        :param model_name: model to set configuration for
        :param config: configuration data to set for model
        :return: nothing
        """
        # get model class to configure
        model_class = self.models.get(model_name)
        if not model_class:
            raise ValueError(f"{model_name} is an invalid model")

        # retrieve default values
        model_config = self.get_model_config(node_id, model_name)
        if not config:
            config = {}
        for key in config:
            value = config[key]
            model_config[key] = value

        # set as node model for startup
        self.node_models[node_id] = model_name

        # set configuration
        self.set_configs(model_config, node_id=node_id, config_type=model_name)

    def get_model_config(self, node_id: int, model_name: str) -> Dict[str, str]:
        """
        Retrieve configuration data for a model.

        :param node_id: node id to set model configuration for
        :param model_name: model to set configuration for
        :return: current model configuration for node
        """
        # get model class to configure
        model_class = self.models.get(model_name)
        if not model_class:
            raise ValueError(f"{model_name} is an invalid model")

        config = self.get_configs(node_id=node_id, config_type=model_name)
        if not config:
            # set default values, when not already set
            config = model_class.default_values()
            self.set_configs(config, node_id=node_id, config_type=model_name)

        return config

    def set_model(
        self,
        node: Union[WlanNode, EmaneNet],
        model_class: "WirelessModelType",
        config: Dict[str, str] = None,
    ) -> None:
        """
        Set model and model configuration for node.

        :param node: node to set model for
        :param model_class: model class to set for node
        :param config: model configuration, None for default configuration
        :return: nothing
        """
        logger.debug(
            "setting model(%s) for node(%s): %s", model_class.name, node.id, config
        )
        self.set_model_config(node.id, model_class.name, config)
        config = self.get_model_config(node.id, model_class.name)
        node.setmodel(model_class, config)

    def get_models(
        self, node: Union[WlanNode, EmaneNet]
    ) -> List[Tuple[Type, Dict[str, str]]]:
        """
        Return a list of model classes and values for a net if one has been
        configured. This is invoked when exporting a session to XML.

        :param node: network node to get models for
        :return: list of model and values tuples for the network node
        """
        all_configs = self.get_all_configs(node.id)
        if not all_configs:
            all_configs = {}

        models = []
        for model_name in all_configs:
            config = all_configs[model_name]
            if model_name == ModelManager._default_node:
                continue
            model_class = self.models[model_name]
            models.append((model_class, config))

        logger.debug("models for node(%s): %s", node.id, models)
        return models
