from typing import Any, Dict, List

import netaddr

from core import utils
from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode

GROUP_NAME = "Utility"


class DefaultRouteService(ConfigService):
    name: str = "DefaultRoute"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["defaultroute.sh"]
    executables: List[str] = ["ip"]
    dependencies: List[str] = []
    startup: List[str] = ["bash defaultroute.sh"]
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        # only add default routes for linked routing nodes
        routes = []
        ifaces = self.node.get_ifaces()
        if ifaces:
            iface = ifaces[0]
            for ip in iface.ips():
                net = ip.cidr
                if net.size > 1:
                    router = net[1]
                    routes.append(str(router))
        return dict(routes=routes)


class DefaultMulticastRouteService(ConfigService):
    name: str = "DefaultMulticastRoute"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["defaultmroute.sh"]
    executables: List[str] = []
    dependencies: List[str] = []
    startup: List[str] = ["bash defaultmroute.sh"]
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ifname = None
        for iface in self.node.get_ifaces(control=False):
            ifname = iface.name
            break
        return dict(ifname=ifname)


class StaticRouteService(ConfigService):
    name: str = "StaticRoute"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["staticroute.sh"]
    executables: List[str] = []
    dependencies: List[str] = []
    startup: List[str] = ["bash staticroute.sh"]
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        routes = []
        for iface in self.node.get_ifaces(control=False):
            for ip in iface.ips():
                address = str(ip.ip)
                if netaddr.valid_ipv6(address):
                    dst = "3ffe:4::/64"
                else:
                    dst = "10.9.8.0/24"
                if ip[-2] != ip[1]:
                    routes.append((dst, ip[1]))
        return dict(routes=routes)


class IpForwardService(ConfigService):
    name: str = "IPForward"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["ipforward.sh"]
    executables: List[str] = ["sysctl"]
    dependencies: List[str] = []
    startup: List[str] = ["bash ipforward.sh"]
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        devnames = []
        for iface in self.node.get_ifaces():
            devname = utils.sysctl_devname(iface.name)
            devnames.append(devname)
        return dict(devnames=devnames)


class SshService(ConfigService):
    name: str = "SSH"
    group: str = GROUP_NAME
    directories: List[str] = ["/etc/ssh", "/var/run/sshd"]
    files: List[str] = ["startsshd.sh", "/etc/ssh/sshd_config"]
    executables: List[str] = ["sshd"]
    dependencies: List[str] = []
    startup: List[str] = ["bash startsshd.sh"]
    validate: List[str] = []
    shutdown: List[str] = ["killall sshd"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        return dict(
            sshcfgdir=self.directories[0],
            sshstatedir=self.directories[1],
            sshlibdir="/usr/lib/openssh",
        )


class DhcpService(ConfigService):
    name: str = "DHCP"
    group: str = GROUP_NAME
    directories: List[str] = ["/etc/dhcp", "/var/lib/dhcp"]
    files: List[str] = ["/etc/dhcp/dhcpd.conf"]
    executables: List[str] = ["dhcpd"]
    dependencies: List[str] = []
    startup: List[str] = ["touch /var/lib/dhcp/dhcpd.leases", "dhcpd"]
    validate: List[str] = ["pidof dhcpd"]
    shutdown: List[str] = ["killall dhcpd"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        subnets = []
        for iface in self.node.get_ifaces(control=False):
            for ip4 in iface.ip4s:
                if ip4.size == 1:
                    continue
                # divide the address space in half
                index = (ip4.size - 2) / 2
                rangelow = ip4[index]
                rangehigh = ip4[-2]
                subnets.append((ip4.cidr.ip, ip4.netmask, rangelow, rangehigh, ip4.ip))
        return dict(subnets=subnets)


class DhcpClientService(ConfigService):
    name: str = "DHCPClient"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["startdhcpclient.sh"]
    executables: List[str] = ["dhclient"]
    dependencies: List[str] = []
    startup: List[str] = ["bash startdhcpclient.sh"]
    validate: List[str] = ["pidof dhclient"]
    shutdown: List[str] = ["killall dhclient"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(ifnames=ifnames)


class FtpService(ConfigService):
    name: str = "FTP"
    group: str = GROUP_NAME
    directories: List[str] = ["/var/run/vsftpd/empty", "/var/ftp"]
    files: List[str] = ["vsftpd.conf"]
    executables: List[str] = ["vsftpd"]
    dependencies: List[str] = []
    startup: List[str] = ["vsftpd ./vsftpd.conf"]
    validate: List[str] = ["pidof vsftpd"]
    shutdown: List[str] = ["killall vsftpd"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}


class PcapService(ConfigService):
    name: str = "pcap"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["pcap.sh"]
    executables: List[str] = ["tcpdump"]
    dependencies: List[str] = []
    startup: List[str] = ["bash pcap.sh start"]
    validate: List[str] = ["pidof tcpdump"]
    shutdown: List[str] = ["bash pcap.sh stop"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict()


class RadvdService(ConfigService):
    name: str = "radvd"
    group: str = GROUP_NAME
    directories: List[str] = ["/etc/radvd", "/var/run/radvd"]
    files: List[str] = ["/etc/radvd/radvd.conf"]
    executables: List[str] = ["radvd"]
    dependencies: List[str] = []
    startup: List[str] = [
        "radvd -C /etc/radvd/radvd.conf -m logfile -l /var/log/radvd.log"
    ]
    validate: List[str] = ["pidof radvd"]
    shutdown: List[str] = ["pkill radvd"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ifaces = []
        for iface in self.node.get_ifaces(control=False):
            prefixes = []
            for ip6 in iface.ip6s:
                prefixes.append(str(ip6))
            if not prefixes:
                continue
            ifaces.append((iface.name, prefixes))
        return dict(ifaces=ifaces)


class AtdService(ConfigService):
    name: str = "atd"
    group: str = GROUP_NAME
    directories: List[str] = ["/var/spool/cron/atjobs", "/var/spool/cron/atspool"]
    files: List[str] = ["startatd.sh"]
    executables: List[str] = ["atd"]
    dependencies: List[str] = []
    startup: List[str] = ["bash startatd.sh"]
    validate: List[str] = ["pidof atd"]
    shutdown: List[str] = ["pkill atd"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}


class HttpService(ConfigService):
    name: str = "HTTP"
    group: str = GROUP_NAME
    directories: List[str] = [
        "/etc/apache2",
        "/var/run/apache2",
        "/var/log/apache2",
        "/run/lock",
        "/var/lock/apache2",
        "/var/www",
    ]
    files: List[str] = [
        "/etc/apache2/apache2.conf",
        "/etc/apache2/envvars",
        "/var/www/index.html",
    ]
    executables: List[str] = ["apache2ctl"]
    dependencies: List[str] = []
    startup: List[str] = ["chown www-data /var/lock/apache2", "apache2ctl start"]
    validate: List[str] = ["pidof apache2"]
    shutdown: List[str] = ["apache2ctl stop"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ifaces = []
        for iface in self.node.get_ifaces(control=False):
            ifaces.append(iface)
        return dict(ifaces=ifaces)
