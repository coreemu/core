import abc
from typing import Any, Dict, List

from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emane.nodes import EmaneNet
from core.nodes.base import CoreNodeBase
from core.nodes.interface import DEFAULT_MTU, CoreInterface
from core.nodes.network import WlanNode

GROUP: str = "FRR"
FRR_STATE_DIR: str = "/var/run/frr"


def has_mtu_mismatch(iface: CoreInterface) -> bool:
    """
    Helper to detect MTU mismatch and add the appropriate FRR
    mtu-ignore command. This is needed when e.g. a node is linked via a
    GreTap device.
    """
    if iface.mtu != DEFAULT_MTU:
        return True
    if not iface.net:
        return False
    for iface in iface.net.get_ifaces():
        if iface.mtu != iface.mtu:
            return True
    return False


def get_min_mtu(iface: CoreInterface) -> int:
    """
    Helper to discover the minimum MTU of interfaces linked with the
    given interface.
    """
    mtu = iface.mtu
    if not iface.net:
        return mtu
    for iface in iface.net.get_ifaces():
        if iface.mtu < mtu:
            mtu = iface.mtu
    return mtu


def get_router_id(node: CoreNodeBase) -> str:
    """
    Helper to return the first IPv4 address of a node as its router ID.
    """
    for iface in node.get_ifaces(control=False):
        ip4 = iface.get_ip4()
        if ip4:
            return str(ip4.ip)
    return "0.0.0.0"


class FRRZebra(ConfigService):
    name: str = "FRRzebra"
    group: str = GROUP
    directories: List[str] = ["/usr/local/etc/frr", "/var/run/frr", "/var/log/frr"]
    files: List[str] = [
        "/usr/local/etc/frr/frr.conf",
        "frrboot.sh",
        "/usr/local/etc/frr/vtysh.conf",
        "/usr/local/etc/frr/daemons",
    ]
    executables: List[str] = ["zebra"]
    dependencies: List[str] = []
    startup: List[str] = ["bash frrboot.sh zebra"]
    validate: List[str] = ["pidof zebra"]
    shutdown: List[str] = ["killall zebra"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        frr_conf = self.files[0]
        frr_bin_search = self.node.session.options.get_config(
            "frr_bin_search", default="/usr/local/bin /usr/bin /usr/lib/frr"
        ).strip('"')
        frr_sbin_search = self.node.session.options.get_config(
            "frr_sbin_search", default="/usr/local/sbin /usr/sbin /usr/lib/frr"
        ).strip('"')

        services = []
        want_ip4 = False
        want_ip6 = False
        for service in self.node.config_services.values():
            if self.name not in service.dependencies:
                continue
            if not isinstance(service, FrrService):
                continue
            if service.ipv4_routing:
                want_ip4 = True
            if service.ipv6_routing:
                want_ip6 = True
            services.append(service)

        ifaces = []
        for iface in self.node.get_ifaces():
            ip4s = []
            ip6s = []
            for ip4 in iface.ip4s:
                ip4s.append(str(ip4.ip))
            for ip6 in iface.ip6s:
                ip6s.append(str(ip6.ip))
            ifaces.append((iface, ip4s, ip6s, iface.control))

        return dict(
            frr_conf=frr_conf,
            frr_sbin_search=frr_sbin_search,
            frr_bin_search=frr_bin_search,
            frr_state_dir=FRR_STATE_DIR,
            ifaces=ifaces,
            want_ip4=want_ip4,
            want_ip6=want_ip6,
            services=services,
        )


class FrrService(abc.ABC):
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = []
    executables: List[str] = []
    dependencies: List[str] = ["FRRzebra"]
    startup: List[str] = []
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}
    ipv4_routing: bool = False
    ipv6_routing: bool = False

    @abc.abstractmethod
    def frr_iface_config(self, iface: CoreInterface) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def frr_config(self) -> str:
        raise NotImplementedError


class FRROspfv2(FrrService, ConfigService):
    """
    The OSPFv2 service provides IPv4 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified frr.conf file.
    """

    name: str = "FRROSPFv2"
    shutdown: List[str] = ["killall ospfd"]
    validate: List[str] = ["pidof ospfd"]
    ipv4_routing: bool = True

    def frr_config(self) -> str:
        router_id = get_router_id(self.node)
        addresses = []
        for iface in self.node.get_ifaces(control=False):
            for ip4 in iface.ip4s:
                addresses.append(str(ip4.ip))
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

    def frr_iface_config(self, iface: CoreInterface) -> str:
        if has_mtu_mismatch(iface):
            return "ip ospf mtu-ignore"
        else:
            return ""


