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
    def test_service_file(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get("MyService")
        node = session.add_node()
        file_name = my_service.configs[0]
        file_path = node.hostfilename(file_name)

        # when
        session.services.create_service_files(node, my_service)

        # then
        assert os.path.exists(file_path)

    def test_service_startup(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get("MyService")
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.startup_service(node, my_service, wait=True)

        # then
        assert not status

    def test_service_startup_error(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get("MyService2")
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.startup_service(node, my_service, wait=True)

        # then
        assert status

    def test_service_stop(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get("MyService")
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.stop_service(node, my_service)

        # then
        assert not status

    def test_service_stop_error(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get("MyService2")
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.stop_service(node, my_service)

        # then
        assert status

    def test_service_set_file(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get("MyService")
        node = session.add_node()
        file_name = my_service.configs[0]
        file_path = node.hostfilename(file_name)
        file_data = "# custom file"
        session.services.set_service_file(node.objid, my_service.name, file_name, file_data)
        custom_service = session.services.get_service(node.objid, my_service.name)

        # when
        session.services.create_service_files(node, custom_service)

        # then
        assert os.path.exists(file_path)
        with open(file_path, "r") as custom_file:
            assert custom_file.read() == file_data

    def test_service_import(self):
        """
        Test importing a custom service.
        """
        ServiceManager.add_services(_SERVICES_PATH)
        assert ServiceManager.get("MyService")
        assert ServiceManager.get("MyService2")

    def test_service_setget(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        service_name = "MyService"
        my_service = ServiceManager.get(service_name)
        node = session.add_node()

        # when
        no_service = session.services.get_service(node.objid, service_name)
        default_service = session.services.get_service(node.objid, service_name, default_service=True)
        session.services.set_service(node.objid, service_name)
        custom_service = session.services.get_service(node.objid, service_name, default_service=True)

        # then
        assert no_service is None
        assert default_service == my_service
        assert custom_service and custom_service != my_service

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
        startups = session.services.create_boot_paths(services)

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
            session.services.create_boot_paths(services)

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
            session.services.create_boot_paths(services)
