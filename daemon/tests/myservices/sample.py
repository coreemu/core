"""
Sample user-defined services for testing.
"""

from core.service import CoreService


class MyService(CoreService):
    _name = "MyService"
    _group = "Utility"
    _depends = ()
    _dirs = ()
    _configs = ('myservice.sh',)
    _startindex = 50
    _startup = ('sh myservice.sh',)
    _shutdown = ()


class MyService2(CoreService):
    _name = "MyService2"
    _group = "Utility"
    _depends = ()
    _dirs = ()
    _configs = ('myservice.sh',)
    _startindex = 50
    _startup = ('sh myservice.sh',)
    _shutdown = ()
