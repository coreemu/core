#
# CORE - define security services : vpnclient, vpnserver, ipsec and firewall
#
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
''' 
security.py: defines security services (vpnclient, vpnserver, ipsec and 
firewall)
'''

import os

from core.service import CoreService, addservice
from core.constants import *

class VPNClient(CoreService):
    ''' 
    '''
    _name = "VPNClient"
    _group = "Security"
    _configs = ('vpnclient.sh', )
    _startindex = 60
    _startup = ('sh vpnclient.sh',)
    _shutdown = ("killall openvpn",)
    _validate = ("pidof openvpn", )
    _custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Return the client.conf and vpnclient.sh file contents to
        '''
        cfg = "#!/bin/sh\n"
        cfg += "# custom VPN Client configuration for service (security.py)\n"
        fname = "%s/examples/services/sampleVPNClient" % CORE_DATA_DIR
        try:
            cfg += open(fname, "rb").read()
        except e:
            print "Error opening VPN client configuration template (%s): %s" % \
                    (fname, e)
        return cfg

# this line is required to add the above class to the list of available services
addservice(VPNClient)

class VPNServer(CoreService):
    ''' 
    '''
    _name = "VPNServer"
    _group = "Security"
    _configs = ('vpnserver.sh', )
    _startindex = 50
    _startup = ('sh vpnserver.sh',)
    _shutdown = ("killall openvpn",)
    _validate = ("pidof openvpn", )
    _custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Return the sample server.conf and vpnserver.sh file contents to
            GUI for user customization.
        '''
        cfg = "#!/bin/sh\n"
        cfg += "# custom VPN Server Configuration for service (security.py)\n"
        fname = "%s/examples/services/sampleVPNServer" % CORE_DATA_DIR
        try:
            cfg += open(fname, "rb").read()
        except e:
            print "Error opening VPN server configuration template (%s): %s" % \
                    (fname, e)
        return cfg

addservice(VPNServer)

class IPsec(CoreService):
    '''
    '''
    _name = "IPsec"
    _group = "Security"
    _configs = ('ipsec.sh', )
    _startindex = 60
    _startup = ('sh ipsec.sh',)
    _shutdown = ("killall racoon",)
    _custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Return the ipsec.conf and racoon.conf file contents to
            GUI for user customization.
        '''
        cfg = "#!/bin/sh\n"
        cfg += "# set up static tunnel mode security assocation for service "
        cfg += "(security.py)\n"
        fname = "%s/examples/services/sampleIPsec" % CORE_DATA_DIR
        try:
            cfg += open(fname, "rb").read()
        except e:
            print "Error opening IPsec configuration template (%s): %s" % \
                    (fname, e)
        return cfg

addservice(IPsec)

class Firewall(CoreService):
    ''' 
    '''
    _name = "Firewall"
    _group = "Security"
    _configs = ('firewall.sh', )
    _startindex = 20
    _startup = ('sh firewall.sh',)
    _custom_needed = True

    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Return the firewall rule examples to GUI for user customization.
        '''
        cfg = "#!/bin/sh\n"
        cfg += "# custom node firewall rules for service (security.py)\n"
        fname = "%s/examples/services/sampleFirewall" % CORE_DATA_DIR
        try:
            cfg += open(fname, "rb").read()
        except e:
            print "Error opening Firewall configuration template (%s): %s" % \
                    (fname, e)
        return cfg

addservice(Firewall)

