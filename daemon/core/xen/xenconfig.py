"""
xenconfig.py: Implementation of the XenConfigManager class for managing
configurable items for XenNodes.

Configuration for a XenNode is available at these three levels:
Global config:         XenConfigManager.configs[0] = (type="xen", values)
   Nodes of this machine type have this config. These are the default values.
   XenConfigManager.default_config comes from defaults + xen.conf
Node type config:      XenConfigManager.configs[0] = (type="mytype", values)
   All nodes of this type have this config.
Node-specific config:  XenConfigManager.configs[nodenumber] = (type, values)
   The node having this specific number has this config.
"""

import ConfigParser
import os
import string

from core import constants
from core.api import coreapi
from core.conf import Configurable
from core.conf import ConfigurableManager
from core.enumerations import ConfigDataTypes
from core.enumerations import ConfigFlags
from core.enumerations import ConfigTlvs
from core.enumerations import RegisterTlvs
from core.misc import log

logger = log.get_logger(__name__)


class XenConfigManager(ConfigurableManager):
    """
    Xen controller object. Lives in a Session instance and is used for
    building Xen profiles.
    """
    name = "xen"
    config_type = RegisterTlvs.EMULATION_SERVER.value

    def __init__(self, session):
        """
        Creates a XenConfigManager instance.

        :param core.session.Session session: session this manager is tied to
        :return: nothing
        """
        ConfigurableManager.__init__(self)
        self.default_config = XenDefaultConfig(session, object_id=None)
        self.loadconfigfile()

    def setconfig(self, nodenum, conftype, values):
        """
        Add configuration values for a node to a dictionary; values are
        usually received from a Configuration Message, and may refer to a
        node for which no object exists yet

        :param int nodenum: node id to configure
        :param str conftype: configuration type
        :param tuple values: values to configure
        :return: None
        """
        # used for storing the global default config
        if nodenum is None:
            nodenum = 0
        return ConfigurableManager.setconfig(self, nodenum, conftype, values)

    def getconfig(self, nodenum, conftype, defaultvalues):
        """
        Get configuration values for a node; if the values don"t exist in
        our dictionary then return the default values supplied; if conftype
        is None then we return a match on any conftype.

        :param int nodenum: node id to configure
        :param str conftype: configuration type
        :param tuple defaultvalues: default values to return
        :return: configuration for node and config type
        :rtype: tuple
        """
        # used for storing the global default config
        if nodenum is None:
            nodenum = 0
        return ConfigurableManager.getconfig(self, nodenum, conftype, defaultvalues)

    def clearconfig(self, nodenum):
        """
        Remove configuration values for a node

        :param int nodenum: node id to clear config
        :return: nothing
        """
        ConfigurableManager.clearconfig(self, nodenum)
        if 0 in self.configs:
            self.configs.pop(0)

    def configure(self, session, config_data):
        """
        Handle configuration messages for global Xen config.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        """
        return self.default_config.configure(self, config_data)

    def loadconfigfile(self, filename=None):
        """
        Load defaults from the /etc/core/xen.conf file into dict object.

        :param str filename: file name of configuration to load
        :return: nothing
        """
        if filename is None:
            filename = os.path.join(constants.CORE_CONF_DIR, "xen.conf")
        cfg = ConfigParser.SafeConfigParser()
        if filename not in cfg.read(filename):
            logger.warn("unable to read Xen config file: %s", filename)
            return
        section = "xen"
        if not cfg.has_section(section):
            logger.warn("%s is missing a xen section!", filename)
            return
        self.configfile = dict(cfg.items(section))
        # populate default config items from config file entries
        vals = list(self.default_config.getdefaultvalues())
        names = self.default_config.getnames()
        for i in range(len(names)):
            if names[i] in self.configfile:
                vals[i] = self.configfile[names[i]]
        # this sets XenConfigManager.configs[0] = (type="xen", vals)
        self.setconfig(None, self.default_config.name, vals)

    def getconfigitem(self, name, model=None, node=None, value=None):
        """
        Get a config item of the given name, first looking for node-specific
        configuration, then model specific, and finally global defaults.
        If a value is supplied, it will override any stored config.

        :param str name: name of config item to get
        :param model: model config to get
        :param node: node config to get
        :param value: value to override stored config, if provided
        :return: nothing
        """
        if value is not None:
            return value
        n = None
        if node:
            n = node.objid
        (t, v) = self.getconfig(nodenum=n, conftype=model, defaultvalues=None)
        if n is not None and v is None:
            # get item from default config for the node type
            (t, v) = self.getconfig(nodenum=None, conftype=model, defaultvalues=None)
        if v is None:
            # get item from default config for the machine type
            (t, v) = self.getconfig(nodenum=None, conftype=self.default_config.name, defaultvalues=None)

        confignames = self.default_config.getnames()
        if v and name in confignames:
            i = confignames.index(name)
            return v[i]
        else:
            # name may only exist in config file
            if name in self.configfile:
                return self.configfile[name]
            else:
                # logger.warn("missing config item "%s"" % name)
                return None


