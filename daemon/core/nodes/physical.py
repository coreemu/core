"""
PhysicalNode class for including real systems in the emulated network.
"""

import logging
import os
import threading

from core import utils
from core.constants import MOUNT_BIN, UMOUNT_BIN
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNodeBase
from core.nodes.interface import CoreInterface
from core.nodes.network import CoreNetwork, GreTap


class PhysicalNode(CoreNodeBase):
    def __init__(
        self, session, _id=None, name=None, nodedir=None, start=True, server=None
    ):
        super().__init__(session, _id, name, start, server)
        if not self.server:
            raise CoreError("physical nodes must be assigned to a remote server")
        self.nodedir = nodedir
        self.up = start
        self.lock = threading.RLock()
        self._mounts = []
        if start:
            self.startup()

    def startup(self):
        with self.lock:
            self.makenodedir()

    def shutdown(self):
        if not self.up:
            return

        with self.lock:
            while self._mounts:
                _source, target = self._mounts.pop(-1)
                self.umount(target)

            for netif in self.netifs():
                netif.shutdown()

            self.rmnodedir()

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return sh

    def sethwaddr(self, ifindex, addr):
        """
        Set hardware address for an interface.
        """
        interface = self._netif[ifindex]
        interface.sethwaddr(addr)
        if self.up:
            self.net_client.device_mac(interface.name, str(addr))

    def addaddr(self, ifindex, addr):
        """
        Add an address to an interface.
        """
        interface = self._netif[ifindex]
        if self.up:
            self.net_client.create_address(interface.name, str(addr))
        interface.addaddr(addr)

    def deladdr(self, ifindex, addr):
        """
        Delete an address from an interface.
        """
        interface = self._netif[ifindex]

        try:
            interface.deladdr(addr)
        except ValueError:
            logging.exception("trying to delete unknown address: %s", addr)

        if self.up:
            self.net_client.delete_address(interface.name, str(addr))

    def adoptnetif(self, netif, ifindex, hwaddr, addrlist):
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
        netif,
        bw=None,
        delay=None,
        loss=None,
        duplicate=None,
        jitter=None,
        netif2=None,
    ):
        """
        Apply tc queing disciplines using LxBrNet.linkconfig()
        """
        # borrow the tc qdisc commands from LxBrNet.linkconfig()
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

    def newifindex(self):
        with self.lock:
            while self.ifindex in self._netif:
                self.ifindex += 1
            ifindex = self.ifindex
            self.ifindex += 1
            return ifindex

    def newnetif(self, net=None, addrlist=None, hwaddr=None, ifindex=None, ifname=None):
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

    def privatedir(self, path):
        if path[0] != "/":
            raise ValueError(f"path not fully qualified: {path}")
        hostpath = os.path.join(
            self.nodedir, os.path.normpath(path).strip("/").replace("/", ".")
        )
        os.mkdir(hostpath)
        self.mount(hostpath, path)

    def mount(self, source, target):
        source = os.path.abspath(source)
        logging.info("mounting %s at %s", source, target)
        os.makedirs(target)
        self.host_cmd(f"{MOUNT_BIN} --bind {source} {target}", cwd=self.nodedir)
        self._mounts.append((source, target))

    def umount(self, target):
        logging.info("unmounting '%s'", target)
        try:
            self.host_cmd(f"{UMOUNT_BIN} -l {target}", cwd=self.nodedir)
        except CoreCommandError:
            logging.exception("unmounting failed for %s", target)

    def opennodefile(self, filename, mode="w"):
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

    def nodefile(self, filename, contents, mode=0o644):
        with self.opennodefile(filename, "w") as node_file:
            node_file.write(contents)
            os.chmod(node_file.name, mode)
            logging.info("created nodefile: '%s'; mode: 0%o", node_file.name, mode)

    def cmd(self, args, wait=True):
        return self.host_cmd(args, wait=wait)


