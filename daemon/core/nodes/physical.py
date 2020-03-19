"""
PhysicalNode class for including real systems in the emulated network.
"""

import logging
import os
import threading
from typing import IO, TYPE_CHECKING, List, Optional

from core import utils
from core.constants import MOUNT_BIN, UMOUNT_BIN
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNetworkBase, CoreNodeBase
from core.nodes.interface import CoreInterface, Veth
from core.nodes.network import CoreNetwork, GreTap

if TYPE_CHECKING:
    from core.emulator.session import Session


class PhysicalNode(CoreNodeBase):
    def __init__(
        self,
        session,
        _id: int = None,
        name: str = None,
        nodedir: str = None,
        start: bool = True,
        server: DistributedServer = None,
    ) -> None:
        super().__init__(session, _id, name, start, server)
        if not self.server:
            raise CoreError("physical nodes must be assigned to a remote server")
        self.nodedir = nodedir
        self.up = start
        self.lock = threading.RLock()
        self._mounts = []
        if start:
            self.startup()

    def startup(self) -> None:
        with self.lock:
            self.makenodedir()

    def shutdown(self) -> None:
        if not self.up:
            return

        with self.lock:
            while self._mounts:
                _source, target = self._mounts.pop(-1)
                self.umount(target)

            for netif in self.netifs():
                netif.shutdown()

            self.rmnodedir()

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        return sh

    def sethwaddr(self, ifindex: int, addr: str) -> None:
        """
        Set hardware address for an interface.

        :param ifindex: index of interface to set hardware address for
        :param addr: hardware address to set
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        addr = utils.validate_mac(addr)
        interface = self._netif[ifindex]
        interface.sethwaddr(addr)
        if self.up:
            self.net_client.device_mac(interface.name, addr)

    def addaddr(self, ifindex: int, addr: str) -> None:
        """
        Add an address to an interface.

        :param ifindex: index of interface to add address to
        :param addr: address to add
        :return: nothing
        """
        addr = utils.validate_ip(addr)
        interface = self._netif[ifindex]
        if self.up:
            self.net_client.create_address(interface.name, addr)
        interface.addaddr(addr)

    def deladdr(self, ifindex: int, addr: str) -> None:
        """
        Delete an address from an interface.

        :param ifindex: index of interface to delete
        :param addr: address to delete
        :return: nothing
        """
        interface = self._netif[ifindex]

        try:
            interface.deladdr(addr)
        except ValueError:
            logging.exception("trying to delete unknown address: %s", addr)

        if self.up:
            self.net_client.delete_address(interface.name, str(addr))

    def adoptnetif(
        self, netif: CoreInterface, ifindex: int, hwaddr: str, addrlist: List[str]
    ) -> None:
        """
        When a link message is received linking this node to another part of
        the emulation, no new interface is created; instead, adopt the
        GreTap netif as the node interface.
        """
        netif.name = f"gt{ifindex}"
        netif.node = self
        self.addnetif(netif, ifindex)

        # use a more reasonable name, e.g. "gt0" instead of "gt.56286.150"
        if self.up:
            self.net_client.device_down(netif.localname)
            self.net_client.device_name(netif.localname, netif.name)

        netif.localname = netif.name

        if hwaddr:
            self.sethwaddr(ifindex, hwaddr)

        for addr in utils.make_tuple(addrlist):
            self.addaddr(ifindex, addr)

        if self.up:
            self.net_client.device_up(netif.localname)

    def linkconfig(
        self,
        netif: CoreInterface,
        bw: float = None,
        delay: float = None,
        loss: float = None,
        duplicate: float = None,
        jitter: float = None,
        netif2: CoreInterface = None,
    ) -> None:
        """
        Apply tc queing disciplines using linkconfig.
        """
        linux_bridge = CoreNetwork(session=self.session, start=False)
        linux_bridge.up = True
        linux_bridge.linkconfig(
            netif,
            bw=bw,
            delay=delay,
            loss=loss,
            duplicate=duplicate,
            jitter=jitter,
            netif2=netif2,
        )
        del linux_bridge

    def newifindex(self) -> int:
        with self.lock:
            while self.ifindex in self._netif:
                self.ifindex += 1
            ifindex = self.ifindex
            self.ifindex += 1
            return ifindex

    def newnetif(
        self,
        net: Veth = None,
        addrlist: List[str] = None,
        hwaddr: str = None,
        ifindex: int = None,
        ifname: str = None,
    ) -> int:
        logging.info("creating interface")
        if not addrlist:
            addrlist = []

        if self.up and net is None:
            raise NotImplementedError

        if ifindex is None:
            ifindex = self.newifindex()

        if ifname is None:
            ifname = f"gt{ifindex}"

        if self.up:
            # this is reached when this node is linked to a network node
            # tunnel to net not built yet, so build it now and adopt it
            _, remote_tap = self.session.distributed.create_gre_tunnel(net, self.server)
            self.adoptnetif(remote_tap, ifindex, hwaddr, addrlist)
            return ifindex
        else:
            # this is reached when configuring services (self.up=False)
            netif = GreTap(node=self, name=ifname, session=self.session, start=False)
            self.adoptnetif(netif, ifindex, hwaddr, addrlist)
            return ifindex

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
        with self.opennodefile(filename, "w") as node_file:
            node_file.write(contents)
            os.chmod(node_file.name, mode)
            logging.info("created nodefile: '%s'; mode: 0%o", node_file.name, mode)

    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        return self.host_cmd(args, wait=wait)


class Rj45Node(CoreNodeBase, CoreInterface):
    """
    RJ45Node is a physical interface on the host linked to the emulated
    network.
    """

    apitype = NodeTypes.RJ45.value
    type = "rj45"

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        mtu: int = 1500,
        start: bool = True,
        server: DistributedServer = None,
    ) -> None:
        """
        Create an RJ45Node instance.

        :param session: core session instance
        :param _id: node id
        :param name: node name
        :param mtu: rj45 mtu
        :param start: start flag
        :param server: remote server node
            will run on, default is None for localhost
        """
        CoreNodeBase.__init__(self, session, _id, name, start, server)
        CoreInterface.__init__(self, session, self, name, mtu, server)
        self.lock = threading.RLock()
        self.ifindex = None
        # the following are PyCoreNetIf attributes
        self.transport_type = "raw"
        self.localname = name
        self.old_up = False
        self.old_addrs = []

        if start:
            self.startup()

    def startup(self) -> None:
        """
        Set the interface in the up state.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        # interface will also be marked up during net.attach()
        self.savestate()
        self.net_client.device_up(self.localname)
        self.up = True

    def shutdown(self) -> None:
        """
        Bring the interface down. Remove any addresses and queuing
        disciplines.

        :return: nothing
        """
        if not self.up:
            return

        try:
            self.net_client.device_down(self.localname)
            self.net_client.device_flush(self.localname)
            self.net_client.delete_tc(self.localname)
        except CoreCommandError:
            logging.exception("error shutting down")

        self.up = False
        self.restorestate()

    # TODO: issue in that both classes inherited from provide the same method with
    #  different signatures
    def attachnet(self, net: CoreNetworkBase) -> None:
        """
        Attach a network.

        :param net: network to attach
        :return: nothing
        """
        CoreInterface.attachnet(self, net)

    # TODO: issue in that both classes inherited from provide the same method with
    #  different signatures
    def detachnet(self) -> None:
        """
        Detach a network.

        :return: nothing
        """
        CoreInterface.detachnet(self)

    def newnetif(
        self,
        net: CoreNetworkBase = None,
        addrlist: List[str] = None,
        hwaddr: str = None,
        ifindex: int = None,
        ifname: str = None,
    ) -> int:
        """
        This is called when linking with another node. Since this node
        represents an interface, we do not create another object here,
        but attach ourselves to the given network.

        :param net: new network instance
        :param addrlist: address list
        :param hwaddr: hardware address
        :param ifindex: interface index
        :param ifname: interface name
        :return: interface index
        :raises ValueError: when an interface has already been created, one max
        """
        with self.lock:
            if ifindex is None:
                ifindex = 0

            if self.net is not None:
                raise ValueError("RJ45 nodes support at most 1 network interface")

            self._netif[ifindex] = self
            # PyCoreNetIf.node is self
            self.node = self
            self.ifindex = ifindex

            if net is not None:
                self.attachnet(net)

            if addrlist:
                for addr in utils.make_tuple(addrlist):
                    self.addaddr(addr)

            return ifindex

    def delnetif(self, ifindex: int) -> None:
        """
        Delete a network interface.

        :param ifindex: interface index to delete
        :return: nothing
        """
        if ifindex is None:
            ifindex = 0

        self._netif.pop(ifindex)

        if ifindex == self.ifindex:
            self.shutdown()
        else:
            raise ValueError(f"ifindex {ifindex} does not exist")

    def netif(
        self, ifindex: int, net: CoreNetworkBase = None
    ) -> Optional[CoreInterface]:
        """
        This object is considered the network interface, so we only
        return self here. This keeps the RJ45Node compatible with
        real nodes.

        :param ifindex: interface index to retrieve
        :param net: network to retrieve
        :return: a network interface
        """
        if net is not None and net == self.net:
            return self

        if ifindex is None:
            ifindex = 0

        if ifindex == self.ifindex:
            return self

        return None

    def getifindex(self, netif: CoreInterface) -> Optional[int]:
        """
        Retrieve network interface index.

        :param netif: network interface to retrieve
            index for
        :return: interface index, None otherwise
        """
        if netif != self:
            return None
        return self.ifindex

    def addaddr(self, addr: str) -> None:
        """
        Add address to to network interface.

        :param addr: address to add
        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        addr = utils.validate_ip(addr)
        if self.up:
            self.net_client.create_address(self.name, addr)
        CoreInterface.addaddr(self, addr)

    def deladdr(self, addr: str) -> None:
        """
        Delete address from network interface.

        :param addr: address to delete
        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.up:
            self.net_client.delete_address(self.name, str(addr))
        CoreInterface.deladdr(self, addr)

    def savestate(self) -> None:
        """
        Save the addresses and other interface state before using the
        interface for emulation purposes. TODO: save/restore the PROMISC flag

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.old_up = False
        self.old_addrs = []
        output = self.net_client.device_show(self.localname)
        for line in output.split("\n"):
            items = line.split()
            if len(items) < 2:
                continue

            if items[1] == f"{self.localname}:":
                flags = items[2][1:-1].split(",")
                if "UP" in flags:
                    self.old_up = True
            elif items[0] == "inet":
                self.old_addrs.append((items[1], items[3]))
            elif items[0] == "inet6":
                if items[1][:4] == "fe80":
                    continue
                self.old_addrs.append((items[1], None))

    def restorestate(self) -> None:
        """
        Restore the addresses and other interface state after using it.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        for addr in self.old_addrs:
            if addr[1] is None:
                self.net_client.create_address(self.localname, addr[0])
            else:
                self.net_client.create_address(
                    self.localname, addr[0], broadcast=addr[1]
                )

        if self.old_up:
            self.net_client.device_up(self.localname)

    def setposition(self, x: float = None, y: float = None, z: float = None) -> None:
        """
        Uses setposition from both parent classes.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: True if position changed, False otherwise
        """
        CoreNodeBase.setposition(self, x, y, z)
        CoreInterface.setposition(self)

    def termcmdstring(self, sh: str) -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        raise NotImplementedError
