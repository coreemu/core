from typing import Any, Dict

import netaddr

from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emulator.enumerations import ConfigDataTypes

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
    default_configs = [
        Configuration(
            _id="keydir",
            _type=ConfigDataTypes.STRING,
            label="Key Dir",
            default="/etc/core/keys",
        ),
        Configuration(
            _id="keyname",
            _type=ConfigDataTypes.STRING,
            label="Key Name",
            default="client1",
        ),
        Configuration(
            _id="server",
            _type=ConfigDataTypes.STRING,
            label="Server",
            default="10.0.2.10",
        ),
    ]
    modes = {}


class VpnServer(ConfigService):
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
    default_configs = [
        Configuration(
            _id="keydir",
            _type=ConfigDataTypes.STRING,
            label="Key Dir",
            default="/etc/core/keys",
        ),
        Configuration(
            _id="keyname",
            _type=ConfigDataTypes.STRING,
            label="Key Name",
            default="server",
        ),
        Configuration(
            _id="subnet",
            _type=ConfigDataTypes.STRING,
            label="Subnet",
            default="10.0.200.0",
        ),
    ]
    modes = {}

    def data(self) -> Dict[str, Any]:
        address = None
        for iface in self.node.get_ifaces(control=False):
            for x in iface.addrlist:
                addr = x.split("/")[0]
                if netaddr.valid_ipv4(addr):
                    address = addr
        return dict(address=address)


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
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(ifnames=ifnames)
