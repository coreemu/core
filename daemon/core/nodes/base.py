"""
Defines the base logic for nodes used within core.
"""
import abc
import logging
import os
import shutil
import threading
from threading import RLock
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type, Union

import netaddr

from core import utils
from core.configservice.dependencies import ConfigServiceDependencies
from core.emulator.data import InterfaceData, LinkData, LinkOptions
from core.emulator.enumerations import LinkTypes, MessageFlags, NodeTypes
from core.errors import CoreCommandError, CoreError
from core.executables import MOUNT, VNODED
from core.nodes.client import VnodeClient
from core.nodes.interface import CoreInterface, TunTap, Veth
from core.nodes.netclient import LinuxNetClient, get_net_client

if TYPE_CHECKING:
    from core.emulator.distributed import DistributedServer
    from core.emulator.session import Session
    from core.configservice.base import ConfigService
    from core.services.coreservices import CoreService

    CoreServices = List[Union[CoreService, Type[CoreService]]]
    ConfigServiceType = Type[ConfigService]

_DEFAULT_MTU = 1500


class NodeBase(abc.ABC):
    """
    Base class for CORE nodes (nodes and networks)
    """

    apitype: Optional[NodeTypes] = None

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Creates a NodeBase instance.

        :param session: CORE session object
        :param _id: id
        :param name: object name
        :param server: remote server node
            will run on, default is None for localhost
        """

        self.session: "Session" = session
        if _id is None:
            _id = session.next_node_id()
        self.id: int = _id
        if name is None:
            name = f"o{self.id}"
        self.name: str = name
        self.server: "DistributedServer" = server
        self.type: Optional[str] = None
        self.services: CoreServices = []
        self.ifaces: Dict[int, CoreInterface] = {}
        self.iface_id: int = 0
        self.canvas: Optional[int] = None
        self.icon: Optional[str] = None
        self.position: Position = Position()
        self.up: bool = False
        self.net_client: LinuxNetClient = get_net_client(
            self.session.use_ovs(), self.host_cmd
        )

    @abc.abstractmethod
    def startup(self) -> None:
        """
        Each object implements its own startup method.

        :return: nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def shutdown(self) -> None:
        """
        Each object implements its own shutdown method.

        :return: nothing
        """
        raise NotImplementedError

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

    def setposition(self, x: float = None, y: float = None, z: float = None) -> bool:
        """
        Set the (x,y,z) position of the object.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: True if position changed, False otherwise
        """
        return self.position.set(x=x, y=y, z=z)

    def getposition(self) -> Tuple[float, float, float]:
        """
        Return an (x,y,z) tuple representing this object's position.

        :return: x,y,z position tuple
        """
        return self.position.get()

    def get_iface(self, iface_id: int) -> CoreInterface:
        """
        Retrieve interface based on id.

        :param iface_id: id of interface to retrieve
        :return: interface
        :raises CoreError: when interface does not exist
        """
        if iface_id not in self.ifaces:
            raise CoreError(f"node({self.name}) does not have interface({iface_id})")
        return self.ifaces[iface_id]

    def get_ifaces(self, control: bool = True) -> List[CoreInterface]:
        """
        Retrieve sorted list of interfaces, optionally do not include control
        interfaces.

        :param control: False to exclude control interfaces, included otherwise
        :return: list of interfaces
        """
        ifaces = []
        for iface_id in sorted(self.ifaces):
            iface = self.ifaces[iface_id]
            if not control and getattr(iface, "control", False):
                continue
            ifaces.append(iface)
        return ifaces

    def get_iface_id(self, iface: CoreInterface) -> int:
        """
        Retrieve id for an interface.

        :param iface: interface to get id for
        :return: interface index if found, -1 otherwise
        """
        for iface_id, local_iface in self.ifaces.items():
            if local_iface is iface:
                return iface_id
        raise CoreError(f"node({self.name}) does not have interface({iface.name})")

    def next_iface_id(self) -> int:
        """
        Create a new interface index.

        :return: interface index
        """
        while self.iface_id in self.ifaces:
            self.iface_id += 1
        iface_id = self.iface_id
        self.iface_id += 1
        return iface_id

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        """
        Build link data for this node.

        :param flags: message flags
        :return: list of link data
        """
        return []


