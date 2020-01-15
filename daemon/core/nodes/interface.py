"""
virtual ethernet classes that implement the interfaces available under Linux.
"""

import logging
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple

from core import utils
from core.errors import CoreCommandError
from core.nodes.netclient import get_net_client

if TYPE_CHECKING:
    from core.emulator.distributed import DistributedServer
    from core.emulator.session import Session
    from core.nodes.base import CoreNetworkBase, CoreNode


class CoreInterface:
    """
    Base class for network interfaces.
    """

    def __init__(
        self,
        session: "Session",
        node: "CoreNode",
        name: str,
        mtu: int,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Creates a CoreInterface instance.

        :param core.emulator.session.Session session: core session instance
        :param core.nodes.base.CoreNode node: node for interface
        :param str name: interface name
        :param int mtu: mtu value
        :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
        """
        self.session = session
        self.node = node
        self.name = name
        if not isinstance(mtu, int):
            raise ValueError
        self.mtu = mtu
        self.net = None
        self._params = {}
        self.addrlist = []
        self.hwaddr = None
        # placeholder position hook
        self.poshook = lambda a, b, c, d: None
        # used with EMANE
        self.transport_type = None
        # node interface index
        self.netindex = None
        # net interface index
        self.netifi = None
        # index used to find flow data
        self.flow_id = None
        self.server = server
        use_ovs = session.options.get_config("ovs") == "True"
        self.net_client = get_net_client(use_ovs, self.host_cmd)

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

        :param str args: command to run
        :param dict env: environment to run command with
        :param str cwd: directory to run command in
        :param bool wait: True to wait for status, False otherwise
        :param bool shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :rtype: str
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

        :param core.nodes.base.CoreNetworkBase net: network to attach
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

    def addaddr(self, addr: str) -> None:
        """
        Add address.

        :param str addr: address to add
        :return: nothing
        """
        addr = utils.validate_ip(addr)
        self.addrlist.append(addr)

    def deladdr(self, addr: str) -> None:
        """
        Delete address.

        :param str addr: address to delete
        :return: nothing
        """
        self.addrlist.remove(addr)

    def sethwaddr(self, addr: str) -> None:
        """
        Set hardware address.

        :param str addr: hardware address to set to.
        :return: nothing
        """
        if addr is not None:
            addr = utils.validate_mac(addr)
        self.hwaddr = addr

    def getparam(self, key: str) -> float:
        """
        Retrieve a parameter from the, or None if the parameter does not exist.

        :param key: parameter to get value for
        :return: parameter value
        """
        return self._params.get(key)

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

        :param str name: name of parameter to swap
        :return: nothing
        """
        tmp = self._params
        if not hasattr(self, name):
            setattr(self, name, {})
        self._params = getattr(self, name)
        setattr(self, name, tmp)

    def setposition(self, x: float, y: float, z: float) -> None:
        """
        Dispatch position hook handler.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        self.poshook(self, x, y, z)

    def __lt__(self, other: "CoreInterface") -> bool:
        """
        Used for comparisons of this object.

        :param other: other interface
        :return: true if less than, false otherwise
        :rtype: bool
        """
        return id(self) < id(other)


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
        mtu: int = 1500,
        server: "DistributedServer" = None,
        start: bool = True,
    ) -> None:
        """
        Creates a VEth instance.

        :param core.emulator.session.Session session: core session instance
        :param core.nodes.base.CoreNode node: related core node
        :param str name: interface name
        :param str localname: interface local name
        :param int mtu: interface mtu
        :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
        :param bool start: start flag
        :raises CoreCommandError: when there is a command exception
        """
        # note that net arg is ignored
        super().__init__(session, node, name, mtu, server)
        self.localname = localname
        self.up = False
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
                logging.exception("error shutting down interface")

        if self.localname:
            try:
                self.net_client.delete_device(self.localname)
            except CoreCommandError:
                logging.info("link already removed: %s", self.localname)

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
        mtu: int = 1500,
        server: "DistributedServer" = None,
        start: bool = True,
    ) -> None:
        """
        Create a TunTap instance.

        :param core.emulator.session.Session session: core session instance
        :param core.nodes.base.CoreNode node: related core node
        :param str name: interface name
        :param str localname: local interface name
        :param int mtu: interface mtu
        :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
        :param bool start: start flag
        """
        super().__init__(session, node, name, mtu, server)
        self.localname = localname
        self.up = False
        self.transport_type = "virtual"
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
        :param int attempts: number of attempts to wait for a zero result
        :param float maxretrydelay: maximum retry delay
        :return: True if wait succeeded, False otherwise
        :rtype: bool
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
        :rtype: int
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
            is_emane_running = self.node.session.emane.emanerunning(self.node)
            if all([should_retry, self.net.is_emane, is_emane_running]):
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

    def setaddrs(self) -> None:
        """
        Set interface addresses based on self.addrlist.

        :return: nothing
        """
        self.waitfordevicenode()
        for addr in self.addrlist:
            self.node.node_net_client.create_address(self.name, str(addr))


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

        :param core.nodes.base.CoreNode node: related core node
        :param str name: interface name
        :param core.emulator.session.Session session: core session instance
        :param int mtu: interface mtu
        :param str remoteip: remote address
        :param int _id: object id
        :param str localip: local address
        :param int ttl: ttl value
        :param int key: gre tap key
        :param bool start: start flag
        :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
        :raises CoreCommandError: when there is a command exception
        """
        super().__init__(session, node, name, mtu, server)
        if _id is None:
            # from PyCoreObj
            _id = ((id(self) >> 16) ^ (id(self) & 0xFFFF)) & 0xFFFF
        self.id = _id
        sessionid = self.session.short_session_id()
        # interface name on the local host machine
        self.localname = f"gt.{self.id}.{sessionid}"
        self.transport_type = "raw"
        if not start:
            self.up = False
            return

        if remoteip is None:
            raise ValueError("missing remote IP required for GRE TAP device")

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

    def data(self, message_type: int) -> None:
        """
        Data for a gre tap.

        :param message_type: message type for data
        :return: None
        """
        return None

    def all_link_data(self, flags: int) -> List:
        """
        Retrieve link data.

        :param flags: link flags
        :return: link data
        :rtype: list[core.emulator.data.LinkData]
        """
        return []
