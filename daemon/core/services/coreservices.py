"""
Definition of CoreService class that is subclassed to define
startup services and routing for nodes. A service is typically a daemon
program launched when a node starts that provides some sort of service.
The CoreServices class handles configuration messages for sending
a list of available services to the GUI and for configuring individual
services.
"""

import logging
import time
from multiprocessing.pool import ThreadPool

import enum
from core.constants import which

from core import CoreCommandError, utils
from core.emulator.data import FileData
from core.emulator.enumerations import MessageFlags
from core.emulator.enumerations import RegisterTlvs


class ServiceBootError(Exception):
    pass


class ServiceMode(enum.Enum):
    BLOCKING = 0
    NON_BLOCKING = 1
    TIMER = 2


class ServiceDependencies(object):
    """
    Can generate boot paths for services, based on their dependencies. Will validate
    that all services will be booted and that all dependencies exist within the services provided.
    """

    def __init__(self, services):
        # helpers to check validity
        self.dependents = {}
        self.booted = set()
        self.node_services = {}
        for service in services:
            self.node_services[service.name] = service
            for dependency in service.dependencies:
                dependents = self.dependents.setdefault(dependency, set())
                dependents.add(service.name)

        # used to find paths
        self.path = []
        self.visited = set()
        self.visiting = set()

    def boot_paths(self):
        """
        Generates the boot paths for the services provided to the class.

        :return: list of services to boot, in order
        :rtype: list[core.coreservices.CoreService]
        """
        paths = []
        for name in self.node_services:
            service = self.node_services[name]
            if service.name in self.booted:
                logging.debug("skipping service that will already be booted: %s", service.name)
                continue

            path = self._start(service)
            if path:
                paths.append(path)

        if self.booted != set(self.node_services):
            raise ValueError("failure to boot all services: %s != %s" % (self.booted, self.node_services.keys()))

        return paths

    def _reset(self):
        self.path = []
        self.visited.clear()
        self.visiting.clear()

    def _start(self, service):
        logging.debug("starting service dependency check: %s", service.name)
        self._reset()
        return self._visit(service)

    def _visit(self, current_service):
        logging.debug("visiting service(%s): %s", current_service.name, self.path)
        self.visited.add(current_service.name)
        self.visiting.add(current_service.name)

        # dive down
        for service_name in current_service.dependencies:
            if service_name not in self.node_services:
                raise ValueError("required dependency was not included in node services: %s" % service_name)

            if service_name in self.visiting:
                raise ValueError("cyclic dependency at service(%s): %s" % (current_service.name, service_name))

            if service_name not in self.visited:
                service = self.node_services[service_name]
                self._visit(service)

        # add service when bottom is found
        logging.debug("adding service to boot path: %s", current_service.name)
        self.booted.add(current_service.name)
        self.path.append(current_service)
        self.visiting.remove(current_service.name)

        # rise back up
        for service_name in self.dependents.get(current_service.name, []):
            if service_name not in self.visited:
                service = self.node_services[service_name]
                self._visit(service)

        return self.path


