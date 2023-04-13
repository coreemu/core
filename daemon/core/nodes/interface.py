"""
virtual ethernet classes that implement the interfaces available under Linux.
"""

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import netaddr

from core import utils
from core.emulator.data import InterfaceData, LinkOptions
from core.emulator.enumerations import TransportType
from core.errors import CoreCommandError, CoreError
from core.executables import TC
from core.nodes.netclient import LinuxNetClient, get_net_client

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session
    from core.emulator.distributed import DistributedServer
    from core.nodes.base import CoreNetworkBase, CoreNode, NodeBase

DEFAULT_MTU: int = 1500
IFACE_NAME_LENGTH: int = 15


def tc_clear_cmd(name: str) -> str:
    """
    Create tc command to clear device configuration.

    :param name: name of device to clear
    :return: tc command
    """
    return f"{TC} qdisc delete dev {name} root handle 10:"


def tc_cmd(name: str, options: LinkOptions, mtu: int) -> str:
    """
    Create tc command to configure a device with given name and options.

    :param name: name of device to configure
    :param options: options to configure with
    :param mtu: mtu for configuration
    :return: tc command
    """
    netem = ""
    if options.bandwidth is not None:
        limit = 1000
        bw = options.bandwidth / 1000
        if options.buffer is not None and options.buffer > 0:
            limit = options.buffer
        elif options.delay and options.bandwidth:
            delay = options.delay / 1000
            limit = max(2, math.ceil((2 * bw * delay) / (8 * mtu)))
        netem += f" rate {bw}kbit"
        netem += f" limit {limit}"
    if options.delay is not None:
        netem += f" delay {options.delay}us"
    if options.jitter is not None:
        if options.delay is None:
            netem += f" delay 0us {options.jitter}us 25%"
        else:
            netem += f" {options.jitter}us 25%"
    if options.loss is not None and options.loss > 0:
        netem += f" loss {min(options.loss, 100)}%"
    if options.dup is not None and options.dup > 0:
        netem += f" duplicate {min(options.dup, 100)}%"
    return f"{TC} qdisc replace dev {name} root handle 10: netem {netem}"


