"""
frr.py: defines routing services provided by FRRouting.
Assumes installation of FRR via https://deb.frrouting.org/
"""
from typing import Optional

import netaddr

from core.emane.nodes import EmaneNet
from core.nodes.base import CoreNode, NodeBase
from core.nodes.interface import DEFAULT_MTU, CoreInterface
from core.nodes.network import PtpNet, WlanNode
from core.nodes.physical import Rj45Node
from core.nodes.wireless import WirelessNode
from core.services.coreservices import CoreService

FRR_STATE_DIR: str = "/var/run/frr"


def is_wireless(node: NodeBase) -> bool:
    """
    Check if the node is a wireless type node.

    :param node: node to check type for
    :return: True if wireless type, False otherwise
    """
    return isinstance(node, (WlanNode, EmaneNet, WirelessNode))


class FRRZebra(CoreService):
    name: str = "FRRzebra"
    group: str = "FRR"
    dirs: tuple[str, ...] = ("/usr/local/etc/frr", "/var/run/frr", "/var/log/frr")
    configs: tuple[str, ...] = (
        "/usr/local/etc/frr/frr.conf",
        "frrboot.sh",
        "/usr/local/etc/frr/vtysh.conf",
        "/usr/local/etc/frr/daemons",
    )
    startup: tuple[str, ...] = ("bash frrboot.sh zebra",)
    shutdown: tuple[str, ...] = ("killall zebra",)
    validate: tuple[str, ...] = ("pidof zebra",)

    @classmethod
    def generate_config(cls, node: CoreNode, filename: str) -> str:
        """
        Return the frr.conf or frrboot.sh file contents.
        """
        if filename == cls.configs[0]:
            return cls.generate_frr_conf(node)
        elif filename == cls.configs[1]:
            return cls.generate_frr_boot(node)
        elif filename == cls.configs[2]:
            return cls.generate_vtysh_conf(node)
        elif filename == cls.configs[3]:
            return cls.generate_frr_daemons(node)
        else:
            raise ValueError(
                "file name (%s) is not a known configuration: %s", filename, cls.configs
            )

    @classmethod
    def generate_vtysh_conf(cls, node: CoreNode) -> str:
        """
        Returns configuration file text.
        """
        return "service integrated-vtysh-config\n"

    @classmethod
    def generate_frr_conf(cls, node: CoreNode) -> str:
        """
        Returns configuration file text. Other services that depend on zebra
        will have hooks that are invoked here.
        """
        # we could verify here that filename == frr.conf
        cfg = ""
        for iface in node.get_ifaces():
            cfg += f"interface {iface.name}\n"
            # include control interfaces in addressing but not routing daemons
            if iface.control:
                cfg += "  "
                cfg += "\n  ".join(map(cls.addrstr, iface.ips()))
                cfg += "\n"
                continue
            cfgv4 = ""
            cfgv6 = ""
            want_ipv4 = False
            want_ipv6 = False
            for s in node.services:
                if cls.name not in s.dependencies:
                    continue
                if not (isinstance(s, FrrService) or issubclass(s, FrrService)):
                    continue
                iface_config = s.generate_frr_iface_config(node, iface)
                if s.ipv4_routing:
                    want_ipv4 = True
                if s.ipv6_routing:
                    want_ipv6 = True
                    cfgv6 += iface_config
                else:
                    cfgv4 += iface_config

            if want_ipv4:
                cfg += "  "
                cfg += "\n  ".join(map(cls.addrstr, iface.ip4s))
                cfg += "\n"
                cfg += cfgv4
            if want_ipv6:
                cfg += "  "
                cfg += "\n  ".join(map(cls.addrstr, iface.ip6s))
                cfg += "\n"
                cfg += cfgv6
            cfg += "!\n"

        for s in node.services:
            if cls.name not in s.dependencies:
                continue
            if not (isinstance(s, FrrService) or issubclass(s, FrrService)):
                continue
            cfg += s.generate_frr_config(node)
        return cfg

    @staticmethod
    def addrstr(ip: netaddr.IPNetwork) -> str:
        """
        helper for mapping IP addresses to zebra config statements
        """
        address = str(ip.ip)
        if netaddr.valid_ipv4(address):
            return f"ip address {ip}"
        elif netaddr.valid_ipv6(address):
            return f"ipv6 address {ip}"
        else:
            raise ValueError(f"invalid address: {ip}")

    @classmethod
    def generate_frr_boot(cls, node: CoreNode) -> str:
        """
        Generate a shell script used to boot the FRR daemons.
        """
        frr_bin_search = node.session.options.get(
            "frr_bin_search", '"/usr/local/bin /usr/bin /usr/lib/frr"'
        )
        frr_sbin_search = node.session.options.get(
            "frr_sbin_search",
            '"/usr/local/sbin /usr/sbin /usr/lib/frr /usr/libexec/frr"',
        )
        cfg = f"""\
#!/bin/sh
# auto-generated by zebra service (frr.py)
FRR_CONF={cls.configs[0]}
FRR_SBIN_SEARCH={frr_sbin_search}
FRR_BIN_SEARCH={frr_bin_search}
FRR_STATE_DIR={FRR_STATE_DIR}

searchforprog()
{{
    prog=$1
    searchpath=$@
    ret=
    for p in $searchpath; do
        if [ -x $p/$prog ]; then
            ret=$p
            break
        fi
    done
    echo $ret
}}

confcheck()
{{
    CONF_DIR=`dirname $FRR_CONF`
    # if /etc/frr exists, point /etc/frr/frr.conf -> CONF_DIR
    if [ "$CONF_DIR" != "/etc/frr" ] && [ -d /etc/frr ] && [ ! -e /etc/frr/frr.conf ]; then
        ln -s $CONF_DIR/frr.conf /etc/frr/frr.conf
    fi
    # if /etc/frr exists, point /etc/frr/vtysh.conf -> CONF_DIR
    if [ "$CONF_DIR" != "/etc/frr" ] && [ -d /etc/frr ] && [ ! -e /etc/frr/vtysh.conf ]; then
        ln -s $CONF_DIR/vtysh.conf /etc/frr/vtysh.conf
    fi
}}

bootdaemon()
{{
    FRR_SBIN_DIR=$(searchforprog $1 $FRR_SBIN_SEARCH)
    if [ "z$FRR_SBIN_DIR" = "z" ]; then
        echo "ERROR: FRR's '$1' daemon not found in search path:"
        echo "  $FRR_SBIN_SEARCH"
        return 1
    fi

    flags=""

    if [ "$1" = "pimd" ] && \\
        grep -E -q '^[[:space:]]*router[[:space:]]+pim6[[:space:]]*$' $FRR_CONF; then
        flags="$flags -6"
    fi

    if [ "$1" = "ospfd" ]; then
        flags="$flags --apiserver"
    fi

    #force FRR to use CORE generated conf file
    flags="$flags -d -f $FRR_CONF"
    $FRR_SBIN_DIR/$1 $flags

    if [ "$?" != "0" ]; then
        echo "ERROR: FRR's '$1' daemon failed to start!:"
        return 1
    fi
}}

bootfrr()
{{
    FRR_BIN_DIR=$(searchforprog 'vtysh' $FRR_BIN_SEARCH)
    if [ "z$FRR_BIN_DIR" = "z" ]; then
        echo "ERROR: FRR's 'vtysh' program not found in search path:"
        echo "  $FRR_BIN_SEARCH"
        return 1
    fi

    # fix /var/run/frr permissions
    id -u frr 2>/dev/null >/dev/null
    if [ "$?" = "0" ]; then
        chown frr $FRR_STATE_DIR
    fi

    bootdaemon "zebra"
    if grep -q "^ip route " $FRR_CONF; then
        bootdaemon "staticd"
    fi
    for r in rip ripng ospf6 ospf bgp babel isis; do
        if grep -q "^router \\<${{r}}\\>" $FRR_CONF; then
            bootdaemon "${{r}}d"
        fi
    done

    if grep -E -q '^[[:space:]]*router[[:space:]]+pim6?[[:space:]]*$' $FRR_CONF; then
        bootdaemon "pimd"
    fi

    $FRR_BIN_DIR/vtysh -b
}}

if [ "$1" != "zebra" ]; then
    echo "WARNING: '$1': all FRR daemons are launched by the 'zebra' service!"
    exit 1
fi

confcheck
bootfrr
"""
        for iface in node.get_ifaces():
            cfg += f"ip link set dev {iface.name} down\n"
            cfg += "sleep 1\n"
            cfg += f"ip link set dev {iface.name} up\n"
        return cfg

    @classmethod
    def generate_frr_daemons(cls, node: CoreNode) -> str:
        """
        Returns configuration file text.
        """
        return """\
#
# When activation a daemon at the first time, a config file, even if it is
# empty, has to be present *and* be owned by the user and group "frr", else
# the daemon will not be started by /etc/init.d/frr. The permissions should
# be u=rw,g=r,o=.
# When using "vtysh" such a config file is also needed. It should be owned by
# group "frrvty" and set to ug=rw,o= though. Check /etc/pam.d/frr, too.
#
# The watchfrr and zebra daemons are always started.
#
bgpd=yes
ospfd=yes
ospf6d=yes
ripd=yes
ripngd=yes
isisd=yes
pimd=yes
ldpd=yes
nhrpd=yes
eigrpd=yes
babeld=yes
sharpd=yes
staticd=yes
pbrd=yes
bfdd=yes
fabricd=yes

#
# If this option is set the /etc/init.d/frr script automatically loads
# the config via "vtysh -b" when the servers are started.
# Check /etc/pam.d/frr if you intend to use "vtysh"!
#
vtysh_enable=yes
zebra_options="  -A 127.0.0.1 -s 90000000"
bgpd_options="   -A 127.0.0.1"
ospfd_options="  -A 127.0.0.1"
ospf6d_options=" -A ::1"
ripd_options="   -A 127.0.0.1"
ripngd_options=" -A ::1"
isisd_options="  -A 127.0.0.1"
pimd_options="   -A 127.0.0.1"
ldpd_options="   -A 127.0.0.1"
nhrpd_options="  -A 127.0.0.1"
eigrpd_options=" -A 127.0.0.1"
babeld_options=" -A 127.0.0.1"
sharpd_options=" -A 127.0.0.1"
pbrd_options="   -A 127.0.0.1"
staticd_options="-A 127.0.0.1"
bfdd_options="   -A 127.0.0.1"
fabricd_options="-A 127.0.0.1"

# The list of daemons to watch is automatically generated by the init script.
#watchfrr_options=""

# for debugging purposes, you can specify a "wrap" command to start instead
# of starting the daemon directly, e.g. to use valgrind on ospfd:
#   ospfd_wrap="/usr/bin/valgrind"
# or you can use "all_wrap" for all daemons, e.g. to use perf record:
#   all_wrap="/usr/bin/perf record --call-graph -"
# the normal daemon command is added to this at the end.
"""


