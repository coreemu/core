"""
ucarp.py: defines high-availability IP address controlled by ucarp
"""
from typing import Tuple

from core.nodes.base import CoreNode
from core.services.coreservices import CoreService

UCARP_ETC = "/usr/local/etc/ucarp"


class Ucarp(CoreService):
    name: str = "ucarp"
    group: str = "Utility"
    dirs: Tuple[str, ...] = (UCARP_ETC,)
    configs: Tuple[str, ...] = (
        UCARP_ETC + "/default.sh",
        UCARP_ETC + "/default-up.sh",
        UCARP_ETC + "/default-down.sh",
        "ucarpboot.sh",
    )
    startup: Tuple[str, ...] = ("bash ucarpboot.sh",)
    shutdown: Tuple[str, ...] = ("killall ucarp",)
    validate: Tuple[str, ...] = ("pidof ucarp",)

    @classmethod
    def generate_config(cls, node: CoreNode, filename: str) -> str:
        """
        Return the default file contents
        """
        if filename == cls.configs[0]:
            return cls.generate_ucarp_conf(node)
        elif filename == cls.configs[1]:
            return cls.generate_vip_up(node)
        elif filename == cls.configs[2]:
            return cls.generate_vip_down(node)
        elif filename == cls.configs[3]:
            return cls.generate_ucarp_boot(node)
        else:
            raise ValueError

    @classmethod
    def generate_ucarp_conf(cls, node: CoreNode) -> str:
        """
        Returns configuration file text.
        """
        ucarp_bin = node.session.options.get_config(
            "ucarp_bin", default="/usr/sbin/ucarp"
        )
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
""" % (
            ucarp_bin,
            UCARP_ETC,
        )

    @classmethod
    def generate_ucarp_boot(cls, node: CoreNode) -> str:
        """
        Generate a shell script used to boot the Ucarp daemons.
        """
        return (
            """\
#!/bin/sh
# Location of the UCARP config directory
UCARP_CFGDIR=%s

chmod a+x ${UCARP_CFGDIR}/*.sh

# Start the default ucarp daemon configuration
${UCARP_CFGDIR}/default.sh

"""
            % UCARP_ETC
        )

    @classmethod
    def generate_vip_up(cls, node: CoreNode) -> str:
        """
        Generate a shell script used to start the virtual ip
        """
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
    def generate_vip_down(cls, node: CoreNode) -> str:
        """
        Generate a shell script used to stop the virtual ip
        """
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
