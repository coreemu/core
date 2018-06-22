"""
Sample user-defined services for testing.
"""

from core.service import CoreService


class MyService(CoreService):
    name = "MyService"
    group = "Utility"
    configs = ("myservice.sh",)
    startup = ("sh myservice.sh",)


class MyService2(CoreService):
    name = "MyService2"
    group = "Utility"
    configs = ("myservice.sh",)
    startup = ("sh myservice.sh",)
