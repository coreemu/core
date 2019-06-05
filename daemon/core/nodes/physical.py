"""
PhysicalNode class for including real systems in the emulated network.
"""

import logging
import os
import subprocess
import threading

from core import CoreCommandError, utils
from core import constants
from core.nodes.base import CoreNodeBase
from core.nodes.interface import CoreInterface
from core.emulator.enumerations import NodeTypes
from core.nodes.network import GreTap
from core.nodes.network import CoreNetwork


class PhysicalNode(CoreNodeBase):
    def __init__(self, session, _id=None, name=None, nodedir=None, start=True):
        CoreNodeBase.__init__(self, session, _id, name, start=start)
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

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        os.chdir(self.nodedir)
        status = utils.cmd(args, wait)
        return status

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        os.chdir(self.nodedir)
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, _ = p.communicate()
        status = p.wait()
        return status, stdout.strip()

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        status, output = self.cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)
        return output.strip()

    def shcmd(self, cmdstr, sh="/bin/sh"):
        return self.cmd([sh, "-c", cmdstr])

    def sethwaddr(self, ifindex, addr):
        """
        same as SimpleLxcNode.sethwaddr()
        """
        self._netif[ifindex].sethwaddr(addr)
        ifname = self.ifname(ifindex)
        if self.up:
            self.check_cmd([constants.IP_BIN, "link", "set", "dev", ifname, "address", str(addr)])

    def addaddr(self, ifindex, addr):
        """
        same as SimpleLxcNode.addaddr()
        """
        if self.up:
            self.check_cmd([constants.IP_BIN, "addr", "add", str(addr), "dev", self.ifname(ifindex)])

        self._netif[ifindex].addaddr(addr)

    def deladdr(self, ifindex, addr):
        """
        same as SimpleLxcNode.deladdr()
        """
        try:
            self._netif[ifindex].deladdr(addr)
        except ValueError:
            logging.exception("trying to delete unknown address: %s", addr)

        if self.up:
            self.check_cmd([constants.IP_BIN, "addr", "del", str(addr), "dev", self.ifname(ifindex)])

    def adoptnetif(self, netif, ifindex, hwaddr, addrlist):
        """
        The broker builds a GreTap tunnel device to this physical node.
        When a link message is received linking this node to another part of
        the emulation, no new interface is created; instead, adopt the
        GreTap netif as the node interface.
        """
        netif.name = "gt%d" % ifindex
        netif.node = self
        self.addnetif(netif, ifindex)

        # use a more reasonable name, e.g. "gt0" instead of "gt.56286.150"
        if self.up:
            self.check_cmd([constants.IP_BIN, "link", "set", "dev", netif.localname, "down"])
            self.check_cmd([constants.IP_BIN, "link", "set", netif.localname, "name", netif.name])

        netif.localname = netif.name

        if hwaddr:
            self.sethwaddr(ifindex, hwaddr)

        for addr in utils.make_tuple(addrlist):
            self.addaddr(ifindex, addr)

        if self.up:
            self.check_cmd([constants.IP_BIN, "link", "set", "dev", netif.localname, "up"])

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None, jitter=None, netif2=None):
        """
        Apply tc queing disciplines using LxBrNet.linkconfig()
        """
        # borrow the tc qdisc commands from LxBrNet.linkconfig()
        linux_bridge = CoreNetwork(session=self.session, start=False)
        linux_bridge.up = True
        linux_bridge.linkconfig(netif, bw=bw, delay=delay, loss=loss, duplicate=duplicate, jitter=jitter, netif2=netif2)
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

        if self.up:
            # this is reached when this node is linked to a network node
            # tunnel to net not built yet, so build it now and adopt it
            gt = self.session.broker.addnettunnel(net.id)
            if gt is None or len(gt) != 1:
                raise ValueError("error building tunnel from adding a new network interface: %s" % gt)
            gt = gt[0]
            net.detach(gt)
            self.adoptnetif(gt, ifindex, hwaddr, addrlist)
            return ifindex

        # this is reached when configuring services (self.up=False)
        if ifname is None:
            ifname = "gt%d" % ifindex

        netif = GreTap(node=self, name=ifname, session=self.session, start=False)
        self.adoptnetif(netif, ifindex, hwaddr, addrlist)
        return ifindex

    def privatedir(self, path):
        if path[0] != "/":
            raise ValueError("path not fully qualified: %s" % path)
        hostpath = os.path.join(self.nodedir, os.path.normpath(path).strip('/').replace('/', '.'))
        os.mkdir(hostpath)
        self.mount(hostpath, path)

    def mount(self, source, target):
        source = os.path.abspath(source)
        logging.info("mounting %s at %s", source, target)
        os.makedirs(target)
        self.check_cmd([constants.MOUNT_BIN, "--bind", source, target])
        self._mounts.append((source, target))

    def umount(self, target):
        logging.info("unmounting '%s'" % target)
        try:
            self.check_cmd([constants.UMOUNT_BIN, "-l", target])
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


