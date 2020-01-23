import logging
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from core.configservice.base import ConfigService


class ConfigServiceDependencies:
    """
    Can generate boot paths for services, based on their dependencies. Will validate
    that all services will be booted and that all dependencies exist within the services provided.
    """

    def __init__(self, services: Dict[str, "ConfigService"]) -> None:
        # helpers to check validity
        self.dependents = {}
        self.booted = set()
        self.node_services = {}
        for service in services.values():
            self.node_services[service.name] = service
            for dependency in service.dependencies:
                dependents = self.dependents.setdefault(dependency, set())
                dependents.add(service.name)

        # used to find paths
        self.path = []
        self.visited = set()
        self.visiting = set()

    def boot_paths(self) -> List[List["ConfigService"]]:
        paths = []
        for name in self.node_services:
            service = self.node_services[name]
            if service.name in self.booted:
                logging.debug(
                    "skipping service that will already be booted: %s", service.name
                )
                continue

            path = self._start(service)
            if path:
                paths.append(path)

        if self.booted != set(self.node_services):
            raise ValueError(
                "failure to boot all services: %s != %s"
                % (self.booted, self.node_services.keys())
            )

        return paths

    def _reset(self) -> None:
        self.path = []
        self.visited.clear()
        self.visiting.clear()

    def _start(self, service: "ConfigService") -> List["ConfigService"]:
        logging.debug("starting service dependency check: %s", service.name)
        self._reset()
        return self._visit(service)

    def _visit(self, current_service: "ConfigService") -> List["ConfigService"]:
        logging.debug("visiting service(%s): %s", current_service.name, self.path)
        self.visited.add(current_service.name)
        self.visiting.add(current_service.name)

        # dive down
        for service_name in current_service.dependencies:
            if service_name not in self.node_services:
                raise ValueError(
                    "required dependency was not included in node services: %s"
                    % service_name
                )

            if service_name in self.visiting:
                raise ValueError(
                    "cyclic dependency at service(%s): %s"
                    % (current_service.name, service_name)
                )

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
