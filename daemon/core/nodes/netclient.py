"""
Clients for dealing with bridge/interface commands.
"""

import os

from core.constants import BRCTL_BIN, ETHTOOL_BIN, IP_BIN, OVS_BIN, TC_BIN


def get_net_client(use_ovs, run):
    """
    Retrieve desired net client for running network commands.

    :param bool use_ovs: True for OVS bridges, False for Linux bridges
    :param func run: function used to run net client commands
    :return: net client class
    """
    if use_ovs:
        return OvsNetClient(run)
    else:
        return LinuxNetClient(run)


class LinuxNetClient(object):
    """
    Client for creating Linux bridges and ip interfaces for nodes.
    """

    def __init__(self, run):
        """
        Create LinuxNetClient instance.

        :param run: function to run commands with
        """
        self.run = run

    def set_hostname(self, name):
        """
        Set network hostname.

        :param str name: name for hostname
        :return: nothing
        """
        self.run("hostname %s" % name)

    def create_route(self, route, device):
        """
        Create a new route for a device.

        :param str route: route to create
        :param str device: device to add route to
        :return: nothing
        """
        self.run("%s route add %s dev %s" % (IP_BIN, route, device))

    def device_up(self, device):
        """
        Bring a device up.

        :param str device: device to bring up
        :return: nothing
        """
        self.run("%s link set %s up" % (IP_BIN, device))

    def device_down(self, device):
        """
        Bring a device down.

        :param str device: device to bring down
        :return: nothing
        """
        self.run("%s link set %s down" % (IP_BIN, device))

    def device_name(self, device, name):
        """
        Set a device name.

        :param str device: device to set name for
        :param str name: name to set
        :return: nothing
        """
        self.run("%s link set %s name %s" % (IP_BIN, device, name))

    def device_show(self, device):
        """
        Show information for a device.

        :param str device: device to get information for
        :return: device information
        :rtype: str
        """
        return self.run("%s link show %s" % (IP_BIN, device))

    def device_ns(self, device, namespace):
        """
        Set netns for a device.

        :param str device: device to setns for
        :param str namespace: namespace to set device to
        :return: nothing
        """
        self.run("%s link set %s netns %s" % (IP_BIN, device, namespace))

    def device_flush(self, device):
        """
        Flush device addresses.

        :param str device: device to flush
        :return: nothing
        """
        self.run("%s -6 address flush dev %s" % (IP_BIN, device))

    def device_mac(self, device, mac):
        """
        Set MAC address for a device.

        :param str device: device to set mac for
        :param str mac: mac to set
        :return: nothing
        """
        self.run("%s link set dev %s address %s" % (IP_BIN, device, mac))

    def delete_device(self, device):
        """
        Delete device.

        :param str device: device to delete
        :return: nothing
        """
        self.run("%s link delete %s" % (IP_BIN, device))

    def delete_tc(self, device):
        """
        Remove traffic control settings for a device.

        :param str device: device to remove tc
        :return: nothing
        """
        self.run("%s qdisc delete dev %s root" % (TC_BIN, device))

    def checksums_off(self, interface_name):
        """
        Turns interface checksums off.

        :param str interface_name: interface to update
        :return: nothing
        """
        self.run("%s -K %s rx off tx off" % (ETHTOOL_BIN, interface_name))

    def create_address(self, device, address, broadcast=None):
        """
        Create address for a device.

        :param str device: device to add address to
        :param str address: address to add
        :param str broadcast: broadcast address to use, default is None
        :return: nothing
        """
        if broadcast is not None:
            self.run(
                "%s address add %s broadcast %s dev %s"
                % (IP_BIN, address, broadcast, device)
            )
        else:
            self.run("%s address add %s dev %s" % (IP_BIN, address, device))

    def delete_address(self, device, address):
        """
        Delete an address from a device.

        :param str device: targeted device
        :param str address: address to remove
        :return: nothing
        """
        self.run("%s address delete %s dev %s" % (IP_BIN, address, device))

    def create_veth(self, name, peer):
        """
        Create a veth pair.

        :param str name: veth name
        :param str peer: peer name
        :return: nothing
        """
        self.run("%s link add name %s type veth peer name %s" % (IP_BIN, name, peer))

    def create_gretap(self, device, address, local, ttl, key):
        """
        Create a GRE tap on a device.

        :param str device: device to add tap to
        :param str address: address to add tap for
        :param str local: local address to tie to
        :param int ttl: time to live value
        :param int key: key for tap
        :return: nothing
        """
        cmd = "%s link add %s type gretap remote %s" % (IP_BIN, device, address)
        if local is not None:
            cmd += " local %s" % local
        if ttl is not None:
            cmd += " ttl %s" % ttl
        if key is not None:
            cmd += " key %s" % key
        self.run(cmd)

    def create_bridge(self, name):
        """
        Create a Linux bridge and bring it up.

        :param str name: bridge name
        :return: nothing
        """
        self.run("%s addbr %s" % (BRCTL_BIN, name))
        self.run("%s stp %s off" % (BRCTL_BIN, name))
        self.run("%s setfd %s 0" % (BRCTL_BIN, name))
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
        self.run("%s delbr %s" % (BRCTL_BIN, name))

    def create_interface(self, bridge_name, interface_name):
        """
        Create an interface associated with a Linux bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run("%s addif %s %s" % (BRCTL_BIN, bridge_name, interface_name))
        self.device_up(interface_name)

    def delete_interface(self, bridge_name, interface_name):
        """
        Delete an interface associated with a Linux bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run("%s delif %s %s" % (BRCTL_BIN, bridge_name, interface_name))

    def existing_bridges(self, _id):
        """
        Checks if there are any existing Linux bridges for a node.

        :param _id: node id to check bridges for
        """
        output = self.run("%s show" % BRCTL_BIN)
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
        self.run("%s setageing %s 0" % (BRCTL_BIN, name))


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
        self.run("%s add-br %s" % (OVS_BIN, name))
        self.run("%s set bridge %s stp_enable=false" % (OVS_BIN, name))
        self.run("%s set bridge %s other_config:stp-max-age=6" % (OVS_BIN, name))
        self.run("%s set bridge %s other_config:stp-forward-delay=4" % (OVS_BIN, name))
        self.device_up(name)

    def delete_bridge(self, name):
        """
        Bring down and delete a OVS bridge.

        :param str name: bridge name
        :return: nothing
        """
        self.device_down(name)
        self.run("%s del-br %s" % (OVS_BIN, name))

    def create_interface(self, bridge_name, interface_name):
        """
        Create an interface associated with a network bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run("%s add-port %s %s" % (OVS_BIN, bridge_name, interface_name))
        self.device_up(interface_name)

    def delete_interface(self, bridge_name, interface_name):
        """
        Delete an interface associated with a OVS bridge.

        :param str bridge_name: bridge name
        :param str interface_name: interface name
        :return: nothing
        """
        self.run("%s del-port %s %s" % (OVS_BIN, bridge_name, interface_name))

    def existing_bridges(self, _id):
        """
        Checks if there are any existing OVS bridges for a node.

        :param _id: node id to check bridges for
        """
        output = self.run("%s list-br" % OVS_BIN)
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
        self.run("%s set bridge %s other_config:mac-aging-time=0" % (OVS_BIN, name))
