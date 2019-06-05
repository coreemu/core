"""
Sample user-defined services for testing.
"""

from core.services.coreservices import CoreService


class MyService(CoreService):
    name = "MyService"
    group = "Utility"
    configs = ("myservice.sh",)
    startup = ("sh myservice.sh",)
    shutdown = ("sh myservice.sh",)

    @classmethod
    def generate_config(cls, node, filename):
        return "# test file"


class MyService2(MyService):
    name = "MyService2"
    group = "Utility"
    configs = ("myservice2.sh",)
    startup = ("sh myservice2.sh",)
    shutdown = startup
    validate = startup

    @classmethod
    def generate_config(cls, node, filename):
        return "exit 1"
