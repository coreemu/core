"""
Clients for dealing with bridge/interface commands.
"""
from typing import Callable

import netaddr

from core.executables import ETHTOOL, IP, OVS_VSCTL, SYSCTL, TC


class LinuxNetClient:
    """
    Client for creating Linux bridges and ip interfaces for nodes.
    """

    def __init__(self, run: Callable[..., str]) -> None:
        """
        Create LinuxNetClient instance.

        :param run: function to run commands with
        """
        self.run: Callable[..., str] = run

    def set_hostname(self, name: str) -> None:
        """
        Set network hostname.

        :param name: name for hostname
        :return: nothing
        """
        self.run(f"hostname {name}")

    def create_route(self, route: str, device: str) -> None:
        """
        Create a new route for a device.

        :param route: route to create
        :param device: device to add route to
        :return: nothing
        """
        self.run(f"{IP} route replace {route} dev {device}")

    def device_up(self, device: str) -> None:
        """
        Bring a device up.

        :param device: device to bring up
        :return: nothing
        """
        self.run(f"{IP} link set {device} up")

    def device_down(self, device: str) -> None:
        """
        Bring a device down.

        :param device: device to bring down
        :return: nothing
        """
        self.run(f"{IP} link set {device} down")

    def device_name(self, device: str, name: str) -> None:
        """
        Set a device name.

        :param device: device to set name for
        :param name: name to set
        :return: nothing
        """
        self.run(f"{IP} link set {device} name {name}")

    def device_show(self, device: str) -> str:
        """
        Show link information for a device.

        :param device: device to get information for
        :return: device information
        """
        return self.run(f"{IP} link show {device}")

    def address_show(self, device: str) -> str:
        """
        Show address information for a device.

        :param device: device name
        :return: address information
        """
        return self.run(f"{IP} address show {device}")

    def get_mac(self, device: str) -> str:
        """
        Retrieve MAC address for a given device.

        :param device: device to get mac for
        :return: MAC address
        """
        return self.run(f"cat /sys/class/net/{device}/address")

    def get_ifindex(self, device: str) -> int:
        """
        Retrieve ifindex for a given device.

        :param device: device to get ifindex for
        :return: ifindex
        """
        return int(self.run(f"cat /sys/class/net/{device}/ifindex"))

    def device_ns(self, device: str, namespace: str) -> None:
        """
        Set netns for a device.

        :param device: device to setns for
        :param namespace: namespace to set device to
        :return: nothing
        """
        self.run(f"{IP} link set {device} netns {namespace}")

    def device_flush(self, device: str) -> None:
        """
        Flush device addresses.

        :param device: device to flush
        :return: nothing
        """
        self.run(f"{IP} address flush dev {device}")

    def device_mac(self, device: str, mac: str) -> None:
        """
        Set MAC address for a device.

        :param device: device to set mac for
        :param mac: mac to set
        :return: nothing
        """
        self.run(f"{IP} link set dev {device} address {mac}")

    def delete_device(self, device: str) -> None:
        """
        Delete device.

        :param device: device to delete
        :return: nothing
        """
        self.run(f"{IP} link delete {device}")

    def delete_tc(self, device: str) -> None:
        """
        Remove traffic control settings for a device.

        :param device: device to remove tc
        :return: nothing
        """
        self.run(f"{TC} qdisc delete dev {device} root")

    def checksums_off(self, iface_name: str) -> None:
        """
        Turns interface checksums off.

        :param iface_name: interface to update
        :return: nothing
        """
        self.run(f"{ETHTOOL} -K {iface_name} rx off tx off")

    def create_address(self, device: str, address: str, broadcast: str = None) -> None:
        """
        Create address for a device.

        :param device: device to add address to
        :param address: address to add
        :param broadcast: broadcast address to use, default is None
        :return: nothing
        """
        if broadcast is not None:
            self.run(f"{IP} address add {address} broadcast {broadcast} dev {device}")
        else:
            self.run(f"{IP} address add {address} dev {device}")
        if netaddr.valid_ipv6(address.split("/")[0]):
            # IPv6 addresses are removed by default on interface down.
            # Make sure that the IPv6 address we add is not removed
            self.run(f"{SYSCTL} -w net.ipv6.conf.{device}.keep_addr_on_down=1")

    def delete_address(self, device: str, address: str) -> None:
        """
        Delete an address from a device.

        :param device: targeted device
        :param address: address to remove
        :return: nothing
        """
        self.run(f"{IP} address delete {address} dev {device}")

    def create_veth(self, name: str, peer: str) -> None:
        """
        Create a veth pair.

        :param name: veth name
        :param peer: peer name
        :return: nothing
        """
        self.run(f"{IP} link add name {name} type veth peer name {peer}")

    def create_gretap(
        self, device: str, address: str, local: str, ttl: int, key: int
    ) -> None:
        """
        Create a GRE tap on a device.

        :param device: device to add tap to
        :param address: address to add tap for
        :param local: local address to tie to
        :param ttl: time to live value
        :param key: key for tap
        :return: nothing
        """
        cmd = f"{IP} link add {device} type gretap remote {address}"
        if local is not None:
            cmd += f" local {local}"
        if ttl is not None:
            cmd += f" ttl {ttl}"
        if key is not None:
            cmd += f" key {key}"
        self.run(cmd)

    def create_bridge(self, name: str) -> None:
        """
        Create a Linux bridge and bring it up.

        :param name: bridge name
        :return: nothing
        """
        self.run(f"{IP} link add name {name} type bridge")
        self.run(f"{IP} link set {name} type bridge stp_state 0")
        self.run(f"{IP} link set {name} type bridge forward_delay 0")
        self.run(f"{IP} link set {name} type bridge mcast_snooping 0")
        self.run(f"{IP} link set {name} type bridge group_fwd_mask 65528")
        self.device_up(name)

    def delete_bridge(self, name: str) -> None:
        """
        Bring down and delete a Linux bridge.

        :param name: bridge name
        :return: nothing
        """
        self.device_down(name)
        self.run(f"{IP} link delete {name} type bridge")

    def set_iface_master(self, bridge_name: str, iface_name: str) -> None:
        """
        Assign interface master to a Linux bridge.

        :param bridge_name: bridge name
        :param iface_name: interface name
        :return: nothing
        """
        self.run(f"{IP} link set dev {iface_name} master {bridge_name}")
        self.device_up(iface_name)

    def delete_iface(self, bridge_name: str, iface_name: str) -> None:
        """
        Delete an interface associated with a Linux bridge.

        :param bridge_name: bridge name
        :param iface_name: interface name
        :return: nothing
        """
        self.run(f"{IP} link set dev {iface_name} nomaster")

    def existing_bridges(self, _id: int) -> bool:
        """
        Checks if there are any existing Linux bridges for a node.

        :param _id: node id to check bridges for
        :return: True if there are existing bridges, False otherwise
        """
        output = self.run(f"{IP} -o link show type bridge")
        lines = output.split("\n")
        for line in lines:
            values = line.split(":")
            if not len(values) >= 2:
                continue
            name = values[1]
            fields = name.split(".")
            if len(fields) != 3:
                continue
            if fields[0] == "b" and fields[1] == _id:
                return True
        return False

    def set_mac_learning(self, name: str, value: int) -> None:
        """
        Set mac learning for a Linux bridge.

        :param name: bridge name
        :param value: ageing time value
        :return: nothing
        """
        self.run(f"{IP} link set {name} type bridge ageing_time {value}")

    def set_mtu(self, name: str, value: int) -> None:
        """
        Sets the mtu value for a device.

        :param name: name of device to set value for
        :param value: mtu value to set
        :return: nothing
        """
        self.run(f"{IP} link set {name} mtu {value}")


