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
    configuration_maps = None
    _default_node = -1

    @classmethod
    def configurations(cls):
        return []

    @classmethod
    def config_groups(cls):
        return None

    @classmethod
    def default_values(cls):
        return OrderedDict([(config.id, config.default) for config in cls.configurations()])

    @classmethod
    def nodes(cls):
        return {node_id for node_id in cls.configuration_maps.iterkeys() if node_id != cls._default_node}

    @classmethod
    def config_reset(cls, node_id=None):
        if not node_id:
            logger.debug("resetting all configurations: %s", cls.__name__)
            cls.configuration_maps.clear()
        elif node_id in cls.configuration_maps:
            logger.debug("resetting node(%s) configurations: %s", node_id, cls.__name__)
            cls.configuration_maps.pop(node_id)

    @classmethod
    def set_config(cls, _id, value, node_id=_default_node):
        logger.debug("setting config for node(%s) type(%s): %s=%s", node_id, _id, value)
        node_configs = cls.get_configs(node_id)
        node_configs[_id] = value

    @classmethod
    def get_config(cls, _id, node_id=_default_node, default=None):
        node_configs = cls.get_configs(node_id)
        value = node_configs.get(_id, default)
        logger.debug("getting config for node(%s): %s = %s", node_id, _id, value)
        return value

    @classmethod
    def set_configs(cls, config=None, node_id=_default_node):
        logger.debug("setting config for node(%s): %s", node_id, config)
        node_config = cls.get_configs(node_id)
        if config:
            for key, value in config.iteritems():
                node_config[key] = value

    @classmethod
    def get_configs(cls, node_id=_default_node):
        logger.debug("getting configs for node(%s)", node_id)
        return cls.configuration_maps.setdefault(node_id, cls.default_values())
