from typing import Any, Dict, List

from core.config import ConfigString, Configuration
from core.configservice.base import ConfigService, ConfigServiceMode

GROUP_NAME: str = "Security"


class VpnClient(ConfigService):
    name: str = "VPNClient"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["vpnclient.sh"]
    executables: List[str] = ["openvpn", "ip", "killall"]
    dependencies: List[str] = []
    startup: List[str] = ["bash vpnclient.sh"]
    validate: List[str] = ["pidof openvpn"]
    shutdown: List[str] = ["killall openvpn"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = [
        ConfigString(id="keydir", label="Key Dir", default="/etc/core/keys"),
        ConfigString(id="keyname", label="Key Name", default="client1"),
        ConfigString(id="server", label="Server", default="10.0.2.10"),
    ]
    modes: Dict[str, Dict[str, str]] = {}


class VpnServer(ConfigService):
    name: str = "VPNServer"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["vpnserver.sh"]
    executables: List[str] = ["openvpn", "ip", "killall"]
    dependencies: List[str] = []
    startup: List[str] = ["bash vpnserver.sh"]
    validate: List[str] = ["pidof openvpn"]
    shutdown: List[str] = ["killall openvpn"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = [
        ConfigString(id="keydir", label="Key Dir", default="/etc/core/keys"),
        ConfigString(id="keyname", label="Key Name", default="server"),
        ConfigString(id="subnet", label="Subnet", default="10.0.200.0"),
    ]
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
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
    directories: List[str] = []
    files: List[str] = ["ipsec.sh"]
    executables: List[str] = ["racoon", "ip", "setkey", "killall"]
    dependencies: List[str] = []
    startup: List[str] = ["bash ipsec.sh"]
    validate: List[str] = ["pidof racoon"]
    shutdown: List[str] = ["killall racoon"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}


class Firewall(ConfigService):
    name: str = "Firewall"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["firewall.sh"]
    executables: List[str] = ["iptables"]
    dependencies: List[str] = []
    startup: List[str] = ["bash firewall.sh"]
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}


class Nat(ConfigService):
    name: str = "NAT"
    group: str = GROUP_NAME
    directories: List[str] = []
    files: List[str] = ["nat.sh"]
    executables: List[str] = ["iptables"]
    dependencies: List[str] = []
    startup: List[str] = ["bash nat.sh"]
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(ifnames=ifnames)
