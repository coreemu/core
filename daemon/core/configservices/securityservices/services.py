from typing import Any

from core.config import ConfigString, Configuration
from core.configservice.base import ConfigService, ConfigServiceMode

GROUP_NAME: str = "Security"


class VpnClient(ConfigService):
    name: str = "VPNClient"
    group: str = GROUP_NAME
    directories: list[str] = []
    files: list[str] = ["vpnclient.sh"]
    executables: list[str] = ["openvpn", "ip", "killall"]
    dependencies: list[str] = []
    startup: list[str] = ["bash vpnclient.sh"]
    validate: list[str] = ["pidof openvpn"]
    shutdown: list[str] = ["killall openvpn"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: list[Configuration] = [
        ConfigString(id="keydir", label="Key Dir", default="/etc/core/keys"),
        ConfigString(id="keyname", label="Key Name", default="client1"),
        ConfigString(id="server", label="Server", default="10.0.2.10"),
    ]
    modes: dict[str, dict[str, str]] = {}


class VpnServer(ConfigService):
    name: str = "VPNServer"
    group: str = GROUP_NAME
    directories: list[str] = []
    files: list[str] = ["vpnserver.sh"]
    executables: list[str] = ["openvpn", "ip", "killall"]
    dependencies: list[str] = []
    startup: list[str] = ["bash vpnserver.sh"]
    validate: list[str] = ["pidof openvpn"]
    shutdown: list[str] = ["killall openvpn"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: list[Configuration] = [
        ConfigString(id="keydir", label="Key Dir", default="/etc/core/keys"),
        ConfigString(id="keyname", label="Key Name", default="server"),
        ConfigString(id="subnet", label="Subnet", default="10.0.200.0"),
    ]
    modes: dict[str, dict[str, str]] = {}

    def data(self) -> dict[str, Any]:
        address = None
        for iface in self.node.get_ifaces(control=False):
            ip4 = iface.get_ip4()
            if ip4:
                address = str(ip4.ip)
                break
        return dict(address=address)


class IPsec(ConfigService):
    name: str = "IPsec"
    group: str = GROUP_NAME
    directories: list[str] = []
    files: list[str] = ["ipsec.sh"]
    executables: list[str] = ["racoon", "ip", "setkey", "killall"]
    dependencies: list[str] = []
    startup: list[str] = ["bash ipsec.sh"]
    validate: list[str] = ["pidof racoon"]
    shutdown: list[str] = ["killall racoon"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: list[Configuration] = []
    modes: dict[str, dict[str, str]] = {}


class Firewall(ConfigService):
    name: str = "Firewall"
    group: str = GROUP_NAME
    directories: list[str] = []
    files: list[str] = ["firewall.sh"]
    executables: list[str] = ["iptables"]
    dependencies: list[str] = []
    startup: list[str] = ["bash firewall.sh"]
    validate: list[str] = []
    shutdown: list[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: list[Configuration] = []
    modes: dict[str, dict[str, str]] = {}


class Nat(ConfigService):
    name: str = "NAT"
    group: str = GROUP_NAME
    directories: list[str] = []
    files: list[str] = ["nat.sh"]
    executables: list[str] = ["iptables"]
    dependencies: list[str] = []
    startup: list[str] = ["bash nat.sh"]
    validate: list[str] = []
    shutdown: list[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: list[Configuration] = []
    modes: dict[str, dict[str, str]] = {}

    def data(self) -> dict[str, Any]:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(ifnames=ifnames)
