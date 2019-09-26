"""
Clients for dealing with bridge and interface commands.
"""

import abc
import os

from core import constants, utils


class NetworkClient(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def create_bridge(self, name):
        return NotImplemented


class BrctlClient(object):
    def create_bridge(self, name):
        utils.check_cmd([constants.BRCTL_BIN, "addbr", name])
        # disable spanning tree protocol and set forward delay to 0
        utils.check_cmd([constants.BRCTL_BIN, "stp", name, "off"])
        utils.check_cmd([constants.BRCTL_BIN, "setfd", name, "0"])
        utils.check_cmd([constants.IP_BIN, "link", "set", name, "up"])

        # turn off multicast snooping so forwarding occurs w/o IGMP joins
        snoop = "/sys/devices/virtual/net/%s/bridge/multicast_snooping" % name
        if os.path.exists(snoop):
            with open(snoop, "w") as f:
                f.write("0")

    def delete_bridge(self, name):
        utils.check_cmd([constants.IP_BIN, "link", "set", name, "down"])
        utils.check_cmd([constants.BRCTL_BIN, "delbr", name])

    def create_interface(self, bridge_name, interface_name):
        utils.check_cmd([constants.BRCTL_BIN, "addif", bridge_name, interface_name])
        utils.check_cmd([constants.IP_BIN, "link", "set", interface_name, "up"])

    def delete_interface(self, bridge_name, interface_name):
        utils.check_cmd([constants.BRCTL_BIN, "delif", bridge_name, interface_name])

    def get_bridges(self):
        return utils.check_cmd([constants.OVS_BIN, "list-br"])

    def disable_mac_learning(self, name):
        utils.check_cmd([constants.BRCTL_BIN, "setageing", name, "0"])


class OvsClient(object):
    def create_bridge(self, name):
        # turn off spanning tree protocol and forwarding delay
        # TODO: verify stp and rstp are always off by default
        # TODO: ovs only supports rstp forward delay and again it's off by default
        utils.check_cmd([constants.OVS_BIN, "add-br", name])
        utils.check_cmd([constants.IP_BIN, "link", "set", name, "up"])

    def delete_bridge(self, name):
        utils.check_cmd([constants.IP_BIN, "link", "set", name, "down"])
        utils.check_cmd([constants.OVS_BIN, "del-br", name])

    def create_interface(self, bridge_name, interface_name):
        utils.check_cmd([constants.OVS_BIN, "add-port", bridge_name, interface_name])
        utils.check_cmd([constants.IP_BIN, "link", "set", interface_name, "up"])

    def delete_interface(self, bridge_name, interface_name):
        utils.check_cmd([constants.OVS_BIN, "del-port", bridge_name, interface_name])

    def get_bridges(self):
        utils.check_cmd([constants.BRCTL_BIN, "show"])

    def disable_mac_learning(self, name):
        pass
