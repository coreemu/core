"""
Common support for configurable CORE objects.
"""

import string

from core import logger
from core.data import ConfigData
from core.enumerations import ConfigDataTypes
from core.enumerations import ConfigFlags


class ConfigurableManager(object):
    """
    A generic class for managing Configurables. This class can register
    with a session to receive Config Messages for setting some parameters
    for itself or for the Configurables that it manages.
    """
    # name corresponds to configuration object field
    name = ""

    # type corresponds with register message types
    config_type = None

    def __init__(self):
        """
        Creates a ConfigurableManager instance.

        :param core.session.Session session: session this manager is tied to
        :return: nothing
        """
        # configurable key=values, indexed by node number
        self.configs = {}

        # TODO: fix the need for this and isolate to the mobility class that wants it
        self._modelclsmap = {}

    def configure(self, session, config_data):
        """
        Handle configure messages. The configuration message sent to a
        ConfigurableManager usually is used to:
        1. Request a list of Configurables (request flag)
        2. Reset manager and clear configs (reset flag)
        3. Send values that configure the manager or one of its
           Configurables

        Returns any reply messages.

        :param core.session.Session session: CORE session object
        :param ConfigData config_data: configuration data for carrying out a configuration
        :return: response messages
        """

        if config_data.type == ConfigFlags.REQUEST.value:
            return self.configure_request(config_data)
        elif config_data.type == ConfigFlags.RESET.value:
            return self.configure_reset(config_data)
        else:
            return self.configure_values(config_data)

    def configure_request(self, config_data):
        """
        Request configuration data.

        :param ConfigData config_data: configuration data for carrying out a configuration
        :return: nothing
        """
        return None

    def configure_reset(self, config_data):
        """
        By default, resets this manager to clear configs.

        :param ConfigData config_data: configuration data for carrying out a configuration
        :return: reset response messages, or None
        """
        return self.reset()

    def configure_values(self, config_data):
        """
        Values have been sent to this manager.

        :param ConfigData config_data: configuration data for carrying out a configuration
        :return: nothing
        """
        return None

    def configure_values_keyvalues(self, config_data, target, keys):
        """
        Helper that can be used for configure_values for parsing in
        'key=value' strings from a values field. The key name must be
        in the keys list, and target.key=value is set.

        :param ConfigData config_data: configuration data for carrying out a configuration
        :param target: target to set attribute values on
        :param keys: list of keys to verify validity
        :return: nothing
        """
        values = config_data.data_values

        if values is None:
            return None

        kvs = values.split('|')
        for kv in kvs:
            try:
                key, value = kv.split('=', 1)
                if value is not None and not value.strip():
                    value = None
            except ValueError:
                # value only
                key = keys[kvs.index(kv)]
                value = kv
            if key not in keys:
                raise ValueError("invalid key: %s" % key)
            if value is not None:
                setattr(target, key, value)

        return None

    def reset(self):
        """
        Reset functionality for the configurable class.

        :return: nothing
        """
        return None

    def setconfig(self, nodenum, conftype, values):
        """
        Add configuration values for a node to a dictionary; values are
        usually received from a Configuration Message, and may refer to a
        node for which no object exists yet

        :param int nodenum: node id
        :param conftype: configuration types
        :param values: configuration values
        :return: nothing
        """
        logger.info("setting config for node(%s): %s - %s", nodenum, conftype, values)
        conflist = []
        if nodenum in self.configs:
            oldlist = self.configs[nodenum]
            found = False
            for t, v in oldlist:
                if t == conftype:
                    # replace existing config
                    found = True
                    conflist.append((conftype, values))
                else:
                    conflist.append((t, v))
            if not found:
                conflist.append((conftype, values))
        else:
            conflist.append((conftype, values))
        self.configs[nodenum] = conflist

    def getconfig(self, nodenum, conftype, defaultvalues):
        """
        Get configuration values for a node; if the values don't exist in
        our dictionary then return the default values supplied

        :param int nodenum: node id
        :param conftype: configuration type
        :param defaultvalues: default values
        :return: configuration type and default values
        :type: tuple
        """
        logger.info("getting config for node(%s): %s - default(%s)",
                    nodenum, conftype, defaultvalues)
        if nodenum in self.configs:
            # return configured values
            conflist = self.configs[nodenum]
            for t, v in conflist:
                if conftype is None or t == conftype:
                    return t, v
        # return default values provided (may be None)
        return conftype, defaultvalues

    def getallconfigs(self, use_clsmap=True):
        """
        Return (nodenum, conftype, values) tuples for all stored configs.
        Used when reconnecting to a session.

        :param bool use_clsmap: should a class map be used, default to True
        :return: list of all configurations
        :rtype: list
        """
        r = []
        for nodenum in self.configs:
            for t, v in self.configs[nodenum]:
                if use_clsmap:
                    t = self._modelclsmap[t]
                r.append((nodenum, t, v))
        return r

    def clearconfig(self, nodenum):
        """
        remove configuration values for the specified node;
        when nodenum is None, remove all configuration values

        :param int nodenum: node id
        :return: nothing
        """
        if nodenum is None:
            self.configs = {}
            return
        if nodenum in self.configs:
            self.configs.pop(nodenum)

    def setconfig_keyvalues(self, nodenum, conftype, keyvalues):
        """
        Key values list of tuples for a node.

        :param int nodenum: node id
        :param conftype: configuration type
        :param keyvalues: key valyes
        :return: nothing
        """
        if conftype not in self._modelclsmap:
            logger.warn("Unknown model type '%s'" % conftype)
            return
        model = self._modelclsmap[conftype]
        keys = model.getnames()
        # defaults are merged with supplied values here
        values = list(model.getdefaultvalues())
        for key, value in keyvalues:
            if key not in keys:
                logger.warn("Skipping unknown configuration key for %s: '%s'" % \
                            (conftype, key))
                continue
            i = keys.index(key)
            values[i] = value
        self.setconfig(nodenum, conftype, values)

    def getmodels(self, n):
        """
        Return a list of model classes and values for a net if one has been
        configured. This is invoked when exporting a session to XML.
        This assumes self.configs contains an iterable of (model-names, values)
        and a self._modelclsmapdict exists.

        :param n: network node to get models for
        :return: list of model and values tuples for the network node
        :rtype: list
        """
        r = []
        if n.objid in self.configs:
            v = self.configs[n.objid]
            for model in v:
                cls = self._modelclsmap[model[0]]
                vals = model[1]
                r.append((cls, vals))
        return r