class FrrService(CoreService):
    """
    Parent class for FRR services. Defines properties and methods
    common to FRR's routing daemons.
    """

    name: Optional[str] = None
    group: str = "FRR"
    dependencies: tuple[str, ...] = ("FRRzebra",)
    meta: str = "The config file for this service can be found in the Zebra service."
    ipv4_routing: bool = False
    ipv6_routing: bool = False

    @staticmethod
    def router_id(node: CoreNode) -> str:
        """
        Helper to return the first IPv4 address of a node as its router ID.
        """
        for iface in node.get_ifaces(control=False):
            ip4 = iface.get_ip4()
            if ip4:
                return str(ip4.ip)
        return "0.0.0.0"

    @staticmethod
    def rj45check(iface: CoreInterface) -> bool:
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

    @classmethod
    def generate_config(cls, node: CoreNode, filename: str) -> str:
        return ""

    @classmethod
    def generate_frr_iface_config(cls, node: CoreNode, iface: CoreInterface) -> str:
        return ""

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        return ""


class FRROspfv2(FrrService):
    """
    The OSPFv2 service provides IPv4 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified frr.conf file.
    """

    name: str = "FRROSPFv2"
    shutdown: tuple[str, ...] = ("killall ospfd",)
    validate: tuple[str, ...] = ("pidof ospfd",)
    ipv4_routing: bool = True

    @staticmethod
    def mtu_check(iface: CoreInterface) -> str:
        """
        Helper to detect MTU mismatch and add the appropriate OSPF
        mtu-ignore command. This is needed when e.g. a node is linked via a
        GreTap device.
        """
        if iface.mtu != DEFAULT_MTU:
            # a workaround for PhysicalNode GreTap, which has no knowledge of
            # the other nodes/nets
            return "  ip ospf mtu-ignore\n"
        if not iface.net:
            return ""
        for iface in iface.net.get_ifaces():
            if iface.mtu != iface.mtu:
                return "  ip ospf mtu-ignore\n"
        return ""

    @staticmethod
    def ptp_check(iface: CoreInterface) -> str:
        """
        Helper to detect whether interface is connected to a notional
        point-to-point link.
        """
        if isinstance(iface.net, PtpNet):
            return "  ip ospf network point-to-point\n"
        return ""

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        cfg = "router ospf\n"
        rtrid = cls.router_id(node)
        cfg += f"  router-id {rtrid}\n"
        # network 10.0.0.0/24 area 0
        for iface in node.get_ifaces(control=False):
            for ip4 in iface.ip4s:
                cfg += f"  network {ip4} area 0\n"
        cfg += "  ospf opaque-lsa\n"
        cfg += "!\n"
        return cfg

    @classmethod
    def generate_frr_iface_config(cls, node: CoreNode, iface: CoreInterface) -> str:
        cfg = cls.mtu_check(iface)
        # external RJ45 connections will use default OSPF timers
        if cls.rj45check(iface):
            return cfg
        cfg += cls.ptp_check(iface)
        return (
            cfg
            + """\
  ip ospf hello-interval 2
  ip ospf dead-interval 6
  ip ospf retransmit-interval 5
"""
        )


