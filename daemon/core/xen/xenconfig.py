#
# CORE
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
xenconfig.py: Implementation of the XenConfigManager class for managing
configurable items for XenNodes.

Configuration for a XenNode is available at these three levels:
Global config:         XenConfigManager.configs[0] = (type='xen', values)
   Nodes of this machine type have this config. These are the default values.
   XenConfigManager.default_config comes from defaults + xen.conf
Node type config:      XenConfigManager.configs[0] = (type='mytype', values)
   All nodes of this type have this config.
Node-specific config:  XenConfigManager.configs[nodenumber] = (type, values)
   The node having this specific number has this config.
'''

import sys, os, threading, subprocess, time, string
import ConfigParser
from xml.dom.minidom import parseString, Document
from core.constants import *
from core.api import coreapi
from core.conf import ConfigurableManager, Configurable


class XenConfigManager(ConfigurableManager):
    ''' Xen controller object. Lives in a Session instance and is used for
        building Xen profiles.
    '''
    _name = "xen"
    _type = coreapi.CORE_TLV_REG_EMULSRV
    
    def __init__(self, session):
        ConfigurableManager.__init__(self, session)
        self.verbose = self.session.getcfgitembool('verbose', False)
        self.default_config = XenDefaultConfig(session, objid=None)
        self.loadconfigfile()

    def setconfig(self, nodenum, conftype, values):
        ''' add configuration values for a node to a dictionary; values are
            usually received from a Configuration Message, and may refer to a
            node for which no object exists yet
        '''
        if nodenum is None: 
            nodenum = 0 # used for storing the global default config
        return ConfigurableManager.setconfig(self, nodenum, conftype, values)

    def getconfig(self, nodenum, conftype, defaultvalues):
        ''' get configuration values for a node; if the values don't exist in
            our dictionary then return the default values supplied; if conftype
            is None then we return a match on any conftype.
        '''
        if nodenum is None: 
            nodenum = 0 # used for storing the global default config
        return ConfigurableManager.getconfig(self, nodenum, conftype,
                                             defaultvalues)

    def clearconfig(self, nodenum):
        ''' remove configuration values for a node
        '''
        ConfigurableManager.clearconfig(self, nodenum)
        if 0 in self.configs:
            self.configs.pop(0)

    def configure(self, session, msg):
        ''' Handle configuration messages for global Xen config.
        '''
        return self.default_config.configure(self, msg)

    def loadconfigfile(self, filename=None):
        ''' Load defaults from the /etc/core/xen.conf file into dict object.
        '''
        if filename is None:
            filename = os.path.join(CORE_CONF_DIR, 'xen.conf')
        cfg = ConfigParser.SafeConfigParser()
        if filename not in cfg.read(filename):
            self.session.warn("unable to read Xen config file: %s" % filename)
            return
        section = "xen"
        if not cfg.has_section(section):
            self.session.warn("%s is missing a xen section!" % filename)
            return
        self.configfile = dict(cfg.items(section))
        # populate default config items from config file entries
        vals = list(self.default_config.getdefaultvalues())
        names = self.default_config.getnames()
        for i in range(len(names)):
            if names[i] in self.configfile:
                vals[i] = self.configfile[names[i]]
        # this sets XenConfigManager.configs[0] = (type='xen', vals)
        self.setconfig(None, self.default_config._name, vals)

    def getconfigitem(self, name, model=None, node=None, value=None):
        ''' Get a config item of the given name, first looking for node-specific
            configuration, then model specific, and finally global defaults.
            If a value is supplied, it will override any stored config.
        '''
        if value is not None:
            return value
        n = None
        if node:
            n = node.objid
        (t, v) = self.getconfig(nodenum=n, conftype=model, defaultvalues=None)
        if n is not None and v is None:
            # get item from default config for the node type
            (t, v) = self.getconfig(nodenum=None, conftype=model,
                                    defaultvalues=None)
        if v is None:
            # get item from default config for the machine type
            (t, v) = self.getconfig(nodenum=None, 
                                    conftype=self.default_config._name,
                                    defaultvalues=None)

        confignames = self.default_config.getnames()
        if v and name in confignames:
            i = confignames.index(name)
            return v[i]
        else:
            # name may only exist in config file
            if name in self.configfile:
                return self.configfile[name]
            else:
                #self.warn("missing config item '%s'" % name)
                return None


class XenConfig(Configurable):
    ''' Manage Xen configuration profiles.
    '''
    
    @classmethod
    def configure(cls, xen, msg):
        ''' Handle configuration messages for setting up a model.
            Similar to Configurable.configure(), but considers opaque data
            for indicating node types.
        '''
        reply = None
        nodenum = msg.gettlv(coreapi.CORE_TLV_CONF_NODE)
        objname = msg.gettlv(coreapi.CORE_TLV_CONF_OBJ)
        conftype = msg.gettlv(coreapi.CORE_TLV_CONF_TYPE)
        opaque = msg.gettlv(coreapi.CORE_TLV_CONF_OPAQUE)

        nodetype = objname
        if opaque is not None:
            opaque_items = opaque.split(':')
            if len(opaque_items) != 2:
                xen.warn("xen config: invalid opaque data in conf message")
                return None
            nodetype = opaque_items[1]

        if xen.verbose:
            xen.info("received configure message for %s" % nodetype)
        if conftype == coreapi.CONF_TYPE_FLAGS_REQUEST:
            if xen.verbose:
                xen.info("replying to configure request for %s " % nodetype)
            # when object name is "all", the reply to this request may be None
            # if this node has not been configured for this model; otherwise we
            # reply with the defaults for this model
            if objname == "all":
                typeflags = coreapi.CONF_TYPE_FLAGS_UPDATE
            else:
                typeflags = coreapi.CONF_TYPE_FLAGS_NONE
            values = xen.getconfig(nodenum, nodetype, defaultvalues=None)[1]
            if values is None:
                # get defaults from default "xen" config which includes
                # settings from both cls._confdefaultvalues and  xen.conf 
                defaults = cls.getdefaultvalues()
                values = xen.getconfig(nodenum, cls._name, defaults)[1]
            if values is None:
                return None
            # reply with config options
            if nodenum is None:
                nodenum = 0
            reply = cls.toconfmsg(0, nodenum, typeflags, nodetype, values)
        elif conftype == coreapi.CONF_TYPE_FLAGS_RESET:
            if objname == "all":
                xen.clearconfig(nodenum)
        #elif conftype == coreapi.CONF_TYPE_FLAGS_UPDATE:
        else:
            # store the configuration values for later use, when the XenNode
            # object has been created
            if objname is None:
                xen.info("no configuration object for node %s" % nodenum)
                return None
            values_str = msg.gettlv(coreapi.CORE_TLV_CONF_VALUES)
            if values_str is None:
                # use default or preconfigured values
                defaults = cls.getdefaultvalues()
                values = xen.getconfig(nodenum, cls._name, defaults)[1]
            else:
                # use new values supplied from the conf message
                values = values_str.split('|')
            xen.setconfig(nodenum, nodetype, values)
        return reply

    @classmethod
    def toconfmsg(cls, flags, nodenum, typeflags, nodetype, values):
        ''' Convert this class to a Config API message. Some TLVs are defined
            by the class, but node number, conf type flags, and values must
            be passed in.
        '''
        values_str = string.join(values, '|')
        tlvdata = ""
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_NODE, nodenum)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_OBJ,
                                            cls._name)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_TYPE,
                                            typeflags) 
        datatypes = tuple( map(lambda x: x[1], cls._confmatrix) )
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_DATA_TYPES,
                                            datatypes) 
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_VALUES,
                                            values_str)
        captions = reduce( lambda a,b: a + '|' + b, \
                           map(lambda x: x[4], cls._confmatrix))
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_CAPTIONS,
                                            captions)
        possiblevals = reduce( lambda a,b: a + '|' + b, \
                               map(lambda x: x[3], cls._confmatrix))
        tlvdata += coreapi.CoreConfTlv.pack(
            coreapi.CORE_TLV_CONF_POSSIBLE_VALUES, possiblevals) 
        if cls._bitmap is not None:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_BITMAP,
                                                cls._bitmap)
        if cls._confgroups is not None:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_GROUPS,
                                                cls._confgroups)
        opaque = "%s:%s" % (cls._name, nodetype)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_OPAQUE,
                                            opaque)
        msg = coreapi.CoreConfMessage.pack(flags, tlvdata)
        return msg


class XenDefaultConfig(XenConfig):
    ''' Global default Xen configuration options.
    '''
    _name = "xen"
    # Configuration items:
    #   ('name', 'type', 'default', 'possible-value-list', 'caption')
    _confmatrix = [
        ('ram_size', coreapi.CONF_DATA_TYPE_STRING, '256', '', 
         'ram size (MB)'),
        ('disk_size', coreapi.CONF_DATA_TYPE_STRING, '256M', '',
         'disk size (use K/M/G suffix)'),
        ('iso_file', coreapi.CONF_DATA_TYPE_STRING, '', '',
         'iso file'),
        ('mount_path', coreapi.CONF_DATA_TYPE_STRING, '', '',
         'mount path'),
        ('etc_path', coreapi.CONF_DATA_TYPE_STRING, '', '',
         'etc path'),
        ('persist_tar_iso', coreapi.CONF_DATA_TYPE_STRING, '', '',
         'iso persist tar file'),
        ('persist_tar', coreapi.CONF_DATA_TYPE_STRING, '', '',
         'persist tar file'),
        ('root_password', coreapi.CONF_DATA_TYPE_STRING, 'password', '',
         'root password'),
        ]

    _confgroups = "domU properties:1-%d" % len(_confmatrix)