class Rj45Node(CoreNodeBase, CoreInterface):
    """
    RJ45Node is a physical interface on the host linked to the emulated
    network.
    """
    apitype = NodeTypes.RJ45.value
    type = "rj45"

    def __init__(self, session, _id=None, name=None, mtu=1500, start=True):
        """
        Create an RJ45Node instance.

        :param core.session.Session session: core session instance
        :param int _id: node id
        :param str name: node name
        :param mtu: rj45 mtu
        :param bool start: start flag
        :return:
        """
        CoreNodeBase.__init__(self, session, _id, name, start=start)
        CoreInterface.__init__(self, node=self, name=name, mtu=mtu)
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
        utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "up"])
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
            utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "down"])
            utils.check_cmd([constants.IP_BIN, "addr", "flush", "dev", self.localname])
            utils.check_cmd([constants.TC_BIN, "qdisc", "del", "dev", self.localname, "root"])
        except CoreCommandError:
            logging.exception("error shutting down")

        self.up = False
        self.restorestate()

    # TODO: issue in that both classes inherited from provide the same method with different signatures
    def attachnet(self, net):
        """
        Attach a network.

        :param core.coreobj.PyCoreNet net: network to attach
        :return: nothing
        """
        CoreInterface.attachnet(self, net)

    # TODO: issue in that both classes inherited from provide the same method with different signatures
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

        :param core.coreobj.PyCoreNet net: new network instance
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
            raise ValueError("ifindex %s does not exist" % ifindex)

    def netif(self, ifindex, net=None):
        """
        This object is considered the network interface, so we only
        return self here. This keeps the RJ45Node compatible with
        real nodes.

        :param int ifindex: interface index to retrieve
        :param net: network to retrieve
        :return: a network interface
        :rtype: core.coreobj.PyCoreNetIf
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

        :param core.coreobj.PyCoreNetIf netif: network interface to retrieve index for
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
            utils.check_cmd([constants.IP_BIN, "addr", "add", str(addr), "dev", self.name])

        CoreInterface.addaddr(self, addr)

    def deladdr(self, addr):
        """
        Delete address from network interface.

        :param str addr: address to delete
        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.up:
            utils.check_cmd([constants.IP_BIN, "addr", "del", str(addr), "dev", self.name])

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
        args = [constants.IP_BIN, "addr", "show", "dev", self.localname]
        output = utils.check_cmd(args)
        for line in output.split("\n"):
            items = line.split()
            if len(items) < 2:
                continue

            if items[1] == "%s:" % self.localname:
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
                utils.check_cmd([constants.IP_BIN, "addr", "add", addr[0], "dev", self.localname])
            else:
                utils.check_cmd([constants.IP_BIN, "addr", "add", addr[0], "brd", addr[1], "dev", self.localname])

        if self.old_up:
            utils.check_cmd([constants.IP_BIN, "link", "set", self.localname, "up"])

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

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: exist status and combined stdout and stderr
        :rtype: tuple[int, str]
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        raise NotImplementedError

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        raise NotImplementedError

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        raise NotImplementedError

    def termcmdstring(self, sh):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        raise NotImplementedError