class FRROspfv3(FrrService):
    """
    The OSPFv3 service provides IPv6 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified frr.conf file.
    """

    name: str = "FRROSPFv3"
    shutdown: tuple[str, ...] = ("killall ospf6d",)
    validate: tuple[str, ...] = ("pidof ospf6d",)
    ipv4_routing: bool = True
    ipv6_routing: bool = True

    @staticmethod
    def min_mtu(iface: CoreInterface) -> int:
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

    @classmethod
    def mtu_check(cls, iface: CoreInterface) -> str:
        """
        Helper to detect MTU mismatch and add the appropriate OSPFv3
        ifmtu command. This is needed when e.g. a node is linked via a
        GreTap device.
        """
        minmtu = cls.min_mtu(iface)
        if minmtu < iface.mtu:
            return f"  ipv6 ospf6 ifmtu {minmtu:d}\n"
        else:
            return ""

    @staticmethod
    def ptp_check(iface: CoreInterface) -> str:
        """
        Helper to detect whether interface is connected to a notional
        point-to-point link.
        """
        if isinstance(iface.net, PtpNet):
            return "  ipv6 ospf6 network point-to-point\n"
        return ""

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        cfg = "router ospf6\n"
        rtrid = cls.router_id(node)
        cfg += f"  router-id {rtrid}\n"
        for iface in node.get_ifaces(control=False):
            cfg += f"  interface {iface.name} area 0.0.0.0\n"
        cfg += "!\n"
        return cfg

    @classmethod
    def generate_frr_iface_config(cls, node: CoreNode, iface: CoreInterface) -> str:
        return cls.mtu_check(iface)


