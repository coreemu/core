import os

import pytest

from core.service import CoreService
from core.service import ServiceManager

_PATH = os.path.abspath(os.path.dirname(__file__))
_SERVICES_PATH = os.path.join(_PATH, "myservices")


class ServiceA(CoreService):
    name = "A"
    dependencies = ("B",)


class ServiceB(CoreService):
    name = "B"
    dependencies = ("C",)


class ServiceC(CoreService):
    name = "C"
    dependencies = ()


class ServiceD(CoreService):
    name = "D"
    dependencies = ("A",)


class ServiceE(CoreService):
    name = "E"
    dependencies = ("Z",)


class ServiceF(CoreService):
    name = "F"
    dependencies = ()


class TestServices:
    def test_service_import(self):
        """
        Test importing a custom service.
        """
        ServiceManager.add_services(_SERVICES_PATH)
        assert ServiceManager.get("MyService")
        assert ServiceManager.get("MyService2")

    def test_service_defaults(self):
        pass

    def test_services_dependencies(self, session):
        # given
        services = [
            ServiceA,
            ServiceB,
            ServiceC,
            ServiceD,
            ServiceF,
        ]

        # when
        startups = session.services.node_boot_paths(services)

        # then
        assert len(startups) == 2

    def test_services_dependencies_not_present(self, session):
        # given
        services = [
            ServiceA,
            ServiceB,
            ServiceC,
            ServiceE
        ]

        # when
        with pytest.raises(ValueError):
            session.services.node_boot_paths(services)

    def test_services_dependencies_cycle(self, session):
        # given
        service_c = ServiceC()
        service_c.dependencies = ("D",)
        services = [
            ServiceA,
            ServiceB,
            service_c,
            ServiceD,
            ServiceF
        ]

        # when
        with pytest.raises(ValueError):
            session.services.node_boot_paths(services)
