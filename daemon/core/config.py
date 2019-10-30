"""
Common support for configurable CORE objects.
"""

import logging
from collections import OrderedDict

from core.emulator.data import ConfigData


class ConfigShim:
    """
    Provides helper methods for converting newer configuration values into TLV compatible formats.
    """

    @classmethod
    def str_to_dict(cls, key_values):
        """
        Converts a TLV key/value string into an ordered mapping.

        :param str key_values:
        :return: ordered mapping of key/value pairs
        :rtype: OrderedDict
        """
        key_values = key_values.split("|")
        values = OrderedDict()
        for key_value in key_values:
            key, value = key_value.split("=", 1)
            values[key] = value
        return values

    @classmethod
    def groups_to_str(cls, config_groups):
        """
        Converts configuration groups to a TLV formatted string.

        :param list[ConfigGroup] config_groups: configuration groups to format
        :return: TLV configuration group string
        :rtype: str
        """
        group_strings = []
        for config_group in config_groups:
            group_string = (
                f"{config_group.name}:{config_group.start}-{config_group.stop}"
            )
            group_strings.append(group_string)
        return "|".join(group_strings)

    @classmethod
    def config_data(cls, flags, node_id, type_flags, configurable_options, config):
        """
        Convert this class to a Config API message. Some TLVs are defined
        by the class, but node number, conf type flags, and values must
        be passed in.

        :param int flags: message flags
        :param int node_id: node id
        :param int type_flags: type flags
        :param ConfigurableOptions configurable_options: options to create config data for
        :param dict config: configuration values for options
        :return: configuration data object
        :rtype: ConfigData
        """
        key_values = None
        captions = None
        data_types = []
        possible_values = []
        logging.debug("configurable: %s", configurable_options)
        logging.debug("configuration options: %s", configurable_options.configurations)
        logging.debug("configuration data: %s", config)
        for configuration in configurable_options.configurations():
            if not captions:
                captions = configuration.label
            else:
                captions += f"|{configuration.label}"

            data_types.append(configuration.type.value)

            options = ",".join(configuration.options)
            possible_values.append(options)

            _id = configuration.id
            config_value = config.get(_id, configuration.default)
            key_value = f"{_id}={config_value}"
            if not key_values:
                key_values = key_value
            else:
                key_values += f"|{key_value}"

        groups_str = cls.groups_to_str(configurable_options.config_groups())
        return ConfigData(
            message_type=flags,
            node=node_id,
            object=configurable_options.name,
            type=type_flags,
            data_types=tuple(data_types),
            data_values=key_values,
            captions=captions,
            possible_values="|".join(possible_values),
            bitmap=configurable_options.bitmap,
            groups=groups_str,
        )


class Configuration:
    """
    Represents a configuration options.
    """

    def __init__(self, _id, _type, label=None, default="", options=None):
        """
        Creates a Configuration object.

        :param str _id: unique name for configuration
        :param core.enumerations.ConfigDataTypes _type: configuration data type
        :param str label: configuration label for display
        :param str default: default value for configuration
        :param list options: list options if this is a configuration with a combobox
        """
        self.id = _id
        self.type = _type
        self.default = default
        if not options:
            options = []
        self.options = options
        if not label:
            label = _id
        self.label = label

    def __str__(self):
        return f"{self.__class__.__name__}(id={self.id}, type={self.type}, default={self.default}, options={self.options})"


