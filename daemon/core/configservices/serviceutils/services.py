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

    def create_files(self):
        addresses = []
        for netif in self.node.netifs():
            if getattr(netif, "control", False):
                continue
            for addr in netif.addrlist:
                net = netaddr.IPNetwork(addr)
                if net[1] != net[-2]:
                    addresses.append(net[1])
        data = dict(addresses=addresses)
        self.render_template("defaultroute.sh", data)


class IpForwardService(ConfigService):
    name = "IPForward"
    group = GROUP_NAME
    directories = []
    executables = ["sysctl"]
    dependencies = []
    startup = ["sh ipforward.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []

    def create_files(self) -> None:
        devnames = []
        for ifc in self.node.netifs():
            devname = utils.sysctl_devname(ifc.name)
            devnames.append(devname)
        data = dict(devnames=devnames)
        self.render_template("ipforward.sh", data)