class Rj45Node(CoreNodeBase, CoreInterface):
    """
    RJ45Node is a physical interface on the host linked to the emulated
    network.
    """

    apitype = NodeTypes.RJ45.value
    type = "rj45"

    def __init__(self, session, _id=None, name=None, mtu=1500, start=True, server=None):
        """
        Create an RJ45Node instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: node id
        :param str name: node name
        :param mtu: rj45 mtu
        :param bool start: start flag
        :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
        """
        CoreNodeBase.__init__(self, session, _id, name, start, server)
        CoreInterface.__init__(self, session, self, name, mtu, server)
        self.up = False
        self.lock = threading.RLock()
        self.ifindex = None
        # the following are PyCoreNetIf attributes
        self.transport_type = "raw"
        self.localname = name
        self.old_up = False
        self.old_addrs = []

        if start:
            self.startup()

    def startup(self):
        """
        Set the interface in the up state.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        # interface will also be marked up during net.attach()
        self.savestate()
        self.net_client.device_up(self.localname)
        self.up = True

    def shutdown(self):
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
    def attachnet(self, net):
        """
        Attach a network.

        :param core.coreobj.PyCoreNet net: network to attach
        :return: nothing
        """
        CoreInterface.attachnet(self, net)

    # TODO: issue in that both classes inherited from provide the same method with
    #  different signatures
    def detachnet(self):
        """
        Detach a network.

        :return: nothing
        """
        CoreInterface.detachnet(self)

    def newnetif(self, net=None, addrlist=None, hwaddr=None, ifindex=None, ifname=None):
        """
        This is called when linking with another node. Since this node
        represents an interface, we do not create another object here,
        but attach ourselves to the given network.

        :param core.nodes.base.CoreNetworkBase net: new network instance
        :param list[str] addrlist: address list
        :param str hwaddr: hardware address
        :param int ifindex: interface index
        :param str ifname: interface name
        :return: interface index
        :rtype: int
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

    def delnetif(self, ifindex):
        """
        Delete a network interface.

        :param int ifindex: interface index to delete
        :return: nothing
        """
        if ifindex is None:
            ifindex = 0

        self._netif.pop(ifindex)

        if ifindex == self.ifindex:
            self.shutdown()
        else:
            raise ValueError(f"ifindex {ifindex} does not exist")

    def netif(self, ifindex, net=None):
        """
        This object is considered the network interface, so we only
        return self here. This keeps the RJ45Node compatible with
        real nodes.

        :param int ifindex: interface index to retrieve
        :param net: network to retrieve
        :return: a network interface
        :rtype: core.nodes.interface,CoreInterface
        """
        if net is not None and net == self.net:
            return self

        if ifindex is None:
            ifindex = 0

        if ifindex == self.ifindex:
            return self

        return None

    def getifindex(self, netif):
        """
        Retrieve network interface index.

        :param core.nodes.interface.CoreInterface netif: network interface to retrieve index for
        :return: interface index, None otherwise
        :rtype: int
        """
        if netif != self:
            return None

        return self.ifindex

    def addaddr(self, addr):
        """
        Add address to to network interface.

        :param str addr: address to add
        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.up:
            self.net_client.create_address(self.name, str(addr))

        CoreInterface.addaddr(self, addr)

    def deladdr(self, addr):
        """
        Delete address from network interface.

        :param str addr: address to delete
        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.up:
            self.net_client.delete_address(self.name, str(addr))

        CoreInterface.deladdr(self, addr)

    def savestate(self):
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

    def restorestate(self):
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

    def setposition(self, x=None, y=None, z=None):
        """
        Uses setposition from both parent classes.

        :param float x: x position
        :param float y: y position
        :param float z: z position
        :return: True if position changed, False otherwise
        :rtype: bool
        """
        result = CoreNodeBase.setposition(self, x, y, z)
        CoreInterface.setposition(self, x, y, z)
        return result

    def termcmdstring(self, sh):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        raise NotImplementedError
