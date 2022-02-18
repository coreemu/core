import abc
import logging
from typing import Any, Dict, List

from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emane.nodes import EmaneNet
from core.nodes.base import CoreNodeBase
from core.nodes.interface import DEFAULT_MTU, CoreInterface
from core.nodes.network import PtpNet, WlanNode
from core.nodes.physical import Rj45Node

logger = logging.getLogger(__name__)
GROUP: str = "Quagga"
QUAGGA_STATE_DIR: str = "/var/run/quagga"


def has_mtu_mismatch(iface: CoreInterface) -> bool:
    """
    Helper to detect MTU mismatch and add the appropriate OSPF
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


def get_min_mtu(iface: CoreInterface):
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


class Zebra(ConfigService):
    name: str = "zebra"
    group: str = GROUP
    directories: List[str] = ["/usr/local/etc/quagga", "/var/run/quagga"]
    files: List[str] = [
        "/usr/local/etc/quagga/Quagga.conf",
        "quaggaboot.sh",
        "/usr/local/etc/quagga/vtysh.conf",
    ]
    executables: List[str] = ["zebra"]
    dependencies: List[str] = []
    startup: List[str] = ["bash quaggaboot.sh zebra"]
    validate: List[str] = ["pidof zebra"]
    shutdown: List[str] = ["killall zebra"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        quagga_bin_search = self.node.session.options.get_config(
            "quagga_bin_search", default="/usr/local/bin /usr/bin /usr/lib/quagga"
        ).strip('"')
        quagga_sbin_search = self.node.session.options.get_config(
            "quagga_sbin_search", default="/usr/local/sbin /usr/sbin /usr/lib/quagga"
        ).strip('"')
        quagga_state_dir = QUAGGA_STATE_DIR
        quagga_conf = self.files[0]

        services = []
        want_ip4 = False
        want_ip6 = False
        for service in self.node.config_services.values():
            if self.name not in service.dependencies:
                continue
            if not isinstance(service, QuaggaService):
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
                ip4s.append(str(ip4))
            for ip6 in iface.ip6s:
                ip6s.append(str(ip6))
            configs = []
            if not iface.control:
                for service in services:
                    config = service.quagga_iface_config(iface)
                    if config:
                        configs.append(config.split("\n"))
            ifaces.append((iface, ip4s, ip6s, configs))

        return dict(
            quagga_bin_search=quagga_bin_search,
            quagga_sbin_search=quagga_sbin_search,
            quagga_state_dir=quagga_state_dir,
            quagga_conf=quagga_conf,
            ifaces=ifaces,
            want_ip4=want_ip4,
            want_ip6=want_ip6,
            services=services,
        )


class QuaggaService(abc.ABC):
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = []
    executables: List[str] = []
    dependencies: List[str] = ["zebra"]
    startup: List[str] = []
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}
    ipv4_routing: bool = False
    ipv6_routing: bool = False

    @abc.abstractmethod
    def quagga_iface_config(self, iface: CoreInterface) -> str:
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

    name: str = "OSPFv2"
    validate: List[str] = ["pidof ospfd"]
    shutdown: List[str] = ["killall ospfd"]
    ipv4_routing: bool = True

    def quagga_iface_config(self, iface: CoreInterface) -> str:
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

    def quagga_config(self) -> str:
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
        !
        """
        return self.render_text(text, data)


class Ospfv3(QuaggaService, ConfigService):
    """
    The OSPFv3 service provides IPv6 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified Quagga.conf file.
    """

    name: str = "OSPFv3"
    shutdown: List[str] = ["killall ospf6d"]
    validate: List[str] = ["pidof ospf6d"]
    ipv4_routing: bool = True
    ipv6_routing: bool = True

    def quagga_iface_config(self, iface: CoreInterface) -> str:
        mtu = get_min_mtu(iface)
        if mtu < iface.mtu:
            return f"ipv6 ospf6 ifmtu {mtu}"
        else:
            return ""

    def quagga_config(self) -> str:
        router_id = get_router_id(self.node)
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
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

    name: str = "OSPFv3MDR"

    def quagga_iface_config(self, iface: CoreInterface) -> str:
        config = super().quagga_iface_config(iface)
        if isinstance(iface.net, (WlanNode, EmaneNet)):
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

    name: str = "BGP"
    shutdown: List[str] = ["killall bgpd"]
    validate: List[str] = ["pidof bgpd"]
    ipv4_routing: bool = True
    ipv6_routing: bool = True

    def quagga_config(self) -> str:
        return ""

    def quagga_iface_config(self, iface: CoreInterface) -> str:
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

    name: str = "RIP"
    shutdown: List[str] = ["killall ripd"]
    validate: List[str] = ["pidof ripd"]
    ipv4_routing: bool = True

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

    def quagga_iface_config(self, iface: CoreInterface) -> str:
        return ""


class Ripng(QuaggaService, ConfigService):
    """
    The RIP NG service provides IPv6 routing for wired networks.
    """

    name: str = "RIPNG"
    shutdown: List[str] = ["killall ripngd"]
    validate: List[str] = ["pidof ripngd"]
    ipv6_routing: bool = True

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

    def quagga_iface_config(self, iface: CoreInterface) -> str:
        return ""


class Babel(QuaggaService, ConfigService):
    """
    The Babel service provides a loop-avoiding distance-vector routing
    protocol for IPv6 and IPv4 with fast convergence properties.
    """

    name: str = "Babel"
    shutdown: List[str] = ["killall babeld"]
    validate: List[str] = ["pidof babeld"]
    ipv6_routing: bool = True

    def quagga_config(self) -> str:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
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

    def quagga_iface_config(self, iface: CoreInterface) -> str:
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


class Xpimd(QuaggaService, ConfigService):
    """
    PIM multicast routing based on XORP.
    """

    name: str = "Xpimd"
    shutdown: List[str] = ["killall xpimd"]
    validate: List[str] = ["pidof xpimd"]
    ipv4_routing: bool = True

    def quagga_config(self) -> str:
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

    def quagga_iface_config(self, iface: CoreInterface) -> str:
        text = """
        ip mfea
        ip pim
        """
        return self.clean_text(text)
