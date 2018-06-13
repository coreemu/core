"""
Common support for configurable CORE objects.
"""

from collections import OrderedDict

from core import logger
from core.data import ConfigData


class ConfigShim(object):
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
        logger.debug("configurable: %s", configurable_options)
        logger.debug("configuration options: %s", configurable_options.configurations)
        logger.debug("configuration data: %s", config)
        for configuration in configurable_options.configurations():
            if not captions:
                captions = configuration.label
            else:
                captions += "|%s" % configuration.label

            data_types.append(configuration.type.value)

            options = ",".join(configuration.options)
            possible_values.append(options)

            _id = configuration.id
            config_value = config.get(_id, configuration.default)
            key_value = "%s=%s" % (_id, config_value)
            if not key_values:
                key_values = key_value
            else:
                key_values += "|%s" % key_value

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
            groups=configurable_options.config_groups()
        )


class Configuration(object):
    """
    Represents a configuration options.
    """

    def __init__(self, _id, _type, label, default="", options=None):
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
        return "%s(id=%s, type=%s, default=%s, options=%s)" % (
            self.__class__.__name__, self.id, self.type, self.default, self.options)


class ConfigurableManager(object):
    """
    Provides convenience methods for storing and retrieving configuration options for nodes.
    """
    _default_node = -1
    _default_type = _default_node

    def __init__(self):
        """
        Creates a ConfigurableManager object.
        """
        self._configuration_maps = {}

    def nodes(self):
        """
        Retrieves the ids of all node configurations known by this manager.

        :return: list of node ids
        :rtype: list
        """
        return [node_id for node_id in self._configuration_maps.iterkeys() if node_id != self._default_node]

    def has_configs(self, node_id):
        """
        Checks if this manager contains a configuration for the node id.

        :param int node_id: node id to check for a configuration
        :return: True if a node configuration exists, False otherwise
        :rtype: bool
        """
        return node_id in self._configuration_maps

    def config_reset(self, node_id=None):
        """
        Clears all configurations or configuration for a specific node.

        :param int node_id: node id to clear configurations for, default is None and clears all configurations
        :return: nothing
        """
        logger.debug("resetting all configurations: %s", self.__class__.__name__)
        if not node_id:
            self._configuration_maps.clear()
        elif node_id in self._configuration_maps:
            self._configuration_maps.pop(node_id)

    def set_config(self, _id, value, node_id=_default_node, config_type=_default_type):
        """
        Set a specific configuration value for a node and configuration type.

        :param str _id: configuration key
        :param str value: configuration value
        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :return: nothing
        """
        logger.debug("setting config for node(%s) type(%s): %s=%s", node_id, config_type, _id, value)
        node_type_map = self.get_configs(node_id, config_type)
        node_type_map[_id] = value

    def set_configs(self, config, node_id=_default_node, config_type=_default_type):
        """
        Set configurations for a node and configuration type.

        :param dict config: configurations to set
        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :return: nothing
        """
        logger.debug("setting config for node(%s) type(%s): %s", node_id, config_type, config)
        node_configs = self.get_all_configs(node_id)
        if config_type in node_configs:
            node_configs.pop(config_type)
        node_configs[config_type] = config

    def get_config(self, _id, node_id=_default_node, config_type=_default_type, default=None):
        """
        Retrieves a specific configuration for a node and configuration type.

        :param str _id: specific configuration to retrieve
        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :param default:
        :return: configuration value
        :rtype str
        """
        logger.debug("getting config for node(%s) type(%s): %s", node_id, config_type, _id)
        node_type_map = self.get_configs(node_id, config_type)
        return node_type_map.get(_id, default)

    def get_configs(self, node_id=_default_node, config_type=_default_type):
        """
        Retrieve configurations for a node and configuration type.

        :param int node_id: node id to store configuration for
        :param str config_type: configuration type to store configuration for
        :return: configurations
        :rtype: dict
        """
        logger.debug("getting configs for node(%s) type(%s)", node_id, config_type)
        node_map = self.get_all_configs(node_id)
        return node_map.setdefault(config_type, {})

    def get_all_configs(self, node_id=_default_node):
        """
        Retrieve all current configuration types for a node.

        :param int node_id: node id to retrieve configurations for
        :return: all configuration types for a node
        :rtype: dict
        """
        logger.debug("getting all configs for node(%s)", node_id)
        return self._configuration_maps.setdefault(node_id, OrderedDict())


class ConfigurableOptions(object):
    """
    Provides a base for defining configuration options within CORE.
    """
    name = None
    bitmap = None
    _default_node = -1

    @classmethod
    def configurations(cls):
        """
        Provides the configurations for this class.

        :return: configurations
        :rtype: list[Configuration]
        """
        return []

    @classmethod
    def config_groups(cls):
        """
        Defines how configurations are grouped.

        :return: configuration group definition
        :rtype: str
        """
        return None

    @classmethod
    def default_values(cls):
        """
        Provides an ordered mapping of configuration keys to default values.

        :return: ordered configuration mapping default values
        :rtype: OrderedDict
        """
        return OrderedDict([(config.id, config.default) for config in cls.configurations()])
