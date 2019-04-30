import os

import pytest

from core.services.coreservices import CoreService
from core.services.coreservices import ServiceDependencies
from core.services.coreservices import ServiceManager

_PATH = os.path.abspath(os.path.dirname(__file__))
_SERVICES_PATH = os.path.join(_PATH, "myservices")

SERVICE_ONE = "MyService"
SERVICE_TWO = "MyService2"


class ServiceA(CoreService):
    name = "A"
    dependencies = ("B",)


class ServiceB(CoreService):
    name = "B"
    dependencies = ()


class ServiceC(CoreService):
    name = "C"
    dependencies = ("B", "D")


class ServiceD(CoreService):
    name = "D"
    dependencies = ()


class ServiceBadDependency(CoreService):
    name = "E"
    dependencies = ("Z",)


class ServiceF(CoreService):
    name = "F"
    dependencies = ()


class ServiceCycleDependency(CoreService):
    name = "G"


class TestServices:
    def test_service_all_files(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        file_name = "myservice.sh"
        node = session.add_node()

        # when
        session.services.set_service_file(node.id, SERVICE_ONE, file_name, "# test")

        # then
        service = session.services.get_service(node.id, SERVICE_ONE)
        all_files = session.services.all_files(service)
        assert service
        assert all_files and len(all_files) == 1

    def test_service_all_configs(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        node = session.add_node()

        # when
        session.services.set_service(node.id, SERVICE_ONE)
        session.services.set_service(node.id, SERVICE_TWO)

        # then
        all_configs = session.services.all_configs()
        assert all_configs
        assert len(all_configs) == 2

    def test_service_add_services(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        node = session.add_node()
        total_service = len(node.services)

        # when
        session.services.add_services(node, node.type, [SERVICE_ONE, SERVICE_TWO])

        # then
        assert node.services
        assert len(node.services) == total_service + 2

    def test_service_file(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_ONE)
        node = session.add_node()
        file_name = my_service.configs[0]
        file_path = node.hostfilename(file_name)

        # when
        session.services.create_service_files(node, my_service)

        # then
        assert os.path.exists(file_path)

    def test_service_validate(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_ONE)
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.validate_service(node, my_service)

        # then
        assert not status

    def test_service_validate_error(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_TWO)
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.validate_service(node, my_service)

        # then
        assert status

    def test_service_startup(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_ONE)
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.startup_service(node, my_service, wait=True)

        # then
        assert not status

    def test_service_startup_error(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_TWO)
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.startup_service(node, my_service, wait=True)

        # then
        assert status

    def test_service_stop(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_ONE)
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.stop_service(node, my_service)

        # then
        assert not status

    def test_service_stop_error(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_TWO)
        node = session.add_node()
        session.services.create_service_files(node, my_service)

        # when
        status = session.services.stop_service(node, my_service)

        # then
        assert status

    def test_service_custom_startup(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_ONE)
        node = session.add_node()

        # when
        session.services.set_service(node.id, my_service.name)
        custom_my_service = session.services.get_service(node.id, my_service.name)
        custom_my_service.startup = ("sh custom.sh",)

        # then
        assert my_service.startup != custom_my_service.startup

    def test_service_set_file(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_ONE)
        node_one = session.add_node()
        node_two = session.add_node()
        file_name = my_service.configs[0]
        file_data_one = "# custom file one"
        file_data_two = "# custom file two"
        session.services.set_service_file(node_one.id, my_service.name, file_name, file_data_one)
        session.services.set_service_file(node_two.id, my_service.name, file_name, file_data_two)

        # when
        custom_service_one = session.services.get_service(node_one.id, my_service.name)
        session.services.create_service_files(node_one, custom_service_one)
        custom_service_two = session.services.get_service(node_two.id, my_service.name)
        session.services.create_service_files(node_two, custom_service_two)

        # then
        file_path_one = node_one.hostfilename(file_name)
        assert os.path.exists(file_path_one)
        with open(file_path_one, "r") as custom_file:
            assert custom_file.read() == file_data_one

        file_path_two = node_two.hostfilename(file_name)
        assert os.path.exists(file_path_two)
        with open(file_path_two, "r") as custom_file:
            assert custom_file.read() == file_data_two

    def test_service_import(self):
        """
        Test importing a custom service.
        """
        ServiceManager.add_services(_SERVICES_PATH)
        assert ServiceManager.get(SERVICE_ONE)
        assert ServiceManager.get(SERVICE_TWO)

    def test_service_setget(self, session):
        # given
        ServiceManager.add_services(_SERVICES_PATH)
        my_service = ServiceManager.get(SERVICE_ONE)
        node = session.add_node()

        # when
        no_service = session.services.get_service(node.id, SERVICE_ONE)
        default_service = session.services.get_service(node.id, SERVICE_ONE, default_service=True)
        session.services.set_service(node.id, SERVICE_ONE)
        custom_service = session.services.get_service(node.id, SERVICE_ONE, default_service=True)

        # then
        assert no_service is None
        assert default_service == my_service
        assert custom_service and custom_service != my_service

    def test_services_dependencies(self):
        # given
        services = [
            ServiceA,
            ServiceB,
            ServiceC,
            ServiceD,
            ServiceF
        ]

        # when
        boot_paths = ServiceDependencies(services).boot_paths()

        # then
        assert len(boot_paths) == 2

    def test_services_dependencies_not_present(self):
        # given
        services = [
            ServiceA,
            ServiceB,
            ServiceC,
            ServiceD,
            ServiceF,
            ServiceBadDependency
        ]

        # when, then
        with pytest.raises(ValueError):
            ServiceDependencies(services).boot_paths()

    def test_services_dependencies_cycle(self):
        # given
        service_d = ServiceD()
        service_d.dependencies = ("C",)
        services = [
            ServiceA,
            ServiceB,
            ServiceC,
            service_d,
            ServiceF
        ]

        # when, then
        with pytest.raises(ValueError):
            ServiceDependencies(services).boot_paths()
