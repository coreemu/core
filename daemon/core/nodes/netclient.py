"""
Clients for dealing with bridge/interface commands.
"""

import abc
import os

from future.utils import with_metaclass

from core.constants import BRCTL_BIN, IP_BIN, OVS_BIN
from core.utils import check_cmd


class NetClientBase(with_metaclass(abc.ABCMeta)):
    """
    Base client for running command line bridge/interface commands.
    """

    @abc.abstractmethod
    def create_bridge(self, name):
        """
        Create a network bridge to connect interfaces to.

        :param str name: bridge name
        :return: nothing
        """
        pass

    @abc.abstractmethod
    def delete_bridge(self, name):
        """
        Delete a network bridge.

        :param str name: bridge name
        :return: nothing
        """
        pass

    @abc.abstractmethod
    def create_interface(self, bridge_name, interface_name):
        """
        Create an interface associated with a network bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        pass

    @abc.abstractmethod
    def delete_interface(self, bridge_name, interface_name):
        """
        Delete an interface associated with a network bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        pass

    @abc.abstractmethod
    def existing_bridges(self, _id):
        """
        Checks if there are any existing bridges for a node.

        :param _id: node id to check bridges for
        """
        pass

    @abc.abstractmethod
    def disable_mac_learning(self, name):
        """
        Disable mac learning for a branch.

        :param str name: branch name
        :return: nothing
        """
        pass


class LinuxNetClient(NetClientBase):
    def create_bridge(self, name):
        check_cmd([BRCTL_BIN, "addbr", name])
        # disable spanning tree protocol and set forward delay to 0
        check_cmd([BRCTL_BIN, "stp", name, "off"])
        check_cmd([BRCTL_BIN, "setfd", name, "0"])
        check_cmd([IP_BIN, "link", "set", name, "up"])

        # turn off multicast snooping so forwarding occurs w/o IGMP joins
        snoop = "/sys/devices/virtual/net/%s/bridge/multicast_snooping" % name
        if os.path.exists(snoop):
            with open(snoop, "w") as f:
                f.write("0")

    def delete_bridge(self, name):
        check_cmd([IP_BIN, "link", "set", name, "down"])
        check_cmd([BRCTL_BIN, "delbr", name])

    def create_interface(self, bridge_name, interface_name):
        check_cmd([BRCTL_BIN, "addif", bridge_name, interface_name])
        check_cmd([IP_BIN, "link", "set", interface_name, "up"])

    def delete_interface(self, bridge_name, interface_name):
        check_cmd([BRCTL_BIN, "delif", bridge_name, interface_name])

    def existing_bridges(self, _id):
        output = check_cmd([BRCTL_BIN, "show"])
        lines = output.split("\n")
        for line in lines[1:]:
            columns = line.split()
            name = columns[0]
            fields = name.split(".")
            if len(fields) != 3:
                continue
            if fields[0] == "b" and fields[1] == _id:
                return True
        return False

    def disable_mac_learning(self, name):
        check_cmd([BRCTL_BIN, "setageing", name, "0"])


class OvsNetClient(NetClientBase):
    def create_bridge(self, name):
        # turn off spanning tree protocol and forwarding delay
        # TODO: verify stp and rstp are always off by default
        # TODO: ovs only supports rstp forward delay and again it's off by default
        check_cmd([OVS_BIN, "add-br", name])
        check_cmd([IP_BIN, "link", "set", name, "up"])

    def delete_bridge(self, name):
        check_cmd([IP_BIN, "link", "set", name, "down"])
        check_cmd([OVS_BIN, "del-br", name])

    def create_interface(self, bridge_name, interface_name):
        check_cmd([OVS_BIN, "add-port", bridge_name, interface_name])
        check_cmd([IP_BIN, "link", "set", interface_name, "up"])

    def delete_interface(self, bridge_name, interface_name):
        check_cmd([OVS_BIN, "del-port", bridge_name, interface_name])

    def existing_bridges(self, _id):
        output = check_cmd([OVS_BIN, "list-br"])
        if output:
            for line in output.split("\n"):
                fields = line.split(".")
                if fields[0] == "b" and fields[1] == _id:
                    return True
        return False

    def disable_mac_learning(self, name):
        check_cmd([OVS_BIN, "set", "bridge", name, "other_config:mac-aging-time=0"])
