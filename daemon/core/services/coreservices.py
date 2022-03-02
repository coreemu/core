"""
Definition of CoreService class that is subclassed to define
startup services and routing for nodes. A service is typically a daemon
program launched when a node starts that provides some sort of service.
The CoreServices class handles configuration messages for sending
a list of available services to the GUI and for configuring individual
services.
"""

import enum
import logging
import pkgutil
import time
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from core import services as core_services
from core import utils
from core.emulator.data import FileData
from core.emulator.enumerations import ExceptionLevels, MessageFlags, RegisterTlvs
from core.errors import (
    CoreCommandError,
    CoreError,
    CoreServiceBootError,
    CoreServiceError,
)
from core.nodes.base import CoreNode

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

    CoreServiceType = Union["CoreService", Type["CoreService"]]


class ServiceMode(enum.Enum):
    BLOCKING = 0
    NON_BLOCKING = 1
    TIMER = 2


class ServiceDependencies:
    """
    Can generate boot paths for services, based on their dependencies. Will validate
    that all services will be booted and that all dependencies exist within the services
    provided.
    """

    def __init__(self, services: List["CoreServiceType"]) -> None:
        self.visited: Set[str] = set()
        self.services: Dict[str, "CoreServiceType"] = {}
        self.paths: Dict[str, List["CoreServiceType"]] = {}
        self.boot_paths: List[List["CoreServiceType"]] = []
        roots = set([x.name for x in services])
        for service in services:
            self.services[service.name] = service
            roots -= set(service.dependencies)
        self.roots: List["CoreServiceType"] = [x for x in services if x.name in roots]
        if services and not self.roots:
            raise ValueError("circular dependency is present")

    def _search(
        self,
        service: "CoreServiceType",
        visiting: Set[str] = None,
        path: List[str] = None,
    ) -> List["CoreServiceType"]:
        if service.name in self.visited:
            return self.paths[service.name]
        self.visited.add(service.name)
        if visiting is None:
            visiting = set()
        visiting.add(service.name)
        if path is None:
            for dependency in service.dependencies:
                path = self.paths.get(dependency)
                if path is not None:
                    break
        for dependency in service.dependencies:
            service_dependency = self.services.get(dependency)
            if not service_dependency:
                raise ValueError(f"required dependency was not provided: {dependency}")
            if dependency in visiting:
                raise ValueError(f"circular dependency, already visited: {dependency}")
            else:
                path = self._search(service_dependency, visiting, path)
        visiting.remove(service.name)
        if path is None:
            path = []
            self.boot_paths.append(path)
        path.append(service)
        self.paths[service.name] = path
        return path

    def boot_order(self) -> List[List["CoreServiceType"]]:
        for service in self.roots:
            self._search(service)
        return self.boot_paths


