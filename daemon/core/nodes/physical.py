"""
PhysicalNode class for including real systems in the emulated network.
"""

import logging
import os
import threading
from typing import IO, TYPE_CHECKING, List, Optional, Tuple

from core.constants import MOUNT_BIN, UMOUNT_BIN
from core.emulator.data import InterfaceData, LinkOptions
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import NodeTypes, TransportType
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNetworkBase, CoreNodeBase
from core.nodes.interface import CoreInterface
from core.nodes.network import CoreNetwork, GreTap

if TYPE_CHECKING:
    from core.emulator.session import Session


class PhysicalNode(CoreNodeBase):
    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        nodedir: str = None,
        server: DistributedServer = None,
    ) -> None:
        super().__init__(session, _id, name, server)
        if not self.server:
            raise CoreError("physical nodes must be assigned to a remote server")
        self.nodedir: Optional[str] = nodedir
        self.lock: threading.RLock = threading.RLock()
        self._mounts: List[Tuple[str, str]] = []

    def startup(self) -> None:
        with self.lock:
            self.makenodedir()
            self.up = True

    def shutdown(self) -> None:
        if not self.up:
            return

        with self.lock:
            while self._mounts:
                _source, target = self._mounts.pop(-1)
                self.umount(target)

            for iface in self.get_ifaces():
                iface.shutdown()

            self.rmnodedir()

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
            self.net_client.device_mac(iface.name, mac)

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

    def linkconfig(
        self, iface: CoreInterface, options: LinkOptions, iface2: CoreInterface = None
    ) -> None:
        """
        Apply tc queing disciplines using linkconfig.
        """
        linux_bridge = CoreNetwork(self.session)
        linux_bridge.up = True
        linux_bridge.linkconfig(iface, options, iface2)
        del linux_bridge

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
        logging.info("creating interface")
        ips = iface_data.get_ips()
        iface_id = iface_data.id
        if iface_id is None:
            iface_id = self.next_iface_id()
        name = iface_data.name
        if name is None:
            name = f"gt{iface_id}"
        if self.up:
            # this is reached when this node is linked to a network node
            # tunnel to net not built yet, so build it now and adopt it
            _, remote_tap = self.session.distributed.create_gre_tunnel(net, self.server)
            self.adopt_iface(remote_tap, iface_id, iface_data.mac, ips)
            return remote_tap
        else:
            # this is reached when configuring services (self.up=False)
            iface = GreTap(node=self, name=name, session=self.session, start=False)
            self.adopt_iface(iface, iface_id, iface_data.mac, ips)
            return iface

    def privatedir(self, path: str) -> None:
        if path[0] != "/":
            raise ValueError(f"path not fully qualified: {path}")
        hostpath = os.path.join(
            self.nodedir, os.path.normpath(path).strip("/").replace("/", ".")
        )
        os.mkdir(hostpath)
        self.mount(hostpath, path)

    def mount(self, source: str, target: str) -> None:
        source = os.path.abspath(source)
        logging.info("mounting %s at %s", source, target)
        os.makedirs(target)
        self.host_cmd(f"{MOUNT_BIN} --bind {source} {target}", cwd=self.nodedir)
        self._mounts.append((source, target))

    def umount(self, target: str) -> None:
        logging.info("unmounting '%s'", target)
        try:
            self.host_cmd(f"{UMOUNT_BIN} -l {target}", cwd=self.nodedir)
        except CoreCommandError:
            logging.exception("unmounting failed for %s", target)

    def opennodefile(self, filename: str, mode: str = "w") -> IO:
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError("no basename for filename: " + filename)

        if dirname and dirname[0] == "/":
            dirname = dirname[1:]

        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode=0o755)

        hostfilename = os.path.join(dirname, basename)
        return open(hostfilename, mode)

    def nodefile(self, filename: str, contents: str, mode: int = 0o644) -> None:
        with self.opennodefile(filename, "w") as f:
            f.write(contents)
            os.chmod(f.name, mode)
            logging.info("created nodefile: '%s'; mode: 0%o", f.name, mode)

    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        return self.host_cmd(args, wait=wait)

    def addfile(self, srcname: str, filename: str) -> None:
        raise CoreError("physical node does not support addfile")


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
        mtu: int = 1500,
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
        self.iface = CoreInterface(session, self, name, name, mtu, server)
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
                raise CoreError("RJ45 nodes support at most 1 network interface")
            self.ifaces[iface_id] = self.iface
            self.iface_id = iface_id
            if net is not None:
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
        logging.info("saved rj45 state: addrs(%s) up(%s)", self.old_addrs, self.old_up)

    def restorestate(self) -> None:
        """
        Restore the addresses and other interface state after using it.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        localname = self.iface.localname
        logging.info("restoring rj45 state: %s", localname)
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

    def addfile(self, srcname: str, filename: str) -> None:
        raise CoreError("rj45 does not support addfile")

    def nodefile(self, filename: str, contents: str, mode: int = 0o644) -> None:
        raise CoreError("rj45 does not support nodefile")

    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        raise CoreError("rj45 does not support cmds")
