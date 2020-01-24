import abc
import logging
from typing import Any, Dict

import netaddr

from core import constants
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emane.nodes import EmaneNet
from core.nodes.base import CoreNodeBase
from core.nodes.interface import CoreInterface
from core.nodes.network import WlanNode

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


def get_min_mtu(ifc):
    """
    Helper to discover the minimum MTU of interfaces linked with the
    given interface.
    """
    mtu = ifc.mtu
    if not ifc.net:
        return mtu
    for i in ifc.net.netifs():
        if i.mtu < mtu:
            mtu = i.mtu
    return mtu


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


class Ospfv3(QuaggaService, ConfigService):
    """
    The OSPFv3 service provides IPv6 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified Quagga.conf file.
    """

    name = "OSPFv3"
    shutdown = ("killall ospf6d",)
    validate = ("pidof ospf6d",)
    ipv4_routing = True
    ipv6_routing = True

    def quagga_interface_config(self, ifc: CoreInterface) -> str:
        mtu = get_min_mtu(ifc)
        if mtu < ifc.mtu:
            return f"ipv6 ospf6 ifmtu {mtu}"
        else:
            return ""

    def quagga_config(self) -> str:
        router_id = get_router_id(self.node)
        ifnames = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
        data = dict(router_id=router_id, ifnames=ifnames)
        text = """
        router ospf6
          instance-id 65
          router-id ${router_id}
          % for ifname in ifnames:
          interface ${ifname} area 0.0.0.0
          % endfor
        !
        """
        return self.render_text(text, data)


class Ospfv3mdr(Ospfv3):
    """
    The OSPFv3 MANET Designated Router (MDR) service provides IPv6
    routing for wireless networks. It does not build its own
    configuration file but has hooks for adding to the
    unified Quagga.conf file.
    """

    name = "OSPFv3MDR"

    def data(self) -> Dict[str, Any]:
        for ifc in self.node.netifs():
            is_wireless = isinstance(ifc.net, (WlanNode, EmaneNet))
            logging.info("MDR wireless: %s", is_wireless)
        return dict()

    def quagga_interface_config(self, ifc: CoreInterface) -> str:
        config = super().quagga_interface_config(ifc)
        if isinstance(ifc.net, (WlanNode, EmaneNet)):
            config = self.clean_text(
                f"""
                {config}
                ipv6 ospf6 hello-interval 2
                ipv6 ospf6 dead-interval 6
                ipv6 ospf6 retransmit-interval 5
                ipv6 ospf6 network manet-designated-router
                ipv6 ospf6 twohoprefresh 3
                ipv6 ospf6 adjacencyconnectivity uniconnected
                ipv6 ospf6 lsafullness mincostlsa
                """
            )
        return config


class Bgp(QuaggaService, ConfigService):
    """
    The BGP service provides interdomain routing.
    Peers must be manually configured, with a full mesh for those
    having the same AS number.
    """

    name = "BGP"
    shutdown = ["killall bgpd"]
    validate = ["pidof bgpd"]
    ipv4_routing = True
    ipv6_routing = True

    def quagga_interface_config(self, ifc: CoreInterface) -> str:
        router_id = get_router_id(self.node)
        text = f"""
        ! BGP configuration
        ! You should configure the AS number below
        ! along with this router's peers.
        router bgp {self.node.id}
          bgp router-id {router_id}
          redistribute connected
          !neighbor 1.2.3.4 remote-as 555
        !
        """
        return self.clean_text(text)


class Rip(QuaggaService, ConfigService):
    """
    The RIP service provides IPv4 routing for wired networks.
    """

    name = "RIP"
    shutdown = ["killall ripd"]
    validate = ["pidof ripd"]
    ipv4_routing = True

    def quagga_config(self) -> str:
        text = """
        router rip
          redistribute static
          redistribute connected
          redistribute ospf
          network 0.0.0.0/0
        !
        """
        return self.clean_text(text)


class Ripng(QuaggaService, ConfigService):
    """
    The RIP NG service provides IPv6 routing for wired networks.
    """

    name = "RIPNG"
    shutdown = ["killall ripngd"]
    validate = ["pidof ripngd"]
    ipv6_routing = True

    def quagga_config(self) -> str:
        text = """
        router ripng
          redistribute static
          redistribute connected
          redistribute ospf6
          network ::/0
        !
        """
        return self.clean_text(text)


class Babel(QuaggaService, ConfigService):
    """
    The Babel service provides a loop-avoiding distance-vector routing
    protocol for IPv6 and IPv4 with fast convergence properties.
    """

    name = "Babel"
    shutdown = ["killall babeld"]
    validate = ["pidof babeld"]
    ipv6_routing = True

    def quagga_config(self) -> str:
        ifnames = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
        text = """
        router babel
          % for ifname in ifnames:
          network ${ifname}
          % endfor
          redistribute static
          redistribute connected
        !
        """
        data = dict(ifnames=ifnames)
        return self.render_text(text, data)

    def quagga_interface_config(self, ifc: CoreInterface) -> str:
        if isinstance(ifc.net, (WlanNode, EmaneNet)):
            text = """
            babel wireless
            no babel split-horizon
            """
        else:
            text = """
            babel wired
            babel split-horizon
            """
        return self.clean_text(text)


class Xpimd(QuaggaService, ConfigService):
    """
    PIM multicast routing based on XORP.
    """

    name = "Xpimd"
    shutdown = ["killall xpimd"]
    validate = ["pidof xpimd"]
    ipv4_routing = True

    def quagga_config(self) -> str:
        ifname = "eth0"
        for ifc in self.node.netifs():
            if ifc.name != "lo":
                ifname = ifc.name
                break

        text = f"""
        router mfea
        !
        router igmp
        !
        router pim
          !ip pim rp-address 10.0.0.1
          ip pim bsr-candidate {ifname}
          ip pim rp-candidate {ifname}
          !ip pim spt-threshold interval 10 bytes 80000
        !
        """
        return self.clean_text(text)

    def quagga_interface_config(self, ifc: CoreInterface) -> str:
        text = """
        ip mfea
        ip pim
        """
        return self.clean_text(text)
