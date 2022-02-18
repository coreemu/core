"""
virtual ethernet classes that implement the interfaces available under Linux.
"""

import logging
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import netaddr

from core import utils
from core.emulator.data import InterfaceData, LinkOptions
from core.emulator.enumerations import TransportType
from core.errors import CoreCommandError, CoreError
from core.executables import TC
from core.nodes.netclient import LinuxNetClient, get_net_client

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.distributed import DistributedServer
    from core.emulator.session import Session
    from core.nodes.base import CoreNetworkBase, CoreNode

DEFAULT_MTU: int = 1500


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
        session: "Session",
        name: str,
        localname: str,
        mtu: int = DEFAULT_MTU,
        server: "DistributedServer" = None,
        node: "CoreNode" = None,
    ) -> None:
        """
        Creates a CoreInterface instance.

        :param session: core session instance
        :param name: interface name
        :param localname: interface local name
        :param mtu: mtu value
        :param server: remote server node will run on, default is None for localhost
        :param node: node for interface
        """
        if len(name) >= 16:
            raise CoreError(f"interface name ({name}) too long, max 16")
        if len(localname) >= 16:
            raise CoreError(f"interface local name ({localname}) too long, max 16")
        self.session: "Session" = session
        self.node: Optional["CoreNode"] = node
        self.name: str = name
        self.localname: str = localname
        self.up: bool = False
        self.mtu: int = mtu
        self.net: Optional[CoreNetworkBase] = None
        self.othernet: Optional[CoreNetworkBase] = None
        self.ip4s: List[netaddr.IPNetwork] = []
        self.ip6s: List[netaddr.IPNetwork] = []
        self.mac: Optional[netaddr.EUI] = None
        # placeholder position hook
        self.poshook: Callable[[CoreInterface], None] = lambda x: None
        # used with EMANE
        self.transport_type: TransportType = TransportType.VIRTUAL
        # id of interface for node
        self.node_id: Optional[int] = None
        # id of interface for network
        self.net_id: Optional[int] = None
        # id used to find flow data
        self.flow_id: Optional[int] = None
        self.server: Optional["DistributedServer"] = server
        self.net_client: LinuxNetClient = get_net_client(
            self.session.use_ovs(), self.host_cmd
        )
        self.control: bool = False
        # configuration data
        self.has_local_netem: bool = False
        self.local_options: LinkOptions = LinkOptions()
        self.has_netem: bool = False
        self.options: LinkOptions = LinkOptions()

    def host_cmd(
        self,
        args: str,
        env: Dict[str, str] = None,
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
        pass

    def shutdown(self) -> None:
        """
        Shutdown method for the interface.

        :return: nothing
        """
        pass

    def attachnet(self, net: "CoreNetworkBase") -> None:
        """
        Attach network.

        :param net: network to attach
        :return: nothing
        """
        if self.net:
            self.detachnet()
            self.net = None
        net.attach(self)
        self.net = net

    def detachnet(self) -> None:
        """
        Detach from a network.

        :return: nothing
        """
        if self.net is not None:
            self.net.detach(self)

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

    def ips(self) -> List[netaddr.IPNetwork]:
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

    def config(self, options: LinkOptions, use_local: bool = True) -> None:
        """
        Configure interface using tc based on existing state and provided
        link options.

        :param options: options to configure with
        :param use_local: True to use localname for device, False for name
        :return: nothing
        """
        # determine name, options, and if anything has changed
        name = self.localname if use_local else self.name
        current_options = self.local_options if use_local else self.options
        changed = current_options.update(options)
        # nothing more to do when nothing has changed or not up
        if not changed or not self.up:
            return
        # clear current settings
        if current_options.is_clear():
            clear_local_netem = use_local and self.has_local_netem
            clear_netem = not use_local and self.has_netem
            if clear_local_netem or clear_netem:
                cmd = tc_clear_cmd(name)
                self.host_cmd(cmd)
                if use_local:
                    self.has_local_netem = False
                else:
                    self.has_netem = False
        # set updated settings
        else:
            cmd = tc_cmd(name, current_options, self.mtu)
            self.host_cmd(cmd)
            if use_local:
                self.has_local_netem = True
            else:
                self.has_netem = True

    def get_data(self) -> InterfaceData:
        """
        Retrieve the data representation of this interface.

        :return: interface data
        """
        if self.node:
            iface_id = self.node.get_iface_id(self)
        else:
            iface_id = self.othernet.get_iface_id(self)
        data = InterfaceData(
            id=iface_id, name=self.name, mac=str(self.mac) if self.mac else None
        )
        ip4 = self.get_ip4()
        if ip4:
            data.ip4 = str(ip4.ip)
            data.ip4_mask = ip4.prefixlen
        ip6 = self.get_ip6()
        if ip6:
            data.ip6 = str(ip6.ip)
            data.ip6_mask = ip6.prefixlen
        return data


class Veth(CoreInterface):
    """
    Provides virtual ethernet functionality for core nodes.
    """

    def adopt_node(self, iface_id: int, name: str, start: bool) -> None:
        """
        Adopt this interface to the provided node, configuring and associating
        with the node as needed.

        :param iface_id: interface id for node
        :param name: name of interface fo rnode
        :param start: True to start interface, False otherwise
        :return: nothing
        """
        if start:
            self.startup()
            self.net_client.device_ns(self.name, str(self.node.pid))
            self.node.node_net_client.checksums_off(self.name)
            self.flow_id = self.node.node_net_client.get_ifindex(self.name)
            logger.debug("interface flow index: %s - %s", self.name, self.flow_id)
            mac = self.node.node_net_client.get_mac(self.name)
            logger.debug("interface mac: %s - %s", self.name, mac)
            self.set_mac(mac)
            self.node.node_net_client.device_name(self.name, name)
        self.name = name
        try:
            self.node.add_iface(self, iface_id)
        except CoreError as e:
            self.shutdown()
            raise e

    def startup(self) -> None:
        """
        Interface startup logic.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.net_client.create_veth(self.localname, self.name)
        if self.mtu > 0:
            self.net_client.set_mtu(self.name, self.mtu)
            self.net_client.set_mtu(self.localname, self.mtu)
        self.net_client.device_up(self.localname)
        self.up = True

    def shutdown(self) -> None:
        """
        Interface shutdown logic.

        :return: nothing
        """
        if not self.up:
            return
        if self.node:
            try:
                self.node.node_net_client.device_flush(self.name)
            except CoreCommandError:
                pass
        if self.localname:
            try:
                self.net_client.delete_device(self.localname)
            except CoreCommandError:
                pass
        self.up = False


class TunTap(CoreInterface):
    """
    TUN/TAP virtual device in TAP mode
    """

    def startup(self) -> None:
        """
        Startup logic for a tunnel tap.

        :return: nothing
        """
        # TODO: more sophisticated TAP creation here
        #   Debian does not support -p (tap) option, RedHat does.
        #   For now, this is disabled to allow the TAP to be created by another
        #   system (e.g. EMANE"s emanetransportd)
        #   check_call(["tunctl", "-t", self.name])
        #   self.install()
        self.up = True

    def shutdown(self) -> None:
        """
        Shutdown functionality for a tunnel tap.

        :return: nothing
        """
        if not self.up:
            return
        try:
            self.node.node_net_client.device_flush(self.name)
        except CoreCommandError:
            logger.exception("error shutting down tunnel tap")
        self.up = False

    def waitfor(
        self, func: Callable[[], int], attempts: int = 10, maxretrydelay: float = 0.25
    ) -> bool:
        """
        Wait for func() to return zero with exponential backoff.

        :param func: function to wait for a result of zero
        :param attempts: number of attempts to wait for a zero result
        :param maxretrydelay: maximum retry delay
        :return: True if wait succeeded, False otherwise
        """
        delay = 0.01
        result = False
        for i in range(1, attempts + 1):
            r = func()
            if r == 0:
                result = True
                break
            msg = f"attempt {i} failed with nonzero exit status {r}"
            if i < attempts + 1:
                msg += ", retrying..."
                logger.info(msg)
                time.sleep(delay)
                delay += delay
                if delay > maxretrydelay:
                    delay = maxretrydelay
            else:
                msg += ", giving up"
                logger.info(msg)

        return result

    def waitfordevicelocal(self) -> None:
        """
        Check for presence of a local device - tap device may not
        appear right away waits

        :return: wait for device local response
        """
        logger.debug("waiting for device local: %s", self.localname)

        def localdevexists():
            try:
                self.net_client.device_show(self.localname)
                return 0
            except CoreCommandError:
                return 1

        self.waitfor(localdevexists)

    def waitfordevicenode(self) -> None:
        """
        Check for presence of a node device - tap device may not appear right away waits.

        :return: nothing
        """
        logger.debug("waiting for device node: %s", self.name)

        def nodedevexists():
            try:
                self.node.node_net_client.device_show(self.name)
                return 0
            except CoreCommandError:
                return 1

        count = 0
        while True:
            result = self.waitfor(nodedevexists)
            if result:
                break

            # TODO: emane specific code
            # check if this is an EMANE interface; if so, continue
            # waiting if EMANE is still running
            should_retry = count < 5
            is_emane = self.session.emane.is_emane_net(self.net)
            is_emane_running = self.session.emane.emanerunning(self.node)
            if all([should_retry, is_emane, is_emane_running]):
                count += 1
            else:
                raise RuntimeError("node device failed to exist")

    def install(self) -> None:
        """
        Install this TAP into its namespace. This is not done from the
        startup() method but called at a later time when a userspace
        program (running on the host) has had a chance to open the socket
        end of the TAP.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.waitfordevicelocal()
        netns = str(self.node.pid)
        self.net_client.device_ns(self.localname, netns)
        self.node.node_net_client.device_name(self.localname, self.name)
        self.node.node_net_client.device_up(self.name)

    def set_ips(self) -> None:
        """
        Set interface ip addresses.

        :return: nothing
        """
        self.waitfordevicenode()
        for ip in self.ips():
            self.node.node_net_client.create_address(self.name, str(ip))


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

        :param session: core session instance
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
        super().__init__(session, name, localname, mtu, server, node)
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
