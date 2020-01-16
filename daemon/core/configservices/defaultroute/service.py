import logging

import netaddr

from core.configservice.base import ConfigService, ConfigServiceMode
from core.emulator.session import Session
from core.nodes.base import CoreNode
from core.nodes.interface import Veth


class DefaultRoute(ConfigService):
    name = "DefaultRoute"
    group = "Utility"
    executables = []
    dependencies = []
    startup = []
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING

    def create_files(self):
        self.create_default_route()

    def create_default_route(self):
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    session = Session(1, mkdir=False)
    node = CoreNode(session, _id=1, start=False)
    netif = Veth(session, node, "eth0", "eth0", start=False)
    netif.addaddr("10.0.0.1/24")
    node.addnetif(netif, 0)
    service = DefaultRoute(node)
    service.create_files()
    # data = service.render(node, "defaultroute.sh", dict(addresses=[]))
    # print(data)
