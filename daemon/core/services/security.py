"""
security.py: defines security services (vpnclient, vpnserver, ipsec and
firewall)
"""

from core import constants
from core import logger
from core.service import CoreService


class VPNClient(CoreService):
    name = "VPNClient"
    group = "Security"
    configs = ('vpnclient.sh',)
    startindex = 60
    startup = ('sh vpnclient.sh',)
    shutdown = ("killall openvpn",)
    validate = ("pidof openvpn",)
    custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        """
        Return the client.conf and vpnclient.sh file contents to
        """
        cfg = "#!/bin/sh\n"
        cfg += "# custom VPN Client configuration for service (security.py)\n"
        fname = "%s/examples/services/sampleVPNClient" % constants.CORE_DATA_DIR

        try:
            cfg += open(fname, "rb").read()
        except IOError:
            logger.exception("Error opening VPN client configuration template (%s)", fname)

        return cfg


class VPNServer(CoreService):
    name = "VPNServer"
    group = "Security"
    configs = ('vpnserver.sh',)
    startindex = 50
    startup = ('sh vpnserver.sh',)
    shutdown = ("killall openvpn",)
    validate = ("pidof openvpn",)
    custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        """
        Return the sample server.conf and vpnserver.sh file contents to
        GUI for user customization.
        """
        cfg = "#!/bin/sh\n"
        cfg += "# custom VPN Server Configuration for service (security.py)\n"
        fname = "%s/examples/services/sampleVPNServer" % constants.CORE_DATA_DIR

        try:
            cfg += open(fname, "rb").read()
        except IOError:
            logger.exception("Error opening VPN server configuration template (%s)", fname)

        return cfg


class IPsec(CoreService):
    name = "IPsec"
    group = "Security"
    configs = ('ipsec.sh',)
    startindex = 60
    startup = ('sh ipsec.sh',)
    shutdown = ("killall racoon",)
    custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        """
        Return the ipsec.conf and racoon.conf file contents to
        GUI for user customization.
        """
        cfg = "#!/bin/sh\n"
        cfg += "# set up static tunnel mode security assocation for service "
        cfg += "(security.py)\n"
        fname = "%s/examples/services/sampleIPsec" % constants.CORE_DATA_DIR

        try:
            cfg += open(fname, "rb").read()
        except IOError:
            logger.exception("Error opening IPsec configuration template (%s)", fname)

        return cfg


class Firewall(CoreService):
    name = "Firewall"
    group = "Security"
    configs = ('firewall.sh',)
    startindex = 20
    startup = ('sh firewall.sh',)
    custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        """
        Return the firewall rule examples to GUI for user customization.
        """
        cfg = "#!/bin/sh\n"
        cfg += "# custom node firewall rules for service (security.py)\n"
        fname = "%s/examples/services/sampleFirewall" % constants.CORE_DATA_DIR

        try:
            cfg += open(fname, "rb").read()
        except IOError:
            logger.exception("Error opening Firewall configuration template (%s)", fname)

        return cfg
