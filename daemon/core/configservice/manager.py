import logging
import pathlib
from pathlib import Path
from typing import Dict, List, Type

from core import utils
from core.configservice.base import ConfigService
from core.errors import CoreError


class ConfigServiceManager:
    """
    Manager for configurable services.
    """

    def __init__(self):
        """
        Create a ConfigServiceManager instance.
        """
        self.services: Dict[str, Type[ConfigService]] = {}

    def get_service(self, name: str) -> Type[ConfigService]:
        """
        Retrieve a service by name.

        :param name: name of service
        :return: service class
        :raises CoreError: when service is not found
        """
        service_class = self.services.get(name)
        if service_class is None:
            raise CoreError(f"service does not exit {name}")
        return service_class

    def add(self, service: Type[ConfigService]) -> None:
        """
        Add service to manager, checking service requirements have been met.

        :param service: service to add to manager
        :return: nothing
        :raises CoreError: when service is a duplicate or has unmet executables
        """
        name = service.name
        logging.debug(
            "loading service: class(%s) name(%s)", service.__class__.__name__, name
        )

        # avoid duplicate services
        if name in self.services:
            raise CoreError(f"duplicate service being added: {name}")

        # validate dependent executables are present
        for executable in service.executables:
            try:
                utils.which(executable, required=True)
            except CoreError as e:
                raise CoreError(f"config service({service.name}): {e}")

        # make service available
        self.services[name] = service

    def load(self, path: Path) -> List[str]:
        """
        Search path provided for configurable services and add them for being managed.

        :param path: path to search configurable services
        :return: list errors when loading and adding services
        """
        path = pathlib.Path(path)
        subdirs = [x for x in path.iterdir() if x.is_dir()]
        subdirs.append(path)
        service_errors = []
        for subdir in subdirs:
            logging.debug("loading config services from: %s", subdir)
            services = utils.load_classes(subdir, ConfigService)
            for service in services:
                try:
                    self.add(service)
                except CoreError as e:
                    service_errors.append(service.name)
                    logging.debug("not loading service(%s): %s", service.name, e)
        return service_errors
