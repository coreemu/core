"""
Common support for configurable CORE objects.
"""

from collections import OrderedDict

from core import logger
from core.data import ConfigData


class ConfigShim(object):
    @classmethod
    def str_to_dict(cls, key_values):
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

        :param flags: message flags
        :param int node_id: node id
        :param type_flags: type flags
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
    def __init__(self, _id, _type, label, default="", options=None):
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


class ConfigurableOptions(object):
    # unique name to receive configuration changes
    name = None
    bitmap = None

    @classmethod
    def configurations(cls):
        """
        Returns configuration options supported by this class.

        :return: list of configuration options
        :rtype: list[Configuration]
        """
        return []

    @classmethod
    def config_groups(cls):
        """
        String formatted to specify configuration groupings, using list index positions.

        Example:
            "Group1:start-stop|Group2:start-stop"

        :return: config groups
        :rtype: str
        """
        return None

    @classmethod
    def default_values(cls):
        """
        Retrieves default values for configurations.

        :return: mapping of configuration options that can also be iterated in order of definition
        :rtype: OrderedDict
        """
        return OrderedDict([(config.id, config.default) for config in cls.configurations()])


class ConfigurableManager(object):
    _default_node = -1
    _default_type = "default"

    def __init__(self):
        self._configuration_maps = {}

    def nodes(self):
        return [node_id for node_id in self._configuration_maps.iterkeys() if node_id != self._default_node]

    def config_reset(self, node_id=None):
        logger.debug("resetting all configurations: %s", self.__class__.__name__)
        if not node_id:
            self._configuration_maps.clear()
        elif node_id in self._configuration_maps:
            self._configuration_maps.pop(node_id)

    def set_config(self, _id, value, node_id=_default_node, config_type=_default_type):
        logger.debug("setting config for node(%s) type(%s): %s=%s", node_id, config_type, _id, value)
        node_type_map = self.get_configs(node_id, config_type)
        node_type_map[_id] = value

    def set_configs(self, config, node_id=_default_node, config_type=_default_type):
        logger.debug("setting config for node(%s) type(%s): %s", node_id, config_type, config)
        node_configs = self.get_all_configs(node_id)
        node_configs[config_type] = config

    def get_config(self, _id, node_id=_default_node, config_type=_default_type):
        logger.debug("getting config for node(%s) type(%s): %s", node_id, config_type, _id)
        node_type_map = self.get_configs(node_id, config_type)
        return node_type_map.get(_id)

    def get_configs(self, node_id=_default_node, config_type=_default_type):
        logger.debug("getting configs for node(%s) type(%s)", node_id, config_type)
        node_map = self.get_all_configs(node_id)
        return node_map.setdefault(config_type, {})

    def get_all_configs(self, node_id=_default_node):
        logger.debug("getting all configs for node(%s)", node_id)
        return self._configuration_maps.setdefault(node_id, {})
