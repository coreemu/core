"""
bird.py: defines routing services provided by the BIRD Internet Routing Daemon.
"""
from typing import Optional, Tuple

from core.nodes.base import CoreNode
from core.services.coreservices import CoreService


class Bird(CoreService):
    """
    Bird router support
    """

    name: str = "bird"
    group: str = "BIRD"
    executables: Tuple[str, ...] = ("bird",)
    dirs: Tuple[str, ...] = ("/etc/bird",)
    configs: Tuple[str, ...] = ("/etc/bird/bird.conf",)
    startup: Tuple[str, ...] = ("bird -c %s" % (configs[0]),)
    shutdown: Tuple[str, ...] = ("killall bird",)
    validate: Tuple[str, ...] = ("pidof bird",)

    @classmethod
    def generate_config(cls, node: CoreNode, filename: str) -> str:
        """
        Return the bird.conf file contents.
        """
        if filename == cls.configs[0]:
            return cls.generate_bird_config(node)
        else:
            raise ValueError

    @staticmethod
    def router_id(node: CoreNode) -> str:
        """
        Helper to return the first IPv4 address of a node as its router ID.
        """
        for iface in node.get_ifaces(control=False):
            ip4 = iface.get_ip4()
            if ip4:
                return str(ip4.ip)
        return "0.0.0.0"

    @classmethod
    def generate_bird_config(cls, node: CoreNode) -> str:
        """
        Returns configuration file text. Other services that depend on bird
        will have hooks that are invoked here.
        """
        cfg = """\
/* Main configuration file for BIRD. This is ony a template,
 * you will *need* to customize it according to your needs
 * Beware that only double quotes \'"\' are valid. No singles. */


log "/var/log/%s.log" all;
#debug protocols all;
#debug commands 2;

router id  %s;       # Mandatory for IPv6, may be automatic for IPv4

protocol kernel {
    persist;                # Don\'t remove routes on BIRD shutdown
    scan time 200;          # Scan kernel routing table every 200 seconds
    export all;
    import all;
}

protocol device {
    scan time 10;           # Scan interfaces every 10 seconds
}

""" % (
            cls.name,
            cls.router_id(node),
        )

        # generate protocol specific configurations
        for s in node.services:
            if cls.name not in s.dependencies:
                continue
            if not (isinstance(s, BirdService) or issubclass(s, BirdService)):
                continue
            cfg += s.generate_bird_config(node)
        return cfg


class BirdService(CoreService):
    """
    Parent class for Bird services. Defines properties and methods
    common to Bird's routing daemons.
    """

    name: Optional[str] = None
    group: str = "BIRD"
    executables: Tuple[str, ...] = ("bird",)
    dependencies: Tuple[str, ...] = ("bird",)
    meta: str = "The config file for this service can be found in the bird service."

    @classmethod
    def generate_bird_config(cls, node: CoreNode) -> str:
        return ""

    @classmethod
    def generate_bird_iface_config(cls, node: CoreNode) -> str:
        """
        Use only bare interfaces descriptions in generated protocol
        configurations. This has the slight advantage of being the same
        everywhere.
        """
        cfg = ""
        for iface in node.get_ifaces(control=False):
            cfg += '        interface "%s";\n' % iface.name
        return cfg


class BirdBgp(BirdService):
    """
    BGP BIRD Service (configuration generation)
    """

    name: str = "BIRD_BGP"
    custom_needed: bool = True

    @classmethod
    def generate_bird_config(cls, node: CoreNode) -> str:
        return """
/* This is a sample config that should be customized with appropriate AS numbers
 * and peers; add one section like this for each neighbor */

protocol bgp {
    local as 65000;                      # Customize your AS number
    neighbor 198.51.100.130 as 64496;    # Customize neighbor AS number && IP
    export filter {                      # We use non-trivial export rules
        # This is an example. You should advertise only *your routes*
        if (source = RTS_DEVICE) || (source = RTS_OSPF) then {
#           bgp_community.add((65000,64501)); # Assign our community
            accept;
        }
        reject;
    };
    import all;
}

"""


class BirdOspf(BirdService):
    """
    OSPF BIRD Service (configuration generation)
    """

    name: str = "BIRD_OSPFv2"

    @classmethod
    def generate_bird_config(cls, node: CoreNode) -> str:
        cfg = "protocol ospf {\n"
        cfg += "    export filter {\n"
        cfg += "        if source = RTS_BGP then {\n"
        cfg += "            ospf_metric1 = 100;\n"
        cfg += "            accept;\n"
        cfg += "        }\n"
        cfg += "        accept;\n"
        cfg += "    };\n"
        cfg += "    area 0.0.0.0 {\n"
        cfg += cls.generate_bird_iface_config(node)
        cfg += "    };\n"
        cfg += "}\n\n"
        return cfg


class BirdRadv(BirdService):
    """
    RADV BIRD Service (configuration generation)
    """

    name: str = "BIRD_RADV"

    @classmethod
    def generate_bird_config(cls, node: CoreNode) -> str:
        cfg = "/* This is a sample config that must be customized */\n"
        cfg += "protocol radv {\n"
        cfg += "    # auto configuration on all interfaces\n"
        cfg += cls.generate_bird_iface_config(node)
        cfg += "    # Advertise DNS\n"
        cfg += "    rdnss {\n"
        cfg += "#        lifetime mult 10;\n"
        cfg += "#        lifetime mult 10;\n"
        cfg += "#        ns 2001:0DB8:1234::11;\n"
        cfg += "#        ns 2001:0DB8:1234::11;\n"
        cfg += "#        ns 2001:0DB8:1234::12;\n"
        cfg += "#        ns 2001:0DB8:1234::12;\n"
        cfg += "    };\n"
        cfg += "}\n\n"
        return cfg


class BirdRip(BirdService):
    """
    RIP BIRD Service (configuration generation)
    """

    name: str = "BIRD_RIP"

    @classmethod
    def generate_bird_config(cls, node: CoreNode) -> str:
        cfg = "protocol rip {\n"
        cfg += "    period 10;\n"
        cfg += "    garbage time 60;\n"
        cfg += cls.generate_bird_iface_config(node)
        cfg += "    honor neighbor;\n"
        cfg += "    authentication none;\n"
        cfg += "    import all;\n"
        cfg += "    export all;\n"
        cfg += "}\n\n"
        return cfg


class BirdStatic(BirdService):
    """
    Static Bird Service (configuration generation)
    """

    name: str = "BIRD_static"
    custom_needed: bool = True

    @classmethod
    def generate_bird_config(cls, node: CoreNode) -> str:
        cfg = "/* This is a sample config that must be customized */\n"
        cfg += "protocol static {\n"
        cfg += "#    route 0.0.0.0/0 via 198.51.100.130; # Default route. Do NOT advertise on BGP !\n"
        cfg += "#    route 203.0.113.0/24 reject;        # Sink route\n"
        cfg += '#    route 10.2.0.0/24 via "arc0";       # Secondary network\n'
        cfg += "}\n\n"
        return cfg
