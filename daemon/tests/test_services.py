import os

from core.service import ServiceManager

_PATH = os.path.abspath(os.path.dirname(__file__))
_SERVICES_PATH = os.path.join(_PATH, "myservices")


class TestServices:
    def test_import_service(self):
        """
        Test importing a custom service.

        :param conftest.Core core: core fixture to test with
        """
        ServiceManager.add_services(_SERVICES_PATH)
        assert ServiceManager.get("MyService")
        assert ServiceManager.get("MyService2")
