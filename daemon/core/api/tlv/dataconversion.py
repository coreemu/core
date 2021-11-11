"""
Converts CORE data objects into legacy API messages.
"""
import logging
from collections import OrderedDict
from typing import Dict, List

from core.api.tlv import coreapi, structutils
from core.api.tlv.enumerations import ConfigTlvs, NodeTlvs
from core.config import ConfigGroup, ConfigurableOptions
from core.emulator.data import ConfigData, NodeData

logger = logging.getLogger(__name__)


def convert_node(node_data: NodeData):
    """
    Convenience method for converting NodeData to a packed TLV message.

    :param core.emulator.data.NodeData node_data: node data to convert
    :return: packed node message
    """
    node = node_data.node
    services = None
    if node.services is not None:
        services = "|".join([x.name for x in node.services])
    server = None
    if node.server is not None:
        server = node.server.name
    tlv_data = structutils.pack_values(
        coreapi.CoreNodeTlv,
        [
            (NodeTlvs.NUMBER, node.id),
            (NodeTlvs.TYPE, node.apitype.value),
            (NodeTlvs.NAME, node.name),
            (NodeTlvs.MODEL, node.type),
            (NodeTlvs.EMULATION_SERVER, server),
            (NodeTlvs.X_POSITION, int(node.position.x)),
            (NodeTlvs.Y_POSITION, int(node.position.y)),
            (NodeTlvs.CANVAS, node.canvas),
            (NodeTlvs.SERVICES, services),
            (NodeTlvs.LATITUDE, str(node.position.lat)),
            (NodeTlvs.LONGITUDE, str(node.position.lon)),
            (NodeTlvs.ALTITUDE, str(node.position.alt)),
            (NodeTlvs.ICON, node.icon),
        ],
    )
    return coreapi.CoreNodeMessage.pack(node_data.message_type.value, tlv_data)


def convert_config(config_data):
    """
    Convenience method for converting ConfigData to a packed TLV message.

    :param core.emulator.data.ConfigData config_data: config data to convert
    :return: packed message
    """
    session = None
    if config_data.session is not None:
        session = str(config_data.session)
    tlv_data = structutils.pack_values(
        coreapi.CoreConfigTlv,
        [
            (ConfigTlvs.NODE, config_data.node),
            (ConfigTlvs.OBJECT, config_data.object),
            (ConfigTlvs.TYPE, config_data.type),
            (ConfigTlvs.DATA_TYPES, config_data.data_types),
            (ConfigTlvs.VALUES, config_data.data_values),
            (ConfigTlvs.CAPTIONS, config_data.captions),
            (ConfigTlvs.BITMAP, config_data.bitmap),
            (ConfigTlvs.POSSIBLE_VALUES, config_data.possible_values),
            (ConfigTlvs.GROUPS, config_data.groups),
            (ConfigTlvs.SESSION, session),
            (ConfigTlvs.IFACE_ID, config_data.iface_id),
            (ConfigTlvs.NETWORK_ID, config_data.network_id),
            (ConfigTlvs.OPAQUE, config_data.opaque),
        ],
    )
    return coreapi.CoreConfMessage.pack(config_data.message_type, tlv_data)


class ConfigShim:
    """
    Provides helper methods for converting newer configuration values into TLV
    compatible formats.
    """

    @classmethod
    def str_to_dict(cls, key_values: str) -> Dict[str, str]:
        """
        Converts a TLV key/value string into an ordered mapping.

        :param key_values:
        :return: ordered mapping of key/value pairs
        """
        key_values = key_values.split("|")
        values = OrderedDict()
        for key_value in key_values:
            key, value = key_value.split("=", 1)
            values[key] = value
        return values

    @classmethod
    def groups_to_str(cls, config_groups: List[ConfigGroup]) -> str:
        """
        Converts configuration groups to a TLV formatted string.

        :param config_groups: configuration groups to format
        :return: TLV configuration group string
        """
        group_strings = []
        for config_group in config_groups:
            group_string = (
                f"{config_group.name}:{config_group.start}-{config_group.stop}"
            )
            group_strings.append(group_string)
        return "|".join(group_strings)

    @classmethod
    def config_data(
        cls,
        flags: int,
        node_id: int,
        type_flags: int,
        configurable_options: ConfigurableOptions,
        config: Dict[str, str],
    ) -> ConfigData:
        """
        Convert this class to a Config API message. Some TLVs are defined
        by the class, but node number, conf type flags, and values must
        be passed in.

        :param flags: message flags
        :param node_id: node id
        :param type_flags: type flags
        :param configurable_options: options to create config data for
        :param config: configuration values for options
        :return: configuration data object
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