class FRROspfv3(FrrService, ConfigService):
    """
    The OSPFv3 service provides IPv6 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified frr.conf file.
    """

    name: str = "FRROSPFv3"
    shutdown: List[str] = ["killall ospf6d"]
    validate: List[str] = ["pidof ospf6d"]
    ipv4_routing: bool = True
    ipv6_routing: bool = True

    def frr_config(self) -> str:
        router_id = get_router_id(self.node)
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        data = dict(router_id=router_id, ifnames=ifnames)
        text = """
        router ospf6
          router-id ${router_id}
          % for ifname in ifnames:
          interface ${ifname} area 0.0.0.0
          % endfor
        !
        """
        return self.render_text(text, data)

    def frr_iface_config(self, iface: CoreInterface) -> str:
        mtu = get_min_mtu(iface)
        if mtu < iface.mtu:
            return f"ipv6 ospf6 ifmtu {mtu}"
        else:
            return ""


class FRRBgp(FrrService, ConfigService):
    """
    The BGP service provides interdomain routing.
    Peers must be manually configured, with a full mesh for those
    having the same AS number.
    """

    name: str = "FRRBGP"
    shutdown: List[str] = ["killall bgpd"]
    validate: List[str] = ["pidof bgpd"]
    custom_needed: bool = True
    ipv4_routing: bool = True
    ipv6_routing: bool = True

    def frr_config(self) -> str:
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

    def frr_iface_config(self, iface: CoreInterface) -> str:
        return ""


class FRRRip(FrrService, ConfigService):
    """
    The RIP service provides IPv4 routing for wired networks.
    """

    name: str = "FRRRIP"
    shutdown: List[str] = ["killall ripd"]
    validate: List[str] = ["pidof ripd"]
    ipv4_routing: bool = True

    def frr_config(self) -> str:
        text = """
        router rip
          redistribute static
          redistribute connected
          redistribute ospf
          network 0.0.0.0/0
        !
        """
        return self.clean_text(text)

    def frr_iface_config(self, iface: CoreInterface) -> str:
        return ""


class FRRRipng(FrrService, ConfigService):
    """
    The RIP NG service provides IPv6 routing for wired networks.
    """

    name: str = "FRRRIPNG"
    shutdown: List[str] = ["killall ripngd"]
    validate: List[str] = ["pidof ripngd"]
    ipv6_routing: bool = True

    def frr_config(self) -> str:
        text = """
        router ripng
          redistribute static
          redistribute connected
          redistribute ospf6
          network ::/0
        !
        """
        return self.clean_text(text)

    def frr_iface_config(self, iface: CoreInterface) -> str:
        return ""


class FRRBabel(FrrService, ConfigService):
    """
    The Babel service provides a loop-avoiding distance-vector routing
    protocol for IPv6 and IPv4 with fast convergence properties.
    """

    name: str = "FRRBabel"
    shutdown: List[str] = ["killall babeld"]
    validate: List[str] = ["pidof babeld"]
    ipv6_routing: bool = True

    def frr_config(self) -> str:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        text = """
        router babel
          % for ifname in ifnames:
          network ${ifname}
          % endfor
          redistribute static
          redistribute ipv4 connected
        !
        """
        data = dict(ifnames=ifnames)
        return self.render_text(text, data)

    def frr_iface_config(self, iface: CoreInterface) -> str:
        if isinstance(iface.net, (WlanNode, EmaneNet)):
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


class FRRpimd(FrrService, ConfigService):
    """
    PIM multicast routing based on XORP.
    """

    name: str = "FRRpimd"
    shutdown: List[str] = ["killall pimd"]
    validate: List[str] = ["pidof pimd"]
    ipv4_routing: bool = True

    def frr_config(self) -> str:
        ifname = "eth0"
        for iface in self.node.get_ifaces():
            if iface.name != "lo":
                ifname = iface.name
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

    def frr_iface_config(self, iface: CoreInterface) -> str:
        text = """
        ip mfea
        ip igmp
        ip pim
        """
        return self.clean_text(text)