class ServiceShim(object):
    keys = ["dirs", "files", "startidx", "cmdup", "cmddown", "cmdval", "meta", "starttime"]

    @classmethod
    def tovaluelist(cls, node, service):
        """
        Convert service properties into a string list of key=value pairs,
        separated by "|".

        :param core.netns.vnode.CoreNode node: node to get value list for
        :param CoreService service: service to get value list for
        :return: value list string
        :rtype: str
        """
        start_time = 0
        start_index = 0
        valmap = [service.dirs, service.configs, start_index, service.startup,
                  service.shutdown, service.validate, service.meta, start_time]
        if not service.custom:
            valmap[1] = service.get_configs(node)
            valmap[3] = service.get_startup(node)
        vals = ["%s=%s" % (x, y) for x, y in zip(cls.keys, valmap)]
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
                logging.exception("error indexing into key")

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
            raise ValueError("key `%s` not in `%s`" % (key, cls.keys))
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
        elif key == "cmdup":
            service.startup = value
        elif key == "cmddown":
            service.shutdown = value
        elif key == "cmdval":
            service.validate = value
        elif key == "meta":
            service.meta = value

    @classmethod
    def servicesfromopaque(cls, opaque):
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
        name = service.name
        logging.debug("loading service: class(%s) name(%s)", service.__name__, name)

        # avoid duplicate services
        if name in cls.services:
            raise ValueError("duplicate service being added: %s" % name)

        # validate dependent executables are present
        for executable in service.executables:
            if not which(executable):
                logging.debug("service(%s) missing executable: %s", service.name, executable)
                raise ValueError("service(%s) missing executable: %s" % (service.name, executable))

        # make service available
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
        :return: list of core services that failed to load
        :rtype: list[str]
        """
        service_errors = []
        services = utils.load_classes(path, CoreService)
        for service in services:
            if not service.name:
                continue
            service.on_load()

            try:
                cls.add(service)
            except ValueError as e:
                service_errors.append(service.name)
                logging.debug("not loading service: %s", e)
        return service_errors


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
        self.default_services = {}
        # dict of node ids to dict of custom services by name
        self.custom_services = {}

    def reset(self):
        """
        Called when config message with reset flag is received
        """
        self.custom_services.clear()

    def get_default_services(self, node_type):
        """
        Get the list of default services that should be enabled for a
        node for the given node type.

        :param node_type: node type to get default services for
        :return: default services
        :rtype: list[CoreService]
        """
        logging.debug("getting default services for type: %s", node_type)
        results = []
        defaults = self.default_services.get(node_type, [])
        for name in defaults:
            logging.debug("checking for service with service manager: %s", name)
            service = ServiceManager.get(name)
            if not service:
                logging.warn("default service %s is unknown", name)
            else:
                results.append(service)
        return results

    def get_service(self, node_id, service_name, default_service=False):
        """
        Get any custom service configured for the given node that matches the specified service name.
        If no custom service is found, return the specified service.

        :param int node_id: object id to get service from
        :param str service_name: name of service to retrieve
        :param bool default_service: True to return default service when custom does not exist, False returns None
        :return: custom service from the node
        :rtype: CoreService
        """
        node_services = self.custom_services.setdefault(node_id, {})
        default = None
        if default_service:
            default = ServiceManager.get(service_name)
        return node_services.get(service_name, default)

    def set_service(self, node_id, service_name):
        """
        Store service customizations in an instantiated service object
        using a list of values that came from a config message.

        :param int node_id: object id to set custom service for
        :param str service_name: name of service to set
        :return: nothing
        """
        logging.debug("setting custom service(%s) for node: %s", service_name, node_id)
        service = self.get_service(node_id, service_name)
        if not service:
            service_class = ServiceManager.get(service_name)
            service = service_class()

            # add the custom service to dict
            node_services = self.custom_services.setdefault(node_id, {})
            node_services[service.name] = service

    def add_services(self, node, node_type, services=None):
        """
        Add services to a node.

        :param core.coreobj.PyCoreNode node: node to add services to
        :param str node_type: node type to add services to
        :param list[str] services: names of services to add to node
        :return: nothing
        """
        if not services:
            logging.info("using default services for node(%s) type(%s)", node.name, node_type)
            services = self.default_services.get(node_type, [])

        logging.info("setting services for node(%s): %s", node.name, services)
        for service_name in services:
            service = self.get_service(node.id, service_name, default_service=True)
            if not service:
                logging.warn("unknown service(%s) for node(%s)", service_name, node.name)
                continue
            logging.info("adding service to node(%s): %s", node.name, service_name)
            node.addservice(service)

    def all_configs(self):
        """
        Return (node_id, service) tuples for all stored configs. Used when reconnecting to a
        session or opening XML.

        :return: list of tuples of node ids and services
        :rtype: list[tuple]
        """
        configs = []
        for node_id in self.custom_services:
            custom_services = self.custom_services[node_id]
            for name in custom_services:
                service = custom_services[name]
                configs.append((node_id, service))
        return configs

    def all_files(self, service):
        """
        Return all customized files stored with a service.
        Used when reconnecting to a session or opening XML.

        :param CoreService service: service to get files for
        :return: list of all custom service files
        :rtype: list[tuple]
        """
        files = []
        if not service.custom:
            return files

        for filename in service.configs:
            data = service.config_data.get(filename)
            if data is None:
                continue
            files.append((filename, data))

        return files

    def boot_services(self, node):
        """
        Start all services on a node.

        :param core.netns.vnode.LxcNode node: node to start services on
        :return: nothing
        """
        pool = ThreadPool()
        results = []

        boot_paths = ServiceDependencies(node.services).boot_paths()
        for boot_path in boot_paths:
            result = pool.apply_async(self._start_boot_paths, (node, boot_path))
            results.append(result)

        pool.close()
        pool.join()
        for result in results:
            result.get()

    def _start_boot_paths(self, node, boot_path):
        """
        Start all service boot paths found, based on dependencies.

        :param core.netns.vnode.LxcNode node: node to start services on
        :param list[CoreService] boot_path: service to start in dependent order
        :return: nothing
        """
        logging.info("booting node services: %s", " -> ".join([x.name for x in boot_path]))
        for service in boot_path:
            try:
                self.boot_service(node, service)
            except:
                logging.exception("exception booting service: %s", service.name)
                raise

    def boot_service(self, node, service):
        """
        Start a service on a node. Create private dirs, generate config
        files, and execute startup commands.

        :param core.netns.vnode.LxcNode node: node to boot services on
        :param CoreService service: service to start
        :return: nothing
        """
        logging.info("starting node(%s) service(%s) validation(%s)", node.name, service.name,
                    service.validation_mode.name)

        # create service directories
        for directory in service.dirs:
            try:
                node.privatedir(directory)
            except (CoreCommandError, ValueError) as e:
                logging.warn("error mounting private dir '%s' for service '%s': %s",
                            directory, service.name, e)

        # create service files
        self.create_service_files(node, service)

        # run startup
        wait = service.validation_mode == ServiceMode.BLOCKING
        status = self.startup_service(node, service, wait)
        if status:
            raise ServiceBootError("node(%s) service(%s) error during startup" % (node.name, service.name))

        # blocking mode is finished
        if wait:
            return

        # timer mode, sleep and return
        if service.validation_mode == ServiceMode.TIMER:
            time.sleep(service.validation_timer)
        # non-blocking, attempt to validate periodically, up to validation_timer time
        elif service.validation_mode == ServiceMode.NON_BLOCKING:
            start = time.time()
            while True:
                status = self.validate_service(node, service)
                if not status:
                    break

                if time.time() - start > service.validation_timer:
                    break

                time.sleep(service.validation_period)

            if status:
                raise ServiceBootError("node(%s) service(%s) failed validation" % (node.name, service.name))

    def copy_service_file(self, node, filename, cfg):
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
            node.nodefilecopy(filename, src, mode=0o644)
            return True
        return False

    def validate_service(self, node, service):
        """
        Run the validation command(s) for a service.

        :param core.netns.vnode.LxcNode node: node to validate service for
        :param CoreService service: service to validate
        :return: service validation status
        :rtype: int
        """
        logging.info("validating node(%s) service(%s)", node.name, service.name)
        cmds = service.validate
        if not service.custom:
            cmds = service.get_validate(node)

        status = 0
        for cmd in cmds:
            logging.debug("validating service(%s) using: %s", service.name, cmd)
            try:
                node.check_cmd(cmd)
            except CoreCommandError as e:
                logging.error("node(%s) service(%s) validate failed", node.name, service.name)
                logging.error("cmd(%s): %s", e.cmd, e.output)
                status = -1
                break

        return status

    def stop_services(self, node):
        """
        Stop all services on a node.

        :param core.netns.vnode.CoreNode node: node to stop services on
        :return: nothing
        """
        for service in node.services:
            self.stop_service(node, service)

    def stop_service(self, node, service):
        """
        Stop a service on a node.

        :param core.netns.vnode.LxcNode node: node to stop a service on
        :param CoreService service: service to stop
        :return: status for stopping the services
        :rtype: str
        """
        status = 0
        for args in service.shutdown:
            try:
                node.check_cmd(args)
            except CoreCommandError:
                logging.exception("error running stop command %s", args)
                status = -1
        return status

    def get_service_file(self, node, service_name, filename):
        """
        Send a File Message when the GUI has requested a service file.
        The file data is either auto-generated or comes from an existing config.

        :param core.netns.vnode.LxcNode node: node to get service file from
        :param str service_name: service to get file from
        :param str filename: file name to retrieve
        :return: file message for node
        """
        # get service to get file from
        service = self.get_service(node.id, service_name, default_service=True)
        if not service:
            raise ValueError("invalid service: %s", service_name)

        # retrieve config files for default/custom service
        if service.custom:
            config_files = service.configs
        else:
            config_files = service.get_configs(node)

        if filename not in config_files:
            raise ValueError("unknown service(%s) config file: %s", service_name, filename)

        # get the file data
        data = service.config_data.get(filename)
        if data is None:
            data = "%s" % service.generate_config(node, filename)
        else:
            data = "%s" % data

        filetypestr = "service:%s" % service.name
        return FileData(
            message_type=MessageFlags.ADD.value,
            node=node.id,
            name=filename,
            type=filetypestr,
            data=data
        )

    def set_service_file(self, node_id, service_name, file_name, data):
        """
        Receive a File Message from the GUI and store the customized file
        in the service config. The filename must match one from the list of
        config files in the service.

        :param int node_id: node id to set service file
        :param str service_name: service name to set file for
        :param str file_name: file name to set
        :param data: data for file to set
        :return: nothing
        """
        # attempt to set custom service, if needed
        self.set_service(node_id, service_name)

        # retrieve custom service
        service = self.get_service(node_id, service_name)
        if service is None:
            logging.warn("received file name for unknown service: %s", service_name)
            return

        # validate file being set is valid
        config_files = service.configs
        if file_name not in config_files:
            logging.warn("received unknown file(%s) for service(%s)", file_name, service_name)
            return

        # set custom service file data
        service.config_data[file_name] = data

    def startup_service(self, node, service, wait=False):
        """
        Startup a node service.

        :param PyCoreNode node: node to reconfigure service for
        :param CoreService service: service to reconfigure
        :param bool wait: determines if we should wait to validate startup
        :return: status of startup
        :rtype: int
        """

        cmds = service.startup
        if not service.custom:
            cmds = service.get_startup(node)

        status = 0
        for cmd in cmds:
            try:
                if wait:
                    node.check_cmd(cmd)
                else:
                    node.cmd(cmd, wait=False)
            except CoreCommandError:
                logging.exception("error starting command")
                status = -1
        return status

    def create_service_files(self, node, service):
        """
        Creates node service files.

        :param PyCoreNode node: node to reconfigure service for
        :param CoreService service: service to reconfigure
        :return: nothing
        """
        logging.info("node(%s) service(%s) creating config files", node.name, service.name)
        # get values depending on if custom or not
        config_files = service.configs
        if not service.custom:
            config_files = service.get_configs(node)

        for file_name in config_files:
            logging.debug("generating service config: %s", file_name)
            if service.custom:
                cfg = service.config_data.get(file_name)
                if cfg is None:
                    cfg = service.generate_config(node, file_name)

                # cfg may have a file:/// url for copying from a file
                try:
                    if self.copy_service_file(node, file_name, cfg):
                        continue
                except IOError:
                    logging.exception("error copying service file: %s", file_name)
                    continue
            else:
                cfg = service.generate_config(node, file_name)

            node.nodefile(file_name, cfg)

    def service_reconfigure(self, node, service):
        """
        Reconfigure a node service.

        :param PyCoreNode node: node to reconfigure service for
        :param CoreService service: service to reconfigure
        :return: nothing
        """
        config_files = service.configs
        if not service.custom:
            config_files = service.get_configs(node)

        for file_name in config_files:
            if file_name[:7] == "file:///":
                # TODO: implement this
                raise NotImplementedError

            cfg = service.config_data.get(file_name)
            if cfg is None:
                cfg = service.generate_config(node, file_name)

            node.nodefile(file_name, cfg)


class CoreService(object):
    """
    Parent class used for defining services.
    """
    # service name should not include spaces
    name = None

    # executables that must exist for service to run
    executables = ()

    # sets service requirements that must be started prior to this service starting
    dependencies = ()

    # group string allows grouping services together
    group = None

    # private, per-node directories required by this service
    dirs = ()

    # config files written by this service
    configs = ()

    # config file data
    config_data = {}

    # list of startup commands
    startup = ()

    # list of shutdown commands
    shutdown = ()

    # list of validate commands
    validate = ()

    # validation mode, used to determine startup success
    validation_mode = ServiceMode.NON_BLOCKING

    # time to wait in seconds for determining if service started successfully
    validation_timer = 5

    # validation period in seconds, how frequent validation is attempted
    validation_period = 0.5

    # metadata associated with this service
    meta = None

    # custom configuration text
    custom = False
    custom_needed = False

    def __init__(self):
        """
        Services are not necessarily instantiated. Classmethods may be used
        against their config. Services are instantiated when a custom
        configuration is used to override their default parameters.
        """
        self.custom = True
        self.config_data = self.__class__.config_data.copy()

    @classmethod
    def on_load(cls):
        pass

    @classmethod
    def get_configs(cls, node):
        """
        Return the tuple of configuration file filenames. This default method
        returns the cls._configs tuple, but this method may be overriden to
        provide node-specific filenames that may be based on other services.

        :param core.netns.vnode.LxcNode node: node to generate config for
        :return: configuration files
        :rtype: tuple
        """
        return cls.configs

    @classmethod
    def generate_config(cls, node, filename):
        """
        Generate configuration file given a node object. The filename is
        provided to allow for multiple config files.
        Return the configuration string to be written to a file or sent
        to the GUI for customization.

        :param core.netns.vnode.LxcNode node: node to generate config for
        :param str filename: file name to generate config for
        :return: nothing
        """
        raise NotImplementedError

    @classmethod
    def get_startup(cls, node):
        """
        Return the tuple of startup commands. This default method
        returns the cls.startup tuple, but this method may be
        overridden to provide node-specific commands that may be
        based on other services.

        :param core.netns.vnode.LxcNode node: node to get startup for
        :return: startup commands
        :rtype: tuple
        """
        return cls.startup

    @classmethod
    def get_validate(cls, node):
        """
        Return the tuple of validate commands. This default method
        returns the cls.validate tuple, but this method may be
        overridden to provide node-specific commands that may be
        based on other services.

        :param core.netns.vnode.LxcNode node: node to validate
        :return: validation commands
        :rtype: tuple
        """
        return cls.validate