class CoreNodeBase(NodeBase):
    """
    Base class for CORE nodes.
    """

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Create a CoreNodeBase instance.

        :param session: CORE session object
        :param _id: object id
        :param name: object name
        :param server: remote server node
            will run on, default is None for localhost
        """
        super().__init__(session, _id, name, server)
        self.config_services: Dict[str, "ConfigService"] = {}
        self.nodedir: Optional[str] = None
        self.tmpnodedir: bool = False

    @abc.abstractmethod
    def startup(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def nodefile(self, filename: str, contents: str, mode: int = 0o644) -> None:
        """
        Create a node file with a given mode.

        :param filename: name of file to create
        :param contents: contents of file
        :param mode: mode for file
        :return: nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def addfile(self, srcname: str, filename: str) -> None:
        """
        Add a file.

        :param srcname: source file name
        :param filename: file name to add
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        raise NotImplementedError

    @abc.abstractmethod
    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        """
        Runs a command within a node container.

        :param args: command to run
        :param wait: True to wait for status, False otherwise
        :param shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        raise NotImplementedError

    @abc.abstractmethod
    def termcmdstring(self, sh: str) -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        raise NotImplementedError

    @abc.abstractmethod
    def new_iface(
        self, net: "CoreNetworkBase", iface_data: InterfaceData
    ) -> CoreInterface:
        """
        Create a new interface.

        :param net: network to associate with
        :param iface_data: interface data for new interface
        :return: interface index
        """
        raise NotImplementedError

    def add_config_service(self, service_class: "ConfigServiceType") -> None:
        """
        Adds a configuration service to the node.

        :param service_class: configuration service class to assign to node
        :return: nothing
        """
        name = service_class.name
        if name in self.config_services:
            raise CoreError(f"node({self.name}) already has service({name})")
        self.config_services[name] = service_class(self)

    def set_service_config(self, name: str, data: Dict[str, str]) -> None:
        """
        Sets configuration service custom config data.

        :param name: name of configuration service
        :param data: custom config data to set
        :return: nothing
        """
        service = self.config_services.get(name)
        if service is None:
            raise CoreError(f"node({self.name}) does not have service({name})")
        service.set_config(data)

    def start_config_services(self) -> None:
        """
        Determines startup paths and starts configuration services, based on their
        dependency chains.

        :return: nothing
        """
        startup_paths = ConfigServiceDependencies(self.config_services).startup_paths()
        for startup_path in startup_paths:
            for service in startup_path:
                service.start()

    def makenodedir(self) -> None:
        """
        Create the node directory.

        :return: nothing
        """
        if self.nodedir is None:
            self.nodedir = os.path.join(self.session.session_dir, self.name + ".conf")
            self.host_cmd(f"mkdir -p {self.nodedir}")
            self.tmpnodedir = True
        else:
            self.tmpnodedir = False

    def rmnodedir(self) -> None:
        """
        Remove the node directory, unless preserve directory has been set.

        :return: nothing
        """
        preserve = self.session.options.get_config("preservedir") == "1"
        if preserve:
            return
        if self.tmpnodedir:
            self.host_cmd(f"rm -rf {self.nodedir}")

    def add_iface(self, iface: CoreInterface, iface_id: int) -> None:
        """
        Add network interface to node and set the network interface index if successful.

        :param iface: network interface to add
        :param iface_id: interface id
        :return: nothing
        """
        if iface_id in self.ifaces:
            raise CoreError(f"interface({iface_id}) already exists")
        self.ifaces[iface_id] = iface
        iface.node_id = iface_id

    def delete_iface(self, iface_id: int) -> None:
        """
        Delete a network interface

        :param iface_id: interface index to delete
        :return: nothing
        """
        if iface_id not in self.ifaces:
            raise CoreError(f"node({self.name}) interface({iface_id}) does not exist")
        iface = self.ifaces.pop(iface_id)
        logging.info("node(%s) removing interface(%s)", self.name, iface.name)
        iface.detachnet()
        iface.shutdown()

    def attachnet(self, iface_id: int, net: "CoreNetworkBase") -> None:
        """
        Attach a network.

        :param iface_id: interface of index to attach
        :param net: network to attach
        :return: nothing
        """
        iface = self.get_iface(iface_id)
        iface.attachnet(net)

    def detachnet(self, iface_id: int) -> None:
        """
        Detach network interface.

        :param iface_id: interface id to detach
        :return: nothing
        """
        iface = self.get_iface(iface_id)
        iface.detachnet()

    def setposition(self, x: float = None, y: float = None, z: float = None) -> None:
        """
        Set position.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        changed = super().setposition(x, y, z)
        if changed:
            for iface in self.get_ifaces():
                iface.setposition()

    def commonnets(
        self, node: "CoreNodeBase", want_ctrl: bool = False
    ) -> List[Tuple["CoreNetworkBase", CoreInterface, CoreInterface]]:
        """
        Given another node or net object, return common networks between
        this node and that object. A list of tuples is returned, with each tuple
        consisting of (network, interface1, interface2).

        :param node: node to get common network with
        :param want_ctrl: flag set to determine if control network are wanted
        :return: tuples of common networks
        """
        common = []
        for iface1 in self.get_ifaces(control=want_ctrl):
            for iface2 in node.get_ifaces():
                if iface1.net == iface2.net:
                    common.append((iface1.net, iface1, iface2))
        return common


class CoreNode(CoreNodeBase):
    """
    Provides standard core node logic.
    """

    apitype: NodeTypes = NodeTypes.DEFAULT

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        nodedir: str = None,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Create a CoreNode instance.

        :param session: core session instance
        :param _id: object id
        :param name: object name
        :param nodedir: node directory
        :param server: remote server node
            will run on, default is None for localhost
        """
        super().__init__(session, _id, name, server)
        self.nodedir: Optional[str] = nodedir
        self.ctrlchnlname: str = os.path.abspath(
            os.path.join(self.session.session_dir, self.name)
        )
        self.client: Optional[VnodeClient] = None
        self.pid: Optional[int] = None
        self.lock: RLock = RLock()
        self._mounts: List[Tuple[str, str]] = []
        self.node_net_client: LinuxNetClient = self.create_node_net_client(
            self.session.use_ovs()
        )

    def create_node_net_client(self, use_ovs: bool) -> LinuxNetClient:
        """
        Create node network client for running network commands within the nodes
        container.

        :param use_ovs: True for OVS bridges, False for Linux bridges
        :return: node network client
        """
        return get_net_client(use_ovs, self.cmd)

    def alive(self) -> bool:
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        """
        try:
            self.host_cmd(f"kill -0 {self.pid}")
        except CoreCommandError:
            return False
        return True

    def startup(self) -> None:
        """
        Start a new namespace node by invoking the vnoded process that
        allocates a new namespace. Bring up the loopback device and set
        the hostname.

        :return: nothing
        """
        with self.lock:
            self.makenodedir()
            if self.up:
                raise ValueError("starting a node that is already up")

            # create a new namespace for this node using vnoded
            vnoded = (
                f"{VNODED} -v -c {self.ctrlchnlname} -l {self.ctrlchnlname}.log "
                f"-p {self.ctrlchnlname}.pid"
            )
            if self.nodedir:
                vnoded += f" -C {self.nodedir}"
            env = self.session.get_environment(state=False)
            env["NODE_NUMBER"] = str(self.id)
            env["NODE_NAME"] = str(self.name)

            output = self.host_cmd(vnoded, env=env)
            self.pid = int(output)
            logging.debug("node(%s) pid: %s", self.name, self.pid)

            # create vnode client
            self.client = VnodeClient(self.name, self.ctrlchnlname)

            # bring up the loopback interface
            logging.debug("bringing up loopback interface")
            self.node_net_client.device_up("lo")

            # set hostname for node
            logging.debug("setting hostname: %s", self.name)
            self.node_net_client.set_hostname(self.name)

            # mark node as up
            self.up = True

            # create private directories
            self.privatedir("/var/run")
            self.privatedir("/var/log")

    def shutdown(self) -> None:
        """
        Shutdown logic for simple lxc nodes.

        :return: nothing
        """
        # nothing to do if node is not up
        if not self.up:
            return

        with self.lock:
            try:
                # unmount all targets (NOTE: non-persistent mount namespaces are
                # removed by the kernel when last referencing process is killed)
                self._mounts = []

                # shutdown all interfaces
                for iface in self.get_ifaces():
                    iface.shutdown()

                # kill node process if present
                try:
                    self.host_cmd(f"kill -9 {self.pid}")
                except CoreCommandError:
                    logging.exception("error killing process")

                # remove node directory if present
                try:
                    self.host_cmd(f"rm -rf {self.ctrlchnlname}")
                except CoreCommandError:
                    logging.exception("error removing node directory")

                # clear interface data, close client, and mark self and not up
                self.ifaces.clear()
                self.client.close()
                self.up = False
            except OSError:
                logging.exception("error during shutdown")
            finally:
                self.rmnodedir()

    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        """
        Runs a command that is used to configure and setup the network within a
        node.

        :param args: command to run
        :param wait: True to wait for status, False otherwise
        :param shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        if self.server is None:
            return self.client.check_cmd(args, wait=wait, shell=shell)
        else:
            args = self.client.create_cmd(args)
            return self.server.remote_cmd(args, wait=wait)

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        terminal = self.client.create_cmd(sh)
        if self.server is None:
            return terminal
        else:
            return f"ssh -X -f {self.server.host} xterm -e {terminal}"

    def privatedir(self, path: str) -> None:
        """
        Create a private directory.

        :param path: path to create
        :return: nothing
        """
        if path[0] != "/":
            raise ValueError(f"path not fully qualified: {path}")
        hostpath = os.path.join(
            self.nodedir, os.path.normpath(path).strip("/").replace("/", ".")
        )
        self.host_cmd(f"mkdir -p {hostpath}")
        self.mount(hostpath, path)

    def mount(self, source: str, target: str) -> None:
        """
        Create and mount a directory.

        :param source: source directory to mount
        :param target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        source = os.path.abspath(source)
        logging.debug("node(%s) mounting: %s at %s", self.name, source, target)
        self.cmd(f"mkdir -p {target}")
        self.cmd(f"{MOUNT} -n --bind {source} {target}")
        self._mounts.append((source, target))

    def next_iface_id(self) -> int:
        """
        Retrieve a new interface index.

        :return: new interface index
        """
        with self.lock:
            return super().next_iface_id()

    def newveth(self, iface_id: int = None, ifname: str = None) -> int:
        """
        Create a new interface.

        :param iface_id: id for the new interface
        :param ifname: name for the new interface
        :return: nothing
        """
        with self.lock:
            if iface_id is None:
                iface_id = self.next_iface_id()

            if ifname is None:
                ifname = f"eth{iface_id}"

            sessionid = self.session.short_session_id()

            try:
                suffix = f"{self.id:x}.{iface_id}.{sessionid}"
            except TypeError:
                suffix = f"{self.id}.{iface_id}.{sessionid}"

            localname = f"veth{suffix}"
            if len(localname) >= 16:
                raise ValueError(f"interface local name ({localname}) too long")

            name = localname + "p"
            if len(name) >= 16:
                raise ValueError(f"interface name ({name}) too long")

            veth = Veth(
                self.session, self, name, localname, start=self.up, server=self.server
            )

            if self.up:
                self.net_client.device_ns(veth.name, str(self.pid))
                self.node_net_client.device_name(veth.name, ifname)
                self.node_net_client.checksums_off(ifname)

            veth.name = ifname

            if self.up:
                flow_id = self.node_net_client.get_ifindex(veth.name)
                veth.flow_id = int(flow_id)
                logging.debug("interface flow index: %s - %s", veth.name, veth.flow_id)
                mac = self.node_net_client.get_mac(veth.name)
                logging.debug("interface mac: %s - %s", veth.name, mac)
                veth.set_mac(mac)

            try:
                # add network interface to the node. If unsuccessful, destroy the
                # network interface and raise exception.
                self.add_iface(veth, iface_id)
            except ValueError as e:
                veth.shutdown()
                del veth
                raise e

            return iface_id

    def newtuntap(self, iface_id: int = None, ifname: str = None) -> int:
        """
        Create a new tunnel tap.

        :param iface_id: interface id
        :param ifname: interface name
        :return: interface index
        """
        with self.lock:
            if iface_id is None:
                iface_id = self.next_iface_id()

            if ifname is None:
                ifname = f"eth{iface_id}"

            sessionid = self.session.short_session_id()
            localname = f"tap{self.id}.{iface_id}.{sessionid}"
            name = ifname
            tuntap = TunTap(self.session, self, name, localname, start=self.up)

            try:
                self.add_iface(tuntap, iface_id)
            except ValueError as e:
                tuntap.shutdown()
                del tuntap
                raise e

            return iface_id

    def set_mac(self, iface_id: int, mac: str) -> None:
        """
        Set hardware address for an interface.

        :param iface_id: id of interface to set hardware address for
        :param mac: mac address to set
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        iface = self.get_iface(iface_id)
        iface.set_mac(mac)
        if self.up:
            self.node_net_client.device_mac(iface.name, str(iface.mac))

    def add_ip(self, iface_id: int, ip: str) -> None:
        """
        Add an ip address to an interface in the format "10.0.0.1/24".

        :param iface_id: id of interface to add address to
        :param ip: address to add to interface
        :return: nothing
        :raises CoreError: when ip address provided is invalid
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        iface = self.get_iface(iface_id)
        iface.add_ip(ip)
        if self.up:
            # ipv4 check
            broadcast = None
            if netaddr.valid_ipv4(ip):
                broadcast = "+"
            self.node_net_client.create_address(iface.name, ip, broadcast)

    def remove_ip(self, iface_id: int, ip: str) -> None:
        """
        Remove an ip address from an interface in the format "10.0.0.1/24".

        :param iface_id: id of interface to delete address from
        :param ip: ip address to remove from interface
        :return: nothing
        :raises CoreError: when ip address provided is invalid
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        iface = self.get_iface(iface_id)
        iface.remove_ip(ip)
        if self.up:
            self.node_net_client.delete_address(iface.name, ip)

    def ifup(self, iface_id: int) -> None:
        """
        Bring an interface up.

        :param iface_id: index of interface to bring up
        :return: nothing
        """
        if self.up:
            iface = self.get_iface(iface_id)
            self.node_net_client.device_up(iface.name)

    def new_iface(
        self, net: "CoreNetworkBase", iface_data: InterfaceData
    ) -> CoreInterface:
        """
        Create a new network interface.

        :param net: network to associate with
        :param iface_data: interface data for new interface
        :return: interface index
        """
        with self.lock:
            if net.has_custom_iface:
                return net.custom_iface(self, iface_data)
            else:
                iface_id = self.newveth(iface_data.id, iface_data.name)
                self.attachnet(iface_id, net)
                if iface_data.mac:
                    self.set_mac(iface_id, iface_data.mac)
                for ip in iface_data.get_ips():
                    self.add_ip(iface_id, ip)
                self.ifup(iface_id)
                return self.get_iface(iface_id)

    def addfile(self, srcname: str, filename: str) -> None:
        """
        Add a file.

        :param srcname: source file name
        :param filename: file name to add
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.info("adding file from %s to %s", srcname, filename)
        directory = os.path.dirname(filename)
        if self.server is None:
            self.client.check_cmd(f"mkdir -p {directory}")
            self.client.check_cmd(f"mv {srcname} {filename}")
            self.client.check_cmd("sync")
        else:
            self.host_cmd(f"mkdir -p {directory}")
            self.server.remote_put(srcname, filename)

    def hostfilename(self, filename: str) -> str:
        """
        Return the name of a node"s file on the host filesystem.

        :param filename: host file name
        :return: path to file
        """
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError(f"no basename for filename: {filename}")
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        return os.path.join(dirname, basename)

    def nodefile(self, filename: str, contents: str, mode: int = 0o644) -> None:
        """
        Create a node file with a given mode.

        :param filename: name of file to create
        :param contents: contents of file
        :param mode: mode for file
        :return: nothing
        """
        hostfilename = self.hostfilename(filename)
        dirname, _basename = os.path.split(hostfilename)
        if self.server is None:
            if not os.path.isdir(dirname):
                os.makedirs(dirname, mode=0o755)
            with open(hostfilename, "w") as open_file:
                open_file.write(contents)
                os.chmod(open_file.name, mode)
        else:
            self.host_cmd(f"mkdir -m {0o755:o} -p {dirname}")
            self.server.remote_put_temp(hostfilename, contents)
            self.host_cmd(f"chmod {mode:o} {hostfilename}")
        logging.debug(
            "node(%s) added file: %s; mode: 0%o", self.name, hostfilename, mode
        )

    def nodefilecopy(self, filename: str, srcfilename: str, mode: int = None) -> None:
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param filename: file name to copy file to
        :param srcfilename: file to copy
        :param mode: mode to copy to
        :return: nothing
        """
        hostfilename = self.hostfilename(filename)
        if self.server is None:
            shutil.copy2(srcfilename, hostfilename)
        else:
            self.server.remote_put(srcfilename, hostfilename)
        if mode is not None:
            self.host_cmd(f"chmod {mode:o} {hostfilename}")
        logging.info(
            "node(%s) copied file: %s; mode: %s", self.name, hostfilename, mode
        )


