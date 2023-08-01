"""
PhysicalNode class for including real systems in the emulated network.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import netaddr

from core.emulator.data import InterfaceData, LinkOptions
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import TransportType
from core.errors import CoreCommandError, CoreError
from core.executables import BASH, TEST, UMOUNT
from core.nodes.base import CoreNode, CoreNodeBase, CoreNodeOptions, NodeOptions
from core.nodes.interface import CoreInterface

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session


class Rj45Node(CoreNodeBase):
    """
    RJ45Node is a physical interface on the host linked to the emulated
    network.
    """

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: DistributedServer = None,
        options: NodeOptions = None,
    ) -> None:
        """
        Create an RJ45Node instance.

        :param session: core session instance
        :param _id: node id
        :param name: node name
        :param server: remote server node
            will run on, default is None for localhost
        :param options: option to create node with
        """
        super().__init__(session, _id, name, server, options)
        self.iface: CoreInterface = CoreInterface(
            self.iface_id, name, name, session.use_ovs(), node=self, server=server
        )
        self.iface.transport_type = TransportType.RAW
        self.old_up: bool = False
        self.old_addrs: list[tuple[str, Optional[str]]] = []

    def startup(self) -> None:
        """
        Set the interface in the up state.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        # interface will also be marked up during net.attach()
        self.save_state()
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
        self.restore_state()

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

    def create_iface(
        self, iface_data: InterfaceData = None, options: LinkOptions = None
    ) -> CoreInterface:
        with self.lock:
            if self.iface.id in self.ifaces:
                raise CoreError(
                    f"rj45({self.name}) nodes support at most 1 network interface"
                )
            if iface_data and iface_data.mtu is not None:
                self.iface.mtu = iface_data.mtu
            self.iface.ip4s.clear()
            self.iface.ip6s.clear()
            for ip in iface_data.get_ips():
                self.iface.add_ip(ip)
            self.ifaces[self.iface.id] = self.iface
        if self.up:
            for ip in self.iface.ips():
                self.net_client.create_address(self.iface.name, str(ip))
        return self.iface

    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        raise CoreError(f"rj45({self.name}) does not support adopt interface")

    def delete_iface(self, iface_id: int) -> None:
        """
        Delete a network interface.

        :param iface_id: interface index to delete
        :return: nothing
        """
        self.get_iface(iface_id)
        self.ifaces.pop(iface_id)
        self.shutdown()

    def get_iface(self, iface_id: int) -> CoreInterface:
        if iface_id not in self.ifaces:
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
        return self.iface.id

    def save_state(self) -> None:
        """
        Save the addresses and other interface state before using the
        interface for emulation purposes.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        # TODO: save/restore the PROMISC flag
        self.old_up = False
        self.old_addrs: list[tuple[str, Optional[str]]] = []
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
                broadcast = None
                if items[2] == "brd":
                    broadcast = items[3]
                self.old_addrs.append((items[1], broadcast))
            elif items[0] == "inet6":
                if items[1][:4] == "fe80":
                    continue
                self.old_addrs.append((items[1], None))
        logger.info("saved rj45 state: addrs(%s) up(%s)", self.old_addrs, self.old_up)

    def restore_state(self) -> None:
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


class PhysicalNode(CoreNode):
    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: DistributedServer = None,
        options: CoreNodeOptions = None,
    ) -> None:
        if not self.server:
            raise CoreError("physical nodes must be assigned to a remote server")
        super().__init__(session, _id, name, server, options)

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

    def create_cmd(self, args: str, shell: bool = False) -> str:
        if shell:
            args = f'{BASH} -c "{args}"'
        return args

    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        # validate iface belongs to node and get id
        iface_id = self.get_iface_id(iface)
        if iface_id == -1:
            raise CoreError(f"adopting unknown iface({iface.name})")
        # turn checksums off
        self.node_net_client.checksums_off(iface.name)
        # retrieve flow id for container
        iface.flow_id = self.node_net_client.get_ifindex(iface.name)
        logger.debug("interface flow index: %s - %s", iface.name, iface.flow_id)
        if iface.mac:
            self.net_client.device_mac(iface.name, str(iface.mac))
        # set all addresses
        for ip in iface.ips():
            # ipv4 check
            broadcast = None
            if netaddr.valid_ipv4(ip):
                broadcast = "+"
            self.node_net_client.create_address(iface.name, str(ip), broadcast)
        # configure iface options
        iface.set_config()
        # set iface up
        self.net_client.device_up(iface.name)

    def umount(self, target_path: Path) -> None:
        logger.info("unmounting '%s'", target_path)
        try:
            self.host_cmd(f"{UMOUNT} -l {target_path}", cwd=self.directory)
        except CoreCommandError:
            logger.exception("unmounting failed for %s", target_path)
