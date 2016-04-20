#
# CORE
# Copyright (c)2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
conf.py: common support for configurable objects
'''
import string
from core.api import coreapi

class ConfigurableManager(object):
    ''' A generic class for managing Configurables. This class can register
        with a session to receive Config Messages for setting some parameters
        for itself or for the Configurables that it manages.
    '''
    # name corresponds to configuration object field
    _name = ""
    # type corresponds with register message types 
    _type = None
    
    def __init__(self, session=None):
        self.session = session
        self.session.addconfobj(self._name, self._type, self.configure)
        # Configurable key=values, indexed by node number
        self.configs = {}

        
    def configure(self, session, msg):
        ''' Handle configure messages. The configuration message sent to a
            ConfigurableManager usually is used to:
            1. Request a list of Configurables (request flag)
            2. Reset manager and clear configs (reset flag)
            3. Send values that configure the manager or one of its 
               Configurables
               
            Returns any reply messages.
        '''
        objname = msg.gettlv(coreapi.CORE_TLV_CONF_OBJ)
        conftype = msg.gettlv(coreapi.CORE_TLV_CONF_TYPE)
        if conftype == coreapi.CONF_TYPE_FLAGS_REQUEST:
            return self.configure_request(msg)            
        elif conftype == coreapi.CONF_TYPE_FLAGS_RESET:
            if objname == "all" or objname == self._name:
                return self.configure_reset(msg)
        else:
            return self.configure_values(msg,
                                    msg.gettlv(coreapi.CORE_TLV_CONF_VALUES))

    def configure_request(self, msg):
        ''' Request configuration data.
        '''
        return None

    def configure_reset(self, msg):
        ''' By default, resets this manager to clear configs.
        '''
        return self.reset()
    
    def configure_values(self, msg, values):
        ''' Values have been sent to this manager.
        '''
        return None
        
    def configure_values_keyvalues(self, msg, values, target, keys):
        ''' Helper that can be used for configure_values for parsing in
            'key=value' strings from a values field. The key name must be
            in the keys list, and target.key=value is set.
        '''
        if values is None:
            return None
        kvs = values.split('|')
        for kv in kvs:
            try:
                # key=value
                (key, value) = kv.split('=', 1)
                if value is not None and not value.strip():
                    value = None
            except ValueError:
                # value only
                key = keys[kvs.index(kv)]
                value = kv
            if key not in keys:
                raise ValueError, "invalid key: %s" % key
            if value is not None:
                setattr(target, key, value)
        return None

    def reset(self):
        return None
        
    def setconfig(self, nodenum, conftype, values):
        ''' add configuration values for a node to a dictionary; values are
            usually received from a Configuration Message, and may refer to a
            node for which no object exists yet
        '''
        conflist = []
        if nodenum in self.configs:
            oldlist = self.configs[nodenum]
            found = False
            for (t, v) in oldlist:
                if (t == conftype):
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
        ''' get configuration values for a node; if the values don't exist in
            our dictionary then return the default values supplied
        '''
        if nodenum in self.configs:
            # return configured values
            conflist = self.configs[nodenum]
            for (t, v) in conflist:
                if (conftype is None) or (t == conftype):
                    return (t, v)
        # return default values provided (may be None)
        return (conftype, defaultvalues)
        
    def getallconfigs(self, use_clsmap=True):
        ''' Return (nodenum, conftype, values) tuples for all stored configs.
        Used when reconnecting to a session.
        '''
        r = []
        for nodenum in self.configs:
            for (t, v) in self.configs[nodenum]:
                if use_clsmap:
                    t = self._modelclsmap[t]
                r.append( (nodenum, t, v) )
        return r

    def clearconfig(self, nodenum):
        ''' remove configuration values for the specified node;
            when nodenum is None, remove all configuration values 
        '''
        if nodenum is None:
            self.configs = {}
            return
        if nodenum in self.configs:
            self.configs.pop(nodenum)

    def setconfig_keyvalues(self, nodenum, conftype, keyvalues):
        ''' keyvalues list of tuples
        '''
        if conftype not in self._modelclsmap:
            self.warn("Unknown model type '%s'" % (conftype))
            return
        model = self._modelclsmap[conftype]
        keys = model.getnames()
        # defaults are merged with supplied values here
        values = list(model.getdefaultvalues())
        for key, value in keyvalues:
            if key not in keys:
                self.warn("Skipping unknown configuration key for %s: '%s'" % \
                          (conftype, key))
                continue
            i = keys.index(key)
            values[i] = value
        self.setconfig(nodenum, conftype, values)

    def getmodels(self, n):
        ''' Return a list of model classes and values for a net if one has been
        configured. This is invoked when exporting a session to XML.
        This assumes self.configs contains an iterable of (model-names, values)
        and a self._modelclsmapdict exists.
        '''
        r = []
        if n.objid in self.configs:
            v = self.configs[n.objid]
            for model in v:
                cls = self._modelclsmap[model[0]]
                vals = model[1]
                r.append((cls, vals))
        return r


    def info(self, msg):
        self.session.info(msg)
    
    def warn(self, msg):
        self.session.warn(msg)


class Configurable(object):
    ''' A generic class for managing configuration parameters.
        Parameters are sent via Configuration Messages, which allow the GUI
        to build dynamic dialogs depending on what is being configured.
    '''
    _name = ""
    # Configuration items:
    #   ('name', 'type', 'default', 'possible-value-list', 'caption')
    _confmatrix = []
    _confgroups = None
    _bitmap = None
    
    def __init__(self, session=None, objid=None):
        self.session = session
        self.objid = objid
    
    def reset(self):
        pass
    
    def register(self):
        pass
        
    @classmethod
    def getdefaultvalues(cls):
        return tuple( map(lambda x: x[2], cls._confmatrix) )
    
    @classmethod
    def getnames(cls):
        return tuple( map( lambda x: x[0], cls._confmatrix) )

    @classmethod
    def configure(cls, mgr, msg):
        ''' Handle configuration messages for this object.
        '''
        reply = None
        nodenum = msg.gettlv(coreapi.CORE_TLV_CONF_NODE)
        objname = msg.gettlv(coreapi.CORE_TLV_CONF_OBJ)
        conftype = msg.gettlv(coreapi.CORE_TLV_CONF_TYPE)
        
        ifacenum = msg.gettlv(coreapi.CORE_TLV_CONF_IFNUM)
        if ifacenum is not None:
            nodenum = nodenum*1000 + ifacenum

        if mgr.verbose:
            mgr.info("received configure message for %s nodenum:%s" % (cls._name, str(nodenum)))
        if conftype == coreapi.CONF_TYPE_FLAGS_REQUEST:
            if mgr.verbose:
                mgr.info("replying to configure request for %s model" %
                           cls._name)
            # when object name is "all", the reply to this request may be None
            # if this node has not been configured for this model; otherwise we
            # reply with the defaults for this model
            if objname == "all":
                defaults = None
                typeflags = coreapi.CONF_TYPE_FLAGS_UPDATE
            else:
                defaults = cls.getdefaultvalues()
                typeflags = coreapi.CONF_TYPE_FLAGS_NONE
            values = mgr.getconfig(nodenum, cls._name, defaults)[1]
            if values is None:
                # node has no active config for this model (don't send defaults)
                return None
            # reply with config options
            reply = cls.toconfmsg(0, nodenum, typeflags, values)
        elif conftype == coreapi.CONF_TYPE_FLAGS_RESET:
            if objname == "all":
                mgr.clearconfig(nodenum)
        #elif conftype == coreapi.CONF_TYPE_FLAGS_UPDATE:
        else:
            # store the configuration values for later use, when the node
            # object has been created
            if objname is None:
                mgr.info("no configuration object for node %s" % nodenum)
                return None
            values_str = msg.gettlv(coreapi.CORE_TLV_CONF_VALUES)
            defaults = cls.getdefaultvalues()
            if values_str is None:
                # use default or preconfigured values
                values = mgr.getconfig(nodenum, cls._name, defaults)[1]
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
                            mgr.info("warning: ignoring invalid key '%s'" % key)
                    values = new_values
            mgr.setconfig(nodenum, objname, values)
        return reply

    @classmethod
    def toconfmsg(cls, flags, nodenum, typeflags, values):
        ''' Convert this class to a Config API message. Some TLVs are defined
            by the class, but node number, conf type flags, and values must
            be passed in.
        '''
        keys = cls.getnames()
        keyvalues = map(lambda a,b: "%s=%s" % (a,b), keys, values)
        values_str = string.join(keyvalues, '|')
        tlvdata = ""
        if nodenum is not None:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_NODE,
                                                nodenum)
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
        msg = coreapi.CoreConfMessage.pack(flags, tlvdata)
        return msg

    @staticmethod
    def booltooffon(value):
        ''' Convenience helper turns bool into on (True) or off (False) string.
        '''
        if value == "1" or value == "true" or value == "on":
            return "on"
        else:
            return "off"
            
    @staticmethod
    def offontobool(value):
        if type(value) == str:
            if value.lower() == "on":
                return 1
            elif value.lower() == "off":
                return 0
        return value

    @classmethod
    def valueof(cls, name,  values):
        ''' Helper to return a value by the name defined in confmatrix.
            Checks if it is boolean'''
        i = cls.getnames().index(name)
        if cls._confmatrix[i][1] == coreapi.CONF_DATA_TYPE_BOOL and \
           values[i] != "":
            return cls.booltooffon(values[i])
        else:
            return values[i]

    @staticmethod
    def haskeyvalues(values):
        ''' Helper to check for list of key=value pairs versus a plain old
            list of values. Returns True if all elements are "key=value".
        '''
        if len(values) == 0:
            return False
        for v in values:
            if "=" not in v:
                return False
        return True
        
    def getkeyvaluelist(self):
        ''' Helper to return a list of (key, value) tuples. Keys come from
        self._confmatrix and values are instance attributes.
        '''
        r = []
        for k in self.getnames():
            if hasattr(self, k):
                r.append((k, getattr(self, k)))
        return r


