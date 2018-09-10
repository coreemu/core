"""
PhysicalNode class for including real systems in the emulated network.
"""

import os
import subprocess
import threading

from core import CoreCommandError
from core import constants
from core import logger
from core.coreobj import PyCoreNode
from core.misc import utils
from core.netns.vnet import GreTap
from core.netns.vnet import LxBrNet


class PhysicalNode(PyCoreNode):
    def __init__(self, session, objid=None, name=None, nodedir=None, start=True):
        PyCoreNode.__init__(self, session, objid, name, start=start)
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
                source, target = self._mounts.pop(-1)
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
            logger.exception("trying to delete unknown address: %s", addr)

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
        linux_bridge = LxBrNet(session=self.session, start=False)
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
        logger.info("creating interface")
        if not addrlist:
            addrlist = []

        if self.up and net is None:
            raise NotImplementedError

        if ifindex is None:
            ifindex = self.newifindex()

        if self.up:
            # this is reached when this node is linked to a network node
            # tunnel to net not built yet, so build it now and adopt it
            gt = self.session.broker.addnettunnel(net.objid)
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
        logger.info("mounting %s at %s", source, target)
        os.makedirs(target)
        self.check_cmd([constants.MOUNT_BIN, "--bind", source, target])
        self._mounts.append((source, target))

    def umount(self, target):
        logger.info("unmounting '%s'" % target)
        try:
            self.check_cmd([constants.UMOUNT_BIN, "-l", target])
        except CoreCommandError:
            logger.exception("unmounting failed for %s", target)

    def opennodefile(self, filename, mode="w"):
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError("no basename for filename: " + filename)

        if dirname and dirname[0] == "/":
            dirname = dirname[1:]

        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode=0755)

        hostfilename = os.path.join(dirname, basename)
        return open(hostfilename, mode)

    def nodefile(self, filename, contents, mode=0644):
        with self.opennodefile(filename, "w") as node_file:
            node_file.write(contents)
            os.chmod(node_file.name, mode)
            logger.info("created nodefile: '%s'; mode: 0%o", node_file.name, mode)