class ServiceShim:
    keys: List[str] = [
        "dirs",
        "files",
        "startidx",
        "cmdup",
        "cmddown",
        "cmdval",
        "meta",
        "starttime",
    ]

    @classmethod
    def tovaluelist(cls, node: CoreNode, service: "CoreService") -> str:
        """
        Convert service properties into a string list of key=value pairs,
        separated by "|".

        :param node: node to get value list for
        :param service: service to get value list for
        :return: value list string
        """
        start_time = 0
        start_index = 0
        valmap = [
            service.dirs,
            service.configs,
            start_index,
            service.startup,
            service.shutdown,
            service.validate,
            service.meta,
            start_time,
        ]
        if not service.custom:
            valmap[1] = service.get_configs(node)
            valmap[3] = service.get_startup(node)
        vals = ["%s=%s" % (x, y) for x, y in zip(cls.keys, valmap)]
        return "|".join(vals)

    @classmethod
    def fromvaluelist(cls, service: "CoreService", values: List[str]) -> None:
        """
        Convert list of values into properties for this instantiated
        (customized) service.

        :param service: service to get value list for
        :param values: value list to set properties from
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
    def setvalue(cls, service: "CoreService", key: str, value: str) -> None:
        """
        Set values for this service.

        :param service: service to get value list for
        :param key: key to set value for
        :param value: value of key to set
        :return: nothing
        """
        if key not in cls.keys:
            raise ValueError("key `%s` not in `%s`" % (key, cls.keys))
        # this handles data conversion to int, string, and tuples
        if value:
            if key == "startidx":
                value = int(value)
            elif key == "starttime":
                value = float(value)
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
    def servicesfromopaque(cls, opaque: str) -> List[str]:
        """
        Build a list of services from an opaque data string.

        :param opaque: opaque data string
        :return: services
        """
        servicesstring = opaque.split(":")
        if servicesstring[0] != "service":
            return []
        return servicesstring[1].split(",")


class ServiceManager:
    """
    Manages services available for CORE nodes to use.
    """

    services: Dict[str, Type["CoreService"]] = {}

    @classmethod
    def add(cls, service: Type["CoreService"]) -> None:
        """
        Add a service to manager.

        :param service: service to add
        :return: nothing
        :raises ValueError: when service cannot be loaded
        """
        name = service.name
        logger.debug("loading service: class(%s) name(%s)", service.__name__, name)
        # avoid services with no name
        if name is None:
            logger.debug("not loading class(%s) with no name", service.__name__)
            return
        # avoid duplicate services
        if name in cls.services:
            raise ValueError(f"duplicate service being added: {name}")
        # validate dependent executables are present
        for executable in service.executables:
            try:
                utils.which(executable, required=True)
            except CoreError as e:
                raise CoreError(f"service({name}): {e}")
        # validate service on load succeeds
        try:
            service.on_load()
        except Exception as e:
            logger.exception("error during service(%s) on load", service.name)
            raise ValueError(e)
        # make service available
        cls.services[name] = service

    @classmethod
    def get(cls, name: str) -> Type["CoreService"]:
        """
        Retrieve a service from the manager.

        :param name: name of the service to retrieve
        :return: service if it exists, None otherwise
        """
        service = cls.services.get(name)
        if service is None:
            raise CoreServiceError(f"service({name}) does not exist")
        return service

    @classmethod
    def add_services(cls, path: Path) -> List[str]:
        """
        Method for retrieving all CoreServices from a given path.

        :param path: path to retrieve services from
        :return: list of core services that failed to load
        """
        service_errors = []
        services = utils.load_classes(path, CoreService)
        for service in services:
            if not service.name:
                continue
            try:
                cls.add(service)
            except (CoreError, ValueError) as e:
                service_errors.append(service.name)
                logger.debug("not loading service(%s): %s", service.name, e)
        return service_errors

    @classmethod
    def load_locals(cls) -> List[str]:
        errors = []
        for module_info in pkgutil.walk_packages(
            core_services.__path__, f"{core_services.__name__}."
        ):
            services = utils.load_module(module_info.name, CoreService)
            for service in services:
                try:
                    cls.add(service)
                except CoreError as e:
                    errors.append(service.name)
                    logger.debug("not loading service(%s): %s", service.name, e)
        return errors


class CoreServices:
    """
    Class for interacting with a list of available startup services for
    nodes. Mostly used to convert a CoreService into a Config API
    message. This class lives in the Session object and remembers
    the default services configured for each node type, and any
    custom service configuration. A CoreService is not a Configurable.
    """

    name: str = "services"
    config_type: RegisterTlvs = RegisterTlvs.UTILITY

    def __init__(self, session: "Session") -> None:
        """
        Creates a CoreServices instance.

        :param session: session this manager is tied to
        """
        self.session: "Session" = session
        # dict of default services tuples, key is node type
        self.default_services: Dict[str, List[str]] = {
            "mdr": ["zebra", "OSPFv3MDR", "IPForward"],
            "PC": ["DefaultRoute"],
            "prouter": [],
            "router": ["zebra", "OSPFv2", "OSPFv3", "IPForward"],
            "host": ["DefaultRoute", "SSH"],
        }
        # dict of node ids to dict of custom services by name
        self.custom_services: Dict[int, Dict[str, "CoreService"]] = {}

    def reset(self) -> None:
        """
        Called when config message with reset flag is received
        """
        self.custom_services.clear()

    def get_default_services(self, node_type: str) -> List[Type["CoreService"]]:
        """
        Get the list of default services that should be enabled for a
        node for the given node type.

        :param node_type: node type to get default services for
        :return: default services
        """
        logger.debug("getting default services for type: %s", node_type)
        results = []
        defaults = self.default_services.get(node_type, [])
        for name in defaults:
            logger.debug("checking for service with service manager: %s", name)
            service = ServiceManager.get(name)
            if not service:
                logger.warning("default service %s is unknown", name)
            else:
                results.append(service)
        return results

    def get_service(
        self, node_id: int, service_name: str, default_service: bool = False
    ) -> "CoreService":
        """
        Get any custom service configured for the given node that matches the specified
        service name. If no custom service is found, return the specified service.

        :param node_id: object id to get service from
        :param service_name: name of service to retrieve
        :param default_service: True to return default service when custom does
            not exist, False returns None
        :return: custom service from the node
        """
        node_services = self.custom_services.setdefault(node_id, {})
        default = None
        if default_service:
            default = ServiceManager.get(service_name)
        return node_services.get(service_name, default)

    def set_service(self, node_id: int, service_name: str) -> None:
        """
        Store service customizations in an instantiated service object
        using a list of values that came from a config message.

        :param node_id: object id to set custom service for
        :param service_name: name of service to set
        :return: nothing
        """
        logger.debug("setting custom service(%s) for node: %s", service_name, node_id)
        service = self.get_service(node_id, service_name)
        if not service:
            service_class = ServiceManager.get(service_name)
            service = service_class()

            # add the custom service to dict
            node_services = self.custom_services.setdefault(node_id, {})
            node_services[service.name] = service

    def add_services(
        self, node: CoreNode, node_type: str, services: List[str] = None
    ) -> None:
        """
        Add services to a node.

        :param node: node to add services to
        :param node_type: node type to add services to
        :param services: names of services to add to node
        :return: nothing
        """
        if not services:
            logger.info(
                "using default services for node(%s) type(%s)", node.name, node_type
            )
            services = self.default_services.get(node_type, [])
        logger.info("setting services for node(%s): %s", node.name, services)
        for service_name in services:
            service = self.get_service(node.id, service_name, default_service=True)
            if not service:
                logger.warning(
                    "unknown service(%s) for node(%s)", service_name, node.name
                )
                continue
            node.services.append(service)

    def all_configs(self) -> List[Tuple[int, "CoreService"]]:
        """
        Return (node_id, service) tuples for all stored configs. Used when reconnecting
        to a session or opening XML.

        :return: list of tuples of node ids and services
        """
        configs = []
        for node_id in self.custom_services:
            custom_services = self.custom_services[node_id]
            for name in custom_services:
                service = custom_services[name]
                configs.append((node_id, service))
        return configs

    def all_files(self, service: "CoreService") -> List[Tuple[str, str]]:
        """
        Return all customized files stored with a service.
        Used when reconnecting to a session or opening XML.

        :param service: service to get files for
        :return: list of all custom service files
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

    def boot_services(self, node: CoreNode) -> None:
        """
        Start all services on a node.

        :param node: node to start services on
        :return: nothing
        """
        boot_paths = ServiceDependencies(node.services).boot_order()
        funcs = []
        for boot_path in boot_paths:
            args = (node, boot_path)
            funcs.append((self._boot_service_path, args, {}))
        result, exceptions = utils.threadpool(funcs)
        if exceptions:
            raise CoreServiceBootError(*exceptions)

    def _boot_service_path(self, node: CoreNode, boot_path: List["CoreServiceType"]):
        logger.info(
            "booting node(%s) services: %s",
            node.name,
            " -> ".join([x.name for x in boot_path]),
        )
        for service in boot_path:
            service = self.get_service(node.id, service.name, default_service=True)
            try:
                self.boot_service(node, service)
            except Exception as e:
                logger.exception("exception booting service: %s", service.name)
                raise CoreServiceBootError(e)

    def boot_service(self, node: CoreNode, service: "CoreServiceType") -> None:
        """
        Start a service on a node. Create private dirs, generate config
        files, and execute startup commands.

        :param node: node to boot services on
        :param service: service to start
        :return: nothing
        """
        logger.info(
            "starting node(%s) service(%s) validation(%s)",
            node.name,
            service.name,
            service.validation_mode.name,
        )

        # create service directories
        for directory in service.dirs:
            dir_path = Path(directory)
            try:
                node.create_dir(dir_path)
            except (CoreCommandError, CoreError) as e:
                logger.warning(
                    "error mounting private dir '%s' for service '%s': %s",
                    directory,
                    service.name,
                    e,
                )

        # create service files
        self.create_service_files(node, service)

        # run startup
        wait = service.validation_mode == ServiceMode.BLOCKING
        status = self.startup_service(node, service, wait)
        if status:
            raise CoreServiceBootError(
                "node(%s) service(%s) error during startup" % (node.name, service.name)
            )

        # blocking mode is finished
        if wait:
            return

        # timer mode, sleep and return
        if service.validation_mode == ServiceMode.TIMER:
            time.sleep(service.validation_timer)
        # non-blocking, attempt to validate periodically, up to validation_timer time
        elif service.validation_mode == ServiceMode.NON_BLOCKING:
            start = time.monotonic()
            while True:
                status = self.validate_service(node, service)
                if not status:
                    break

                if time.monotonic() - start > service.validation_timer:
                    break

                time.sleep(service.validation_period)

            if status:
                raise CoreServiceBootError(
                    "node(%s) service(%s) failed validation" % (node.name, service.name)
                )

    def copy_service_file(self, node: CoreNode, file_path: Path, cfg: str) -> bool:
        """
        Given a configured service filename and config, determine if the
        config references an existing file that should be copied.
        Returns True for local files, False for generated.

        :param node: node to copy service for
        :param file_path: file name for a configured service
        :param cfg: configuration string
        :return: True if successful, False otherwise
        """
        if cfg[:7] == "file://":
            src = cfg[7:]
            src = src.split("\n")[0]
            src = utils.expand_corepath(src, node.session, node)
            # TODO: glob here
            node.copy_file(src, file_path, mode=0o644)
            return True
        return False

    def validate_service(self, node: CoreNode, service: "CoreServiceType") -> int:
        """
        Run the validation command(s) for a service.

        :param node: node to validate service for
        :param service: service to validate
        :return: service validation status
        """
        logger.debug("validating node(%s) service(%s)", node.name, service.name)
        cmds = service.validate
        if not service.custom:
            cmds = service.get_validate(node)

        status = 0
        for cmd in cmds:
            logger.debug("validating service(%s) using: %s", service.name, cmd)
            try:
                node.cmd(cmd)
            except CoreCommandError as e:
                logger.debug(
                    "node(%s) service(%s) validate failed", node.name, service.name
                )
                logger.debug("cmd(%s): %s", e.cmd, e.output)
                status = -1
                break

        return status

    def stop_services(self, node: CoreNode) -> None:
        """
        Stop all services on a node.

        :param node: node to stop services on
        :return: nothing
        """
        for service in node.services:
            self.stop_service(node, service)

    def stop_service(self, node: CoreNode, service: "CoreServiceType") -> int:
        """
        Stop a service on a node.

        :param node: node to stop a service on
        :param service: service to stop
        :return: status for stopping the services
        """
        status = 0
        for args in service.shutdown:
            try:
                node.cmd(args)
            except CoreCommandError as e:
                self.session.exception(
                    ExceptionLevels.ERROR,
                    "services",
                    f"error stopping service {service.name}: {e.stderr}",
                    node.id,
                )
                logger.exception("error running stop command %s", args)
                status = -1
        return status

    def get_service_file(
        self, node: CoreNode, service_name: str, filename: str
    ) -> FileData:
        """
        Send a File Message when the GUI has requested a service file.
        The file data is either auto-generated or comes from an existing config.

        :param node: node to get service file from
        :param service_name: service to get file from
        :param filename: file name to retrieve
        :return: file data
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
            raise ValueError(
                "unknown service(%s) config file: %s", service_name, filename
            )

        # get the file data
        data = service.config_data.get(filename)
        if data is None:
            data = "%s" % service.generate_config(node, filename)
        else:
            data = "%s" % data

        filetypestr = "service:%s" % service.name
        return FileData(
            message_type=MessageFlags.ADD,
            node=node.id,
            name=filename,
            type=filetypestr,
            data=data,
        )

    def set_service_file(
        self, node_id: int, service_name: str, file_name: str, data: str
    ) -> None:
        """
        Receive a File Message from the GUI and store the customized file
        in the service config. The filename must match one from the list of
        config files in the service.

        :param node_id: node id to set service file
        :param service_name: service name to set file for
        :param file_name: file name to set
        :param data: data for file to set
        :return: nothing
        """
        # attempt to set custom service, if needed
        self.set_service(node_id, service_name)

        # retrieve custom service
        service = self.get_service(node_id, service_name)
        if service is None:
            logger.warning("received file name for unknown service: %s", service_name)
            return

        # validate file being set is valid
        config_files = service.configs
        if file_name not in config_files:
            logger.warning(
                "received unknown file(%s) for service(%s)", file_name, service_name
            )
            return

        # set custom service file data
        service.config_data[file_name] = data

    def startup_service(
        self, node: CoreNode, service: "CoreServiceType", wait: bool = False
    ) -> int:
        """
        Startup a node service.

        :param node: node to reconfigure service for
        :param service: service to reconfigure
        :param wait: determines if we should wait to validate startup
        :return: status of startup
        """
        cmds = service.startup
        if not service.custom:
            cmds = service.get_startup(node)

        status = 0
        for cmd in cmds:
            try:
                node.cmd(cmd, wait)
            except CoreCommandError:
                logger.exception("error starting command")
                status = -1
        return status

    def create_service_files(self, node: CoreNode, service: "CoreServiceType") -> None:
        """
        Creates node service files.

        :param node: node to reconfigure service for
        :param service: service to reconfigure
        :return: nothing
        """
        # get values depending on if custom or not
        config_files = service.configs
        if not service.custom:
            config_files = service.get_configs(node)
        for file_name in config_files:
            file_path = Path(file_name)
            logger.debug(
                "generating service config custom(%s): %s", service.custom, file_name
            )
            if service.custom:
                cfg = service.config_data.get(file_name)
                if cfg is None:
                    cfg = service.generate_config(node, file_name)
                # cfg may have a file:/// url for copying from a file
                try:
                    if self.copy_service_file(node, file_path, cfg):
                        continue
                except IOError:
                    logger.exception("error copying service file: %s", file_name)
                    continue
            else:
                cfg = service.generate_config(node, file_name)
            node.create_file(file_path, cfg)

    def service_reconfigure(self, node: CoreNode, service: "CoreService") -> None:
        """
        Reconfigure a node service.

        :param node: node to reconfigure service for
        :param service: service to reconfigure
        :return: nothing
        """
        config_files = service.configs
        if not service.custom:
            config_files = service.get_configs(node)
        for file_name in config_files:
            file_path = Path(file_name)
            if file_name[:7] == "file:///":
                # TODO: implement this
                raise NotImplementedError
            cfg = service.config_data.get(file_name)
            if cfg is None:
                cfg = service.generate_config(node, file_name)
            node.create_file(file_path, cfg)


class CoreService:
    """
    Parent class used for defining services.
    """

    # service name should not include spaces
    name: Optional[str] = None

    # executables that must exist for service to run
    executables: Tuple[str, ...] = ()

    # sets service requirements that must be started prior to this service starting
    dependencies: Tuple[str, ...] = ()

    # group string allows grouping services together
    group: Optional[str] = None

    # private, per-node directories required by this service
    dirs: Tuple[str, ...] = ()

    # config files written by this service
    configs: Tuple[str, ...] = ()

    # config file data
    config_data: Dict[str, str] = {}

    # list of startup commands
    startup: Tuple[str, ...] = ()

    # list of shutdown commands
    shutdown: Tuple[str, ...] = ()

    # list of validate commands
    validate: Tuple[str, ...] = ()

    # validation mode, used to determine startup success
    validation_mode: ServiceMode = ServiceMode.NON_BLOCKING

    # time to wait in seconds for determining if service started successfully
    validation_timer: int = 5

    # validation period in seconds, how frequent validation is attempted
    validation_period: float = 0.5

    # metadata associated with this service
    meta: Optional[str] = None

    # custom configuration text
    custom: bool = False
    custom_needed: bool = False

    def __init__(self) -> None:
        """
        Services are not necessarily instantiated. Classmethods may be used
        against their config. Services are instantiated when a custom
        configuration is used to override their default parameters.
        """
        self.custom: bool = True
        self.config_data: Dict[str, str] = self.__class__.config_data.copy()

    @classmethod
    def on_load(cls) -> None:
        pass

    @classmethod
    def get_configs(cls, node: CoreNode) -> Iterable[str]:
        """
        Return the tuple of configuration file filenames. This default method
        returns the cls._configs tuple, but this method may be overriden to
        provide node-specific filenames that may be based on other services.

        :param node: node to generate config for
        :return: configuration files
        """
        return cls.configs

    @classmethod
    def generate_config(cls, node: CoreNode, filename: str) -> None:
        """
        Generate configuration file given a node object. The filename is
        provided to allow for multiple config files.
        Return the configuration string to be written to a file or sent
        to the GUI for customization.

        :param node: node to generate config for
        :param filename: file name to generate config for
        :return: nothing
        """
        raise NotImplementedError

    @classmethod
    def get_startup(cls, node: CoreNode) -> Iterable[str]:
        """
        Return the tuple of startup commands. This default method
        returns the cls.startup tuple, but this method may be
        overridden to provide node-specific commands that may be
        based on other services.

        :param node: node to get startup for
        :return: startup commands
        """
        return cls.startup

    @classmethod
    def get_validate(cls, node: CoreNode) -> Iterable[str]:
        """
        Return the tuple of validate commands. This default method
        returns the cls.validate tuple, but this method may be
        overridden to provide node-specific commands that may be
        based on other services.

        :param node: node to validate
        :return: validation commands
        """
        return cls.validate
