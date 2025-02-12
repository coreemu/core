from typing import Any

import netaddr

from core import utils
from core.services.base import CoreService

GROUP_NAME = "Utility"


class DefaultRouteService(CoreService):
    name: str = "DefaultRoute"
    group: str = GROUP_NAME
    files: list[str] = ["defaultroute.sh"]
    executables: list[str] = ["ip"]
    startup: list[str] = ["bash defaultroute.sh"]

    def data(self) -> dict[str, Any]:
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


class DefaultMulticastRouteService(CoreService):
    name: str = "DefaultMulticastRoute"
    group: str = GROUP_NAME
    files: list[str] = ["defaultmroute.sh"]
    startup: list[str] = ["bash defaultmroute.sh"]

    def data(self) -> dict[str, Any]:
        ifname = None
        for iface in self.node.get_ifaces(control=False):
            ifname = iface.name
            break
        return dict(ifname=ifname)


class StaticRouteService(CoreService):
    name: str = "StaticRoute"
    group: str = GROUP_NAME
    files: list[str] = ["staticroute.sh"]
    startup: list[str] = ["bash staticroute.sh"]

    def data(self) -> dict[str, Any]:
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


class IpForwardService(CoreService):
    name: str = "IPForward"
    group: str = GROUP_NAME
    files: list[str] = ["ipforward.sh"]
    executables: list[str] = ["sysctl"]
    startup: list[str] = ["bash ipforward.sh"]

    def data(self) -> dict[str, Any]:
        devnames = []
        for iface in self.node.get_ifaces():
            devname = utils.sysctl_devname(iface.name)
            devnames.append(devname)
        return dict(devnames=devnames)


class SshService(CoreService):
    name: str = "SSH"
    group: str = GROUP_NAME
    directories: list[str] = ["/etc/ssh", "/var/run/sshd"]
    files: list[str] = ["startsshd.sh", "/etc/ssh/sshd_config"]
    executables: list[str] = ["sshd"]
    startup: list[str] = ["bash startsshd.sh"]
    shutdown: list[str] = ["pkill -f sshd"]

    def data(self) -> dict[str, Any]:
        return dict(
            sshcfgdir=self.directories[0],
            sshstatedir=self.directories[1],
            sshlibdir="/usr/lib/openssh",
        )


class DhcpService(CoreService):
    name: str = "DHCP"
    group: str = GROUP_NAME
    directories: list[str] = ["/etc/dhcp", "/var/lib/dhcp"]
    files: list[str] = ["/etc/dhcp/dhcpd.conf"]
    executables: list[str] = ["dhcpd"]
    startup: list[str] = ["touch /var/lib/dhcp/dhcpd.leases", "dhcpd"]
    validate: list[str] = ["pidof dhcpd"]
    shutdown: list[str] = ["pkill -f dhcpd"]

    def data(self) -> dict[str, Any]:
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


class DhcpClientService(CoreService):
    name: str = "DHCPClient"
    group: str = GROUP_NAME
    files: list[str] = ["startdhcpclient.sh"]
    executables: list[str] = ["dhclient"]
    startup: list[str] = ["bash startdhcpclient.sh"]
    validate: list[str] = ["pidof dhclient"]
    shutdown: list[str] = ["pkill -f dhclient"]

    def data(self) -> dict[str, Any]:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(ifnames=ifnames)


class FtpService(CoreService):
    name: str = "FTP"
    group: str = GROUP_NAME
    directories: list[str] = ["/var/run/vsftpd/empty", "/var/ftp"]
    files: list[str] = ["vsftpd.conf"]
    executables: list[str] = ["vsftpd"]
    startup: list[str] = ["vsftpd ./vsftpd.conf"]
    validate: list[str] = ["pidof vsftpd"]
    shutdown: list[str] = ["pkill -f vsftpd"]


class PcapService(CoreService):
    name: str = "pcap"
    group: str = GROUP_NAME
    files: list[str] = ["pcap.sh"]
    executables: list[str] = ["tcpdump"]
    startup: list[str] = ["bash pcap.sh start"]
    validate: list[str] = ["pidof tcpdump"]
    shutdown: list[str] = ["bash pcap.sh stop"]

    def data(self) -> dict[str, Any]:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(ifnames=ifnames)


class RadvdService(CoreService):
    name: str = "radvd"
    group: str = GROUP_NAME
    directories: list[str] = ["/etc/radvd", "/var/run/radvd"]
    files: list[str] = ["/etc/radvd/radvd.conf"]
    executables: list[str] = ["radvd"]
    startup: list[str] = [
        "radvd -C /etc/radvd/radvd.conf -m logfile -l /var/log/radvd.log"
    ]
    validate: list[str] = ["pidof radvd"]
    shutdown: list[str] = ["pkill radvd"]

    def data(self) -> dict[str, Any]:
        ifaces = []
        for iface in self.node.get_ifaces(control=False):
            prefixes = []
            for ip6 in iface.ip6s:
                prefixes.append(str(ip6))
            if not prefixes:
                continue
            ifaces.append((iface.name, prefixes))
        return dict(ifaces=ifaces)


class AtdService(CoreService):
    name: str = "atd"
    group: str = GROUP_NAME
    directories: list[str] = ["/var/spool/cron/atjobs", "/var/spool/cron/atspool"]
    files: list[str] = ["startatd.sh"]
    executables: list[str] = ["atd"]
    startup: list[str] = ["bash startatd.sh"]
    validate: list[str] = ["pidof atd"]
    shutdown: list[str] = ["pkill atd"]


class HttpService(CoreService):
    name: str = "HTTP"
    group: str = GROUP_NAME
    directories: list[str] = [
        "/etc/apache2",
        "/var/run/apache2",
        "/var/log/apache2",
        "/run/lock",
        "/var/lock/apache2",
        "/var/www",
    ]
    files: list[str] = [
        "/etc/apache2/apache2.conf",
        "/etc/apache2/envvars",
        "/var/www/index.html",
    ]
    executables: list[str] = ["apache2ctl"]
    startup: list[str] = ["chown www-data /var/lock/apache2", "apache2ctl start"]
    validate: list[str] = ["pidof apache2"]
    shutdown: list[str] = ["apache2ctl stop"]

    def data(self) -> dict[str, Any]:
        ifaces = []
        for iface in self.node.get_ifaces(control=False):
            ifaces.append(iface)
        return dict(ifaces=ifaces)
