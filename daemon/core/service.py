"""
Definition of CoreService class that is subclassed to define
startup services and routing for nodes. A service is typically a daemon
program launched when a node starts that provides some sort of service.
The CoreServices class handles configuration messages for sending
a list of available services to the GUI and for configuring individual
services.
"""

import os
import shlex
import sys
import time
from itertools import repeat

from core.api import coreapi
from core.conf import Configurable
from core.conf import ConfigurableManager
from core.data import EventData, ConfigData, FileData
from core.enumerations import ConfigDataTypes
from core.enumerations import ConfigFlags
from core.enumerations import EventTypes
from core.enumerations import FileTlvs
from core.enumerations import MessageFlags
from core.enumerations import RegisterTlvs
from core.misc import log
from core.misc import utils

logger = log.get_logger(__name__)


class ServiceManager(object):
    """
    Manages services available for CORE nodes to use.
    """
    services = []

    @classmethod
    def add(cls, service):
        """
        Add a service to manager.

        :param CoreService service: service to add
        :return: nothing
        """
        insert = 0
        for index, known_service in enumerate(cls.services):
            if known_service._group == service._group:
                insert = index + 1
                break

        logger.info("loading service: %s - %s: %s", insert, service, service._name)
        cls.services.insert(insert, service)

    @classmethod
    def get(cls, name):
        """
        Retrieve a service from the manager.

        :param str name: name of the service to retrieve
        :return: service if it exists, None otherwise
        :rtype: CoreService
        """
        for service in cls.services:
            if service._name == name:
                return service
        return None


