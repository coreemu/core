from typing import Any, Dict

import netaddr

from core import utils
from core.configservice.base import ConfigService, ConfigServiceMode

GROUP = "ProtoSvc"


class MgenSinkService(ConfigService):
    name = "MGEN_Sink"
    group = GROUP
    directories = []
    files = ["mgensink.sh", "sink.mgen"]
    executables = ["mgen"]
    dependencies = []
    startup = ["sh mgensink.sh"]
    validate = ["pidof mgen"]
    shutdown = ["killall mgen"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        ifnames = []
        for ifc in self.node.netifs():
            name = utils.sysctl_devname(ifc.name)
            ifnames.append(name)
        return dict(ifnames=ifnames)


class NrlNhdp(ConfigService):
    name = "NHDP"
    group = GROUP
    directories = []
    files = ["nrlnhdp.sh"]
    executables = ["nrlnhdp"]
    dependencies = []
    startup = ["sh nrlnhdp.sh"]
    validate = ["pidof nrlnhdp"]
    shutdown = ["killall nrlnhdp"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        ifnames = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
        return dict(has_smf=has_smf, ifnames=ifnames)


class NrlSmf(ConfigService):
    name = "SMF"
    group = GROUP
    directories = []
    files = ["startsmf.sh"]
    executables = ["nrlsmf", "killall"]
    dependencies = []
    startup = ["sh startsmf.sh"]
    validate = ["pidof nrlsmf"]
    shutdown = ["killall nrlsmf"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        has_arouted = "arouted" in self.node.config_services
        has_nhdp = "NHDP" in self.node.config_services
        has_olsr = "OLSR" in self.node.config_services
        ifnames = []
        ip4_prefix = None
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
            if ip4_prefix:
                continue
            for a in ifc.addrlist:
                a = a.split("/")[0]
                if netaddr.valid_ipv4(a):
                    ip4_prefix = f"{a}/{24}"
                    break
        return dict(
            has_arouted=has_arouted,
            has_nhdp=has_nhdp,
            has_olsr=has_olsr,
            ifnames=ifnames,
            ip4_prefix=ip4_prefix,
        )


class NrlOlsr(ConfigService):
    name = "OLSR"
    group = GROUP
    directories = []
    files = ["nrlolsrd.sh"]
    executables = ["nrlolsrd"]
    dependencies = []
    startup = ["sh nrlolsrd.sh"]
    validate = ["pidof nrlolsrd"]
    shutdown = ["killall nrlolsrd"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        has_zebra = "zebra" in self.node.config_services
        ifname = None
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifname = ifc.name
            break
        return dict(has_smf=has_smf, has_zebra=has_zebra, ifname=ifname)


class NrlOlsrv2(ConfigService):
    name = "OLSRv2"
    group = GROUP
    directories = []
    files = ["nrlolsrv2.sh"]
    executables = ["nrlolsrv2"]
    dependencies = []
    startup = ["sh nrlolsrv2.sh"]
    validate = ["pidof nrlolsrv2"]
    shutdown = ["killall nrlolsrv2"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        ifnames = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
        return dict(has_smf=has_smf, ifnames=ifnames)


class OlsrOrg(ConfigService):
    name = "OLSRORG"
    group = GROUP
    directories = ["/etc/olsrd"]
    files = ["olsrd.sh", "/etc/olsrd/olsrd.conf"]
    executables = ["olsrd"]
    dependencies = []
    startup = ["sh olsrd.sh"]
    validate = ["pidof olsrd"]
    shutdown = ["killall olsrd"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        has_smf = "SMF" in self.node.config_services
        ifnames = []
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            ifnames.append(ifc.name)
        return dict(has_smf=has_smf, ifnames=ifnames)


class MgenActor(ConfigService):
    name = "MgenActor"
    group = GROUP
    directories = []
    files = ["start_mgen_actor.sh"]
    executables = ["mgen"]
    dependencies = []
    startup = ["sh start_mgen_actor.sh"]
    validate = ["pidof mgen"]
    shutdown = ["killall mgen"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}


class Arouted(ConfigService):
    name = "arouted"
    group = GROUP
    directories = []
    files = ["startarouted.sh"]
    executables = ["arouted"]
    dependencies = []
    startup = ["sh startarouted.sh"]
    validate = ["pidof arouted"]
    shutdown = ["pkill arouted"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    def data(self) -> Dict[str, Any]:
        ip4_prefix = None
        for ifc in self.node.netifs():
            if getattr(ifc, "control", False):
                continue
            if ip4_prefix:
                continue
            for a in ifc.addrlist:
                a = a.split("/")[0]
                if netaddr.valid_ipv4(a):
                    ip4_prefix = f"{a}/{24}"
                    break
        return dict(ip4_prefix=ip4_prefix)
