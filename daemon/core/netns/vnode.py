"""
PyCoreNode and LxcNode classes that implement the network namespac virtual node.
"""

import os
import random
import shutil
import signal
import string
import threading

from core import CoreCommandError
from core import constants
from core import logger
from core.coreobj import PyCoreNetIf
from core.coreobj import PyCoreNode
from core.enumerations import NodeTypes
from core.misc import nodeutils
from core.misc import utils
from core.netns import vnodeclient
from core.netns.vif import TunTap
from core.netns.vif import VEth

_DEFAULT_MTU = 1500

utils.check_executables([constants.IP_BIN])


class SimpleLxcNode(PyCoreNode):
    """
    Provides simple lxc functionality for core nodes.

    :var nodedir: str
    :var ctrlchnlname: str
    :var client: core.netns.vnodeclient.VnodeClient
    :var pid: int
    :var up: bool
    :var lock: threading.RLock
    :var _mounts: list[tuple[str, str]]
    """
    valid_address_types = {"inet", "inet6", "inet6link"}

    def __init__(self, session, objid=None, name=None, nodedir=None, start=True):
        """
        Create a SimpleLxcNode instance.

        :param core.session.Session session: core session instance
        :param int objid: object id
        :param str name: object name
        :param str nodedir: node directory
        :param bool start: start flag
        """
        PyCoreNode.__init__(self, session, objid, name, start=start)
        self.nodedir = nodedir
        self.ctrlchnlname = os.path.abspath(os.path.join(self.session.session_dir, self.name))
        self.client = None
        self.pid = None
        self.up = False
        self.lock = threading.RLock()
        self._mounts = []

    def alive(self):
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        :rtype: bool
        """
        try:
            os.kill(self.pid, 0)
        except OSError:
            return False

        return True

    def startup(self):
        """
        Start a new namespace node by invoking the vnoded process that
        allocates a new namespace. Bring up the loopback device and set
        the hostname.

        :return: nothing
        """
        if self.up:
            raise ValueError("starting a node that is already up")

        # create a new namespace for this node using vnoded
        vnoded = [
            constants.VNODED_BIN,
            "-v",
            "-c", self.ctrlchnlname,
            "-l", self.ctrlchnlname + ".log",
            "-p", self.ctrlchnlname + ".pid"
        ]
        if self.nodedir:
            vnoded += ["-C", self.nodedir]
        env = self.session.get_environment(state=False)
        env["NODE_NUMBER"] = str(self.objid)
        env["NODE_NAME"] = str(self.name)

        output = utils.check_cmd(vnoded, env=env)
        self.pid = int(output)

        # create vnode client
        self.client = vnodeclient.VnodeClient(self.name, self.ctrlchnlname)

        # bring up the loopback interface
        logger.info("bringing up loopback interface")
        self.check_cmd([constants.IP_BIN, "link", "set", "lo", "up"])

        # set hostname for node
        logger.info("setting hostname: %s" % self.name)
        self.check_cmd(["hostname", self.name])

        # mark node as up
        self.up = True

    def shutdown(self):
        """
        Shutdown logic for simple lxc nodes.

        :return: nothing
        """
        # nothing to do if node is not up
        if not self.up:
            return

        # unmount all targets
        while self._mounts:
            source, target = self._mounts.pop(-1)
            self.umount(target)

        # shutdown all interfaces
        for netif in self.netifs():
            netif.shutdown()

        # attempt to kill node process and wait for termination of children
        try:
            os.kill(self.pid, signal.SIGTERM)
            os.waitpid(self.pid, 0)
        except OSError:
            logger.exception("error killing process")

        # remove node directory if present
        try:
            if os.path.exists(self.ctrlchnlname):
                os.unlink(self.ctrlchnlname)
        except OSError:
            logger.exception("error removing node directory")

        # clear interface data, close client, and mark self and not up
        self._netif.clear()
        self.client.close()
        self.up = False

    def boot(self):
        """
        Boot logic.

        :return: nothing
        """
        return None

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        return self.client.cmd(args, wait)

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        return self.client.cmd_output(args)

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        return self.client.check_cmd(args)

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return self.client.termcmdstring(sh)

    def mount(self, source, target):
        """
        Create and mount a directory.

        :param str source: source directory to mount
        :param str target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        source = os.path.abspath(source)
        logger.info("mounting %s at %s" % (source, target))
        cmd = 'mkdir -p "%s" && %s -n --bind "%s" "%s"' % (target, constants.MOUNT_BIN, source, target)
        status, output = self.client.shcmd_result(cmd)
        if status:
            raise CoreCommandError(status, cmd, output)
        self._mounts.append((source, target))

    def umount(self, target):
        """
        Unmount a target directory.

        :param str target: target directory to unmount
        :return: nothing
        """
        logger.info("unmounting: %s", target)
        try:
            self.check_cmd([constants.UMOUNT_BIN, "-n", "-l", target])
        except CoreCommandError:
            logger.exception("error during unmount")

    def newifindex(self):
        """
        Retrieve a new interface index.

        :return: new interface index
        :rtype: int
        """
        with self.lock:
            return super(SimpleLxcNode, self).newifindex()

    def newveth(self, ifindex=None, ifname=None, net=None):
        """
        Create a new interface.

        :param int ifindex: index for the new interface
        :param str ifname: name for the new interface
        :param net: network to associate interface with
        :return: nothing
        """
        with self.lock:
            if ifindex is None:
                ifindex = self.newifindex()

            if ifname is None:
                ifname = "eth%d" % ifindex

            sessionid = self.session.short_session_id()

            try:
                suffix = "%x.%s.%s" % (self.objid, ifindex, sessionid)
            except TypeError:
                suffix = "%s.%s.%s" % (self.objid, ifindex, sessionid)

            localname = "veth" + suffix
            if len(localname) >= 16:
                raise ValueError("interface local name (%s) too long" % localname)

            name = localname + "p"
            if len(name) >= 16:
                raise ValueError("interface name (%s) too long" % name)

            veth = VEth(node=self, name=name, localname=localname, net=net, start=self.up)

            if self.up:
                utils.check_cmd([constants.IP_BIN, "link", "set", veth.name, "netns", str(self.pid)])
                self.check_cmd([constants.IP_BIN, "link", "set", veth.name, "name", ifname])

            veth.name = ifname

            if self.up:
                # TODO: potentially find better way to query interface ID
                # retrieve interface information
                output = self.check_cmd(["ip", "link", "show", veth.name])
                logger.info("interface command output: %s", output)
                output = output.split("\n")
                veth.flow_id = int(output[0].strip().split(":")[0]) + 1
                logger.info("interface flow index: %s - %s", veth.name, veth.flow_id)
                veth.hwaddr = output[1].strip().split()[1]
                logger.info("interface mac: %s - %s", veth.name, veth.hwaddr)

            try:
                self.addnetif(veth, ifindex)
            except ValueError as e:
                veth.shutdown()
                del veth
                raise e

            return ifindex

    def newtuntap(self, ifindex=None, ifname=None, net=None):
        """
        Create a new tunnel tap.

        :param int ifindex: interface index
        :param str ifname: interface name
        :param net: network to associate with
        :return: interface index
        :rtype: int
        """
        with self.lock:
            if ifindex is None:
                ifindex = self.newifindex()

            if ifname is None:
                ifname = "eth%d" % ifindex

            sessionid = self.session.short_session_id()
            localname = "tap%s.%s.%s" % (self.objid, ifindex, sessionid)
            name = ifname
            tuntap = TunTap(node=self, name=name, localname=localname, net=net, start=self.up)

            try:
                self.addnetif(tuntap, ifindex)
            except ValueError as e:
                tuntap.shutdown()
                del tuntap
                raise e

            return ifindex

    def sethwaddr(self, ifindex, addr):
        """
        Set hardware addres for an interface.

        :param int ifindex: index of interface to set hardware address for
        :param core.misc.ipaddress.MacAddress addr: hardware address to set
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        self._netif[ifindex].sethwaddr(addr)
        if self.up:
            args = [constants.IP_BIN, "link", "set", "dev", self.ifname(ifindex), "address", str(addr)]
            self.check_cmd(args)

    def addaddr(self, ifindex, addr):
        """
        Add interface address.

        :param int ifindex: index of interface to add address to
        :param str addr: address to add to interface
        :return: nothing
        """
        if self.up:
            # check if addr is ipv6
            if ":" in str(addr):
                args = [constants.IP_BIN, "addr", "add", str(addr), "dev", self.ifname(ifindex)]
                self.check_cmd(args)
            else:
                args = [constants.IP_BIN, "addr", "add", str(addr), "broadcast", "+", "dev", self.ifname(ifindex)]
                self.check_cmd(args)

        self._netif[ifindex].addaddr(addr)

    def deladdr(self, ifindex, addr):
        """
        Delete address from an interface.

        :param int ifindex: index of interface to delete address from
        :param str addr: address to delete from interface
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        try:
            self._netif[ifindex].deladdr(addr)
        except ValueError:
            logger.exception("trying to delete unknown address: %s" % addr)

        if self.up:
            self.check_cmd([constants.IP_BIN, "addr", "del", str(addr), "dev", self.ifname(ifindex)])

    def delalladdr(self, ifindex, address_types=valid_address_types):
        """
        Delete all addresses from an interface.

        :param int ifindex: index of interface to delete address types from
        :param tuple[str] address_types: address types to delete
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        interface_name = self.ifname(ifindex)
        addresses = self.client.getaddr(interface_name, rescan=True)

        for address_type in address_types:
            if address_type not in self.valid_address_types:
                raise ValueError("addr type must be in: %s" % " ".join(self.valid_address_types))
            for address in addresses[address_type]:
                self.deladdr(ifindex, address)

        # update cached information
        self.client.getaddr(interface_name, rescan=True)

    def ifup(self, ifindex):
        """
        Bring an interface up.

        :param int ifindex: index of interface to bring up
        :return: nothing
        """
        if self.up:
            self.check_cmd([constants.IP_BIN, "link", "set", self.ifname(ifindex), "up"])

    def newnetif(self, net=None, addrlist=None, hwaddr=None, ifindex=None, ifname=None):
        """
        Create a new network interface.

        :param net: network to associate with
        :param list addrlist: addresses to add on the interface
        :param core.misc.ipaddress.MacAddress hwaddr: hardware address to set for interface
        :param int ifindex: index of interface to create
        :param str ifname: name for interface
        :return: interface index
        :rtype: int
        """
        if not addrlist:
            addrlist = []

        with self.lock:
            # TODO: see if you can move this to emane specific code
            if nodeutils.is_node(net, NodeTypes.EMANE):
                ifindex = self.newtuntap(ifindex=ifindex, ifname=ifname, net=net)
                # TUN/TAP is not ready for addressing yet; the device may
                #   take some time to appear, and installing it into a
                #   namespace after it has been bound removes addressing;
                #   save addresses with the interface now
                self.attachnet(ifindex, net)
                netif = self.netif(ifindex)
                netif.sethwaddr(hwaddr)
                for address in utils.make_tuple(addrlist):
                    netif.addaddr(address)
                return ifindex
            else:
                ifindex = self.newveth(ifindex=ifindex, ifname=ifname, net=net)

            if net is not None:
                self.attachnet(ifindex, net)

            if hwaddr:
                self.sethwaddr(ifindex, hwaddr)

            for address in utils.make_tuple(addrlist):
                self.addaddr(ifindex, address)

            self.ifup(ifindex)
            return ifindex

    def connectnode(self, ifname, othernode, otherifname):
        """
        Connect a node.

        :param str ifname: name of interface to connect
        :param core.netns.nodes.LxcNode othernode: node to connect to
        :param str otherifname: interface name to connect to
        :return: nothing
        """
        tmplen = 8
        tmp1 = "tmp." + "".join([random.choice(string.ascii_lowercase) for _ in xrange(tmplen)])
        tmp2 = "tmp." + "".join([random.choice(string.ascii_lowercase) for _ in xrange(tmplen)])
        utils.check_cmd([constants.IP_BIN, "link", "add", "name", tmp1, "type", "veth", "peer", "name", tmp2])

        utils.check_cmd([constants.IP_BIN, "link", "set", tmp1, "netns", str(self.pid)])
        self.check_cmd([constants.IP_BIN, "link", "set", tmp1, "name", ifname])
        interface = PyCoreNetIf(node=self, name=ifname, mtu=_DEFAULT_MTU)
        self.addnetif(interface, self.newifindex())

        utils.check_cmd([constants.IP_BIN, "link", "set", tmp2, "netns", str(othernode.pid)])
        othernode.check_cmd([constants.IP_BIN, "link", "set", tmp2, "name", otherifname])
        other_interface = PyCoreNetIf(node=othernode, name=otherifname, mtu=_DEFAULT_MTU)
        othernode.addnetif(other_interface, othernode.newifindex())

    def addfile(self, srcname, filename):
        """
        Add a file.

        :param str srcname: source file name
        :param str filename: file name to add
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logger.info("adding file from %s to %s", srcname, filename)
        directory = os.path.dirname(filename)

        cmd = 'mkdir -p "%s" && mv "%s" "%s" && sync' % (directory, srcname, filename)
        status, output = self.client.shcmd_result(cmd)
        if status:
            raise CoreCommandError(status, cmd, output)


