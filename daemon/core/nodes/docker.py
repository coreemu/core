import logging
import os
import random
import shutil
import string
import threading

from core import utils, CoreCommandError, constants
from core.emulator.enumerations import NodeTypes
from core.nodes.base import CoreNodeBase
from core.nodes.interface import Veth, TunTap, CoreInterface

_DEFAULT_MTU = 1500


class DockerClient(object):
    def __init__(self, name):
        self.name = name
        self.pid = None
        self._addr = {}

    def create_container(self, image):
        utils.check_cmd("docker run -td --net=none --hostname {name} --name {name} {image} /bin/bash".format(
            name=self.name,
            image=image
        ))

    def is_container_alive(self):
        status, output = utils.cmd_output("docker containers ls -f name={name}".format(
            name=self.name
        ))
        return not status and len(output.split("\n")) == 2

    def stop_container(self):
        utils.check_cmd("docker rm -f {name}".format(
            name=self.name
        ))

    def run_cmd(self, cmd):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        return utils.cmd_output("docker exec -it {name} {cmd}".format(
            name=self.name,
            cmd=cmd
        ))

    def ns_cmd(self, cmd):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        status, output = utils.cmd_output("nsenter -t {pid} -m -u -i -p -n {cmd}".format(
            pid=self.pid,
            cmd=cmd
        ))
        if status:
            raise CoreCommandError(status, output)
        return output

    def get_pid(self):
        status, output = utils.cmd_output("docker inspect -f '{{{{.State.Pid}}}}' {name}".format(name=self.name))
        if status:
            raise CoreCommandError(status, output)
        self.pid = output
        logging.debug("node(%s) pid: %s", self.name, self.pid)
        return output

    def getaddr(self, ifname, rescan=False):
        """
        Get address for interface on node.

        :param str ifname: interface name to get address for
        :param bool rescan: rescan flag
        :return: interface information
        :rtype: dict
        """
        if ifname in self._addr and not rescan:
            return self._addr[ifname]

        interface = {"ether": [], "inet": [], "inet6": [], "inet6link": []}
        args = ["ip", "addr", "show", "dev", ifname]
        status, output = self.ns_cmd(args)
        for line in output:
            line = line.strip().split()
            if line[0] == "link/ether":
                interface["ether"].append(line[1])
            elif line[0] == "inet":
                interface["inet"].append(line[1])
            elif line[0] == "inet6":
                if line[3] == "global":
                    interface["inet6"].append(line[1])
                elif line[3] == "link":
                    interface["inet6link"].append(line[1])
                else:
                    logging.warning("unknown scope: %s" % line[3])

        if status:
            logging.warning("nonzero exist status (%s) for cmd: %s", status, args)
        self._addr[ifname] = interface
        return interface