class FRRBgp(FrrService):
    """
    The BGP service provides interdomain routing.
    Peers must be manually configured, with a full mesh for those
    having the same AS number.
    """

    name: str = "FRRBGP"
    shutdown: tuple[str, ...] = ("killall bgpd",)
    validate: tuple[str, ...] = ("pidof bgpd",)
    custom_needed: bool = True
    ipv4_routing: bool = True
    ipv6_routing: bool = True

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        cfg = "!\n! BGP configuration\n!\n"
        cfg += "! You should configure the AS number below,\n"
        cfg += "! along with this router's peers.\n!\n"
        cfg += f"router bgp {node.id}\n"
        rtrid = cls.router_id(node)
        cfg += f"  bgp router-id {rtrid}\n"
        cfg += "  redistribute connected\n"
        cfg += "! neighbor 1.2.3.4 remote-as 555\n!\n"
        return cfg


class FRRRip(FrrService):
    """
    The RIP service provides IPv4 routing for wired networks.
    """

    name: str = "FRRRIP"
    shutdown: tuple[str, ...] = ("killall ripd",)
    validate: tuple[str, ...] = ("pidof ripd",)
    ipv4_routing: bool = True

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        cfg = """\
router rip
  redistribute static
  redistribute connected
  redistribute ospf
  network 0.0.0.0/0
!
"""
        return cfg


