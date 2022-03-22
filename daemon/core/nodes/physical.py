"""
PhysicalNode class for including real systems in the emulated network.
"""

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from core.emulator.data import InterfaceData
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import NodeTypes, TransportType
from core.errors import CoreCommandError, CoreError
from core.executables import MOUNT, TEST, UMOUNT
from core.nodes.base import CoreNetworkBase, CoreNodeBase
from core.nodes.interface import DEFAULT_MTU, CoreInterface

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session


class PhysicalNode(CoreNodeBase):
    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        directory: Path = None,
        server: DistributedServer = None,
    ) -> None:
        super().__init__(session, _id, name, server)
        if not self.server:
            raise CoreError("physical nodes must be assigned to a remote server")
        self.directory: Optional[Path] = directory
        self.lock: threading.RLock = threading.RLock()
        self._mounts: List[Tuple[Path, Path]] = []

    def startup(self) -> None:
        with self.lock:
            self.makenodedir()
            self.up = True

    def shutdown(self) -> None:
        if not self.up:
            return
        with self.lock:
            while self._mounts:
                _, target_path = self._mounts.pop(-1)
                self.umount(target_path)
            for iface in self.get_ifaces():
                iface.shutdown()
            self.rmnodedir()

    def path_exists(self, path: str) -> bool:
        """
        Determines if a file or directory path exists.

        :param path: path to file or directory
        :return: True if path exists, False otherwise
        """
        try:
            self.host_cmd(f"{TEST} -e {path}")
            return True
        except CoreCommandError:
            return False

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        return sh

    def set_mac(self, iface_id: int, mac: str) -> None:
        """
        Set mac address for an interface.

        :param iface_id: index of interface to set hardware address for
        :param mac: mac address to set
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        iface = self.get_iface(iface_id)
        iface.set_mac(mac)
        if self.up:
            self.net_client.device_mac(iface.name, str(iface.mac))

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
            self.net_client.create_address(iface.name, ip)

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
            self.net_client.delete_address(iface.name, ip)

    def adopt_iface(
        self, iface: CoreInterface, iface_id: int, mac: str, ips: List[str]
    ) -> None:
        """
        When a link message is received linking this node to another part of
        the emulation, no new interface is created; instead, adopt the
        GreTap interface as the node interface.
        """
        iface.name = f"gt{iface_id}"
        iface.node = self
        self.add_iface(iface, iface_id)
        # use a more reasonable name, e.g. "gt0" instead of "gt.56286.150"
        if self.up:
            self.net_client.device_down(iface.localname)
            self.net_client.device_name(iface.localname, iface.name)
        iface.localname = iface.name
        if mac:
            self.set_mac(iface_id, mac)
        for ip in ips:
            self.add_ip(iface_id, ip)
        if self.up:
            self.net_client.device_up(iface.localname)

    def next_iface_id(self) -> int:
        with self.lock:
            while self.iface_id in self.ifaces:
                self.iface_id += 1
            iface_id = self.iface_id
            self.iface_id += 1
            return iface_id

    def new_iface(
        self, net: CoreNetworkBase, iface_data: InterfaceData
    ) -> CoreInterface:
        logger.info("creating interface")
        ips = iface_data.get_ips()
        iface_id = iface_data.id
        if iface_id is None:
            iface_id = self.next_iface_id()
        name = iface_data.name
        if name is None:
            name = f"gt{iface_id}"
        _, remote_tap = self.session.distributed.create_gre_tunnel(
            net, self.server, iface_data.mtu, self.up
        )
        self.adopt_iface(remote_tap, iface_id, iface_data.mac, ips)
        return remote_tap

    def privatedir(self, dir_path: Path) -> None:
        if not str(dir_path).startswith("/"):
            raise CoreError(f"private directory path not fully qualified: {dir_path}")
        host_path = self.host_path(dir_path, is_dir=True)
        self.host_cmd(f"mkdir -p {host_path}")
        self.mount(host_path, dir_path)

    def mount(self, src_path: Path, target_path: Path) -> None:
        logger.debug("node(%s) mounting: %s at %s", self.name, src_path, target_path)
        self.cmd(f"mkdir -p {target_path}")
        self.host_cmd(f"{MOUNT} --bind {src_path} {target_path}", cwd=self.directory)
        self._mounts.append((src_path, target_path))

    def umount(self, target_path: Path) -> None:
        logger.info("unmounting '%s'", target_path)
        try:
            self.host_cmd(f"{UMOUNT} -l {target_path}", cwd=self.directory)
        except CoreCommandError:
            logger.exception("unmounting failed for %s", target_path)

    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        return self.host_cmd(args, wait=wait)

    def create_dir(self, dir_path: Path) -> None:
        raise CoreError("physical node does not support creating directories")

    def create_file(self, file_path: Path, contents: str, mode: int = 0o644) -> None:
        raise CoreError("physical node does not support creating files")

    def copy_file(self, src_path: Path, dst_path: Path, mode: int = None) -> None:
        raise CoreError("physical node does not support copying files")


class Rj45Node(CoreNodeBase):
    """
    RJ45Node is a physical interface on the host linked to the emulated
    network.
    """

    apitype: NodeTypes = NodeTypes.RJ45
    type: str = "rj45"

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        mtu: int = DEFAULT_MTU,
        server: DistributedServer = None,
    ) -> None:
        """
        Create an RJ45Node instance.

        :param session: core session instance
        :param _id: node id
        :param name: node name
        :param mtu: rj45 mtu
        :param server: remote server node
            will run on, default is None for localhost
        """
        super().__init__(session, _id, name, server)
        self.iface: CoreInterface = CoreInterface(
            session, name, name, mtu, server, self
        )
        self.iface.transport_type = TransportType.RAW
        self.lock: threading.RLock = threading.RLock()
        self.iface_id: Optional[int] = None
        self.old_up: bool = False
        self.old_addrs: List[Tuple[str, Optional[str]]] = []

    def startup(self) -> None:
        """
        Set the interface in the up state.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        # interface will also be marked up during net.attach()
        self.savestate()
        self.net_client.device_up(self.iface.localname)
        self.up = True

    def shutdown(self) -> None:
        """
        Bring the interface down. Remove any addresses and queuing
        disciplines.

        :return: nothing
        """
        if not self.up:
            return
        localname = self.iface.localname
        self.net_client.device_down(localname)
        self.net_client.device_flush(localname)
        try:
            self.net_client.delete_tc(localname)
        except CoreCommandError:
            pass
        self.up = False
        self.restorestate()

    def path_exists(self, path: str) -> bool:
        """
        Determines if a file or directory path exists.

        :param path: path to file or directory
        :return: True if path exists, False otherwise
        """
        try:
            self.host_cmd(f"{TEST} -e {path}")
            return True
        except CoreCommandError:
            return False

    def new_iface(
        self, net: CoreNetworkBase, iface_data: InterfaceData
    ) -> CoreInterface:
        """
        This is called when linking with another node. Since this node
        represents an interface, we do not create another object here,
        but attach ourselves to the given network.

        :param net: new network instance
        :param iface_data: interface data for new interface
        :return: interface index
        :raises ValueError: when an interface has already been created, one max
        """
        with self.lock:
            iface_id = iface_data.id
            if iface_id is None:
                iface_id = 0
            if self.iface.net is not None:
                raise CoreError(
                    f"RJ45({self.name}) nodes support at most 1 network interface"
                )
            self.ifaces[iface_id] = self.iface
            self.iface_id = iface_id
            self.iface.attachnet(net)
            for ip in iface_data.get_ips():
                self.add_ip(ip)
            return self.iface

    def delete_iface(self, iface_id: int) -> None:
        """
        Delete a network interface.

        :param iface_id: interface index to delete
        :return: nothing
        """
        self.get_iface(iface_id)
        self.ifaces.pop(iface_id)
        if self.iface.net is None:
            raise CoreError(
                f"RJ45({self.name}) is not currently connected to a network"
            )
        self.iface.detachnet()
        self.iface.net = None
        self.shutdown()

    def get_iface(self, iface_id: int) -> CoreInterface:
        if iface_id != self.iface_id or iface_id not in self.ifaces:
            raise CoreError(f"node({self.name}) interface({iface_id}) does not exist")
        return self.iface

    def get_iface_id(self, iface: CoreInterface) -> Optional[int]:
        """
        Retrieve network interface index.

        :param iface: network interface to retrieve
            index for
        :return: interface index, None otherwise
        """
        if iface is not self.iface:
            raise CoreError(f"node({self.name}) does not have interface({iface.name})")
        return self.iface_id

    def add_ip(self, ip: str) -> None:
        """
        Add an ip address to an interface in the format "10.0.0.1/24".

        :param ip: address to add to interface
        :return: nothing
        :raises CoreError: when ip address provided is invalid
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        self.iface.add_ip(ip)
        if self.up:
            self.net_client.create_address(self.name, ip)

    def remove_ip(self, ip: str) -> None:
        """
        Remove an ip address from an interface in the format "10.0.0.1/24".

        :param ip: ip address to remove from interface
        :return: nothing
        :raises CoreError: when ip address provided is invalid
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        self.iface.remove_ip(ip)
        if self.up:
            self.net_client.delete_address(self.name, ip)

    def savestate(self) -> None:
        """
        Save the addresses and other interface state before using the
        interface for emulation purposes. TODO: save/restore the PROMISC flag

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.old_up = False
        self.old_addrs: List[Tuple[str, Optional[str]]] = []
        localname = self.iface.localname
        output = self.net_client.address_show(localname)
        for line in output.split("\n"):
            items = line.split()
            if len(items) < 2:
                continue
            if items[1] == f"{localname}:":
                flags = items[2][1:-1].split(",")
                if "UP" in flags:
                    self.old_up = True
            elif items[0] == "inet":
                self.old_addrs.append((items[1], items[3]))
            elif items[0] == "inet6":
                if items[1][:4] == "fe80":
                    continue
                self.old_addrs.append((items[1], None))
        logger.info("saved rj45 state: addrs(%s) up(%s)", self.old_addrs, self.old_up)

    def restorestate(self) -> None:
        """
        Restore the addresses and other interface state after using it.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        localname = self.iface.localname
        logger.info("restoring rj45 state: %s", localname)
        for addr in self.old_addrs:
            self.net_client.create_address(localname, addr[0], addr[1])
        if self.old_up:
            self.net_client.device_up(localname)

    def setposition(self, x: float = None, y: float = None, z: float = None) -> None:
        """
        Uses setposition from both parent classes.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: True if position changed, False otherwise
        """
        super().setposition(x, y, z)
        self.iface.setposition()

    def termcmdstring(self, sh: str) -> str:
        raise CoreError("rj45 does not support terminal commands")

    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        raise CoreError("rj45 does not support cmds")

    def create_dir(self, dir_path: Path) -> None:
        raise CoreError("rj45 does not support creating directories")

    def create_file(self, file_path: Path, contents: str, mode: int = 0o644) -> None:
        raise CoreError("rj45 does not support creating files")

    def copy_file(self, src_path: Path, dst_path: Path, mode: int = None) -> None:
        raise CoreError("rj45 does not support copying files")
