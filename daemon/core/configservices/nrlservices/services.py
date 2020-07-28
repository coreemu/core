from typing import Any, Dict, List

from core import utils
from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode

GROUP: str = "ProtoSvc"


class MgenSinkService(ConfigService):
    name: str = "MGEN_Sink"
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = ["mgensink.sh", "sink.mgen"]
    executables: List[str] = ["mgen"]
    dependencies: List[str] = []
    startup: List[str] = ["bash mgensink.sh"]
    validate: List[str] = ["pidof mgen"]
    shutdown: List[str] = ["killall mgen"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for iface in self.node.get_ifaces():
            name = utils.sysctl_devname(iface.name)
            ifnames.append(name)
        return dict(ifnames=ifnames)


class NrlNhdp(ConfigService):
    name: str = "NHDP"
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = ["nrlnhdp.sh"]
    executables: List[str] = ["nrlnhdp"]
    dependencies: List[str] = []
    startup: List[str] = ["bash nrlnhdp.sh"]
    validate: List[str] = ["pidof nrlnhdp"]
    shutdown: List[str] = ["killall nrlnhdp"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(has_smf=has_smf, ifnames=ifnames)


class NrlSmf(ConfigService):
    name: str = "SMF"
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = ["startsmf.sh"]
    executables: List[str] = ["nrlsmf", "killall"]
    dependencies: List[str] = []
    startup: List[str] = ["bash startsmf.sh"]
    validate: List[str] = ["pidof nrlsmf"]
    shutdown: List[str] = ["killall nrlsmf"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        has_arouted = "arouted" in self.node.config_services
        has_nhdp = "NHDP" in self.node.config_services
        has_olsr = "OLSR" in self.node.config_services
        ifnames = []
        ip4_prefix = None
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
            ip4 = iface.get_ip4()
            if ip4:
                ip4_prefix = f"{ip4.ip}/{24}"
                break
        return dict(
            has_arouted=has_arouted,
            has_nhdp=has_nhdp,
            has_olsr=has_olsr,
            ifnames=ifnames,
            ip4_prefix=ip4_prefix,
        )


class NrlOlsr(ConfigService):
    name: str = "OLSR"
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = ["nrlolsrd.sh"]
    executables: List[str] = ["nrlolsrd"]
    dependencies: List[str] = []
    startup: List[str] = ["bash nrlolsrd.sh"]
    validate: List[str] = ["pidof nrlolsrd"]
    shutdown: List[str] = ["killall nrlolsrd"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        has_zebra = "zebra" in self.node.config_services
        ifname = None
        for iface in self.node.get_ifaces(control=False):
            ifname = iface.name
            break
        return dict(has_smf=has_smf, has_zebra=has_zebra, ifname=ifname)


class NrlOlsrv2(ConfigService):
    name: str = "OLSRv2"
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = ["nrlolsrv2.sh"]
    executables: List[str] = ["nrlolsrv2"]
    dependencies: List[str] = []
    startup: List[str] = ["bash nrlolsrv2.sh"]
    validate: List[str] = ["pidof nrlolsrv2"]
    shutdown: List[str] = ["killall nrlolsrv2"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(has_smf=has_smf, ifnames=ifnames)


class OlsrOrg(ConfigService):
    name: str = "OLSRORG"
    group: str = GROUP
    directories: List[str] = ["/etc/olsrd"]
    files: List[str] = ["olsrd.sh", "/etc/olsrd/olsrd.conf"]
    executables: List[str] = ["olsrd"]
    dependencies: List[str] = []
    startup: List[str] = ["bash olsrd.sh"]
    validate: List[str] = ["pidof olsrd"]
    shutdown: List[str] = ["killall olsrd"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        ifnames = []
        for iface in self.node.get_ifaces(control=False):
            ifnames.append(iface.name)
        return dict(has_smf=has_smf, ifnames=ifnames)


class MgenActor(ConfigService):
    name: str = "MgenActor"
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = ["start_mgen_actor.sh"]
    executables: List[str] = ["mgen"]
    dependencies: List[str] = []
    startup: List[str] = ["bash start_mgen_actor.sh"]
    validate: List[str] = ["pidof mgen"]
    shutdown: List[str] = ["killall mgen"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}


class Arouted(ConfigService):
    name: str = "arouted"
    group: str = GROUP
    directories: List[str] = []
    files: List[str] = ["startarouted.sh"]
    executables: List[str] = ["arouted"]
    dependencies: List[str] = []
    startup: List[str] = ["bash startarouted.sh"]
    validate: List[str] = ["pidof arouted"]
    shutdown: List[str] = ["pkill arouted"]
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}

    def data(self) -> Dict[str, Any]:
        ip4_prefix = None
        for iface in self.node.get_ifaces(control=False):
            ip4 = iface.get_ip4()
            if ip4:
                ip4_prefix = f"{ip4.ip}/{24}"
                break
        return dict(ip4_prefix=ip4_prefix)