class FRRRipng(FrrService):
    """
    The RIP NG service provides IPv6 routing for wired networks.
    """

    name: str = "FRRRIPNG"
    shutdown: tuple[str, ...] = ("killall ripngd",)
    validate: tuple[str, ...] = ("pidof ripngd",)
    ipv6_routing: bool = True

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        cfg = """\
router ripng
  redistribute static
  redistribute connected
  redistribute ospf6
  network ::/0
!
"""
        return cfg


class FRRBabel(FrrService):
    """
    The Babel service provides a loop-avoiding distance-vector routing
    protocol for IPv6 and IPv4 with fast convergence properties.
    """

    name: str = "FRRBabel"
    shutdown: tuple[str, ...] = ("killall babeld",)
    validate: tuple[str, ...] = ("pidof babeld",)
    ipv6_routing: bool = True

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        cfg = "router babel\n"
        for iface in node.get_ifaces(control=False):
            cfg += f"  network {iface.name}\n"
        cfg += "  redistribute static\n  redistribute ipv4 connected\n"
        return cfg

    @classmethod
    def generate_frr_iface_config(cls, node: CoreNode, iface: CoreInterface) -> str:
        if is_wireless(iface.net):
            return "  babel wireless\n  no babel split-horizon\n"
        else:
            return "  babel wired\n  babel split-horizon\n"


class FRRpimd(FrrService):
    """
    PIM multicast routing based on XORP.
    """

    name: str = "FRRpimd"
    shutdown: tuple[str, ...] = ("killall pimd",)
    validate: tuple[str, ...] = ("pidof pimd",)
    ipv4_routing: bool = True

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        ifname = "eth0"
        for iface in node.get_ifaces():
            if iface.name != "lo":
                ifname = iface.name
                break
        cfg = "router mfea\n!\n"
        cfg += "router igmp\n!\n"
        cfg += "router pim\n"
        cfg += "  !ip pim rp-address 10.0.0.1\n"
        cfg += f"  ip pim bsr-candidate {ifname}\n"
        cfg += f"  ip pim rp-candidate {ifname}\n"
        cfg += "  !ip pim spt-threshold interval 10 bytes 80000\n"
        return cfg

    @classmethod
    def generate_frr_iface_config(cls, node: CoreNode, iface: CoreInterface) -> str:
        return "  ip mfea\n  ip igmp\n  ip pim\n"


class FRRIsis(FrrService):
    """
    The ISIS service provides IPv4 and IPv6 routing for wired networks. It does
    not build its own configuration file but has hooks for adding to the
    unified frr.conf file.
    """

    name: str = "FRRISIS"
    shutdown: tuple[str, ...] = ("killall isisd",)
    validate: tuple[str, ...] = ("pidof isisd",)
    ipv4_routing: bool = True
    ipv6_routing: bool = True

    @staticmethod
    def ptp_check(iface: CoreInterface) -> str:
        """
        Helper to detect whether interface is connected to a notional
        point-to-point link.
        """
        if isinstance(iface.net, PtpNet):
            return "  isis network point-to-point\n"
        return ""

    @classmethod
    def generate_frr_config(cls, node: CoreNode) -> str:
        cfg = "router isis DEFAULT\n"
        cfg += f"  net 47.0001.0000.1900.{node.id:04x}.00\n"
        cfg += "  metric-style wide\n"
        cfg += "  is-type level-2-only\n"
        cfg += "!\n"
        return cfg

    @classmethod
    def generate_frr_iface_config(cls, node: CoreNode, iface: CoreInterface) -> str:
        cfg = "  ip router isis DEFAULT\n"
        cfg += "  ipv6 router isis DEFAULT\n"
        cfg += "  isis circuit-type level-2-only\n"
        cfg += cls.ptp_check(iface)
        return cfg
