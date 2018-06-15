"""
Definition of CoreService class that is subclassed to define
startup services and routing for nodes. A service is typically a daemon
program launched when a node starts that provides some sort of service.
The CoreServices class handles configuration messages for sending
a list of available services to the GUI and for configuring individual
services.
"""

from core import CoreCommandError
from core import logger
from core.data import FileData
from core.enumerations import MessageFlags
from core.enumerations import RegisterTlvs
from core.misc import utils


class ServiceShim(object):
    keys = ["dirs", "files", "startidx", "cmdup", "cmddown", "cmdval", "meta", "starttime"]

    @classmethod
    def tovaluelist(cls, service, node, services):
        """
        Convert service properties into a string list of key=value pairs,
        separated by "|".

        :param CoreService service: service to get value list for
        :param core.netns.nodes.CoreNode node: node to get value list for
        :param list[CoreService] services: services for node
        :return: value list string
        :rtype: str
        """
        valmap = [service.dirs, service.configs, service.startindex, service.startup,
                  service.shutdown, service.validate, service.meta, service.starttime]
        if not service.custom:
            # this is always reached due to classmethod
            valmap[valmap.index(service.configs)] = service.getconfigfilenames(node.objid, services)
            valmap[valmap.index(service.startup)] = service.getstartup(node, services)
        vals = map(lambda a, b: "%s=%s" % (a, str(b)), cls.keys, valmap)
        return "|".join(vals)

    @classmethod
    def fromvaluelist(cls, service, values):
        """
        Convert list of values into properties for this instantiated
        (customized) service.

        :param CoreService service: service to get value list for
        :param dict values: value list to set properties from
        :return: nothing
        """
        # TODO: support empty value? e.g. override default meta with ''
        for key in cls.keys:
            try:
                cls.setvalue(service, key, values[cls.keys.index(key)])
            except IndexError:
                # old config does not need to have new keys
                logger.exception("error indexing into key")

    @classmethod
    def setvalue(cls, service, key, value):
        """
        Set values for this service.

        :param CoreService service: service to get value list for
        :param str key: key to set value for
        :param value: value of key to set
        :return: nothing
        """
        if key not in cls.keys:
            raise ValueError('key `%s` not in `%s`' % (key, cls.keys))
        # this handles data conversion to int, string, and tuples
        if value:
            if key == "startidx":
                value = int(value)
            elif key == "meta":
                value = str(value)
            else:
                value = utils.make_tuple_fromstr(value, str)

        if key == "dirs":
            service.dirs = value
        elif key == "files":
            service.configs = value
        elif key == "startidx":
            service.startindex = value
        elif key == "cmdup":
            service.startup = value
        elif key == "cmddown":
            service.shutdown = value
        elif key == "cmdval":
            service.validate = value
        elif key == "meta":
            service.meta = value
        elif key == "starttime":
            service.starttime = value

    @classmethod
    def servicesfromopaque(self, opaque):
        """
        Build a list of services from an opaque data string.

        :param str opaque: opaque data string
        :return: services
        :rtype: list
        """
        servicesstring = opaque.split(':')
        if servicesstring[0] != "service":
            return []
        return servicesstring[1].split(',')


class ServiceManager(object):
    """
    Manages services available for CORE nodes to use.
    """
    services = {}

    @classmethod
    def add(cls, service):
        """
        Add a service to manager.

        :param CoreService service: service to add
        :return: nothing
        """
        logger.info("loading service: %s", service.__name__)
        name = service.name
        if name in cls.services:
            raise ValueError("duplicate service being added: %s" % name)
        cls.services[name] = service

    @classmethod
    def get(cls, name):
        """
        Retrieve a service from the manager.

        :param str name: name of the service to retrieve
        :return: service if it exists, None otherwise
        :rtype: CoreService.class
        """
        return cls.services.get(name)

    @classmethod
    def add_services(cls, path):
        """
        Method for retrieving all CoreServices from a given path.

        :param str path: path to retrieve services from
        :return: list of core services
        :rtype: list
        """
        services = utils.load_classes(path, CoreService)
        for service in services:
            if not service.name:
                continue
            service.on_load()
            cls.add(service)


