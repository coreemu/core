"""
Defines the base logic for nodes used within core.
"""
import abc
import logging
import shutil
import threading
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type, Union

import netaddr

from core import utils
from core.configservice.dependencies import ConfigServiceDependencies
from core.emulator.data import InterfaceData, LinkOptions
from core.emulator.enumerations import LinkTypes, NodeTypes
from core.errors import CoreCommandError, CoreError
from core.executables import BASH, MOUNT, TEST, VCMD, VNODED
from core.nodes.interface import DEFAULT_MTU, CoreInterface
from core.nodes.netclient import LinuxNetClient, get_net_client

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.distributed import DistributedServer
    from core.emulator.session import Session
    from core.configservice.base import ConfigService
    from core.services.coreservices import CoreService

    CoreServices = List[Union[CoreService, Type[CoreService]]]
    ConfigServiceType = Type[ConfigService]

PRIVATE_DIRS: List[Path] = [Path("/var/run"), Path("/var/log")]


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
        self.lock: RLock = RLock()
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

    @abc.abstractmethod
    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        """
        Adopt an interface, placing within network namespacing for containers
        and setting to bridge masters for network like nodes.

        :param iface: interface to adopt
        :param name: proper name to use for interface
        :return: nothing
        """
        raise NotImplementedError

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

    def create_iface(
        self, iface_data: InterfaceData = None, options: LinkOptions = None
    ) -> CoreInterface:
        """
        Creates an interface and adopts it to a node.

        :param iface_data: data to create interface with
        :param options: options to create interface with
        :return: created interface
        """
        with self.lock:
            if iface_data and iface_data.id is not None:
                if iface_data.id in self.ifaces:
                    raise CoreError(
                        f"node({self.id}) interface({iface_data.id}) already exists"
                    )
                iface_id = iface_data.id
            else:
                iface_id = self.next_iface_id()
            mtu = DEFAULT_MTU
            if iface_data and iface_data.mtu is not None:
                mtu = iface_data.mtu
            name = f"veth{self.id}.{iface_id}.{self.session.short_session_id()}"
            localname = f"{name}p"
            iface = CoreInterface(
                iface_id,
                name,
                localname,
                self.session.use_ovs(),
                mtu,
                node=self,
                server=self.server,
            )
            if iface_data:
                if iface_data.mac:
                    iface.set_mac(iface_data.mac)
                for ip in iface_data.get_ips():
                    iface.add_ip(ip)
            if options:
                iface.options.update(options)
            self.ifaces[iface_id] = iface
        if self.up:
            iface.startup()
            if iface_data and iface_data.name is not None:
                name = iface_data.name
            else:
                name = iface.name
            self.adopt_iface(iface, name)
        return iface

    def delete_iface(self, iface_id: int) -> CoreInterface:
        """
        Delete an interface.

        :param iface_id: interface id to delete
        :return: the removed interface
        """
        if iface_id not in self.ifaces:
            raise CoreError(f"node({self.name}) interface({iface_id}) does not exist")
        iface = self.ifaces.pop(iface_id)
        logger.info("node(%s) removing interface(%s)", self.name, iface.name)
        iface.shutdown()
        return iface

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
            if not control and iface.control:
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
        self.directory: Optional[Path] = None
        self.tmpnodedir: bool = False

    @abc.abstractmethod
    def create_dir(self, dir_path: Path) -> None:
        """
        Create a node private directory.

        :param dir_path: path to create
        :return: nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def create_file(self, file_path: Path, contents: str, mode: int = 0o644) -> None:
        """
        Create a node file with a given mode.

        :param file_path: name of file to create
        :param contents: contents of file
        :param mode: mode for file
        :return: nothing
        """
        raise NotImplementedError

    @abc.abstractmethod
    def copy_file(self, src_path: Path, dst_path: Path, mode: int = None) -> None:
        """
        Copy source file to node host destination, updating the file mode when
        provided.

        :param src_path: source file to copy
        :param dst_path: node host destination
        :param mode: file mode
        :return: nothing
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
    def path_exists(self, path: str) -> bool:
        """
        Determines if a file or directory path exists.

        :param path: path to file or directory
        :return: True if path exists, False otherwise
        """
        raise NotImplementedError

    def host_path(self, path: Path, is_dir: bool = False) -> Path:
        """
        Return the name of a node's file on the host filesystem.

        :param path: path to translate to host path
        :param is_dir: True if path is a directory path, False otherwise
        :return: path to file
        """
        if is_dir:
            directory = str(path).strip("/").replace("/", ".")
            return self.directory / directory
        else:
            directory = str(path.parent).strip("/").replace("/", ".")
            return self.directory / directory / path.name

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
        if self.directory is None:
            self.directory = self.session.directory / f"{self.name}.conf"
            self.host_cmd(f"mkdir -p {self.directory}")
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
            self.host_cmd(f"rm -rf {self.directory}")

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
        directory: Path = None,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Create a CoreNode instance.

        :param session: core session instance
        :param _id: object id
        :param name: object name
        :param directory: node directory
        :param server: remote server node
            will run on, default is None for localhost
        """
        super().__init__(session, _id, name, server)
        self.directory: Optional[Path] = directory
        self.ctrlchnlname: Path = self.session.directory / self.name
        self.pid: Optional[int] = None
        self._mounts: List[Tuple[Path, Path]] = []
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
            if self.directory:
                vnoded += f" -C {self.directory}"
            env = self.session.get_environment(state=False)
            env["NODE_NUMBER"] = str(self.id)
            env["NODE_NAME"] = str(self.name)
            output = self.host_cmd(vnoded, env=env)
            self.pid = int(output)
            logger.debug("node(%s) pid: %s", self.name, self.pid)
            # bring up the loopback interface
            logger.debug("bringing up loopback interface")
            self.node_net_client.device_up("lo")
            # set hostname for node
            logger.debug("setting hostname: %s", self.name)
            self.node_net_client.set_hostname(self.name)
            # mark node as up
            self.up = True
            # create private directories
            for dir_path in PRIVATE_DIRS:
                self.create_dir(dir_path)

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
                    try:
                        self.node_net_client.device_flush(iface.name)
                    except CoreCommandError:
                        pass
                    iface.shutdown()
                # kill node process if present
                try:
                    self.host_cmd(f"kill -9 {self.pid}")
                except CoreCommandError:
                    logger.exception("error killing process")
                # remove node directory if present
                try:
                    self.host_cmd(f"rm -rf {self.ctrlchnlname}")
                except CoreCommandError:
                    logger.exception("error removing node directory")
                # clear interface data, close client, and mark self and not up
                self.ifaces.clear()
                self.up = False
            except OSError:
                logger.exception("error during shutdown")
            finally:
                self.rmnodedir()

    def _create_cmd(self, args: str, shell: bool = False) -> str:
        """
        Create command used to run commands within the context of a node.

        :param args: command arguments
        :param shell: True to run shell like, False otherwise
        :return: node command
        """
        if shell:
            args = f'{BASH} -c "{args}"'
        return f"{VCMD} -c {self.ctrlchnlname} -- {args}"

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
        args = self._create_cmd(args, shell)
        if self.server is None:
            return utils.cmd(args, wait=wait, shell=shell)
        else:
            return self.server.remote_cmd(args, wait=wait)

    def path_exists(self, path: str) -> bool:
        """
        Determines if a file or directory path exists.

        :param path: path to file or directory
        :return: True if path exists, False otherwise
        """
        try:
            self.cmd(f"{TEST} -e {path}")
            return True
        except CoreCommandError:
            return False

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        terminal = self._create_cmd(sh)
        if self.server is None:
            return terminal
        else:
            return f"ssh -X -f {self.server.host} xterm -e {terminal}"

    def create_dir(self, dir_path: Path) -> None:
        """
        Create a node private directory.

        :param dir_path: path to create
        :return: nothing
        """
        if not dir_path.is_absolute():
            raise CoreError(f"private directory path not fully qualified: {dir_path}")
        logger.debug("node(%s) creating private directory: %s", self.name, dir_path)
        parent_path = self._find_parent_path(dir_path)
        if parent_path:
            self.host_cmd(f"mkdir -p {parent_path}")
        else:
            host_path = self.host_path(dir_path, is_dir=True)
            self.host_cmd(f"mkdir -p {host_path}")
            self.mount(host_path, dir_path)

    def mount(self, src_path: Path, target_path: Path) -> None:
        """
        Create and mount a directory.

        :param src_path: source directory to mount
        :param target_path: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logger.debug("node(%s) mounting: %s at %s", self.name, src_path, target_path)
        self.cmd(f"mkdir -p {target_path}")
        self.cmd(f"{MOUNT} -n --bind {src_path} {target_path}")
        self._mounts.append((src_path, target_path))

    def _find_parent_path(self, path: Path) -> Optional[Path]:
        """
        Check if there is a mounted parent directory created for this node.

        :param path: existing parent path to use
        :return: exist parent path if exists, None otherwise
        """
        logger.debug("looking for existing parent: %s", path)
        existing_path = None
        for parent in path.parents:
            node_path = self.host_path(parent, is_dir=True)
            if node_path == self.directory:
                break
            if self.path_exists(str(node_path)):
                relative_path = path.relative_to(parent)
                existing_path = node_path / relative_path
                break
        return existing_path

    def create_file(self, file_path: Path, contents: str, mode: int = 0o644) -> None:
        """
        Create file within a node at the given path, using contents and mode.

        :param file_path: desired path for file
        :param contents: contents of file
        :param mode: mode to create file with
        :return: nothing
        """
        logger.debug("node(%s) create file(%s) mode(%o)", self.name, file_path, mode)
        host_path = self._find_parent_path(file_path)
        if host_path:
            self.host_cmd(f"mkdir -p {host_path.parent}")
        else:
            host_path = self.host_path(file_path)
        directory = host_path.parent
        if self.server is None:
            if not directory.exists():
                directory.mkdir(parents=True, mode=0o755)
            with host_path.open("w") as f:
                f.write(contents)
            host_path.chmod(mode)
        else:
            self.host_cmd(f"mkdir -m {0o755:o} -p {directory}")
            self.server.remote_put_temp(host_path, contents)
            self.host_cmd(f"chmod {mode:o} {host_path}")

    def copy_file(self, src_path: Path, dst_path: Path, mode: int = None) -> None:
        """
        Copy source file to node host destination, updating the file mode when
        provided.

        :param src_path: source file to copy
        :param dst_path: node host destination
        :param mode: file mode
        :return: nothing
        """
        logger.debug(
            "node(%s) copying file src(%s) to dst(%s) mode(%o)",
            self.name,
            src_path,
            dst_path,
            mode or 0,
        )
        host_path = self._find_parent_path(dst_path)
        if host_path:
            self.host_cmd(f"mkdir -p {host_path.parent}")
        else:
            host_path = self.host_path(dst_path)
        if self.server is None:
            shutil.copy2(src_path, host_path)
        else:
            self.server.remote_put(src_path, host_path)
        if mode is not None:
            self.host_cmd(f"chmod {mode:o} {host_path}")

    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        """
        Adopt interface to the network namespace of the node and setting
        the proper name provided.

        :param iface: interface to adopt
        :param name: proper name for interface
        :return: nothing
        """
        # TODO: container, checksums off (container only?)
        # TODO: container, get flow id (container only?)
        # validate iface belongs to node and get id
        iface_id = self.get_iface_id(iface)
        if iface_id == -1:
            raise CoreError(f"adopting unknown iface({iface.name})")
        # add iface to container namespace
        self.net_client.device_ns(iface.name, str(self.pid))
        # update iface name to container name
        name = name if name else f"eth{iface_id}"
        self.node_net_client.device_name(iface.name, name)
        iface.name = name
        # turn checksums off
        self.node_net_client.checksums_off(iface.name)
        # retrieve flow id for container
        iface.flow_id = self.node_net_client.get_ifindex(iface.name)
        logger.debug("interface flow index: %s - %s", iface.name, iface.flow_id)
        # set mac address
        self.node_net_client.device_mac(iface.name, str(iface.mac))
        logger.debug("interface mac: %s - %s", iface.name, iface.mac)
        # set all addresses
        for ip in iface.ips():
            # ipv4 check
            broadcast = None
            if netaddr.valid_ipv4(ip):
                broadcast = "+"
            self.node_net_client.create_address(iface.name, str(ip), broadcast)
        # configure iface options
        iface.set_config(self)
        # set iface up
        self.node_net_client.device_up(iface.name)


class CoreNetworkBase(NodeBase):
    """
    Base class for networks
    """

    linktype: LinkTypes = LinkTypes.WIRED

    def __init__(
        self,
        session: "Session",
        _id: int,
        name: str,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Create a CoreNetworkBase instance.

        :param session: session object
        :param _id: object id
        :param name: object name
        :param server: remote server node
            will run on, default is None for localhost
        """
        super().__init__(session, _id, name, server)
        self.mtu: int = DEFAULT_MTU
        self.brname: Optional[str] = None
        self.linked: Dict[CoreInterface, Dict[CoreInterface, bool]] = {}
        self.linked_lock: threading.Lock = threading.Lock()

    def attach(self, iface: CoreInterface) -> None:
        """
        Attach network interface.

        :param iface: network interface to attach
        :return: nothing
        """
        i = self.next_iface_id()
        self.ifaces[i] = iface
        iface.net = self
        iface.net_id = i
        with self.linked_lock:
            self.linked[iface] = {}

    def detach(self, iface: CoreInterface) -> None:
        """
        Detach network interface.

        :param iface: network interface to detach
        :return: nothing
        """
        del self.ifaces[iface.net_id]
        iface.net = None
        iface.net_id = None
        with self.linked_lock:
            del self.linked[iface]


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