class LxcNode(SimpleLxcNode):
    """
    Provides lcx node functionality for core nodes.
    """

    def __init__(self, session, objid=None, name=None, nodedir=None, bootsh="boot.sh", start=True):
        """
        Create a LxcNode instance.

        :param core.session.Session session: core session instance
        :param int objid: object id
        :param str name: object name
        :param str nodedir: node directory
        :param bootsh: boot shell
        :param bool start: start flag
        """
        super(LxcNode, self).__init__(session=session, objid=objid, name=name, nodedir=nodedir, start=start)
        self.bootsh = bootsh
        if start:
            self.startup()

    def boot(self):
        """
        Boot the node.

        :return: nothing
        """
        self.session.services.bootnodeservices(self)

    def validate(self):
        """
        Validate the node.

        :return: nothing
        """
        self.session.services.validatenodeservices(self)

    def startup(self):
        """
        Startup logic for the node.

        :return: nothing
        """
        with self.lock:
            self.makenodedir()
            super(LxcNode, self).startup()
            self.privatedir("/var/run")
            self.privatedir("/var/log")

    def shutdown(self):
        """
        Shutdown logic for the node.

        :return: nothing
        """
        if not self.up:
            return

        with self.lock:
            try:
                super(LxcNode, self).shutdown()
            except OSError:
                logger.exception("error during shutdown")
            finally:
                self.rmnodedir()

    # TODO: should change how this exception is just swallowed up
    def privatedir(self, path):
        """
        Create a private directory.

        :param str path: path to create
        :return: nothing
        """
        if path[0] != "/":
            raise ValueError("path not fully qualified: %s" % path)
        hostpath = os.path.join(self.nodedir, os.path.normpath(path).strip("/").replace("/", "."))
        os.mkdir(hostpath)
        self.mount(hostpath, path)

    def hostfilename(self, filename):
        """
        Return the name of a node"s file on the host filesystem.

        :param str filename: host file name
        :return: path to file
        """
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError("no basename for filename: %s" % filename)
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        return os.path.join(dirname, basename)

    def opennodefile(self, filename, mode="w"):
        """
        Open a node file, within it"s directory.

        :param str filename: file name to open
        :param str mode: mode to open file in
        :return: open file
        :rtype: file
        """
        hostfilename = self.hostfilename(filename)
        dirname, basename = os.path.split(hostfilename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode=0755)
        return open(hostfilename, mode)

    def nodefile(self, filename, contents, mode=0644):
        """
        Create a node file with a given mode.

        :param str filename: name of file to create
        :param contents: contents of file
        :param int mode: mode for file
        :return: nothing
        """
        with self.opennodefile(filename, "w") as open_file:
            open_file.write(contents)
            os.chmod(open_file.name, mode)
            logger.info("created nodefile: %s; mode: 0%o", open_file.name, mode)

    def nodefilecopy(self, filename, srcfilename, mode=None):
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param str filename: file name to copy file to
        :param str srcfilename: file to copy
        :param int mode: mode to copy to
        :return: nothing
        """
        hostfilename = self.hostfilename(filename)
        shutil.copy2(srcfilename, hostfilename)
        if mode is not None:
            os.chmod(hostfilename, mode)
        logger.info("copied nodefile: %s; mode: %s", hostfilename, mode)
