#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
service.py: definition of CoreService class that is subclassed to define
startup services and routing for nodes. A service is typically a daemon
program launched when a node starts that provides some sort of
service. The CoreServices class handles configuration messages for sending
a list of available services to the GUI and for configuring individual
services.
'''

import sys, os, shlex

from itertools import repeat
from core.api import coreapi
from core.conf import ConfigurableManager, Configurable
from core.misc.utils import maketuplefromstr, expandcorepath

servicelist = []

def addservice(service):
    global servicelist
    i = 0
    found = -1
    for s in servicelist:
        if s._group == service._group:
            found = i
        elif (found >= 0):
            # insert service into list next to existing group
            i = found + 1
            break
        i += 1
    servicelist.insert(i, service)

class CoreServices(ConfigurableManager):
    ''' Class for interacting with a list of available startup services for
        nodes. Mostly used to convert a CoreService into a Config API
        message. This class lives in the Session object and remembers
        the default services configured for each node type, and any
        custom service configuration. A CoreService is not a Configurable.
    '''
    _name = "services"
    _type = coreapi.CORE_TLV_REG_UTILITY

    _invalid_custom_names = ('core', 'addons', 'api', 'bsd', 'emane', 'misc',
                             'netns', 'phys', 'services', 'xen')
    
    def __init__(self, session):
        ConfigurableManager.__init__(self, session)
        # dict of default services tuples, key is node type
        self.defaultservices = {}
        # dict of tuple of service objects, key is node number
        self.customservices = {}
        importcmd = "from core.services import *"
        exec(importcmd)
        paths = self.session.getcfgitem('custom_services_dir')
        if paths:
            for path in paths.split(','):
                path = path.strip()
                self.importcustom(path)
        self.isStartupService = startup.Startup.isStartupService

    def importcustom(self, path):
        ''' Import services from a myservices directory.
        '''
        if not path or len(path) == 0:
            return
        if not os.path.isdir(path):
            self.session.warn("invalid custom service directory specified" \
                              ": %s" % path)
            return
        try:
            parentdir, childdir = os.path.split(path)
            if childdir in self._invalid_custom_names:
                raise ValueError, "use a unique custom services dir name, " \
                        "not '%s'" % childdir
            if not parentdir in sys.path:
                sys.path.append(parentdir)
            exec("from %s import *" % childdir)
        except Exception, e:
            self.session.warn("error importing custom services from " \
                "%s:\n%s" % (path, e))

    def reset(self):
        ''' Called when config message with reset flag is received
        '''
        self.defaultservices.clear()
        self.customservices.clear()
        
    def get(self):
        ''' Get the list of available services.
        '''
        global servicelist
        return servicelist
    
    def getservicebyname(self, name):
        ''' Get a service class from the global servicelist given its name.
            Returns None when the name is not found.
        '''
        global servicelist
        for s in servicelist:
            if s._name == name:
                return s
        return None
        
    def getdefaultservices(self, type):
        ''' Get the list of default services that should be enabled for a
            node for the given node type.
        '''
        r = []
        if type in self.defaultservices:
            defaults = self.defaultservices[type]
            for name in defaults:
                s = self.getservicebyname(name)
                if s is None:
                    self.session.warn("default service %s is unknown" % name)
                else:
                    r.append(s)
        return r
    
    def getcustomservice(self, objid, service):
        ''' Get any custom service configured for the given node that
            matches the specified service name. If no custom service
            is found, return the specified service.
        '''
        if objid in self.customservices:
            for s in self.customservices[objid]:
                if s._name == service._name:
                    return s
        return service

    def setcustomservice(self, objid, service, values):
        ''' Store service customizations in an instantiated service object
            using a list of values that came from a config message.
        '''
        if service._custom:
            s = service
        else:
            # instantiate the class, for storing config customization
            s = service()
        # values are new key=value format; not all keys need to be present
        # a missing key means go with the default
        if Configurable.haskeyvalues(values):
            for v in values:
                key, value = v.split('=', 1)
                s.setvalue(key, value)
        # old-style config, list of values
        else:
            s.fromvaluelist(values)
            
        # assume custom service already in dict
        if service._custom:
            return
        # add the custom service to dict
        if objid in self.customservices:
            self.customservices[objid] += (s, )
        else:
            self.customservices[objid] = (s, )

    def addservicestonode(self, node, nodetype, services_str, verbose):
        ''' Populate the node.service list using (1) the list of services 
            requested from the services TLV, (2) using any custom service
            configuration, or (3) using the default services for this node type.
        '''
        if services_str is not None:
            services = services_str.split('|')
            for name in services:
                s = self.getservicebyname(name)
                if s is None:
                    self.session.warn("configured service %s for node %s is " \
                                                "unknown" % (name,  node.name))
                    continue
                if verbose:
                    self.session.info("adding configured service %s to " \
                                            "node %s" % (s._name,  node.name))
                s = self.getcustomservice(node.objid, s)
                node.addservice(s)
        else:
            services = self.getdefaultservices(nodetype)
            for s in services:
                if verbose:
                    self.session.info("adding default service %s to node %s" % \
                                        (s._name,  node.name))
                s = self.getcustomservice(node.objid, s)
                node.addservice(s)

    def getallconfigs(self):
        ''' Return (nodenum, service) tuples for all stored configs.
        Used when reconnecting to a session or opening XML.
        '''
        r = []
        for nodenum in self.customservices:
            for s in self.customservices[nodenum]:
                r.append( (nodenum, s) )
        return r

    def getallfiles(self, service):
        ''' Return all customized files stored with a service.
        Used when reconnecting to a session or opening XML.
        '''
        r = []
        if not service._custom:
            return r
        for filename in service._configs:
            data = self.getservicefiledata(service, filename)
            if data is None:
                continue
            r.append( (filename, data) )
        return r

    def bootnodeservices(self, node):
        ''' Start all services on a node.
        '''
        services = sorted(node.services,
                          key=lambda service: service._startindex)
        useStartupService = any(map(self.isStartupService, services))
        for s in services:
            if len(str(s._starttime)) > 0:
                try:
                    t = float(s._starttime)
                    if t > 0.0:
                        fn = self.bootnodeservice                    
                        self.session.evq.add_event(t, fn, node, s, services, False)
                        continue
                except ValueError:
                    pass
            self.bootnodeservice(node, s, services, useStartupService)
    
    def bootnodeservice(self, node, s, services, useStartupService):
        ''' Start a service on a node. Create private dirs, generate config
            files, and execute startup commands.
        '''
        if s._custom:
            self.bootnodecustomservice(node, s, services, useStartupService)
            return
        if node.verbose:
            node.info("starting service %s (%s)" % (s._name, s._startindex))
        for d in s._dirs:
            try:
                node.privatedir(d)
            except Exception,  e:
                node.warn("Error making node %s dir %s: %s" % \
                          (node.name,  d,  e))
        for filename in s.getconfigfilenames(node.objid, services): 
            cfg = s.generateconfig(node,  filename, services)
            node.nodefile(filename,  cfg)
        if useStartupService and not self.isStartupService(s):
            return
        for cmd in s.getstartup(node, services):
            try:
                # NOTE: this wait=False can be problematic!
                node.cmd(shlex.split(cmd),  wait = False)
            except Exception, e:
                node.warn("error starting command %s: %s" % (cmd, e))

    def bootnodecustomservice(self, node, s, services, useStartupService):
        ''' Start a custom service on a node. Create private dirs, use supplied
            config files, and execute  supplied startup commands.
        '''
        if node.verbose:
            node.info("starting service %s (%s)(custom)" % (s._name, s._startindex))
        for d in s._dirs:
            try:
                node.privatedir(d)
            except Exception,  e:
                node.warn("Error making node %s dir %s: %s" % \
                          (node.name,  d,  e))
        for i, filename in enumerate(s._configs): 
            if len(filename) == 0:
                continue
            cfg = self.getservicefiledata(s, filename)
            if cfg is None:
                cfg = s.generateconfig(node, filename, services)                
            # cfg may have a file:/// url for copying from a file
            try:
                if self.copyservicefile(node, filename, cfg):
                    continue
            except IOError, e:
                node.warn("Error copying service file %s" % filename)
                node.exception(coreapi.CORE_EXCP_LEVEL_ERROR,
                    "service:%s" % s._name, 
                    "error copying service file '%s': %s" % (filename, e))
                continue
            node.nodefile(filename,  cfg)
            
        if useStartupService and not self.isStartupService(s):
            return

        for cmd in s._startup:
            try:
                # NOTE: this wait=False can be problematic!
                node.cmd(shlex.split(cmd),  wait = False)
            except Exception, e:
                node.warn("error starting command %s: %s" % (cmd, e))
                
    def copyservicefile(self, node, filename, cfg):
        ''' Given a configured service filename and config, determine if the
        config references an existing file that should be copied.
        Returns True for local files, False for generated.
        '''
        if cfg[:7] == 'file://':
            src = cfg[7:]
            src = src.split('\n')[0]
            src = expandcorepath(src, node.session, node)
            # TODO: glob here
            node.nodefilecopy(filename, src, mode = 0644)
            return True
        return False
        

    def validatenodeservices(self, node):
        ''' Run validation commands for all services on a node.
        '''
        services = sorted(node.services,
                          key=lambda service: service._startindex)
        for s in services:
            self.validatenodeservice(node, s, services)

    def validatenodeservice(self, node, s, services):
        ''' Run the validation command(s) for a service.
        '''
        if node.verbose:
            node.info("validating service %s (%s)" % (s._name, s._startindex))
        if s._custom:
            validate_cmds = s._validate
        else:
            validate_cmds = s.getvalidate(node, services)
        if len(validate_cmds) == 0:
            # doesn't have a validate command
            status = 0
        else:
            for cmd in validate_cmds:
                if node.verbose:
                    node.info("validating service %s using: %s" % (s._name, cmd))
                try:
                    (status, result) = node.cmdresult(shlex.split(cmd))
                    if status != 0:
                        raise ValueError, "non-zero exit status"
                except:
                    node.warn("validation command '%s' failed" % cmd)
                    node.exception(coreapi.CORE_EXCP_LEVEL_ERROR,
                        "service:%s" % s._name, 
                        "validate command failed: %s" % cmd)
                    status = -1
        return status
        
    def stopnodeservices(self, node):
        ''' Stop all services on a node.
        '''
        services = sorted(node.services,
                          key=lambda service: service._startindex)
        for s in services:
            self.stopnodeservice(node, s)
    
    def stopnodeservice(self, node, s):
        ''' Stop a service on a node.
        '''
        status = ""
        if len(s._shutdown) == 0:
            # doesn't have a shutdown command
            status += "0"
        else:
            for cmd in s._shutdown:
                try:
                    tmp = node.cmd(shlex.split(cmd),  wait = True)
                    status += "%s" % (tmp)
                except:
                    node.warn("error running stop command %s" % cmd)
                    status += "-1"
        return status


    def configure_request(self, msg):
        ''' Receive configuration message for configuring services.
            With a request flag set, a list of services has been requested.
            When the opaque field is present, a specific service is being
            configured or requested.
        '''
        objname = msg.gettlv(coreapi.CORE_TLV_CONF_OBJ)
        conftype = msg.gettlv(coreapi.CORE_TLV_CONF_TYPE)
        nodenum = msg.gettlv(coreapi.CORE_TLV_CONF_NODE)
        sessionnum = msg.gettlv(coreapi.CORE_TLV_CONF_SESSION)
        opaque = msg.gettlv(coreapi.CORE_TLV_CONF_OPAQUE)

        # send back a list of available services
        if opaque is None:
            global servicelist
            tf = coreapi.CONF_TYPE_FLAGS_NONE
            datatypes = tuple(repeat(coreapi.CONF_DATA_TYPE_BOOL,
                                            len(servicelist)))
            vals = "|".join(repeat('0', len(servicelist)))
            names = map(lambda x: x._name,  servicelist)
            captions = "|".join(names)
            possiblevals = ""
            for s in servicelist:
                if s._custom_needed:
                    possiblevals += '1'
                possiblevals += '|'
            groups = self.buildgroups(servicelist)
        # send back the properties for this service
        else:
            if nodenum is None:
                return None
            n = self.session.obj(nodenum)
            if n is None:
                self.session.warn("Request to configure service %s for " \
                    "unknown node %s" % (svc._name,  nodenum))
                return None
            servicesstring = opaque.split(':')
            services,unknown = self.servicesfromopaque(opaque, n.objid)
            for u in unknown:
                self.session.warn("Request for unknown service '%s'" % u)

            if len(services) < 1:
                return None
            if len(servicesstring) == 3:
                # a file request: e.g. "service:zebra:quagga.conf"
                return self.getservicefile(services, n, servicesstring[2])
            
            # the first service in the list is the one being configured
            svc = services[0]
            # send back:
            # dirs, configs, startindex, startup, shutdown, metadata, config
            tf = coreapi.CONF_TYPE_FLAGS_UPDATE
            datatypes = tuple(repeat(coreapi.CONF_DATA_TYPE_STRING,
                                     len(svc.keys)))
            vals = svc.tovaluelist(n, services)
            captions = None
            possiblevals = None
            groups = None
            
        tlvdata = ""
        if nodenum is not None:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_NODE,
                                                nodenum)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_OBJ,
                                            self._name)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_TYPE, tf)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_DATA_TYPES,
                                            datatypes)
        tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_VALUES,
                                            vals)
        if captions:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_CAPTIONS,
                                                captions)
        if possiblevals:
            tlvdata += coreapi.CoreConfTlv.pack(
                coreapi.CORE_TLV_CONF_POSSIBLE_VALUES, possiblevals)
        if groups:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_GROUPS,
                                                groups)
        if sessionnum is not None:
            tlvdata += coreapi.CoreConfTlv.pack(
                            coreapi.CORE_TLV_CONF_SESSION, sessionnum)
        if opaque:
            tlvdata += coreapi.CoreConfTlv.pack(coreapi.CORE_TLV_CONF_OPAQUE,
                                                opaque)
        return coreapi.CoreConfMessage.pack(0, tlvdata)


    def configure_values(self, msg, values):
        ''' Receive configuration message for configuring services.
            With a request flag set, a list of services has been requested.
            When the opaque field is present, a specific service is being
            configured or requested.
        '''
        nodenum = msg.gettlv(coreapi.CORE_TLV_CONF_NODE)
        opaque = msg.gettlv(coreapi.CORE_TLV_CONF_OPAQUE)
        
        errmsg = "services config message that I don't know how to handle"
        if values is None:
            self.session.info(errmsg)
            return None
        else:
            values = values.split('|')

        if opaque is None:
            # store default services for a node type in self.defaultservices[]
            data_types = msg.gettlv(coreapi.CORE_TLV_CONF_DATA_TYPES)
            if values is None or data_types is None or \
               data_types[0] != coreapi.CONF_DATA_TYPE_STRING:
                self.session.info(errmsg)
                return None
            key = values.pop(0)
            self.defaultservices[key] = values
            self.session.info("default services for type %s set to %s" % \
                              (key, values))
        else:
            # store service customized config in self.customservices[]
            if nodenum is None:
                return None
            services,unknown = self.servicesfromopaque(opaque, nodenum)
            for u in unknown:
                self.session.warn("Request for unknown service '%s'" % u)

            if len(services) < 1:
                return None
            svc = services[0]
            self.setcustomservice(nodenum, svc, values)
        return None

    def servicesfromopaque(self, opaque, objid):
        ''' Build a list of services from an opaque data string.
        '''
        services = []
        unknown = []
        servicesstring = opaque.split(':')
        if servicesstring[0] != "service":
            return []
        servicenames = servicesstring[1].split(',')
        for name in servicenames:
            s = self.getservicebyname(name)
            s = self.getcustomservice(objid, s)
            if s is None:
                unknown.append(name)
            else:
                services.append(s)
        return services,unknown

    def buildgroups(self,  servicelist):
        ''' Build a string of groups for use in a configuration message given
            a list of services. The group list string has the format 
            "title1:1-5|title2:6-9|10-12", where title is an optional group title
            and i-j is a numeric range of value indices; groups are
            separated by commas.
        '''
        i = 0
        r = ""
        lastgroup = "<undefined>"
        for service in servicelist:
            i += 1
            group = service._group
            if group != lastgroup:
                lastgroup = group
                # finish previous group
                if i > 1:
                    r += "-%d|" % (i -1)                
                # optionally include group title
                if group == "":
                    r += "%d" % i
                else:
                    r += "%s:%d" % (group,  i)
        # finish the last group list
        if i > 0:
            r += "-%d" % i
        return r
        
    def getservicefile(self, services, node, filename):
        ''' Send a File Message when the GUI has requested a service file.
        The file data is either auto-generated or comes from an existing config.
        '''
        svc = services[0]
        # get the filename and determine the config file index
        if svc._custom:
            cfgfiles = svc._configs
        else:
            cfgfiles = svc.getconfigfilenames(node.objid,  services)
        if filename not in cfgfiles:
            self.session.warn("Request for unknown file '%s' for service '%s'" \
                             % (filename, services[0]))
            return None
            
        # get the file data
        data = self.getservicefiledata(svc, filename)
        if data is None:
            data = "%s" % (svc.generateconfig(node, filename, services))
        else:
            data = "%s" % data
        filetypestr = "service:%s" % svc._name
            
        # send a file message
        flags = coreapi.CORE_API_ADD_FLAG
        tlvdata = coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_NODE, node.objid)
        tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_NAME, filename)
        tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_TYPE, filetypestr)
        tlvdata += coreapi.CoreFileTlv.pack(coreapi.CORE_TLV_FILE_DATA, data)
        reply = coreapi.CoreFileMessage.pack(flags, tlvdata)
        return reply
        
    def getservicefiledata(self, service, filename):
        ''' Get the customized file data associated with a service. Return None
        for invalid filenames or missing file data.
        '''
        try:
            i = service._configs.index(filename)
        except ValueError:
            return None
        if i >= len(service._configtxt) or service._configtxt[i] is None:
            return None
        return service._configtxt[i]
    
    def setservicefile(self, nodenum, type, filename, srcname, data):
        ''' Receive a File Message from the GUI and store the customized file
        in the service config. The filename must match one from the list of
        config files in the service.
        '''
        if len(type.split(':')) < 2:
            self.session.warn("Received file type did not contain service info.")
            return
        if srcname is not None:
            raise NotImplementedError
        (svcid, svcname) = type.split(':')[:2]
        svc = self.getservicebyname(svcname)
        svc = self.getcustomservice(nodenum, svc)
        if svc is None:
            self.session.warn("Received filename for unknown service '%s'" % \
                              svcname)
            return
        cfgfiles = svc._configs
        if filename not in cfgfiles:
            self.session.warn("Received unknown file '%s' for service '%s'" \
                             % (filename, svcname))
            return
        i = cfgfiles.index(filename)
        configtxtlist = list(svc._configtxt)
        numitems = len(configtxtlist)
        if numitems < i+1:
            # add empty elements to list to support index assignment
            for j in range(1, (i + 2) - numitems):
                configtxtlist += None,
        configtxtlist[i] = data
        svc._configtxt = configtxtlist
    
    def handleevent(self, msg):
        ''' Handle an Event Message used to start, stop, restart, or validate
            a service on a given node.
        '''
        eventtype = msg.gettlv(coreapi.CORE_TLV_EVENT_TYPE)
        nodenum = msg.gettlv(coreapi.CORE_TLV_EVENT_NODE)
        name = msg.gettlv(coreapi.CORE_TLV_EVENT_NAME)
        try:
            node = self.session.obj(nodenum)
        except KeyError:
            self.session.warn("Ignoring event for service '%s', unknown node " \
                              "'%s'" % (name, nodenum))
            return
            
        fail = ""
        services,unknown = self.servicesfromopaque(name, nodenum)
        for s in services:
            if eventtype == coreapi.CORE_EVENT_STOP or \
                eventtype == coreapi.CORE_EVENT_RESTART:
                status = self.stopnodeservice(node, s)
                if status != "0":
                    fail += "Stop %s," % (s._name)
            if eventtype == coreapi.CORE_EVENT_START or \
                eventtype == coreapi.CORE_EVENT_RESTART:
                if s._custom:
                    cmds = s._startup
                else:
                    cmds = s.getstartup(node, services)
                if len(cmds) > 0:
                    for cmd in cmds:
                        try:
                            #node.cmd(shlex.split(cmd),  wait = False)
                            status = node.cmd(shlex.split(cmd), wait = True)
                            if status != 0:
                                fail += "Start %s(%s)," % (s._name, cmd)
                        except:
                            node.warn("error starting command %s" % cmd)
                            fail += "Start %s," % (s._name)
            if eventtype == coreapi.CORE_EVENT_PAUSE:
                status = self.validatenodeservice(node, s, services)
                if status != 0:
                    fail += "%s," % (s._name)
            if eventtype == coreapi.CORE_EVENT_RECONFIGURE:
                if s._custom:
                    cfgfiles = s._configs
                else:
                    cfgfiles = s.getconfigfilenames(node.objid,  services)
                if len(cfgfiles) > 0:
                    for filename in cfgfiles:
                        if filename[:7] == "file:///":
                            raise NotImplementedError  # TODO
                        cfg = self.getservicefiledata(s, filename)
                        if cfg is None:
                            cfg = s.generateconfig(node, filename, services)
                        try:
                            node.nodefile(filename, cfg)
                        except:
                            self.warn("error in configure file: %s" % filename)
                            fail += "%s," % (s._name)

        fdata = ""
        if len(fail) > 0:
            fdata += "Fail:" + fail
        udata = ""
        num  = len(unknown)
        if num > 0:
            for u in unknown:
                udata += u
                if num > 1:
                    udata += ", "
                num -= 1
            self.session.warn("Event requested for unknown service(s): %s" % udata);
            udata = "Unknown:" + udata

        tlvdata = ""
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_NODE,
                                             nodenum)
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                             eventtype)
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_NAME,
                                             name)
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_DATA,
                                             fdata + ";" + udata)
        msg = coreapi.CoreEventMessage.pack(0, tlvdata)
        try:
            self.session.broadcastraw(None, msg)
        except Exception, e:
            self.warn("Error sending Event Message: %s" % e)
    

class CoreService(object):
    ''' Parent class used for defining services.
    '''
    # service name should not include spaces
    _name = ""
    # group string allows grouping services together
    _group = ""
    # list name(s) of services that this service depends upon
    _depends = ()
    keys = ["dirs","files","startidx","cmdup","cmddown","cmdval","meta","starttime"]
    # private, per-node directories required by this service
    _dirs = ()
    # config files written by this service
    _configs = ()
    # index used to determine start order with other services
    _startindex = 0
    # time in seconds after runtime to run startup commands
    _starttime = ""
    # list of startup commands
    _startup = ()
    # list of shutdown commands
    _shutdown = ()
    # list of validate commands
    _validate = ()
    # metadata associated with this service
    _meta = ""
    # custom configuration text
    _configtxt = ()
    _custom = False
    _custom_needed = False

    def __init__(self):
        ''' Services are not necessarily instantiated. Classmethods may be used
            against their config. Services are instantiated when a custom
            configuration is used to override their default parameters.
        '''
        self._custom = True
    
    @classmethod
    def getconfigfilenames(cls,  nodenum,  services):
        ''' Return the tuple of configuration file filenames. This default method
            returns the cls._configs tuple, but this method may be overriden to
            provide node-specific filenames that may be based on other services.
        '''
        return cls._configs
        
    @classmethod
    def generateconfig(cls, node,  filename,  services):
        ''' Generate configuration file given a node object. The filename is
            provided to allow for multiple config files. The other services are
            provided to allow interdependencies (e.g. zebra and OSPF).
            Return the configuration string to be written to a file or sent 
            to the GUI for customization.
        '''
        raise NotImplementedError
        
    @classmethod
    def getstartup(cls,  node,  services):
        ''' Return the tuple of startup commands. This default method
            returns the cls._startup tuple, but this method may be
            overriden to provide node-specific commands that may be
            based on other services.
        '''
        return cls._startup

    @classmethod
    def getvalidate(cls,  node,  services):
        ''' Return the tuple of validate commands. This default method
            returns the cls._validate tuple, but this method may be
            overriden to provide node-specific commands that may be
            based on other services.
        '''
        return cls._validate
        
    @classmethod
    def tovaluelist(cls, node, services):
        ''' Convert service properties into a string list of key=value pairs,
            separated by "|".
        '''
        valmap = [cls._dirs, cls._configs, cls._startindex, cls._startup, 
                  cls._shutdown, cls._validate, cls._meta, cls._starttime]
        if not cls._custom:
            # this is always reached due to classmethod
            valmap[valmap.index(cls._configs)] = \
                cls.getconfigfilenames(node.objid, services)
            valmap[valmap.index(cls._startup)] = \
                cls.getstartup(node,  services)
        vals = map( lambda a,b: "%s=%s" % (a, str(b)), cls.keys, valmap)
        return "|".join(vals)

    def fromvaluelist(self, values):
        ''' Convert list of values into properties for this instantiated
            (customized) service.
        '''
        # TODO: support empty value? e.g. override default meta with ''
        for key in self.keys:
            try:
                self.setvalue(key, values[self.keys.index(key)])
            except IndexError:
                # old config does not need to have new keys
                pass

    def setvalue(self, key, value):
        if key not in self.keys:
            raise ValueError
        # this handles data conversion to int, string, and tuples
        if value:
            if key == "startidx":
                value = int(value)
            elif key == "meta":
                value = str(value)
            else:
                value = maketuplefromstr(value, str)
        
        if key == "dirs":
            self._dirs = value
        elif key == "files":
            self._configs = value
        elif key == "startidx":
            self._startindex = value
        elif key == "cmdup":
            self._startup = value
        elif key == "cmddown":
            self._shutdown = value
        elif key == "cmdval":
            self._validate = value
        elif key == "meta":
            self._meta = value
        elif key == "starttime":
            self._starttime = value
