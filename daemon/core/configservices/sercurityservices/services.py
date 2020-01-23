from typing import Any, Dict

from core.configservice.base import ConfigService, ConfigServiceMode

GROUP_NAME = "Security"


class VpnClient(ConfigService):
    name = "VPNClient"
    group = GROUP_NAME
    directories = []
    files = ["vpnclient.sh"]
    executables = ["openvpn", "ip", "killall"]
    dependencies = []
    startup = ["sh vpnclient.sh"]
    validate = ["pidof openvpn"]
    shutdown = ["killall openvpn"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}


class VPNServer(ConfigService):
    name = "VPNServer"
    group = GROUP_NAME
    directories = []
    files = ["vpnserver.sh"]
    executables = ["openvpn", "ip", "killall"]
    dependencies = []
    startup = ["sh vpnserver.sh"]
    validate = ["pidof openvpn"]
    shutdown = ["killall openvpn"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}


class IPsec(ConfigService):
    name = "IPsec"
    group = GROUP_NAME
    directories = []
    files = ["ipsec.sh"]
    executables = ["racoon", "ip", "setkey", "killall"]
    dependencies = []
    startup = ["sh ipsec.sh"]
    validate = ["pidof racoon"]
    shutdown = ["killall racoon"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}


class Firewall(ConfigService):
    name = "Firewall"
    group = GROUP_NAME
    directories = []
    files = ["firewall.sh"]
    executables = ["iptables"]
    dependencies = []
    startup = ["sh firewall.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}


class Nat(ConfigService):
    name = "NAT"
    group = GROUP_NAME
    directories = []
    files = ["nat.sh"]
    executables = ["iptables"]
    dependencies = []
    startup = ["sh nat.sh"]
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for ifc in self.node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            ifnames.append(ifc.name)
        return dict(ifnames=ifnames)