class CoreInterface:
    """
    Base class for network interfaces.
    """

    def __init__(
        self,
        _id: int,
        name: str,
        localname: str,
        use_ovs: bool,
        mtu: int = DEFAULT_MTU,
        node: "NodeBase" = None,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Creates a CoreInterface instance.

        :param _id: interface id for associated node
        :param name: interface name
        :param localname: interface local name
        :param use_ovs: True to use ovs, False otherwise
        :param mtu: mtu value
        :param node: node associated with this interface
        :param server: remote server node will run on, default is None for localhost
        """
        if len(name) >= IFACE_NAME_LENGTH:
            raise CoreError(
                f"interface name ({name}) too long, max {IFACE_NAME_LENGTH}"
            )
        if len(localname) >= IFACE_NAME_LENGTH:
            raise CoreError(
                f"interface local name ({localname}) too long, max {IFACE_NAME_LENGTH}"
            )
        self.id: int = _id
        self.node: Optional["NodeBase"] = node
        # id of interface for network, used by wlan/emane
        self.net_id: Optional[int] = None
        self.name: str = name
        self.localname: str = localname
        self.up: bool = False
        self.mtu: int = mtu
        self.net: Optional[CoreNetworkBase] = None
        self.ip4s: list[netaddr.IPNetwork] = []
        self.ip6s: list[netaddr.IPNetwork] = []
        self.mac: Optional[netaddr.EUI] = None
        # placeholder position hook
        self.poshook: Callable[[CoreInterface], None] = lambda x: None
        # used with EMANE
        self.transport_type: TransportType = TransportType.VIRTUAL
        # id used to find flow data
        self.flow_id: Optional[int] = None
        self.server: Optional["DistributedServer"] = server
        self.net_client: LinuxNetClient = get_net_client(use_ovs, self.host_cmd)
        self.control: bool = False
        # configuration data
        self.has_netem: bool = False
        self.options: LinkOptions = LinkOptions()

    def host_cmd(
        self,
        args: str,
        env: dict[str, str] = None,
        cwd: Path = None,
        wait: bool = True,
        shell: bool = False,
    ) -> str:
        """
        Runs a command on the host system or distributed server.

        :param args: command to run
        :param env: environment to run command with
        :param cwd: directory to run command in
        :param wait: True to wait for status, False otherwise
        :param shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        if self.server is None:
            return utils.cmd(args, env, cwd, wait, shell)
        else:
            return self.server.remote_cmd(args, env, cwd, wait)

    def startup(self) -> None:
        """
        Startup method for the interface.

        :return: nothing
        """
        self.net_client.create_veth(self.localname, self.name)
        if self.mtu > 0:
            self.net_client.set_mtu(self.name, self.mtu)
            self.net_client.set_mtu(self.localname, self.mtu)
        self.net_client.device_up(self.name)
        self.net_client.device_up(self.localname)
        self.up = True

    def shutdown(self) -> None:
        """
        Shutdown method for the interface.

        :return: nothing
        """
        if not self.up:
            return
        if self.localname:
            try:
                self.net_client.delete_device(self.localname)
            except CoreCommandError:
                pass
        self.up = False

    def add_ip(self, ip: str) -> None:
        """
        Add ip address in the format "10.0.0.1/24".

        :param ip: ip address to add
        :return: nothing
        :raises CoreError: when ip address provided is invalid
        """
        try:
            ip = netaddr.IPNetwork(ip)
            address = str(ip.ip)
            if netaddr.valid_ipv4(address):
                self.ip4s.append(ip)
            else:
                self.ip6s.append(ip)
        except netaddr.AddrFormatError as e:
            raise CoreError(f"adding invalid address {ip}: {e}")

    def remove_ip(self, ip: str) -> None:
        """
        Remove ip address in the format "10.0.0.1/24".

        :param ip: ip address to delete
        :return: nothing
        :raises CoreError: when ip address provided is invalid
        """
        try:
            ip = netaddr.IPNetwork(ip)
            address = str(ip.ip)
            if netaddr.valid_ipv4(address):
                self.ip4s.remove(ip)
            else:
                self.ip6s.remove(ip)
        except (netaddr.AddrFormatError, ValueError) as e:
            raise CoreError(f"deleting invalid address {ip}: {e}")

    def get_ip4(self) -> Optional[netaddr.IPNetwork]:
        """
        Looks for the first ip4 address.

        :return: ip4 address, None otherwise
        """
        return next(iter(self.ip4s), None)

    def get_ip6(self) -> Optional[netaddr.IPNetwork]:
        """
        Looks for the first ip6 address.

        :return: ip6 address, None otherwise
        """
        return next(iter(self.ip6s), None)

    def ips(self) -> list[netaddr.IPNetwork]:
        """
        Retrieve a list of all ip4 and ip6 addresses combined.

        :return: ip4 and ip6 addresses
        """
        return self.ip4s + self.ip6s

    def set_mac(self, mac: Optional[str]) -> None:
        """
        Set mac address.

        :param mac: mac address to set, None for random mac
        :return: nothing
        :raises CoreError: when there is an invalid mac address
        """
        if mac is None:
            self.mac = mac
        else:
            try:
                self.mac = netaddr.EUI(mac, dialect=netaddr.mac_unix_expanded)
            except netaddr.AddrFormatError as e:
                raise CoreError(f"invalid mac address({mac}): {e}")

    def setposition(self) -> None:
        """
        Dispatch position hook handler when possible.

        :return: nothing
        """
        if self.poshook and self.node:
            self.poshook(self)

    def __lt__(self, other: "CoreInterface") -> bool:
        """
        Used for comparisons of this object.

        :param other: other interface
        :return: true if less than, false otherwise
        """
        return id(self) < id(other)

    def is_raw(self) -> bool:
        """
        Used to determine if this interface is considered a raw interface.

        :return: True if raw interface, False otherwise
        """
        return self.transport_type == TransportType.RAW

    def is_virtual(self) -> bool:
        """
        Used to determine if this interface is considered a virtual interface.

        :return: True if virtual interface, False otherwise
        """
        return self.transport_type == TransportType.VIRTUAL

    def set_config(self) -> None:
        # clear current settings
        if self.options.is_clear():
            if self.has_netem:
                cmd = tc_clear_cmd(self.name)
                if self.node:
                    self.node.cmd(cmd)
                else:
                    self.host_cmd(cmd)
                self.has_netem = False
        # set updated settings
        else:
            cmd = tc_cmd(self.name, self.options, self.mtu)
            if self.node:
                self.node.cmd(cmd)
            else:
                self.host_cmd(cmd)
            self.has_netem = True

    def get_data(self) -> InterfaceData:
        """
        Retrieve the data representation of this interface.

        :return: interface data
        """
        ip4 = self.get_ip4()
        ip4_addr = str(ip4.ip) if ip4 else None
        ip4_mask = ip4.prefixlen if ip4 else None
        ip6 = self.get_ip6()
        ip6_addr = str(ip6.ip) if ip6 else None
        ip6_mask = ip6.prefixlen if ip6 else None
        mac = str(self.mac) if self.mac else None
        return InterfaceData(
            id=self.id,
            name=self.name,
            mac=mac,
            ip4=ip4_addr,
            ip4_mask=ip4_mask,
            ip6=ip6_addr,
            ip6_mask=ip6_mask,
        )


class GreTap(CoreInterface):
    """
    GRE TAP device for tunneling between emulation servers.
    Uses the "gretap" tunnel device type from Linux which is a GRE device
    having a MAC address. The MAC address is required for bridging.
    """

    def __init__(
        self,
        session: "Session",
        remoteip: str,
        key: int = None,
        node: "CoreNode" = None,
        mtu: int = DEFAULT_MTU,
        _id: int = None,
        localip: str = None,
        ttl: int = 255,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Creates a GreTap instance.

        :param session: session for this gre tap
        :param remoteip: remote address
        :param key: gre tap key
        :param node: related core node
        :param mtu: interface mtu
        :param _id: object id
        :param localip: local address
        :param ttl: ttl value
        :param server: remote server node
            will run on, default is None for localhost
        :raises CoreCommandError: when there is a command exception
        """
        if _id is None:
            _id = ((id(self) >> 16) ^ (id(self) & 0xFFFF)) & 0xFFFF
        self.id: int = _id
        sessionid = session.short_session_id()
        localname = f"gt.{self.id}.{sessionid}"
        name = f"{localname}p"
        super().__init__(0, name, localname, session.use_ovs(), mtu, node, server)
        self.transport_type: TransportType = TransportType.RAW
        self.remote_ip: str = remoteip
        self.ttl: int = ttl
        self.key: Optional[int] = key
        self.local_ip: Optional[str] = localip

    def startup(self) -> None:
        """
        Startup logic for a GreTap.

        :return: nothing
        """
        self.net_client.create_gretap(
            self.localname, self.remote_ip, self.local_ip, self.ttl, self.key
        )
        if self.mtu > 0:
            self.net_client.set_mtu(self.localname, self.mtu)
        self.net_client.device_up(self.localname)
        self.up = True

    def shutdown(self) -> None:
        """
        Shutdown logic for a GreTap.

        :return: nothing
        """
        if self.localname:
            try:
                self.net_client.device_down(self.localname)
                self.net_client.delete_device(self.localname)
            except CoreCommandError:
                logger.exception("error during shutdown")
            self.localname = None