class XenConfig(Configurable):
    """
    Manage Xen configuration profiles.
    """

    @classmethod
    def configure(cls, xen, config_data):
        """
        Handle configuration messages for setting up a model.
        Similar to Configurable.configure(), but considers opaque data
        for indicating node types.

        :param xen: xen instance to configure
        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        """
        reply = None
        node_id = config_data.node
        object_name = config_data.object
        config_type = config_data.type
        opaque = config_data.opaque
        values_str = config_data.data_values

        nodetype = object_name
        if opaque is not None:
            opaque_items = opaque.split(":")
            if len(opaque_items) != 2:
                logger.warn("xen config: invalid opaque data in conf message")
                return None
            nodetype = opaque_items[1]

        logger.info("received configure message for %s", nodetype)
        if config_type == ConfigFlags.REQUEST.value:
            logger.info("replying to configure request for %s " % nodetype)
            # when object name is "all", the reply to this request may be None
            # if this node has not been configured for this model; otherwise we
            # reply with the defaults for this model
            if object_name == "all":
                typeflags = ConfigFlags.UPDATE.value
            else:
                typeflags = ConfigFlags.NONE.value
            values = xen.getconfig(node_id, nodetype, defaultvalues=None)[1]
            if values is None:
                # get defaults from default "xen" config which includes
                # settings from both cls._confdefaultvalues and  xen.conf
                defaults = cls.getdefaultvalues()
                values = xen.getconfig(node_id, cls.name, defaults)[1]
            if values is None:
                return None
            # reply with config options
            if node_id is None:
                node_id = 0
            reply = cls.config_data(0, node_id, typeflags, nodetype, values)
        elif config_type == ConfigFlags.RESET.value:
            if object_name == "all":
                xen.clearconfig(node_id)
        # elif conftype == coreapi.CONF_TYPE_FLAGS_UPDATE:
        else:
            # store the configuration values for later use, when the XenNode
            # object has been created
            if object_name is None:
                logger.info("no configuration object for node %s" % node_id)
                return None
            if values_str is None:
                # use default or preconfigured values
                defaults = cls.getdefaultvalues()
                values = xen.getconfig(node_id, cls.name, defaults)[1]
            else:
                # use new values supplied from the conf message
                values = values_str.split("|")
            xen.setconfig(node_id, nodetype, values)

        return reply

    @classmethod
    def config_data(cls, flags, node_id, type_flags, nodetype, values):
        """
        Convert this class to a Config API message. Some TLVs are defined
        by the class, but node number, conf type flags, and values must
        be passed in.

        :param int flags: configuration flags
        :param int node_id: node id
        :param int type_flags: type flags
        :param int nodetype: node type
        :param tuple values: values
        :return: configuration message
        """
        values_str = string.join(values, "|")
        tlvdata = ""
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.NODE.value, node_id)
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.OBJECT.value, cls.name)
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.TYPE.value, type_flags)
        datatypes = tuple(map(lambda x: x[1], cls.config_matrix))
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.DATA_TYPES.value, datatypes)
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.VALUES.value, values_str)
        captions = reduce(lambda a, b: a + "|" + b, map(lambda x: x[4], cls.config_matrix))
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.CAPTIONS, captions)
        possiblevals = reduce(lambda a, b: a + "|" + b, map(lambda x: x[3], cls.config_matrix))
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.POSSIBLE_VALUES.value, possiblevals)
        if cls.bitmap is not None:
            tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.BITMAP.value, cls.bitmap)
        if cls.config_groups is not None:
            tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.GROUPS.value, cls.config_groups)
        opaque = "%s:%s" % (cls.name, nodetype)
        tlvdata += coreapi.CoreConfigTlv.pack(ConfigTlvs.OPAQUE.value, opaque)
        msg = coreapi.CoreConfMessage.pack(flags, tlvdata)
        return msg


class XenDefaultConfig(XenConfig):
    """
    Global default Xen configuration options.
    """
    name = "xen"
    # Configuration items:
    #   ("name", "type", "default", "possible-value-list", "caption")
    config_matrix = [
        ("ram_size", ConfigDataTypes.STRING.value, "256", "",
         "ram size (MB)"),
        ("disk_size", ConfigDataTypes.STRING.value, "256M", "",
         "disk size (use K/M/G suffix)"),
        ("iso_file", ConfigDataTypes.STRING.value, "", "",
         "iso file"),
        ("mount_path", ConfigDataTypes.STRING.value, "", "",
         "mount path"),
        ("etc_path", ConfigDataTypes.STRING.value, "", "",
         "etc path"),
        ("persist_tar_iso", ConfigDataTypes.STRING.value, "", "",
         "iso persist tar file"),
        ("persist_tar", ConfigDataTypes.STRING.value, "", "",
         "persist tar file"),
        ("root_password", ConfigDataTypes.STRING.value, "password", "",
         "root password"),
    ]

    config_groups = "domU properties:1-%d" % len(config_matrix)
