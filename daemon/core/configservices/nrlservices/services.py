from typing import Any, Dict

import netaddr

from core import utils
from core.configservice.base import ConfigService, ConfigServiceMode

GROUP = "ProtoSvc"


class NrlService(ConfigService):
    name = "NrlBase"
    group = GROUP
    directories = []
    files = []
    executables = []
    dependencies = []
    startup = []
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}

    @classmethod
    def generate_config(cls, node, filename):
        return ""

    @staticmethod
    def firstipv4prefix(node, prefixlen=24):
        """
        Similar to QuaggaService.routerid(). Helper to return the first IPv4
        prefix of a node, using the supplied prefix length. This ignores the
        interface's prefix length, so e.g. '/32' can turn into '/24'.
        """
        for ifc in node.netifs():
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            for a in ifc.addrlist:
                a = a.split("/")[0]
                if netaddr.valid_ipv4(a):
                    return f"{a}/{prefixlen}"
        # raise ValueError,  "no IPv4 address found"
        return "0.0.0.0/%s" % prefixlen


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


class NrlNhdp(NrlService):
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
            if hasattr(ifc, "control") and ifc.control is True:
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
            if hasattr(ifc, "control") and ifc.control is True:
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
            if hasattr(ifc, "control") and ifc.control is True:
                continue
            ifname = ifc.name
            break
        return dict(has_smf=has_smf, has_zebra=has_zebra, ifname=ifname)