class Configurable(object):
    """
    A generic class for managing configuration parameters.
    Parameters are sent via Configuration Messages, which allow the GUI
    to build dynamic dialogs depending on what is being configured.
    """
    name = ""
    # Configuration items:
    #   ('name', 'type', 'default', 'possible-value-list', 'caption')
    config_matrix = []
    config_groups = None
    bitmap = None

    def __init__(self, session=None, object_id=None):
        """
        Creates a Configurable instance.

        :param core.session.Session session: session for this configurable
        :param object_id:
        """
        self.session = session
        self.object_id = object_id

    def reset(self):
        """
        Reset method.

        :return: nothing
        """
        pass

    def register(self):
        """
        Register method.

        :return: nothing
        """
        pass

    @classmethod
    def getdefaultvalues(cls):
        """
        Retrieve default values from configuration matrix.

        :return: tuple of default values
        :rtype: tuple
        """
        return tuple(map(lambda x: x[2], cls.config_matrix))

    @classmethod
    def getnames(cls):
        """
        Retrieve name values from configuration matrix.

        :return: tuple of name values
        :rtype: tuple
        """
        return tuple(map(lambda x: x[0], cls.config_matrix))

    @classmethod
    def configure(cls, manager, config_data):
        """
        Handle configuration messages for this object.

        :param ConfigurableManager manager: configuration manager
        :param config_data: configuration data
        :return: configuration data object
        :rtype: ConfigData
        """
        reply = None
        node_id = config_data.node
        object_name = config_data.object
        config_type = config_data.type
        interface_id = config_data.interface_number
        values_str = config_data.data_values

        if interface_id is not None:
            node_id = node_id * 1000 + interface_id

        logger.info("received configure message for %s nodenum:%s", cls.name, str(node_id))
        if config_type == ConfigFlags.REQUEST.value:
            logger.info("replying to configure request for %s model", cls.name)
            # when object name is "all", the reply to this request may be None
            # if this node has not been configured for this model; otherwise we
            # reply with the defaults for this model
            if object_name == "all":
                defaults = None
                typeflags = ConfigFlags.UPDATE.value
            else:
                defaults = cls.getdefaultvalues()
                typeflags = ConfigFlags.NONE.value
            values = manager.getconfig(node_id, cls.name, defaults)[1]
            if values is None:
                logger.warn("no active configuration for node (%s), ignoring request")
                # node has no active config for this model (don't send defaults)
                return None
            # reply with config options
            reply = cls.config_data(0, node_id, typeflags, values)
        elif config_type == ConfigFlags.RESET.value:
            if object_name == "all":
                manager.clearconfig(node_id)
        # elif conftype == coreapi.CONF_TYPE_FLAGS_UPDATE:
        else:
            # store the configuration values for later use, when the node
            # object has been created
            if object_name is None:
                logger.info("no configuration object for node %s", node_id)
                return None
            defaults = cls.getdefaultvalues()
            if values_str is None:
                # use default or preconfigured values
                values = manager.getconfig(node_id, cls.name, defaults)[1]
            else:
                # use new values supplied from the conf message
                values = values_str.split('|')
                # determine new or old style config
                new = cls.haskeyvalues(values)
                if new:
                    new_values = list(defaults)
                    keys = cls.getnames()
                    for v in values:
                        key, value = v.split('=', 1)
                        try:
                            new_values[keys.index(key)] = value
                        except ValueError:
                            logger.info("warning: ignoring invalid key '%s'" % key)
                    values = new_values
            manager.setconfig(node_id, object_name, values)

        return reply

    @classmethod
    def config_data(cls, flags, node_id, type_flags, values):
        """
        Convert this class to a Config API message. Some TLVs are defined
        by the class, but node number, conf type flags, and values must
        be passed in.

        :param flags: message flags
        :param int node_id: node id
        :param type_flags: type flags
        :param values: values
        :return: configuration data object
        :rtype: ConfigData
        """
        keys = cls.getnames()
        keyvalues = map(lambda a, b: "%s=%s" % (a, b), keys, values)
        values_str = string.join(keyvalues, '|')
        datatypes = tuple(map(lambda x: x[1], cls.config_matrix))
        captions = reduce(lambda a, b: a + '|' + b, map(lambda x: x[4], cls.config_matrix))
        possible_valuess = reduce(lambda a, b: a + '|' + b, map(lambda x: x[3], cls.config_matrix))

        return ConfigData(
            message_type=flags,
            node=node_id,
            object=cls.name,
            type=type_flags,
            data_types=datatypes,
            data_values=values_str,
            captions=captions,
            possible_values=possible_valuess,
            bitmap=cls.bitmap,
            groups=cls.config_groups
        )

    @staticmethod
    def booltooffon(value):
        """
        Convenience helper turns bool into on (True) or off (False) string.

        :param str value: value to retrieve on/off value for
        :return: on or off string
        :rtype: str
        """
        if value == "1" or value == "true" or value == "on":
            return "on"
        else:
            return "off"

    @staticmethod
    def offontobool(value):
        """
        Convenience helper for converting an on/off string to a integer.

        :param str value: on/off string
        :return: on/off integer value
        :rtype: int
        """
        if type(value) == str:
            if value.lower() == "on":
                return 1
            elif value.lower() == "off":
                return 0
        return value

    @classmethod
    def valueof(cls, name, values):
        """
        Helper to return a value by the name defined in confmatrix.
        Checks if it is boolean

        :param str name: name to get value of
        :param values: values to get value from
        :return: value for name
        """
        i = cls.getnames().index(name)
        if cls.config_matrix[i][1] == ConfigDataTypes.BOOL.value and values[i] != "":
            return cls.booltooffon(values[i])
        else:
            return values[i]

    @staticmethod
    def haskeyvalues(values):
        """
        Helper to check for list of key=value pairs versus a plain old
        list of values. Returns True if all elements are "key=value".

        :param values: items to check for key/value pairs
        :return: True if all values are key/value pairs, False otherwise
        :rtype: bool
        """
        if len(values) == 0:
            return False
        for v in values:
            if "=" not in v:
                return False
        return True

    def getkeyvaluelist(self):
        """
        Helper to return a list of (key, value) tuples. Keys come from
        configuration matrix and values are instance attributes.

        :return: tuples of key value pairs
        :rtype: list
        """
        key_values = []

        for name in self.getnames():
            if hasattr(self, name):
                value = getattr(self, name)
                key_values.append((name, value))

        return key_values
