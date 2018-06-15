"""
Sample user-defined services for testing.
"""

from core.service import CoreService


class MyService(CoreService):
    name = "MyService"
    group = "Utility"
    depends = ()
    dirs = ()
    configs = ('myservice.sh',)
    startindex = 50
    startup = ('sh myservice.sh',)
    shutdown = ()


class MyService2(CoreService):
    name = "MyService2"
    group = "Utility"
    depends = ()
    dirs = ()
    configs = ('myservice.sh',)
    startindex = 50
    startup = ('sh myservice.sh',)
    shutdown = ()