class CoreServices(object):
    """
    Class for interacting with a list of available startup services for
    nodes. Mostly used to convert a CoreService into a Config API
    message. This class lives in the Session object and remembers
    the default services configured for each node type, and any
    custom service configuration. A CoreService is not a Configurable.
    """
    name = "services"
    config_type = RegisterTlvs.UTILITY.value

    def __init__(self, session):
        """
        Creates a CoreServices instance.

        :param core.session.Session session: session this manager is tied to
        """
        self.session = session
        # dict of default services tuples, key is node type
        self.defaultservices = {}
        # dict of tuple of service objects, key is node number
        self.customservices = {}

        # TODO: remove need for cyclic import
        from core.services import startup
        self.is_startup_service = startup.Startup.is_startup_service

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
        :rtype: list[CoreService]
        """
        logger.debug("getting default services for type: %s", service_type)
        results = []
        defaults = self.defaultservices.get(service_type, [])
        for name in defaults:
            logger.debug("checking for service with service manager: %s", name)
            service = ServiceManager.get(name)
            if not service:
                logger.warn("default service %s is unknown", name)
            else:
                results.append(service)
        return results

    def getcustomservice(self, node_id, service_name, default_service=False):
        """
        Get any custom service configured for the given node that matches the specified service name.
        If no custom service is found, return the specified service.

        :param int node_id: object id to get service from
        :param str service_name: name of service to retrieve
        :param bool default_service: True to return default service when custom does not exist, False returns None
        :return: custom service from the node
        :rtype: CoreService
        """
        node_services = self.customservices.setdefault(node_id, {})
        default = None
        if default_service:
            default = ServiceManager.get(service_name)
        return node_services.get(service_name, default)

    def setcustomservice(self, node_id, service_name):
        """
        Store service customizations in an instantiated service object
        using a list of values that came from a config message.

        :param int node_id: object id to set custom service for
        :param str service_name: name of service to set
        :return: nothing
        """
        logger.debug("setting custom service(%s) for node: %s", node_id, service_name)
        service = self.getcustomservice(node_id, service_name)
        if not service:
            service_class = ServiceManager.get(service_name)
            service = service_class()

            # add the custom service to dict
            node_services = self.customservices.setdefault(node_id, {})
            node_services[service.name] = service

    def addservicestonode(self, node, node_type, services=None):
        """
        Add services to a node.

        :param core.coreobj.PyCoreNode node: node to add services to
        :param str node_type: node type to add services to
        :param list[str] services: services to add to node
        :return: nothing
        """
        if not services:
            logger.info("using default services for node(%s) type(%s)", node.name, node_type)
            services = self.defaultservices.get(node_type, [])

        logger.info("setting services for node(%s): %s", node.name, services)
        for service_name in services:
            service = self.getcustomservice(node.objid, service_name, default_service=True)
            if not service:
                logger.warn("unknown service(%s) for node(%s)", service_name, node.name)
                continue
            logger.info("adding service to node(%s): %s", node.name, service_name)
            node.addservice(service)

    def getallconfigs(self):
        """
        Return (nodenum, service) tuples for all stored configs. Used when reconnecting to a
        session or opening XML.

        :param bool use_clsmap: should a class map be used, default to True
        :return: list of tuples of node ids and services
        :rtype: list
        """
        configs = []
        for node_id in self.customservices.iterkeys():
            for service in self.customservices[node_id].itervalues():
                configs.append((node_id, service))
        return configs

    def getallfiles(self, service):
        """
        Return all customized files stored with a service.
        Used when reconnecting to a session or opening XML.

        :param CoreService service: service to get files for
        :return:
        """
        files = []

        if not service.custom:
            return files

        for filename in service.configs:
            data = service.configtxt.get(filename)
            if data is None:
                continue
            files.append((filename, data))

        return files

    def bootnodeservices(self, node):
        """
        Start all services on a node.

        :param core.netns.vnode.LxcNode node: node to start services on
        :return: nothing
        """
        services = sorted(node.services, key=lambda x: x.startindex)
        use_startup_service = any(map(self.is_startup_service, services))
        for service in services:
            if len(str(service.starttime)) > 0:
                try:
                    starttime = float(service.starttime)
                    if starttime > 0.0:
                        fn = self.bootnodeservice
                        self.session.event_loop.add_event(starttime, fn, node, service, services, False)
                        continue
                except ValueError:
                    logger.exception("error converting start time to float")
            self.bootnodeservice(node, service, services, use_startup_service)

    def bootnodeservice(self, node, service, services, use_startup_service):
        """
        Start a service on a node. Create private dirs, generate config
        files, and execute startup commands.

        :param core.netns.vnode.LxcNode node: node to boot services on
        :param CoreService service: service to start
        :param list services: service list
        :param bool use_startup_service: flag to use startup services or not
        :return: nothing
        """
        if service.custom:
            self.bootnodecustomservice(node, service, services, use_startup_service)
            return

        logger.info("starting node(%s) service: %s (%s)", node.name, service.name, service.startindex)
        for directory in service.dirs:
            node.privatedir(directory)

        for filename in service.getconfigfilenames(node.objid, services):
            cfg = service.generateconfig(node, filename, services)
            node.nodefile(filename, cfg)

        if use_startup_service and not self.is_startup_service(service):
            return

        for args in service.getstartup(node, services):
            # TODO: this wait=False can be problematic!
            node.cmd(args, wait=False)

    def bootnodecustomservice(self, node, service, services, use_startup_service):
        """
        Start a custom service on a node. Create private dirs, use supplied
        config files, and execute  supplied startup commands.

        :param core.netns.vnode.LxcNode node: node to boot services on
        :param CoreService service: service to start
        :param list services: service list
        :param bool use_startup_service: flag to use startup services or not
        :return: nothing
        """
        logger.info("starting node(%s) service(custom): %s (%s)", node.name, service.name, service.startindex)
        for directory in service.dirs:
            node.privatedir(directory)

        logger.info("service configurations: %s", service.configs)
        for filename in service.configs:
            logger.info("generating service config: %s", filename)
            cfg = service.configtxt.get(filename)
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

        for args in service.startup:
            # TODO: this wait=False can be problematic!
            node.cmd(args, wait=False)

    def copyservicefile(self, node, filename, cfg):
        """
        Given a configured service filename and config, determine if the
        config references an existing file that should be copied.
        Returns True for local files, False for generated.

        :param core.netns.vnode.LxcNode node: node to copy service for
        :param str filename: file name for a configured service
        :param str cfg: configuration string
        :return: True if successful, False otherwise
        :rtype: bool
        """
        if cfg[:7] == 'file://':
            src = cfg[7:]
            src = src.split('\n')[0]
            src = utils.expand_corepath(src, node.session, node)
            # TODO: glob here
            node.nodefilecopy(filename, src, mode=0644)
            return True
        return False

    def validatenodeservices(self, node):
        """
        Run validation commands for all services on a node.

        :param core.netns.vnode.LxcNode node: node to validate services for
        :return: nothing
        """
        services = sorted(node.services, key=lambda service: service.startindex)
        for service in services:
            self.validatenodeservice(node, service, services)

    def validatenodeservice(self, node, service, services):
        """
        Run the validation command(s) for a service.

        :param core.netns.vnode.LxcNode node: node to validate service for
        :param CoreService service: service to validate
        :param list services: services for node
        :return: service validation status
        :rtype: int
        """
        logger.info("validating service for node (%s): %s (%s)", node.name, service.name, service.startindex)
        if service.custom:
            validate_cmds = service.validate
        else:
            validate_cmds = service.getvalidate(node, services)

        status = 0
        for args in validate_cmds:
            logger.info("validating service %s using: %s", service.name, args)
            try:
                node.check_cmd(args)
            except CoreCommandError:
                logger.exception("validate command failed")
                status = -1

        return status

    def stopnodeservices(self, node):
        """
        Stop all services on a node.

        :param core.netns.nodes.CoreNode node: node to stop services on
        :return: nothing
        """
        services = sorted(node.services, key=lambda x: x.startindex)
        for service in services:
            self.stopnodeservice(node, service)

    def stopnodeservice(self, node, service):
        """
        Stop a service on a node.

        :param core.netns.vnode.LxcNode node: node to stop a service on
        :param CoreService service: service to stop
        :return: status for stopping the services
        :rtype: str
        """
        status = "0"
        for args in service.shutdown:
            try:
                node.check_cmd(args)
            except CoreCommandError:
                logger.exception("error running stop command %s", args)
                # TODO: determine if its ok to just return the bad exit status
                status = "-1"
        return status

    def getservicefile(self, service_name, node, filename, services):
        """
        Send a File Message when the GUI has requested a service file.
        The file data is either auto-generated or comes from an existing config.

        :param str service_name: service to get file from
        :param core.netns.vnode.LxcNode node: node to get service file from
        :param str filename: file name to retrieve
        :param list[str] services: list of services associated with node
        :return: file message for node
        """
        # get service to get file from
        service = self.getcustomservice(node.objid, service_name, default_service=True)
        if not service:
            raise ValueError("invalid service: %s", service_name)

        # get service for node
        node_services = []
        for service_name in services:
            node_service = self.getcustomservice(node.objid, service_name, default_service=True)
            if not node_service:
                logger.warn("unknown service: %s", service)
                continue
            node_services.append(node_service)

        # retrieve config files for default/custom service
        if service.custom:
            config_files = service.configs
        else:
            config_files = service.getconfigfilenames(node.objid, node_services)

        if filename not in config_files:
            raise ValueError("unknown service(%s) config file: %s", service_name, filename)

        # get the file data
        data = service.configtxt.get(filename)
        if data is None:
            data = "%s" % service.generateconfig(node, filename, services)
        else:
            data = "%s" % data

        filetypestr = "service:%s" % service.name
        return FileData(
            message_type=MessageFlags.ADD.value,
            node=node.objid,
            name=filename,
            type=filetypestr,
            data=data
        )

    def setservicefile(self, node_id, service_name, filename, data):
        """
        Receive a File Message from the GUI and store the customized file
        in the service config. The filename must match one from the list of
        config files in the service.

        :param int node_id: node id to set service file
        :param str service_name: service name to set file for
        :param str filename: file name to set
        :param data: data for file to set
        :return: nothing
        """
        # attempt to set custom service, if needed
        self.setcustomservice(node_id, service_name)

        # retrieve custom service
        svc = self.getcustomservice(node_id, service_name)
        if svc is None:
            logger.warn("received filename for unknown service: %s", service_name)
            return

        # validate file being set is valid
        cfgfiles = svc.configs
        if filename not in cfgfiles:
            logger.warn("received unknown file '%s' for service '%s'", filename, service_name)
            return

        # set custom service file data
        svc.configtxt[filename] = data

    def node_service_startup(self, node, service, services):
        """
        Startup a node service.

        :param PyCoreNode node: node to reconfigure service for
        :param CoreService service: service to reconfigure
        :param list[CoreService] services: node services
        :return: status of startup
        :rtype: str
        """

        if service.custom:
            cmds = service.startup
        else:
            cmds = service.getstartup(node, services)

        status = "0"
        for args in cmds:
            try:
                node.check_cmd(args)
            except CoreCommandError:
                logger.exception("error starting command")
                status = "-1"
        return status

    def node_service_reconfigure(self, node, service, services):
        """
        Reconfigure a node service.

        :param PyCoreNode node: node to reconfigure service for
        :param CoreService service: service to reconfigure
        :param list[CoreService] services: node services
        :return: nothing
        """
        if service.custom:
            cfgfiles = service.configs
        else:
            cfgfiles = service.getconfigfilenames(node.objid, services)

        for filename in cfgfiles:
            if filename[:7] == "file:///":
                # TODO: implement this
                raise NotImplementedError

            cfg = service.configtxt.get(filename)
            if cfg is None:
                cfg = service.generateconfig(node, filename, services)

            node.nodefile(filename, cfg)


class CoreService(object):
    """
    Parent class used for defining services.
    """
    # service name should not include spaces
    name = None

    # group string allows grouping services together
    group = None

    # list name(s) of services that this service depends upon
    depends = ()

    # private, per-node directories required by this service
    dirs = ()

    # config files written by this service
    configs = ()

    # index used to determine start order with other services
    startindex = 0

    # time in seconds after runtime to run startup commands
    starttime = 0

    # list of startup commands
    startup = ()

    # list of shutdown commands
    shutdown = ()

    # list of validate commands
    validate = ()

    # metadata associated with this service
    meta = None

    # custom configuration text
    configtxt = {}
    custom = False
    custom_needed = False

    def __init__(self):
        """
        Services are not necessarily instantiated. Classmethods may be used
        against their config. Services are instantiated when a custom
        configuration is used to override their default parameters.
        """
        self.custom = True
        self.dirs = self.__class__.dirs
        self.configs = self.__class__.configs
        self.startindex = self.__class__.startindex
        self.startup = self.__class__.startup
        self.shutdown = self.__class__.shutdown
        self.validate = self.__class__.validate
        self.meta = self.__class__.meta
        self.starttime = self.__class__.starttime
        self.configtxt = self.__class__.configtxt

    @classmethod
    def on_load(cls):
        pass

    @classmethod
    def getconfigfilenames(cls, node_id, services):
        """
        Return the tuple of configuration file filenames. This default method
        returns the cls._configs tuple, but this method may be overriden to
        provide node-specific filenames that may be based on other services.

        :param int node_id: node id to get config file names for
        :param list services: node services
        :return: class configuration files
        :rtype: tuple
        """
        return cls.configs

    @classmethod
    def generateconfig(cls, node, filename, services):
        """
        Generate configuration file given a node object. The filename is
        provided to allow for multiple config files. The other services are
        provided to allow interdependencies (e.g. zebra and OSPF).
        Return the configuration string to be written to a file or sent
        to the GUI for customization.

        :param core.netns.vnode.LxcNode node: node to generate config for
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

        :param core.netns.vnode.LxcNode node: node to get startup for
        :param list services: services for node
        :return: startup commands
        :rtype: tuple
        """
        return cls.startup

    @classmethod
    def getvalidate(cls, node, services):
        """
        Return the tuple of validate commands. This default method
        returns the cls._validate tuple, but this method may be
        overriden to provide node-specific commands that may be
        based on other services.

        :param core.netns.vnode.LxcNode node: node to validate
        :param list services: services for node
        :return: validation commands
        :rtype: tuple
        """
        return cls.validate