class OvsNetClient(LinuxNetClient):
    """
    Client for creating OVS bridges and ip interfaces for nodes.
    """

    def create_bridge(self, name: str) -> None:
        """
        Create a OVS bridge and bring it up.

        :param name: bridge name
        :return: nothing
        """
        self.run(f"{OVS_VSCTL} add-br {name}")
        self.run(f"{OVS_VSCTL} set bridge {name} stp_enable=false")
        self.run(f"{OVS_VSCTL} set bridge {name} other_config:stp-max-age=6")
        self.run(f"{OVS_VSCTL} set bridge {name} other_config:stp-forward-delay=4")
        self.device_up(name)

    def delete_bridge(self, name: str) -> None:
        """
        Bring down and delete a OVS bridge.

        :param name: bridge name
        :return: nothing
        """
        self.device_down(name)
        self.run(f"{OVS_VSCTL} del-br {name}")

    def set_iface_master(self, bridge_name: str, iface_name: str) -> None:
        """
        Create an interface associated with a network bridge.

        :param bridge_name: bridge name
        :param iface_name: interface name
        :return: nothing
        """
        self.run(f"{OVS_VSCTL} add-port {bridge_name} {iface_name}")
        self.device_up(iface_name)

    def delete_iface(self, bridge_name: str, iface_name: str) -> None:
        """
        Delete an interface associated with a OVS bridge.

        :param bridge_name: bridge name
        :param iface_name: interface name
        :return: nothing
        """
        self.run(f"{OVS_VSCTL} del-port {bridge_name} {iface_name}")

    def existing_bridges(self, _id: int) -> bool:
        """
        Checks if there are any existing OVS bridges for a node.

        :param _id: node id to check bridges for
        :return: True if there are existing bridges, False otherwise
        """
        output = self.run(f"{OVS_VSCTL} list-br")
        if output:
            for line in output.split("\n"):
                fields = line.split(".")
                if fields[0] == "b" and fields[1] == _id:
                    return True
        return False

    def set_mac_learning(self, name: str, value: int) -> None:
        """
        Set mac learning for an OVS bridge.

        :param name: bridge name
        :param value: ageing time value
        :return: nothing
        """
        self.run(f"{OVS_VSCTL} set bridge {name} other_config:mac-aging-time={value}")


def get_net_client(use_ovs: bool, run: Callable[..., str]) -> LinuxNetClient:
    """
    Retrieve desired net client for running network commands.

    :param use_ovs: True for OVS bridges, False for Linux bridges
    :param run: function used to run net client commands
    :return: net client class
    """
    if use_ovs:
        return OvsNetClient(run)
    else:
        return LinuxNetClient(run)