class CoreNetworkBase(NodeBase):
    """
    Base class for networks
    """

    linktype: LinkTypes = LinkTypes.WIRED
    has_custom_iface: bool = False

    def __init__(
        self,
        session: "Session",
        _id: int,
        name: str,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Create a CoreNetworkBase instance.

        :param session: CORE session object
        :param _id: object id
        :param name: object name
        :param server: remote server node
            will run on, default is None for localhost
        """
        super().__init__(session, _id, name, server)
        self.brname = None
        self._linked = {}
        self._linked_lock = threading.Lock()

    @abc.abstractmethod
    def startup(self) -> None:
        """
        Each object implements its own startup method.

        :return: nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def shutdown(self) -> None:
        """
        Each object implements its own shutdown method.

        :return: nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def linknet(self, net: "CoreNetworkBase") -> CoreInterface:
        """
        Link network to another.

        :param net: network to link with
        :return: created interface
        """
        raise NotImplementedError

    @abc.abstractmethod
    def linkconfig(
        self, iface: CoreInterface, options: LinkOptions, iface2: CoreInterface = None
    ) -> None:
        """
        Configure link parameters by applying tc queuing disciplines on the interface.

        :param iface: interface one
        :param options: options for configuring link
        :param iface2: interface two
        :return: nothing
        """
        raise NotImplementedError

    def custom_iface(self, node: CoreNode, iface_data: InterfaceData) -> CoreInterface:
        raise NotImplementedError

    def get_linked_iface(self, net: "CoreNetworkBase") -> Optional[CoreInterface]:
        """
        Return the interface that links this net with another net.

        :param net: interface to get link for
        :return: interface the provided network is linked to
        """
        for iface in self.get_ifaces():
            if iface.othernet == net:
                return iface
        return None

    def attach(self, iface: CoreInterface) -> None:
        """
        Attach network interface.

        :param iface: network interface to attach
        :return: nothing
        """
        i = self.next_iface_id()
        self.ifaces[i] = iface
        iface.net_id = i
        with self._linked_lock:
            self._linked[iface] = {}

    def detach(self, iface: CoreInterface) -> None:
        """
        Detach network interface.

        :param iface: network interface to detach
        :return: nothing
        """
        del self.ifaces[iface.net_id]
        iface.net_id = None
        with self._linked_lock:
            del self._linked[iface]

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        """
        Build link data objects for this network. Each link object describes a link
        between this network and a node.

        :param flags: message type
        :return: list of link data
        """
        all_links = []

        # build a link message from this network node to each node having a
        # connected interface
        for iface in self.get_ifaces():
            uni = False
            linked_node = iface.node
            if linked_node is None:
                # two layer-2 switches/hubs linked together via linknet()
                if not iface.othernet:
                    continue
                linked_node = iface.othernet
                if linked_node.id == self.id:
                    continue
                iface.swapparams("_params_up")
                upstream_params = iface.getparams()
                iface.swapparams("_params_up")
                if iface.getparams() != upstream_params:
                    uni = True

            unidirectional = 0
            if uni:
                unidirectional = 1

            iface2_data = InterfaceData(
                id=linked_node.get_iface_id(iface), name=iface.name, mac=str(iface.mac)
            )
            ip4 = iface.get_ip4()
            if ip4:
                iface2_data.ip4 = str(ip4.ip)
                iface2_data.ip4_mask = ip4.prefixlen
            ip6 = iface.get_ip6()
            if ip6:
                iface2_data.ip6 = str(ip6.ip)
                iface2_data.ip6_mask = ip6.prefixlen

            options_data = iface.get_link_options(unidirectional)
            link_data = LinkData(
                message_type=flags,
                type=self.linktype,
                node1_id=self.id,
                node2_id=linked_node.id,
                iface2=iface2_data,
                options=options_data,
            )
            all_links.append(link_data)

            if not uni:
                continue
            iface.swapparams("_params_up")
            options_data = iface.get_link_options(unidirectional)
            link_data = LinkData(
                message_type=MessageFlags.NONE,
                type=self.linktype,
                node1_id=linked_node.id,
                node2_id=self.id,
                options=options_data,
            )
            iface.swapparams("_params_up")
            all_links.append(link_data)
        return all_links


class Position:
    """
    Helper class for Cartesian coordinate position
    """

    def __init__(self, x: float = None, y: float = None, z: float = None) -> None:
        """
        Creates a Position instance.

        :param x: x position
        :param y: y position
        :param z: z position
        """
        self.x: float = x
        self.y: float = y
        self.z: float = z
        self.lon: Optional[float] = None
        self.lat: Optional[float] = None
        self.alt: Optional[float] = None

    def set(self, x: float = None, y: float = None, z: float = None) -> bool:
        """
        Returns True if the position has actually changed.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: True if position changed, False otherwise
        """
        if self.x == x and self.y == y and self.z == z:
            return False
        self.x = x
        self.y = y
        self.z = z
        return True

    def get(self) -> Tuple[float, float, float]:
        """
        Retrieve x,y,z position.

        :return: x,y,z position tuple
        """
        return self.x, self.y, self.z

    def set_geo(self, lon: float, lat: float, alt: float) -> None:
        """
        Set geo position lon, lat, alt.

        :param lon: longitude value
        :param lat: latitude value
        :param alt: altitude value
        :return: nothing
        """
        self.lon = lon
        self.lat = lat
        self.alt = alt

    def get_geo(self) -> Tuple[float, float, float]:
        """
        Retrieve current geo position lon, lat, alt.

        :return: lon, lat, alt position tuple
        """
        return self.lon, self.lat, self.alt
