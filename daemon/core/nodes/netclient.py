"""
Clients for dealing with bridge/interface commands.
"""

import os

from core.constants import BRCTL_BIN, ETHTOOL_BIN, IP_BIN, OVS_BIN, TC_BIN
from core.utils import check_cmd


class LinuxNetClient(object):
    """
    Client for creating Linux bridges and ip interfaces for nodes.
    """

    def __init__(self, run_func):
        self.run_func = run_func

    def run(self, cmd):
        return self.run_func(cmd)

    def set_hostname(self, name):
        self.run(["hostname", name])

    def add_route(self, route, device):
        self.run([IP_BIN, "route", "add", route, "dev", device])

    def device_up(self, device):
        self.run([IP_BIN, "link", "set", device, "up"])

    def device_down(self, device):
        self.run([IP_BIN, "link", "set", device, "down"])

    def device_name(self, device, name):
        self.run([IP_BIN, "link", "set", device, "name", name])

    def device_show(self, device):
        return self.run([IP_BIN, "link", "show", device])

    def device_ns(self, device, namespace):
        self.run([IP_BIN, "link", "set", device, "netns", namespace])

    def device_flush(self, device):
        self.run([IP_BIN, "-6", "address", "flush", "dev", device])

    def device_mac(self, device, mac):
        self.run([IP_BIN, "link", "set", "dev", device, "address", mac])

    def delete_device(self, device):
        self.run([IP_BIN, "link", "delete", device])

    def delete_tc(self, device):
        self.run([TC_BIN, "qdisc", "del", "dev", device, "root"])

    def checksums_off(self, interface_name):
        self.run([ETHTOOL_BIN, "-K", interface_name, "rx", "off", "tx", "off"])

    def delete_address(self, device, address):
        self.run([IP_BIN, "address", "delete", address, "dev", device])

    def create_veth(self, name, peer):
        self.run(
            [IP_BIN, "link", "add", "name", name, "type", "veth", "peer", "name", peer]
        )

    def create_gretap(self, device, address, local, ttl, key):
        cmd = [IP_BIN, "link", "add", device, "type", "gretap", "remote", address]
        if local is not None:
            cmd.extend(["local", local])
        if ttl is not None:
            cmd.extend(["ttl", ttl])
        if key is not None:
            cmd.extend(["key", key])
        self.run(cmd)

    def create_address(self, device, address, broadcast=None):
        if broadcast is not None:
            self.run(
                [
                    IP_BIN,
                    "address",
                    "add",
                    address,
                    "broadcast",
                    broadcast,
                    "dev",
                    device,
                ]
            )
        else:
            self.run([IP_BIN, "address", "add", address, "dev", device])

    def create_bridge(self, name):
        """
        Create a Linux bridge and bring it up.

        :param str name: bridge name
        :return: nothing
        """
        self.run([BRCTL_BIN, "addbr", name])
        self.run([BRCTL_BIN, "stp", name, "off"])
        self.run([BRCTL_BIN, "setfd", name, "0"])
        self.device_up(name)

        # turn off multicast snooping so forwarding occurs w/o IGMP joins
        snoop = "/sys/devices/virtual/net/%s/bridge/multicast_snooping" % name
        if os.path.exists(snoop):
            with open(snoop, "w") as f:
                f.write("0")

    def delete_bridge(self, name):
        """
        Bring down and delete a Linux bridge.

        :param str name: bridge name
        :return: nothing
        """
        self.device_down(name)
        self.run([BRCTL_BIN, "delbr", name])

    def create_interface(self, bridge_name, interface_name):
        """
        Create an interface associated with a Linux bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run([BRCTL_BIN, "addif", bridge_name, interface_name])
        self.device_up(interface_name)

    def delete_interface(self, bridge_name, interface_name):
        """
        Delete an interface associated with a Linux bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run([BRCTL_BIN, "delif", bridge_name, interface_name])

    def existing_bridges(self, _id):
        """
        Checks if there are any existing Linux bridges for a node.

        :param _id: node id to check bridges for
        """
        output = self.run([BRCTL_BIN, "show"])
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
        """
        Disable mac learning for a Linux bridge.

        :param str name: bridge name
        :return: nothing
        """
        check_cmd([BRCTL_BIN, "setageing", name, "0"])


class OvsNetClient(LinuxNetClient):
    """
    Client for creating OVS bridges and ip interfaces for nodes.
    """

    def create_bridge(self, name):
        """
        Create a OVS bridge and bring it up.

        :param str name: bridge name
        :return: nothing
        """
        self.run([OVS_BIN, "add-br", name])
        self.run([OVS_BIN, "set", "bridge", name, "stp_enable=false"])
        self.run([OVS_BIN, "set", "bridge", name, "other_config:stp-max-age=6"])
        self.run([OVS_BIN, "set", "bridge", name, "other_config:stp-forward-delay=4"])
        self.device_up(name)

    def delete_bridge(self, name):
        """
        Bring down and delete a OVS bridge.

        :param str name: bridge name
        :return: nothing
        """
        self.device_down(name)
        self.run([OVS_BIN, "del-br", name])

    def create_interface(self, bridge_name, interface_name):
        """
        Create an interface associated with a network bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run([OVS_BIN, "add-port", bridge_name, interface_name])
        self.device_up(interface_name)

    def delete_interface(self, bridge_name, interface_name):
        """
        Delete an interface associated with a OVS bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run([OVS_BIN, "del-port", bridge_name, interface_name])

    def existing_bridges(self, _id):
        """
        Checks if there are any existing OVS bridges for a node.

        :param _id: node id to check bridges for
        """
        output = self.run([OVS_BIN, "list-br"])
        if output:
            for line in output.split("\n"):
                fields = line.split(".")
                if fields[0] == "b" and fields[1] == _id:
                    return True
        return False

    def disable_mac_learning(self, name):
        """
        Disable mac learning for a OVS bridge.

        :param str name: bridge name
        :return: nothing
        """
        self.run([OVS_BIN, "set", "bridge", name, "other_config:mac-aging-time=0"])
