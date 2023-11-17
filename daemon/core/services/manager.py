import logging
import pathlib
import pkgutil
from pathlib import Path

from core import utils
from core.errors import CoreError
from core.services import defaults
from core.services.base import CoreService

logger = logging.getLogger(__name__)


class ServiceManager:
    """
    Manager for services.
    """

    def __init__(self):
        """
        Create a ServiceManager instance.
        """
        self.services: dict[str, type[CoreService]] = {}
        self.defaults: dict[str, list[str]] = {
            "mdr": ["zebra", "OSPFv3MDR", "IPForward"],
            "PC": ["DefaultRoute"],
            "prouter": [],
            "router": ["zebra", "OSPFv2", "OSPFv3", "IPForward"],
            "host": ["DefaultRoute", "SSH"],
        }

    def get_service(self, name: str) -> type[CoreService]:
        """
        Retrieve a service by name.

        :param name: name of service
        :return: service class
        :raises CoreError: when service is not found
        """
        service_class = self.services.get(name)
        if service_class is None:
            raise CoreError(f"service does not exist {name}")
        return service_class

    def add(self, service: type[CoreService]) -> None:
        """
        Add service to manager, checking service requirements have been met.

        :param service: service to add to manager
        :return: nothing
        :raises CoreError: when service is a duplicate or has unmet executables
        """
        logger.debug(
            "loading service: class(%s) name(%s)",
            service.__class__.__name__,
            service.name,
        )
        # avoid undefined services
        if service.name is None or service.group is None:
            raise CoreError(
                f"service name({service.name}) and group({service.group}) must be defined"
            )

        # avoid duplicate services
        if service.name in self.services:
            raise CoreError(f"duplicate service being added: {service.name}")

        # validate dependent executables are present
        for executable in service.executables:
            try:
                utils.which(executable, required=True)
            except CoreError as e:
                raise CoreError(f"service({service.name}): {e}")

        # make service available
        self.services[service.name] = service

    def load_locals(self) -> list[str]:
        """
        Search and add service from local core module.

        :return: list of errors when loading services
        """
        errors = []
        for module_info in pkgutil.walk_packages(
            defaults.__path__, f"{defaults.__name__}."
        ):
            services = utils.load_module(module_info.name, CoreService)
            for service in services:
                try:
                    self.add(service)
                except CoreError as e:
                    errors.append(service.name)
                    logger.debug("not loading service(%s): %s", service.name, e)
        return errors

    def load(self, path: Path) -> list[str]:
        """
        Search path provided for services and add them for being managed.

        :param path: path to search services
        :return: list errors when loading services
        """
        path = pathlib.Path(path)
        subdirs = [x for x in path.iterdir() if x.is_dir()]
        subdirs.append(path)
        service_errors = []
        for subdir in subdirs:
            logger.debug("loading services from: %s", subdir)
            services = utils.load_classes(subdir, CoreService)
            for service in services:
                try:
                    self.add(service)
                except CoreError as e:
                    service_errors.append(service.name)
                    logger.debug("not loading service(%s): %s", service.name, e)
        return service_errors
