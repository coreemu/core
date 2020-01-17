import logging
import os

import netaddr

from core import utils
from core.config import Configuration
from core.configservice.base import (
    ConfigService,
    ConfigServiceManager,
    ConfigServiceMode,
)
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import ConfigDataTypes, EventTypes, NodeTypes

GROUP_NAME = "Utility"


class DefaultRoute(ConfigService):
    name = "DefaultRoute"
    group = GROUP_NAME
    directories = []
    executables = []
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
        self.render("defaultroute.sh", data)


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
        self.render("ipforward.sh", data)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # setup basic network
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
    options = NodeOptions(model="nothing")
    # options.services = []
    coreemu = CoreEmu()
    session = coreemu.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE)
    switch = session.add_node(_type=NodeTypes.SWITCH)

    # node one
    node_one = session.add_node(options=options)
    interface = prefixes.create_interface(node_one)
    session.add_link(node_one.id, switch.id, interface_one=interface)

    # node two
    node_two = session.add_node(options=options)
    interface = prefixes.create_interface(node_two)
    session.add_link(node_two.id, switch.id, interface_one=interface)

    session.instantiate()

    # manager load config services
    manager = ConfigServiceManager()
    path = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
    manager.load(path)

    clazz = manager.services["DefaultRoute"]
    dr_service = clazz(node_one)
    dr_service.set_config({"value1": "custom"})
    dr_service.start()

    clazz = manager.services["IPForward"]
    dr_service = clazz(node_one)
    dr_service.start()

    input("press enter to exit")
    session.shutdown()