class ConfigurableManager:
    """
    Provides convenience methods for storing and retrieving configuration options for nodes.
    """

    _default_node = -1
    _default_type = _default_node

    def __init__(self):
        """
        Creates a ConfigurableManager object.
        """
        self.node_configurations = {}

    def nodes(self):
        """
        Retrieves the ids of all node configurations known by this manager.

        :return: list of node ids
        :rtype: list
        """
        return [x for x in self.node_configurations if x != self._default_node]

    def config_reset(self, node_id=None):
        """
        Clears all configurations or configuration for a specific node.

        :param int node_id: node id to clear configurations for, default is None and clears all configurations
        :return: nothing
        """
        if not node_id:
            self.node_configurations.clear()
        elif node_id in self.node_configurations:
            self.node_configurations.pop(node_id)

    def set_config(self, _id, value, node_id=_default_node, config_type=_default_type):
        """
        Set a specific configuration value for a node and configuration type.

        :param str _id: configuration key
        :param str value: configuration value
        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :return: nothing
        """
        node_configs = self.node_configurations.setdefault(node_id, OrderedDict())
        node_type_configs = node_configs.setdefault(config_type, OrderedDict())
        node_type_configs[_id] = value

    def set_configs(self, config, node_id=_default_node, config_type=_default_type):
        """
        Set configurations for a node and configuration type.

        :param dict config: configurations to set
        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :return: nothing
        """
        logging.debug(
            "setting config for node(%s) type(%s): %s", node_id, config_type, config
        )
        node_configs = self.node_configurations.setdefault(node_id, OrderedDict())
        node_configs[config_type] = config

    def get_config(
        self, _id, node_id=_default_node, config_type=_default_type, default=None
    ):
        """
        Retrieves a specific configuration for a node and configuration type.

        :param str _id: specific configuration to retrieve
        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :param default: default value to return when value is not found
        :return: configuration value
        :rtype str
        """
        result = default
        node_type_configs = self.get_configs(node_id, config_type)
        if node_type_configs:
            result = node_type_configs.get(_id, default)
        return result

    def get_configs(self, node_id=_default_node, config_type=_default_type):
        """
        Retrieve configurations for a node and configuration type.

        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :return: configurations
        :rtype: dict
        """
        result = None
        node_configs = self.node_configurations.get(node_id)
        if node_configs:
            result = node_configs.get(config_type)
        return result

    def get_all_configs(self, node_id=_default_node):
        """
        Retrieve all current configuration types for a node.

        :param int node_id: node id to retrieve configurations for
        :return: all configuration types for a node
        :rtype: dict
        """
        return self.node_configurations.get(node_id)


class ConfigGroup:
    """
    Defines configuration group tabs used for display by ConfigurationOptions.
    """

    def __init__(self, name, start, stop):
        """
        Creates a ConfigGroup object.

        :param str name: configuration group display name
        :param int start: configurations start index for this group
        :param int stop: configurations stop index for this group
        """
        self.name = name
        self.start = start
        self.stop = stop


class ConfigurableOptions:
    """
    Provides a base for defining configuration options within CORE.
    """

    name = None
    bitmap = None
    options = []

    @classmethod
    def configurations(cls):
        """
        Provides the configurations for this class.

        :return: configurations
        :rtype: list[Configuration]
        """
        return cls.options

    @classmethod
    def config_groups(cls):
        """
        Defines how configurations are grouped.

        :return: configuration group definition
        :rtype: list[ConfigGroup]
        """
        return [ConfigGroup("Options", 1, len(cls.configurations()))]

    @classmethod
    def default_values(cls):
        """
        Provides an ordered mapping of configuration keys to default values.

        :return: ordered configuration mapping default values
        :rtype: OrderedDict
        """
        return OrderedDict(
            [(config.id, config.default) for config in cls.configurations()]
        )


class ModelManager(ConfigurableManager):
    """
    Helps handle setting models for nodes and managing their model configurations.
    """

    def __init__(self):
        """
        Creates a ModelManager object.
        """
        super().__init__()
        self.models = {}
        self.node_models = {}

    def set_model_config(self, node_id, model_name, config=None):
        """
        Set configuration data for a model.

        :param int node_id: node id to set model configuration for
        :param str model_name: model to set configuration for
        :param dict config: configuration data to set for model
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

    def get_model_config(self, node_id, model_name):
        """
        Retrieve configuration data for a model.

        :param int node_id: node id to set model configuration for
        :param str model_name: model to set configuration for
        :return: current model configuration for node
        :rtype: dict
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

    def set_model(self, node, model_class, config=None):
        """
        Set model and model configuration for node.

        :param node: node to set model for
        :param model_class: model class to set for node
        :param dict config: model configuration, None for default configuration
        :return: nothing
        """
        logging.debug(
            "setting model(%s) for node(%s): %s", model_class.name, node.id, config
        )
        self.set_model_config(node.id, model_class.name, config)
        config = self.get_model_config(node.id, model_class.name)
        node.setmodel(model_class, config)

    def get_models(self, node):
        """
        Return a list of model classes and values for a net if one has been
        configured. This is invoked when exporting a session to XML.

        :param node: network node to get models for
        :return: list of model and values tuples for the network node
        :rtype: list
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

        logging.debug("models for node(%s): %s", node.id, models)
        return models
