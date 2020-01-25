import logging
import pathlib
from typing import List, Type

from core import utils
from core.configservice.base import ConfigService
from core.errors import CoreError


class ConfigServiceManager:
    def __init__(self):
        self.services = {}

    def get_service(self, name: str) -> Type[ConfigService]:
        service_class = self.services.get(name)
        if service_class is None:
            raise CoreError(f"service does not exit {name}")
        return service_class

    def add(self, service: ConfigService) -> None:
        name = service.name
        logging.debug("loading service: class(%s) name(%s)", service.__class__, name)

        # avoid duplicate services
        if name in self.services:
            raise CoreError(f"duplicate service being added: {name}")

        # validate dependent executables are present
        for executable in service.executables:
            try:
                utils.which(executable, required=True)
            except ValueError:
                raise CoreError(
                    f"service({service.name}) missing executable {executable}"
                )

            # make service available
        self.services[name] = service

    def load(self, path: str) -> List[str]:
        path = pathlib.Path(path)
        subdirs = [x for x in path.iterdir() if x.is_dir()]
        subdirs.append(path)
        service_errors = []
        for subdir in subdirs:
            logging.debug("loading config services from: %s", subdir)
            services = utils.load_classes(str(subdir), ConfigService)
            for service in services:
                logging.debug("found service: %s", service)
                try:
                    self.add(service)
                except CoreError as e:
                    service_errors.append(service.name)
                    logging.debug("not loading service(%s): %s", service.name, e)
        return service_errors