class DockerNode(CoreNodeBase):
    apitype = NodeTypes.DOCKER.value
    valid_address_types = {"inet", "inet6", "inet6link"}

    def __init__(self, session, _id=None, name=None, nodedir=None, bootsh="boot.sh", start=True):
        """
        Create a CoreNode instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: object id
        :param str name: object name
        :param str nodedir: node directory
        :param str bootsh: boot shell to use
        :param bool start: start flag
        """
        super(CoreNodeBase, self).__init__(session, _id, name, start=start)
        self.nodedir = nodedir
        self.ctrlchnlname = os.path.abspath(os.path.join(self.session.session_dir, self.name))
        self.client = DockerClient(self.name)
        self.pid = None
        self.up = False
        self.lock = threading.RLock()
        self._mounts = []
        self.bootsh = bootsh
        if start:
            self.startup()

    def alive(self):
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        :rtype: bool
        """
        return self.client.is_container_alive()

    def startup(self):
        """
        Start a new namespace node by invoking the vnoded process that
        allocates a new namespace. Bring up the loopback device and set
        the hostname.

        :return: nothing
        """
        with self.lock:
            if self.up:
                raise ValueError("starting a node that is already up")
            self.client.create_container("ubuntu:ifconfig")
            self.pid = self.client.get_pid()
            self.up = True

    def shutdown(self):
        """
        Shutdown logic.

        :return: nothing
        """
        # nothing to do if node is not up
        if not self.up:
            return

        with self.lock:
            self._netif.clear()
            self.client.stop_container()
            self.up = False

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        status, _ = self.client.run_cmd(args)
        return status

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        return self.client.run_cmd(args)

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        status, output = self.client.run_cmd(args)
        if status:
            raise CoreCommandError(status, output)
        return output

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return ""

    def privatedir(self, path):
        """
        Create a private directory.

        :param str path: path to create
        :return: nothing
        """
        pass

    def mount(self, source, target):
        """
        Create and mount a directory.

        :param str source: source directory to mount
        :param str target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        pass

    def newifindex(self):
        """
        Retrieve a new interface index.

        :return: new interface index
        :rtype: int
        """
        with self.lock:
            return super(DockerNode, self).newifindex()

    def newveth(self, ifindex=None, ifname=None, net=None):
        """
        Create a new interface.

        :param int ifindex: index for the new interface
        :param str ifname: name for the new interface
        :param core.nodes.base.CoreNetworkBase net: network to associate interface with
        :return: nothing
        """
        with self.lock:
            if ifindex is None:
                ifindex = self.newifindex()

            if ifname is None:
                ifname = "eth%d" % ifindex

            sessionid = self.session.short_session_id()

            try:
                suffix = "%x.%s.%s" % (self.id, ifindex, sessionid)
            except TypeError:
                suffix = "%s.%s.%s" % (self.id, ifindex, sessionid)

            localname = "veth" + suffix
            if len(localname) >= 16:
                raise ValueError("interface local name (%s) too long" % localname)

            name = localname + "p"
            if len(name) >= 16:
                raise ValueError("interface name (%s) too long" % name)

            veth = Veth(node=self, name=name, localname=localname, net=net, start=self.up)

            if self.up:
                utils.check_cmd([constants.IP_BIN, "link", "set", veth.name, "netns", str(self.pid)])
                self.client.ns_cmd(["ip", "link", "set", veth.name, "name", ifname])
                self.client.ns_cmd(["ethtool", "-K", ifname, "rx", "off", "tx", "off"])

            veth.name = ifname

            if self.up:
                # TODO: potentially find better way to query interface ID
                # retrieve interface information
                output = self.client.ns_cmd([constants.IP_BIN, "link", "show", veth.name])
                logging.debug("interface command output: %s", output)
                output = output.split("\n")
                veth.flow_id = int(output[0].strip().split(":")[0]) + 1
                logging.debug("interface flow index: %s - %s", veth.name, veth.flow_id)
                # TODO: mimic packed hwaddr
                # veth.hwaddr = MacAddress.from_string(output[1].strip().split()[1])
                logging.debug("interface mac: %s - %s", veth.name, veth.hwaddr)

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
            localname = "tap%s.%s.%s" % (self.id, ifindex, sessionid)
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
        :param core.nodes.ipaddress.MacAddress addr: hardware address to set
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        self._netif[ifindex].sethwaddr(addr)
        if self.up:
            args = ["ip", "link", "set", "dev", self.ifname(ifindex), "address", str(addr)]
            self.client.ns_cmd(args)

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
                args = ["ip", "addr", "add", str(addr), "dev", self.ifname(ifindex)]
                self.client.ns_cmd(args)
            else:
                args = ["ip", "addr", "add", str(addr), "broadcast", "+", "dev", self.ifname(ifindex)]
                self.client.ns_cmd(args)

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
            logging.exception("trying to delete unknown address: %s" % addr)

        if self.up:
            self.check_cmd(["ip", "addr", "del", str(addr), "dev", self.ifname(ifindex)])

    def delalladdr(self, ifindex, address_types=None):
        """
        Delete all addresses from an interface.

        :param int ifindex: index of interface to delete address types from
        :param tuple[str] address_types: address types to delete
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        if not address_types:
            address_types = self.valid_address_types

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
            # self.check_cmd(["ip", "link", "set", self.ifname(ifindex), "up"])
            self.client.ns_cmd(["ip", "link", "set", self.ifname(ifindex), "up"])

    def newnetif(self, net=None, addrlist=None, hwaddr=None, ifindex=None, ifname=None):
        """
        Create a new network interface.

        :param core.nodes.base.CoreNetworkBase net: network to associate with
        :param list addrlist: addresses to add on the interface
        :param core.nodes.ipaddress.MacAddress hwaddr: hardware address to set for interface
        :param int ifindex: index of interface to create
        :param str ifname: name for interface
        :return: interface index
        :rtype: int
        """
        if not addrlist:
            addrlist = []

        with self.lock:
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
        :param core.nodes.CoreNodeBase othernode: node to connect to
        :param str otherifname: interface name to connect to
        :return: nothing
        """
        tmplen = 8
        tmp1 = "tmp." + "".join([random.choice(string.ascii_lowercase) for _ in range(tmplen)])
        tmp2 = "tmp." + "".join([random.choice(string.ascii_lowercase) for _ in range(tmplen)])
        utils.check_cmd([constants.IP_BIN, "link", "add", "name", tmp1, "type", "veth", "peer", "name", tmp2])

        utils.check_cmd([constants.IP_BIN, "link", "set", tmp1, "netns", str(self.pid)])
        self.check_cmd(["ip", "link", "set", tmp1, "name", ifname])
        interface = CoreInterface(node=self, name=ifname, mtu=_DEFAULT_MTU)
        self.addnetif(interface, self.newifindex())

        utils.check_cmd([constants.IP_BIN, "link", "set", tmp2, "netns", str(othernode.pid)])
        othernode.check_cmd([constants.IP_BIN, "link", "set", tmp2, "name", otherifname])
        other_interface = CoreInterface(node=othernode, name=otherifname, mtu=_DEFAULT_MTU)
        othernode.addnetif(other_interface, othernode.newifindex())

    def addfile(self, srcname, filename):
        """
        Add a file.

        :param str srcname: source file name
        :param str filename: file name to add
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.info("adding file from %s to %s", srcname, filename)
        directory = os.path.dirname(filename)

        cmd = 'mkdir -p "%s" && mv "%s" "%s" && sync' % (directory, srcname, filename)
        status, output = self.client.run_cmd(cmd)
        if status:
            raise CoreCommandError(status, cmd, output)

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
        dirname, _basename = os.path.split(hostfilename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode=0o755)
        return open(hostfilename, mode)

    def nodefile(self, filename, contents, mode=0o644):
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
            logging.info("node(%s) added file: %s; mode: 0%o", self.name, open_file.name, mode)

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
        logging.info("node(%s) copied file: %s; mode: %s", self.name, hostfilename, mode)
