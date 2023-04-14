import abc
from typing import Any

from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emane.nodes import EmaneNet
from core.nodes.base import CoreNodeBase, NodeBase
from core.nodes.interface import DEFAULT_MTU, CoreInterface
from core.nodes.network import PtpNet, WlanNode
from core.nodes.physical import Rj45Node
from core.nodes.wireless import WirelessNode

GROUP: str = "FRR"
FRR_STATE_DIR: str = "/var/run/frr"


def is_wireless(node: NodeBase) -> bool:
    """
    Check if the node is a wireless type node.

    :param node: node to check type for
    :return: True if wireless type, False otherwise
    """
    return isinstance(node, (WlanNode, EmaneNet, WirelessNode))


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


def rj45_check(iface: CoreInterface) -> bool:
    """
    Helper to detect whether interface is connected an external RJ45
    link.
    """
    if iface.net:
        for peer_iface in iface.net.get_ifaces():
            if peer_iface == iface:
                continue
            if isinstance(peer_iface.node, Rj45Node):
                return True
    return False


class FRRZebra(ConfigService):
    name: str = "FRRzebra"
    group: str = GROUP
    directories: list[str] = ["/usr/local/etc/frr", "/var/run/frr", "/var/log/frr"]
    files: list[str] = [
        "/usr/local/etc/frr/frr.conf",
        "frrboot.sh",
        "/usr/local/etc/frr/vtysh.conf",
        "/usr/local/etc/frr/daemons",
    ]
    executables: list[str] = ["zebra"]
    dependencies: list[str] = []
    startup: list[str] = ["bash frrboot.sh zebra"]
    validate: list[str] = ["pidof zebra"]
    shutdown: list[str] = ["killall zebra"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: list[Configuration] = []
    modes: dict[str, dict[str, str]] = {}

    def data(self) -> dict[str, Any]:
        frr_conf = self.files[0]
        frr_bin_search = self.node.session.options.get(
            "frr_bin_search", default="/usr/local/bin /usr/bin /usr/lib/frr"
        ).strip('"')
        frr_sbin_search = self.node.session.options.get(
            "frr_sbin_search",
            default="/usr/local/sbin /usr/sbin /usr/lib/frr /usr/libexec/frr",
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
    directories: list[str] = []
    files: list[str] = []
    executables: list[str] = []
    dependencies: list[str] = ["FRRzebra"]
    startup: list[str] = []
    validate: list[str] = []
    shutdown: list[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: list[Configuration] = []
    modes: dict[str, dict[str, str]] = {}
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
    shutdown: list[str] = ["killall ospfd"]
    validate: list[str] = ["pidof ospfd"]
    ipv4_routing: bool = True

    def frr_config(self) -> str:
        router_id = get_router_id(self.node)
        addresses = []
        for iface in self.node.get_ifaces(control=False):
            for ip4 in iface.ip4s:
                addresses.append(str(ip4))
        data = dict(router_id=router_id, addresses=addresses)
        text = """
        router ospf
          router-id ${router_id}
          % for addr in addresses:
          network ${addr} area 0
          % endfor
          ospf opaque-lsa
        !
        """
        return self.render_text(text, data)

    def frr_iface_config(self, iface: CoreInterface) -> str:
        has_mtu = has_mtu_mismatch(iface)
        has_rj45 = rj45_check(iface)
        is_ptp = isinstance(iface.net, PtpNet)
        data = dict(has_mtu=has_mtu, is_ptp=is_ptp, has_rj45=has_rj45)
        text = """
        % if has_mtu:
        ip ospf mtu-ignore
        % endif
        % if has_rj45:
        <% return STOP_RENDERING %>
        % endif
        % if is_ptp:
        ip ospf network point-to-point
        % endif
        ip ospf hello-interval 2
        ip ospf dead-interval 6
        ip ospf retransmit-interval 5
        """
        return self.render_text(text, data)


class FRROspfv3(FrrService, ConfigService):
    """
    The OSPFv3 service provides IPv6 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified frr.conf file.
    """

    name: str = "FRROSPFv3"
    shutdown: list[str] = ["killall ospf6d"]
    validate: list[str] = ["pidof ospf6d"]
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
    shutdown: list[str] = ["killall bgpd"]
    validate: list[str] = ["pidof bgpd"]
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
    shutdown: list[str] = ["killall ripd"]
    validate: list[str] = ["pidof ripd"]
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
    shutdown: list[str] = ["killall ripngd"]
    validate: list[str] = ["pidof ripngd"]
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
    shutdown: list[str] = ["killall babeld"]
    validate: list[str] = ["pidof babeld"]
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
        if is_wireless(iface.net):
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
    shutdown: list[str] = ["killall pimd"]
    validate: list[str] = ["pidof pimd"]
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
