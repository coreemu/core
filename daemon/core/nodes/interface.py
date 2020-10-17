"""
virtual ethernet classes that implement the interfaces available under Linux.
"""

import logging
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

import netaddr

from core import utils
from core.emulator.data import LinkOptions
from core.emulator.enumerations import TransportType
from core.errors import CoreCommandError, CoreError
from core.nodes.netclient import LinuxNetClient, get_net_client

if TYPE_CHECKING:
    from core.emulator.distributed import DistributedServer
    from core.emulator.session import Session
    from core.nodes.base import CoreNetworkBase, CoreNode

DEFAULT_MTU: int = 1500


class CoreInterface:
    """
    Base class for network interfaces.
    """

    def __init__(
        self,
        session: "Session",
        node: "CoreNode",
        name: str,
        localname: str,
        mtu: int,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Creates a CoreInterface instance.

        :param session: core session instance
        :param node: node for interface
        :param name: interface name
        :param localname: interface local name
        :param mtu: mtu value
        :param server: remote server node
            will run on, default is None for localhost
        """
        self.session: "Session" = session
        self.node: "CoreNode" = node
        self.name: str = name
        self.localname: str = localname
        self.up: bool = False
        self.mtu: int = mtu
        self.net: Optional[CoreNetworkBase] = None
        self.othernet: Optional[CoreNetworkBase] = None
        self._params: Dict[str, float] = {}
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

    def host_cmd(
        self,
        args: str,
        env: Dict[str, str] = None,
        cwd: str = None,
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

    def getparam(self, key: str) -> float:
        """
        Retrieve a parameter from the, or None if the parameter does not exist.

        :param key: parameter to get value for
        :return: parameter value
        """
        return self._params.get(key)

    def get_link_options(self, unidirectional: int) -> LinkOptions:
        """
        Get currently set params as link options.

        :param unidirectional: unidirectional setting
        :return: link options
        """
        delay = self.getparam("delay")
        if delay is not None:
            delay = int(delay)
        bandwidth = self.getparam("bw")
        if bandwidth is not None:
            bandwidth = int(bandwidth)
        dup = self.getparam("duplicate")
        if dup is not None:
            dup = int(dup)
        jitter = self.getparam("jitter")
        if jitter is not None:
            jitter = int(jitter)
        return LinkOptions(
            delay=delay,
            bandwidth=bandwidth,
            dup=dup,
            jitter=jitter,
            loss=self.getparam("loss"),
            unidirectional=unidirectional,
        )

    def getparams(self) -> List[Tuple[str, float]]:
        """
        Return (key, value) pairs for parameters.
        """
        parameters = []
        for k in sorted(self._params.keys()):
            parameters.append((k, self._params[k]))
        return parameters

    def setparam(self, key: str, value: float) -> bool:
        """
        Set a parameter value, returns True if the parameter has changed.

        :param key: parameter name to set
        :param value: parameter value
        :return: True if parameter changed, False otherwise
        """
        # treat None and 0 as unchanged values
        logging.debug("setting param: %s - %s", key, value)
        if value is None or value < 0:
            return False

        current_value = self._params.get(key)
        if current_value is not None and current_value == value:
            return False

        self._params[key] = value
        return True

    def swapparams(self, name: str) -> None:
        """
        Swap out parameters dict for name. If name does not exist,
        intialize it. This is for supporting separate upstream/downstream
        parameters when two layer-2 nodes are linked together.

        :param name: name of parameter to swap
        :return: nothing
        """
        tmp = self._params
        if not hasattr(self, name):
            setattr(self, name, {})
        self._params = getattr(self, name)
        setattr(self, name, tmp)

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


class Veth(CoreInterface):
    """
    Provides virtual ethernet functionality for core nodes.
    """

    def __init__(
        self,
        session: "Session",
        node: "CoreNode",
        name: str,
        localname: str,
        mtu: int = DEFAULT_MTU,
        server: "DistributedServer" = None,
        start: bool = True,
    ) -> None:
        """
        Creates a VEth instance.

        :param session: core session instance
        :param node: related core node
        :param name: interface name
        :param localname: interface local name
        :param mtu: interface mtu
        :param server: remote server node
            will run on, default is None for localhost
        :param start: start flag
        :raises CoreCommandError: when there is a command exception
        """
        # note that net arg is ignored
        super().__init__(session, node, name, localname, mtu, server)
        if start:
            self.startup()

    def startup(self) -> None:
        """
        Interface startup logic.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.net_client.create_veth(self.localname, self.name)
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

    def __init__(
        self,
        session: "Session",
        node: "CoreNode",
        name: str,
        localname: str,
        mtu: int = DEFAULT_MTU,
        server: "DistributedServer" = None,
        start: bool = True,
    ) -> None:
        """
        Create a TunTap instance.

        :param session: core session instance
        :param node: related core node
        :param name: interface name
        :param localname: local interface name
        :param mtu: interface mtu
        :param server: remote server node
            will run on, default is None for localhost
        :param start: start flag
        """
        super().__init__(session, node, name, localname, mtu, server)
        if start:
            self.startup()

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
            logging.exception("error shutting down tunnel tap")

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
                logging.info(msg)
                time.sleep(delay)
                delay += delay
                if delay > maxretrydelay:
                    delay = maxretrydelay
            else:
                msg += ", giving up"
                logging.info(msg)

        return result

    def waitfordevicelocal(self) -> None:
        """
        Check for presence of a local device - tap device may not
        appear right away waits

        :return: wait for device local response
        """
        logging.debug("waiting for device local: %s", self.localname)

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
        logging.debug("waiting for device node: %s", self.name)

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
        node: "CoreNode" = None,
        name: str = None,
        session: "Session" = None,
        mtu: int = 1458,
        remoteip: str = None,
        _id: int = None,
        localip: str = None,
        ttl: int = 255,
        key: int = None,
        start: bool = True,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Creates a GreTap instance.

        :param node: related core node
        :param name: interface name
        :param session: core session instance
        :param mtu: interface mtu
        :param remoteip: remote address
        :param _id: object id
        :param localip: local address
        :param ttl: ttl value
        :param key: gre tap key
        :param start: start flag
        :param server: remote server node
            will run on, default is None for localhost
        :raises CoreCommandError: when there is a command exception
        """
        if _id is None:
            _id = ((id(self) >> 16) ^ (id(self) & 0xFFFF)) & 0xFFFF
        self.id = _id
        sessionid = session.short_session_id()
        localname = f"gt.{self.id}.{sessionid}"
        super().__init__(session, node, name, localname, mtu, server)
        self.transport_type = TransportType.RAW
        if not start:
            return
        if remoteip is None:
            raise CoreError("missing remote IP required for GRE TAP device")
        self.net_client.create_gretap(self.localname, remoteip, localip, ttl, key)
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
                logging.exception("error during shutdown")
            self.localname = None
