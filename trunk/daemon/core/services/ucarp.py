#
# CORE configuration for UCARP 
# Copyright (c) 2012 Jonathan deBoer
# See the LICENSE file included in this distribution.
#
#
# author: Jonathan deBoer <jdccdevel@gmail.com>
#
'''
ucarp.py: defines high-availability IP address controlled by ucarp
'''

import os

from core.service import CoreService, addservice
from core.misc.ipaddr import IPv4Prefix
from core.constants import *


UCARP_ETC="/usr/local/etc/ucarp"

class Ucarp(CoreService):
    ''' 
    '''
    _name = "ucarp"
    _group = "Utility"
    _depends = ( )
    _dirs = (UCARP_ETC, )
    _configs = (UCARP_ETC + "/default.sh", UCARP_ETC + "/default-up.sh", UCARP_ETC + "/default-down.sh", "ucarpboot.sh",)
    _startindex = 65
    _startup = ("sh ucarpboot.sh",)
    _shutdown = ("killall ucarp", )
    _validate = ("pidof ucarp", )

    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Return the default file contents
        '''
        if filename == cls._configs[0]:
            return cls.generateUcarpConf(node, services)
        elif filename == cls._configs[1]:
            return cls.generateVipUp(node, services)
        elif filename == cls._configs[2]:
            return cls.generateVipDown(node, services)
        elif filename == cls._configs[3]:
            return cls.generateUcarpBoot(node, services)
        else:
            raise ValueError
        
    @classmethod
    def generateUcarpConf(cls, node, services):
        ''' Returns configuration file text. 
        '''
        try:
            ucarp_bin = node.session.cfg['ucarp_bin']
        except KeyError:
            ucarp_bin = "/usr/sbin/ucarp"
        return """\
#!/bin/sh
# Location of UCARP executable
UCARP_EXEC=%s

# Location of the UCARP config directory
UCARP_CFGDIR=%s

# Logging Facility
FACILITY=daemon

# Instance ID
# Any number from 1 to 255
INSTANCE_ID=1

# Password
# Master and Backup(s) need to be the same
PASSWORD="changeme"

# The failover application address
VIRTUAL_ADDRESS=127.0.0.254
VIRTUAL_NET=8

# Interface for IP Address
INTERFACE=lo

# Maintanence address of the local machine
SOURCE_ADDRESS=127.0.0.1

# The ratio number to be considered before marking the node as dead
DEAD_RATIO=3

# UCARP base, lower number will be preferred master
# set to same to have master stay as long as possible
UCARP_BASE=1
SKEW=0

# UCARP options
# -z run shutdown script on exit
# -P force preferred master
# -n don't run down script at start up when we are backup
# -M use broadcast instead of multicast
# -S ignore interface state
OPTIONS="-z -n -M"

# Send extra parameter to down and up scripts
#XPARAM="-x <enter param here>"
XPARAM="-x ${VIRTUAL_NET}"

# The start and stop scripts
START_SCRIPT=${UCARP_CFGDIR}/default-up.sh
STOP_SCRIPT=${UCARP_CFGDIR}/default-down.sh

# These line should not need to be touched
UCARP_OPTS="$OPTIONS -b $UCARP_BASE -k $SKEW -i $INTERFACE -v $INSTANCE_ID -p $PASSWORD -u $START_SCRIPT -d $STOP_SCRIPT -a $VIRTUAL_ADDRESS -s $SOURCE_ADDRESS -f $FACILITY $XPARAM"

${UCARP_EXEC} -B ${UCARP_OPTS} 
""" %  (ucarp_bin, UCARP_ETC)
    
    @classmethod
    def generateUcarpBoot(cls, node, services):
        ''' Generate a shell script used to boot the Ucarp daemons.
        '''
        try:
            ucarp_bin = node.session.cfg['ucarp_bin']
        except KeyError:
            ucarp_bin = "/usr/sbin/ucarp"
        return """\
#!/bin/sh
# Location of the UCARP config directory
UCARP_CFGDIR=%s

chmod a+x ${UCARP_CFGDIR}/*.sh

# Start the default ucarp daemon configuration
${UCARP_CFGDIR}/default.sh

""" % (UCARP_ETC)

    @classmethod
    def generateVipUp(cls, node, services):
        ''' Generate a shell script used to start the virtual ip
        '''
        try:
            ucarp_bin = node.session.cfg['ucarp_bin']
        except KeyError:
            ucarp_bin = "/usr/sbin/ucarp"
        return """\
#!/bin/bash

# Should be invoked as "default-up.sh <dev> <ip>"
exec 2> /dev/null

IP="${2}"
NET="${3}"
if [ -z "$NET" ]; then
	NET="24"
fi

/sbin/ip addr add ${IP}/${NET} dev "$1"


""" 

    @classmethod
    def generateVipDown(cls, node, services):
        ''' Generate a shell script used to stop the virtual ip
        '''
        try:
            ucarp_bin = node.session.cfg['ucarp_bin']
        except KeyError:
            ucarp_bin = "/usr/sbin/ucarp"
        return """\
#!/bin/bash

# Should be invoked as "default-down.sh <dev> <ip>"
exec 2> /dev/null

IP="${2}"
NET="${3}"
if [ -z "$NET" ]; then
	NET="24"
fi

/sbin/ip addr del ${IP}/${NET} dev "$1"


""" 


addservice(Ucarp)

