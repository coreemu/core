"""
security.py: defines security services (vpnclient, vpnserver, ipsec and
firewall)
"""

from core import constants
from core import logger
from core.service import CoreService
from core.service import ServiceManager


class VPNClient(CoreService):
    _name = "VPNClient"
    _group = "Security"
    _configs = ('vpnclient.sh',)
    _startindex = 60
    _startup = ('sh vpnclient.sh',)
    _shutdown = ("killall openvpn",)
    _validate = ("pidof openvpn",)
    _custom_needed = True

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
    _name = "VPNServer"
    _group = "Security"
    _configs = ('vpnserver.sh',)
    _startindex = 50
    _startup = ('sh vpnserver.sh',)
    _shutdown = ("killall openvpn",)
    _validate = ("pidof openvpn",)
    _custom_needed = True

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
    _name = "IPsec"
    _group = "Security"
    _configs = ('ipsec.sh',)
    _startindex = 60
    _startup = ('sh ipsec.sh',)
    _shutdown = ("killall racoon",)
    _custom_needed = True

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
    _name = "Firewall"
    _group = "Security"
    _configs = ('firewall.sh',)
    _startindex = 20
    _startup = ('sh firewall.sh',)
    _custom_needed = True

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


def load_services():
    # this line is required to add the above class to the list of available services
    ServiceManager.add(VPNClient)
    ServiceManager.add(VPNServer)
    ServiceManager.add(IPsec)
    ServiceManager.add(Firewall)