class CoreServices(ConfigurableManager):
    """
    Class for interacting with a list of available startup services for
    nodes. Mostly used to convert a CoreService into a Config API
    message. This class lives in the Session object and remembers
    the default services configured for each node type, and any
    custom service configuration. A CoreService is not a Configurable.
    """
    name = "services"
    config_type = RegisterTlvs.UTILITY.value

    _invalid_custom_names = (
        'core', 'addons', 'api', 'bsd', 'emane', 'misc', 'netns', 'phys', 'services', 'xen'
    )

    def __init__(self, session):
        """
        Creates a CoreServices instance.

        :param core.session.Session session: session this manager is tied to
        :return: nothing
        """
        ConfigurableManager.__init__(self)
        self.session = session
        # dict of default services tuples, key is node type
        self.defaultservices = {}
        # dict of tuple of service objects, key is node number
        self.customservices = {}

        paths = self.session.get_config_item('custom_services_dir')
        if paths:
            for path in paths.split(','):
                path = path.strip()
                self.importcustom(path)

        # TODO: remove need for cyclic import
        from core.services import startup
        self.is_startup_service = startup.Startup.is_startup_service

    @classmethod
    def add_service_path(cls, path):
        cls.service_path.add(path)

    def importcustom(self, path):
        """
        Import services from a myservices directory.

        :param str path: path to import custom services from
        :return: nothing
        """
        if not path or len(path) == 0:
            return

        if not os.path.isdir(path):
            logger.warn("invalid custom service directory specified" ": %s" % path)
            return

        try:
            parentdir, childdir = os.path.split(path)
            if childdir in self._invalid_custom_names:
                raise ValueError("use a unique custom services dir name, " "not '%s'" % childdir)
            if parentdir not in sys.path:
                sys.path.append(parentdir)
            # TODO: remove use of this exec statement
            statement = "from %s import *" % childdir
            logger.info("custom import: %s", statement)
            exec (statement)
        except:
            logger.exception("error importing custom services from %s", path)

    def reset(self):
        """
        Called when config message with reset flag is received
        """
        self.defaultservices.clear()
        self.customservices.clear()

    def getdefaultservices(self, service_type):
        """
        Get the list of default services that should be enabled for a
        node for the given node type.

        :param service_type: service type to get default services for
        :return: default services
        :rtype: list
        """
        logger.debug("getting default services for type: %s", service_type)
        results = []
        if service_type in self.defaultservices:
            defaults = self.defaultservices[service_type]
            for name in defaults:
                logger.debug("checking for service with service manager: %s", name)
                service = ServiceManager.get(name)
                if not service:
                    logger.warn("default service %s is unknown", name)
                else:
                    results.append(service)
        return results

    def getcustomservice(self, object_id, service):
        """
        Get any custom service configured for the given node that matches the specified service name.
        If no custom service is found, return the specified service.

        :param int object_id: object id to get service from
        :param CoreService service: custom service to retrieve
        :return: custom service from the node
        :rtype: CoreService
        """
        if object_id in self.customservices:
            for s in self.customservices[object_id]:
                if s._name == service._name:
                    return s
        return service

    def setcustomservice(self, object_id, service, values):
        """
        Store service customizations in an instantiated service object
        using a list of values that came from a config message.

        :param int object_id: object id to set custom service for
        :param class service: service to set
        :param list values: values to
        :return:
        """
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
        if object_id in self.customservices:
            self.customservices[object_id] += (s,)
        else:
            self.customservices[object_id] = (s,)

    def addservicestonode(self, node, nodetype, services_str):
        """
        Populate the node.service list using (1) the list of services
        requested from the services TLV, (2) using any custom service
        configuration, or (3) using the default services for this node type.

        :param core.coreobj.PyCoreNode node: node to add services to
        :param str nodetype: node type to add services to
        :param str services_str: string formatted service list
        :return: nothing
        """
        if services_str is not None:
            logger.info("setting node specific services: %s", services_str)
            services = services_str.split("|")
            for name in services:
                s = ServiceManager.get(name)
                if s is None:
                    logger.warn("configured service %s for node %s is unknown", name, node.name)
                    continue
                logger.info("adding configured service %s to node %s", s._name, node.name)
                s = self.getcustomservice(node.objid, s)
                node.addservice(s)
        else:
            logger.info("setting default services for node (%s) type (%s)", node.objid, nodetype)
            services = self.getdefaultservices(nodetype)
            for s in services:
                logger.info("adding default service %s to node %s", s._name, node.name)
                s = self.getcustomservice(node.objid, s)
                node.addservice(s)

    def getallconfigs(self, use_clsmap=True):
        """
        Return (nodenum, service) tuples for all stored configs. Used when reconnecting to a
        session or opening XML.

        :param bool use_clsmap: should a class map be used, default to True
        :return: list of tuples of node ids and services
        :rtype: list
        """
        configs = []
        for nodenum in self.customservices:
            for service in self.customservices[nodenum]:
                configs.append((nodenum, service))
        return configs

    def getallfiles(self, service):
        """
        Return all customized files stored with a service.
        Used when reconnecting to a session or opening XML.

        :param CoreService service: service to get files for
        :return:
        """
        files = []

        if not service._custom:
            return files

        for filename in service._configs:
            data = self.getservicefiledata(service, filename)
            if data is None:
                continue
            files.append((filename, data))

        return files

    def bootnodeservices(self, node):
        """
        Start all services on a node.

        :param core.netns.nodes.CoreNode node: node to start services on
        :return:
        """
        services = sorted(node.services, key=lambda service: service._startindex)
        use_startup_service = any(map(self.is_startup_service, services))
        for s in services:
            if len(str(s._starttime)) > 0:
                try:
                    t = float(s._starttime)
                    if t > 0.0:
                        fn = self.bootnodeservice
                        self.session.event_loop.add_event(t, fn, node, s, services, False)
                        continue
                except ValueError:
                    logger.exception("error converting start time to float")
            self.bootnodeservice(node, s, services, use_startup_service)

    def bootnodeservice(self, node, service, services, use_startup_service):
        """
        Start a service on a node. Create private dirs, generate config
        files, and execute startup commands.

        :param core.netns.nodes.CoreNode node: node to boot services on
        :param CoreService service: service to start
        :param list services: service list
        :param bool use_startup_service: flag to use startup services or not
        :return: nothing
        """
        if service._custom:
            self.bootnodecustomservice(node, service, services, use_startup_service)
            return

        logger.info("starting service %s (%s)" % (service._name, service._startindex))
        for directory in service._dirs:
            try:
                node.privatedir(directory)
            except:
                logger.exception("Error making node %s dir %s", node.name, directory)

        for filename in service.getconfigfilenames(node.objid, services):
            cfg = service.generateconfig(node, filename, services)
            node.nodefile(filename, cfg)

        if use_startup_service and not self.is_startup_service(service):
            return

        for cmd in service.getstartup(node, services):
            try:
                # NOTE: this wait=False can be problematic!
                node.cmd(shlex.split(cmd), wait=False)
            except:
                logger.exception("error starting command %s", cmd)

    def bootnodecustomservice(self, node, service, services, use_startup_service):
        """
        Start a custom service on a node. Create private dirs, use supplied
        config files, and execute  supplied startup commands.

        :param core.netns.nodes.CoreNode node: node to boot services on
        :param CoreService service: service to start
        :param list services: service list
        :param bool use_startup_service: flag to use startup services or not
        :return: nothing
        """
        logger.info("starting service(%s) %s (%s)(custom)",
                    service, service._name, service._startindex)
        for directory in service._dirs:
            try:
                node.privatedir(directory)
            except:
                logger.exception("error making node %s dir %s", node.name, directory)

        logger.info("service configurations: %s", service._configs)
        for i, filename in enumerate(service._configs):
            logger.info("generating service config: %s", filename)
            if len(filename) == 0:
                continue
            cfg = self.getservicefiledata(service, filename)
            if cfg is None:
                cfg = service.generateconfig(node, filename, services)
            # cfg may have a file:/// url for copying from a file
            try:
                if self.copyservicefile(node, filename, cfg):
                    continue
            except IOError:
                logger.exception("error copying service file '%s'", filename)
                continue
            node.nodefile(filename, cfg)

        if use_startup_service and not self.is_startup_service(service):
            return

        for cmd in service._startup:
            try:
                # NOTE: this wait=False can be problematic!
                node.cmd(shlex.split(cmd), wait=False)
            except:
                logger.exception("error starting command %s", cmd)

    def copyservicefile(self, node, filename, cfg):
        """
        Given a configured service filename and config, determine if the
        config references an existing file that should be copied.
        Returns True for local files, False for generated.

        :param core.netns.nodes.CoreNode node: node to copy service for
        :param str filename: file name for a configured service
        :param str cfg: configuration string
        :return: True if successful, False otherwise
        :rtype: bool
        """
        if cfg[:7] == 'file://':
            src = cfg[7:]
            src = src.split('\n')[0]
            src = utils.expandcorepath(src, node.session, node)
            # TODO: glob here
            node.nodefilecopy(filename, src, mode=0644)
            return True
        return False

    def validatenodeservices(self, node):
        """
        Run validation commands for all services on a node.

        :param core.netns.nodes.CoreNode node: node to validate services for
        :return: nothing
        """
        services = sorted(node.services, key=lambda service: service._startindex)
        for s in services:
            self.validatenodeservice(node, s, services)

    def validatenodeservice(self, node, service, services):
        """
        Run the validation command(s) for a service.

        :param core.netns.nodes.CoreNode node: node to validate service for
        :param CoreService service: service to validate
        :param list services: services for node
        :return: service validation status
        :rtype: int
        """
        logger.info("validating service for node (%s - %s): %s (%s)",
                    node.objid, node.name, service._name, service._startindex)
        if service._custom:
            validate_cmds = service._validate
        else:
            validate_cmds = service.getvalidate(node, services)

        status = 0
        # has validate commands
        if len(validate_cmds) > 0:
            for cmd in validate_cmds:
                logger.info("validating service %s using: %s", service._name, cmd)
                try:
                    status, result = node.cmdresult(shlex.split(cmd))
                    if status != 0:
                        raise ValueError("non-zero exit status")
                except:
                    logger.exception("validate command failed: %s", cmd)
                    status = -1

        return status

    def stopnodeservices(self, node):
        """
        Stop all services on a node.

        :param core.netns.nodes.CoreNode node: node to stop services on
        :return: nothing
        """
        services = sorted(node.services, key=lambda service: service._startindex)
        for s in services:
            self.stopnodeservice(node, s)

    def stopnodeservice(self, node, service):
        """
        Stop a service on a node.

        :param core.netns.nodes.CoreNode node: node to stop a service on
        :param CoreService service: service to stop
        :return: status for stopping the services
        :rtype: str
        """
        status = ""
        if len(service._shutdown) == 0:
            # doesn't have a shutdown command
            status += "0"
        else:
            for cmd in service._shutdown:
                try:
                    tmp = node.cmd(shlex.split(cmd), wait=True)
                    status += "%s" % tmp
                except:
                    logger.exception("error running stop command %s", cmd)
                    status += "-1"
        return status

    def configure_request(self, config_data):
        """
        Receive configuration message for configuring services.
        With a request flag set, a list of services has been requested.
        When the opaque field is present, a specific service is being
        configured or requested.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :return: response messages
        :rtype: ConfigData
        """
        node_id = config_data.node
        session_id = config_data.session
        opaque = config_data.opaque

        logger.info("configuration request: node(%s) session(%s) opaque(%s)", node_id, session_id, opaque)

        # send back a list of available services
        if opaque is None:
            type_flag = ConfigFlags.NONE.value
            data_types = tuple(repeat(ConfigDataTypes.BOOL.value, len(ServiceManager.services)))
            values = "|".join(repeat('0', len(ServiceManager.services)))
            names = map(lambda x: x._name, ServiceManager.services)
            captions = "|".join(names)
            possible_values = ""
            for s in ServiceManager.services:
                if s._custom_needed:
                    possible_values += '1'
                possible_values += '|'
            groups = self.buildgroups(ServiceManager.services)
        # send back the properties for this service
        else:
            if node_id is None:
                return None
            node = self.session.get_object(node_id)
            if node is None:
                logger.warn("Request to configure service for unknown node %s", node_id)
                return None
            servicesstring = opaque.split(':')
            services, unknown = self.servicesfromopaque(opaque, node.objid)
            for u in unknown:
                logger.warn("Request for unknown service '%s'" % u)

            if len(services) < 1:
                return None

            if len(servicesstring) == 3:
                # a file request: e.g. "service:zebra:quagga.conf"
                file_data = self.getservicefile(services, node, servicesstring[2])
                self.session.broadcast_file(file_data)

                # short circuit this request early to avoid returning response below
                return None

            # the first service in the list is the one being configured
            svc = services[0]
            # send back:
            # dirs, configs, startindex, startup, shutdown, metadata, config
            type_flag = ConfigFlags.UPDATE.value
            data_types = tuple(repeat(ConfigDataTypes.STRING.value, len(svc.keys)))
            values = svc.tovaluelist(node, services)
            captions = None
            possible_values = None
            groups = None

        return ConfigData(
            message_type=0,
            node=node_id,
            object=self.name,
            type=type_flag,
            data_types=data_types,
            data_values=values,
            captions=captions,
            possible_values=possible_values,
            groups=groups,
            session=session_id,
            opaque=opaque
        )

    def configure_values(self, config_data):
        """
        Receive configuration message for configuring services.
        With a request flag set, a list of services has been requested.
        When the opaque field is present, a specific service is being
        configured or requested.

        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        :return: None
        """
        data_types = config_data.data_types
        values = config_data.data_values
        node_id = config_data.node
        opaque = config_data.opaque

        error_message = "services config message that I don't know how to handle"
        if values is None:
            logger.error(error_message)
            return None
        else:
            values = values.split('|')

        if opaque is None:
            # store default services for a node type in self.defaultservices[]
            if data_types is None or data_types[0] != ConfigDataTypes.STRING.value:
                logger.info(error_message)
                return None
            key = values.pop(0)
            self.defaultservices[key] = values
            logger.info("default services for type %s set to %s" % (key, values))
        else:
            # store service customized config in self.customservices[]
            if node_id is None:
                return None
            services, unknown = self.servicesfromopaque(opaque, node_id)
            for u in unknown:
                logger.warn("Request for unknown service '%s'" % u)

            if len(services) < 1:
                return None
            svc = services[0]
            self.setcustomservice(node_id, svc, values)

        return None

    def servicesfromopaque(self, opaque, object_id):
        """
        Build a list of services from an opaque data string.

        :param str opaque: opaque data string
        :param int object_id: object id
        :return: services and unknown services lists tuple
        :rtype: tuple
        """
        services = []
        unknown = []
        servicesstring = opaque.split(':')
        if servicesstring[0] != "service":
            return []
        servicenames = servicesstring[1].split(',')
        for name in servicenames:
            s = ServiceManager.get(name)
            s = self.getcustomservice(object_id, s)
            if s is None:
                unknown.append(name)
            else:
                services.append(s)
        return services, unknown

    def buildgroups(self, servicelist):
        """
        Build a string of groups for use in a configuration message given
        a list of services. The group list string has the format
        "title1:1-5|title2:6-9|10-12", where title is an optional group title
        and i-j is a numeric range of value indices; groups are
        separated by commas.

        :param list servicelist: service list to build group string from
        :return: groups string
        :rtype: str
        """
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
                    r += "-%d|" % (i - 1)
                # optionally include group title
                if group == "":
                    r += "%d" % i
                else:
                    r += "%s:%d" % (group, i)
        # finish the last group list
        if i > 0:
            r += "-%d" % i
        return r

    def getservicefile(self, services, node, filename):
        """
        Send a File Message when the GUI has requested a service file.
        The file data is either auto-generated or comes from an existing config.

        :param list services: service list
        :param core.netns.nodes.CoreNode node: node to get service file from
        :param str filename: file name to retrieve
        :return: file message for node
        """
        svc = services[0]
        # get the filename and determine the config file index
        if svc._custom:
            cfgfiles = svc._configs
        else:
            cfgfiles = svc.getconfigfilenames(node.objid, services)
        if filename not in cfgfiles:
            logger.warn("Request for unknown file '%s' for service '%s'" % (filename, services[0]))
            return None

        # get the file data
        data = self.getservicefiledata(svc, filename)
        if data is None:
            data = "%s" % (svc.generateconfig(node, filename, services))
        else:
            data = "%s" % data
        filetypestr = "service:%s" % svc._name

        return FileData(
            message_type=MessageFlags.ADD.value,
            node=node.objid,
            name=filename,
            type=filetypestr,
            data=data
        )

    def getservicefiledata(self, service, filename):
        """
        Get the customized file data associated with a service. Return None
        for invalid filenames or missing file data.

        :param CoreService service: service to get file data from
        :param str filename: file name to get data from
        :return: file data
        """
        try:
            i = service._configs.index(filename)
        except ValueError:
            return None
        if i >= len(service._configtxt) or service._configtxt[i] is None:
            return None
        return service._configtxt[i]

    def setservicefile(self, nodenum, type, filename, srcname, data):
        """
        Receive a File Message from the GUI and store the customized file
        in the service config. The filename must match one from the list of
        config files in the service.

        :param int nodenum: node id to set service file
        :param str type: file type to set
        :param str filename: file name to set
        :param str srcname: source name of file to set
        :param data: data for file to set
        :return: nothing
        """
        if len(type.split(':')) < 2:
            logger.warn("Received file type did not contain service info.")
            return
        if srcname is not None:
            raise NotImplementedError
        svcid, svcname = type.split(':')[:2]
        svc = ServiceManager.get(svcname)
        svc = self.getcustomservice(nodenum, svc)
        if svc is None:
            logger.warn("Received filename for unknown service '%s'" % svcname)
            return
        cfgfiles = svc._configs
        if filename not in cfgfiles:
            logger.warn("Received unknown file '%s' for service '%s'" % (filename, svcname))
            return
        i = cfgfiles.index(filename)
        configtxtlist = list(svc._configtxt)
        numitems = len(configtxtlist)
        if numitems < i + 1:
            # add empty elements to list to support index assignment
            for j in range(1, (i + 2) - numitems):
                configtxtlist += None,
        configtxtlist[i] = data
        svc._configtxt = configtxtlist

    def handleevent(self, event_data):
        """
        Handle an Event Message used to start, stop, restart, or validate
        a service on a given node.

        :param EventData event_data: event data to handle
        :return: nothing
        """
        event_type = event_data.event_type
        node_id = event_data.node
        name = event_data.name

        try:
            node = self.session.get_object(node_id)
        except KeyError:
            logger.warn("Ignoring event for service '%s', unknown node '%s'", name, node_id)
            return

        fail = ""
        services, unknown = self.servicesfromopaque(name, node_id)
        for s in services:
            if event_type == EventTypes.STOP.value or event_type == EventTypes.RESTART.value:
                status = self.stopnodeservice(node, s)
                if status != "0":
                    fail += "Stop %s," % s._name
            if event_type == EventTypes.START.value or event_type == EventTypes.RESTART.value:
                if s._custom:
                    cmds = s._startup
                else:
                    cmds = s.getstartup(node, services)
                if len(cmds) > 0:
                    for cmd in cmds:
                        try:
                            # node.cmd(shlex.split(cmd),  wait = False)
                            status = node.cmd(shlex.split(cmd), wait=True)
                            if status != 0:
                                fail += "Start %s(%s)," % (s._name, cmd)
                        except:
                            logger.exception("error starting command %s", cmd)
                            fail += "Start %s," % s._name
            if event_type == EventTypes.PAUSE.value:
                status = self.validatenodeservice(node, s, services)
                if status != 0:
                    fail += "%s," % s._name
            if event_type == EventTypes.RECONFIGURE.value:
                if s._custom:
                    cfgfiles = s._configs
                else:
                    cfgfiles = s.getconfigfilenames(node.objid, services)
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
                            logger.exception("error in configure file: %s", filename)
                            fail += "%s," % s._name

        fail_data = ""
        if len(fail) > 0:
            fail_data += "Fail:" + fail
        unknown_data = ""
        num = len(unknown)
        if num > 0:
            for u in unknown:
                unknown_data += u
                if num > 1:
                    unknown_data += ", "
                num -= 1
            logger.warn("Event requested for unknown service(s): %s", unknown_data)
            unknown_data = "Unknown:" + unknown_data

        event_data = EventData(
            node=node_id,
            event_type=event_type,
            name=name,
            data=fail_data + ";" + unknown_data,
            time="%s" % time.time()
        )

        self.session.broadcast_event(event_data)


