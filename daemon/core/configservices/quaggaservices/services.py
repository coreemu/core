import abc
from typing import Any, Dict

import netaddr

from core import constants
from core.configservice.base import ConfigService, ConfigServiceMode
from core.nodes.base import CoreNodeBase
from core.nodes.interface import CoreInterface

GROUP = "Quagga"


def has_mtu_mismatch(ifc: CoreInterface) -> bool:
    """
    Helper to detect MTU mismatch and add the appropriate OSPF
    mtu-ignore command. This is needed when e.g. a node is linked via a
    GreTap device.
    """
    if ifc.mtu != 1500:
        return True
    if not ifc.net:
        return False
    for i in ifc.net.netifs():
        if i.mtu != ifc.mtu:
            return True
    return False


def get_router_id(node: CoreNodeBase) -> str:
    """
    Helper to return the first IPv4 address of a node as its router ID.
    """
    for ifc in node.netifs():
        if getattr(ifc, "control", False):
            continue
        for a in ifc.addrlist:
            a = a.split("/")[0]
            if netaddr.valid_ipv4(a):
                return a
    return "0.0.0.0"


class Zebra(ConfigService):
    name = "zebra"
    group = GROUP
    directories = ["/usr/local/etc/quagga", "/var/run/quagga"]
    files = [
        "/usr/local/etc/quagga/Quagga.conf",
        "quaggaboot.sh",
        "/usr/local/etc/quagga/vtysh.conf",
    ]
    executables = ["zebra"]
    dependencies = []
    startup = ["sh quaggaboot.sh zebra"]
    validate = ["pidof zebra"]
    shutdown = ["killall zebra"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        quagga_bin_search = self.node.session.options.get_config(
            "quagga_bin_search", default="/usr/local/bin /usr/bin /usr/lib/quagga"
        ).strip('"')
        quagga_sbin_search = self.node.session.options.get_config(
            "quagga_sbin_search", default="/usr/local/sbin /usr/sbin /usr/lib/quagga"
        ).strip('"')
        quagga_state_dir = constants.QUAGGA_STATE_DIR
        quagga_conf = self.files[0]

        services = []
        want_ip4 = False
        want_ip6 = False
        for service in self.node.config_services.values():
            if self.name not in service.dependencies:
                continue
            if service.ipv4_routing:
                want_ip4 = True
            if service.ipv6_routing:
                want_ip6 = True
            services.append(service)

        interfaces = []
        for ifc in self.node.netifs():
            ip4s = []
            ip6s = []
            for x in ifc.addrlist:
                addr = x.split("/")[0]
                if netaddr.valid_ipv4(addr):
                    ip4s.append(x)
                else:
                    ip6s.append(x)
            is_control = getattr(ifc, "control", False)
            interfaces.append((ifc, ip4s, ip6s, is_control))

        return dict(
            quagga_bin_search=quagga_bin_search,
            quagga_sbin_search=quagga_sbin_search,
            quagga_state_dir=quagga_state_dir,
            quagga_conf=quagga_conf,
            interfaces=interfaces,
            want_ip4=want_ip4,
            want_ip6=want_ip6,
            services=services,
        )


class QuaggaService(abc.ABC):
    group = GROUP
    directories = []
    files = []
    executables = []
    dependencies = ["zebra"]
    startup = []
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}
    ipv4_routing = False
    ipv6_routing = False

    @abc.abstractmethod
    def quagga_interface_config(self, ifc: CoreInterface) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def quagga_config(self) -> str:
        raise NotImplementedError


class Ospfv2(QuaggaService, ConfigService):
    """
    The OSPFv2 service provides IPv4 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified Quagga.conf file.
    """

    name = "OSPFv2"
    validate = ["pidof ospfd"]
    shutdown = ["killall ospfd"]
    ipv4_routing = True

    def quagga_interface_config(self, ifc: CoreInterface) -> str:
        if has_mtu_mismatch(ifc):
            return "ip ospf mtu-ignore"
        else:
            return ""

    def quagga_config(self) -> str:
        router_id = get_router_id(self.node)
        addresses = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            for a in ifc.addrlist:
                addr = a.split("/")[0]
                if netaddr.valid_ipv4(addr):
                    addresses.append(a)
        data = dict(router_id=router_id, addresses=addresses)
        text = """
        router ospf
          router-id ${router_id}
          % for addr in addresses:
          network ${addr} area 0
          % endfor
        !
        """
        return self.render_text(text, data)
