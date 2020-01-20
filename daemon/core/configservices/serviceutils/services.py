from typing import Any, Dict

import netaddr

from core import utils
from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emulator.enumerations import ConfigDataTypes

GROUP_NAME = "Utility"


class DefaultRoute(ConfigService):
    name = "DefaultRoute"
    group = GROUP_NAME
    directories = []
    files = ["defaultroute.sh"]
    executables = ["ip"]
    dependencies = []
    startup = ["sh defaultroute.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = [
        Configuration(_id="value1", _type=ConfigDataTypes.STRING, label="Value 1"),
        Configuration(_id="value2", _type=ConfigDataTypes.STRING, label="Value 2"),
        Configuration(_id="value3", _type=ConfigDataTypes.STRING, label="Value 3"),
    ]

    def data(self) -> Dict[str, Any]:
        addresses = []
        for netif in self.node.netifs():
            if getattr(netif, "control", False):
                continue
            for addr in netif.addrlist:
                net = netaddr.IPNetwork(addr)
                if net[1] != net[-2]:
                    addresses.append(net[1])
        return dict(addresses=addresses)


class IpForwardService(ConfigService):
    name = "IPForward"
    group = GROUP_NAME
    directories = []
    files = ["ipforward.sh"]
    executables = ["sysctl"]
    dependencies = []
    startup = ["sh ipforward.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []

    def data(self) -> Dict[str, Any]:
        devnames = []
        for ifc in self.node.netifs():
            devname = utils.sysctl_devname(ifc.name)
            devnames.append(devname)
        return dict(devnames=devnames)
