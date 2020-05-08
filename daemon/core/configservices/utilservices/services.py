from typing import Any, Dict

import netaddr

from core import utils
from core.configservice.base import ConfigService, ConfigServiceMode

GROUP_NAME = "Utility"


class DefaultRouteService(ConfigService):
    name = "DefaultRoute"
    group = GROUP_NAME
    directories = []
    files = ["defaultroute.sh"]
    executables = ["ip"]
    dependencies = []
    startup = ["sh defaultroute.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        # only add default routes for linked routing nodes
        routes = []
        netifs = self.node.netifs(sort=True)
        if netifs:
            netif = netifs[0]
            for x in netif.addrlist:
                net = netaddr.IPNetwork(x).cidr
                if net.size > 1:
                    router = net[1]
                    routes.append(str(router))
        return dict(routes=routes)


class DefaultMulticastRouteService(ConfigService):
    name = "DefaultMulticastRoute"
    group = GROUP_NAME
    directories = []
    files = ["defaultmroute.sh"]
    executables = []
    dependencies = []
    startup = ["sh defaultmroute.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        ifname = None
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifname = ifc.name
            break
        return dict(ifname=ifname)


class StaticRouteService(ConfigService):
    name = "StaticRoute"
    group = GROUP_NAME
    directories = []
    files = ["staticroute.sh"]
    executables = []
    dependencies = []
    startup = ["sh staticroute.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        routes = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            for x in ifc.addrlist:
                addr = x.split("/")[0]
                if netaddr.valid_ipv6(addr):
                    dst = "3ffe:4::/64"
                else:
                    dst = "10.9.8.0/24"
                net = netaddr.IPNetwork(x)
                if net[-2] != net[1]:
                    routes.append((dst, net[1]))
        return dict(routes=routes)


class IpForwardService(ConfigService):
    name = "IPForward"
    group = GROUP_NAME
    directories = []
    files = ["ipforward.sh"]
    executables = ["sysctl"]
    dependencies = []
    startup = ["sh ipforward.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        devnames = []
        for ifc in self.node.netifs():
            devname = utils.sysctl_devname(ifc.name)
            devnames.append(devname)
        return dict(devnames=devnames)


class SshService(ConfigService):
    name = "SSH"
    group = GROUP_NAME
    directories = ["/etc/ssh", "/var/run/sshd"]
    files = ["startsshd.sh", "/etc/ssh/sshd_config"]
    executables = ["sshd"]
    dependencies = []
    startup = ["sh startsshd.sh"]
    validate = []
    shutdown = ["killall sshd"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        return dict(
            sshcfgdir=self.directories[0],
            sshstatedir=self.directories[1],
            sshlibdir="/usr/lib/openssh",
        )


class DhcpService(ConfigService):
    name = "DHCP"
    group = GROUP_NAME
    directories = ["/etc/dhcp", "/var/lib/dhcp"]
    files = ["/etc/dhcp/dhcpd.conf"]
    executables = ["dhcpd"]
    dependencies = []
    startup = ["touch /var/lib/dhcp/dhcpd.leases", "dhcpd"]
    validate = ["pidof dhcpd"]
    shutdown = ["killall dhcpd"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        subnets = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            for x in ifc.addrlist:
                addr = x.split("/")[0]
                if netaddr.valid_ipv4(addr):
                    net = netaddr.IPNetwork(x)
                    # divide the address space in half
                    index = (net.size - 2) / 2
                    rangelow = net[index]
                    rangehigh = net[-2]
                    subnets.append((net.ip, net.netmask, rangelow, rangehigh, addr))
        return dict(subnets=subnets)


class DhcpClientService(ConfigService):
    name = "DHCPClient"
    group = GROUP_NAME
    directories = []
    files = ["startdhcpclient.sh"]
    executables = ["dhclient"]
    dependencies = []
    startup = ["sh startdhcpclient.sh"]
    validate = ["pidof dhclient"]
    shutdown = ["killall dhclient"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
        return dict(ifnames=ifnames)


class FtpService(ConfigService):
    name = "FTP"
    group = GROUP_NAME
    directories = ["/var/run/vsftpd/empty", "/var/ftp"]
    files = ["vsftpd.conf"]
    executables = ["vsftpd"]
    dependencies = []
    startup = ["vsftpd ./vsftpd.conf"]
    validate = ["pidof vsftpd"]
    shutdown = ["killall vsftpd"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}


class PcapService(ConfigService):
    name = "pcap"
    group = GROUP_NAME
    directories = []
    files = ["pcap.sh"]
    executables = ["tcpdump"]
    dependencies = []
    startup = ["sh pcap.sh start"]
    validate = ["pidof tcpdump"]
    shutdown = ["sh pcap.sh stop"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
        return dict()


class RadvdService(ConfigService):
    name = "radvd"
    group = GROUP_NAME
    directories = ["/etc/radvd"]
    files = ["/etc/radvd/radvd.conf"]
    executables = ["radvd"]
    dependencies = []
    startup = ["radvd -C /etc/radvd/radvd.conf -m logfile -l /var/log/radvd.log"]
    validate = ["pidof radvd"]
    shutdown = ["pkill radvd"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        interfaces = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            prefixes = []
            for x in ifc.addrlist:
                addr = x.split("/")[0]
                if netaddr.valid_ipv6(addr):
                    prefixes.append(x)
            if not prefixes:
                continue
            interfaces.append((ifc.name, prefixes))
        return dict(interfaces=interfaces)


class AtdService(ConfigService):
    name = "atd"
    group = GROUP_NAME
    directories = ["/var/spool/cron/atjobs", "/var/spool/cron/atspool"]
    files = ["startatd.sh"]
    executables = ["atd"]
    dependencies = []
    startup = ["sh startatd.sh"]
    validate = ["pidof atd"]
    shutdown = ["pkill atd"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}


class HttpService(ConfigService):
    name = "HTTP"
    group = GROUP_NAME
    directories = [
        "/etc/apache2",
        "/var/run/apache2",
        "/var/log/apache2",
        "/run/lock",
        "/var/lock/apache2",
        "/var/www",
    ]
    files = ["/etc/apache2/apache2.conf", "/etc/apache2/envvars", "/var/www/index.html"]
    executables = ["apache2ctl"]
    dependencies = []
    startup = ["chown www-data /var/lock/apache2", "apache2ctl start"]
    validate = ["pidof apache2"]
    shutdown = ["apache2ctl stop"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        interfaces = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            interfaces.append(ifc)
        return dict(interfaces=interfaces)