class CoreService(object):
    """
    Parent class used for defining services.
    """
    # service name should not include spaces
    _name = ""
    # group string allows grouping services together
    _group = ""
    # list name(s) of services that this service depends upon
    _depends = ()
    keys = ["dirs", "files", "startidx", "cmdup", "cmddown", "cmdval", "meta", "starttime"]
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
        """
        Services are not necessarily instantiated. Classmethods may be used
        against their config. Services are instantiated when a custom
        configuration is used to override their default parameters.
        """
        self._custom = True

    @classmethod
    def getconfigfilenames(cls, nodenum, services):
        """
        Return the tuple of configuration file filenames. This default method
        returns the cls._configs tuple, but this method may be overriden to
        provide node-specific filenames that may be based on other services.

        :param int nodenum: node id to get config file names for
        :param list services: node services
        :return: class configuration files
        :rtype: tuple
        """
        return cls._configs

    @classmethod
    def generateconfig(cls, node, filename, services):
        """
        Generate configuration file given a node object. The filename is
        provided to allow for multiple config files. The other services are
        provided to allow interdependencies (e.g. zebra and OSPF).
        Return the configuration string to be written to a file or sent
        to the GUI for customization.

        :param core.netns.nodes.CoreNode node: node to generate config for
        :param str filename: file name to generate config for
        :param list services: services for node
        :return: nothing
        """
        raise NotImplementedError

    @classmethod
    def getstartup(cls, node, services):
        """
        Return the tuple of startup commands. This default method
        returns the cls._startup tuple, but this method may be
        overridden to provide node-specific commands that may be
        based on other services.

        :param core.netns.nodes.CoreNode node: node to get startup for
        :param list services: services for node
        :return: startup commands
        :rtype: tuple
        """
        return cls._startup

    @classmethod
    def getvalidate(cls, node, services):
        """
        Return the tuple of validate commands. This default method
        returns the cls._validate tuple, but this method may be
        overriden to provide node-specific commands that may be
        based on other services.

        :param core.netns.nodes.CoreNode node: node to validate
        :param list services: services for node
        :return: validation commands
        :rtype: tuple
        """
        return cls._validate

    @classmethod
    def tovaluelist(cls, node, services):
        """
        Convert service properties into a string list of key=value pairs,
        separated by "|".

        :param core.netns.nodes.CoreNode node: node to get value list for
        :param list services: services for node
        :return: value list string
        :rtype: str
        """
        valmap = [cls._dirs, cls._configs, cls._startindex, cls._startup,
                  cls._shutdown, cls._validate, cls._meta, cls._starttime]
        if not cls._custom:
            # this is always reached due to classmethod
            valmap[valmap.index(cls._configs)] = \
                cls.getconfigfilenames(node.objid, services)
            valmap[valmap.index(cls._startup)] = \
                cls.getstartup(node, services)
        vals = map(lambda a, b: "%s=%s" % (a, str(b)), cls.keys, valmap)
        return "|".join(vals)

    def fromvaluelist(self, values):
        """
        Convert list of values into properties for this instantiated
        (customized) service.

        :param list values: value list to set properties from
        :return: nothing
        """
        # TODO: support empty value? e.g. override default meta with ''
        for key in self.keys:
            try:
                self.setvalue(key, values[self.keys.index(key)])
            except IndexError:
                # old config does not need to have new keys
                logger.exception("error indexing into key")

    def setvalue(self, key, value):
        """
        Set values for this service.

        :param str key: key to set value for
        :param value: value of key to set
        :return: nothing
        """
        if key not in self.keys:
            raise ValueError('key `%s` not in `%s`' % (key, self.keys))
        # this handles data conversion to int, string, and tuples
        if value:
            if key == "startidx":
                value = int(value)
            elif key == "meta":
                value = str(value)
            else:
                value = utils.maketuplefromstr(value, str)

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
