import json
import logging
import os
import threading
import time

from core import utils, CoreCommandError
from core.emulator.enumerations import NodeTypes
from core.nodes.base import CoreNode


class LxdClient(object):
    def __init__(self, name, image):
        self.name = name
        self.image = image
        self.pid = None
        self._addr = {}

    def create_container(self):
        utils.check_cmd("lxc launch {image} {name}".format(
            name=self.name,
            image=self.image
        ))
        data = self._get_data()[0]
        self.pid = data["state"]["pid"]
        return self.pid

    def _get_data(self):
        args = "lxc list {name} --format json".format(name=self.name)
        status, output = utils.cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)
        return json.loads(output)

    def _cmd_args(self, cmd):
        return "lxc exec {name} -- {cmd}".format(
            name=self.name,
            cmd=cmd
        )

    def is_alive(self):
        data = self._get_data()
        if not data:
            return False
        data = data[0]
        return data["state"]["status"] == "Running"

    def stop_container(self):
        utils.check_cmd("lxc delete --force {name}".format(
            name=self.name
        ))

    def run_cmd_output(self, cmd):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        args = self._cmd_args(cmd)
        logging.info("lxc cmd output: %s", args)
        return utils.cmd_output(args)

    def run_cmd(self, cmd, wait=True):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        args = self._cmd_args(cmd)
        logging.info("lxc cmd: %s", args)
        return utils.cmd(args, wait)

    def _ns_args(self, cmd):
        return "nsenter -t {pid} -m -u -i -p -n {cmd}".format(
            pid=self.pid,
            cmd=cmd
        )

    def ns_cmd_output(self, cmd):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        args = self._ns_args(cmd)
        logging.info("ns cmd: %s", args)
        return utils.cmd_output(args)

    def ns_cmd(self, cmd, wait=True):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        args = self._ns_args(cmd)
        logging.info("ns cmd: %s", args)
        return utils.cmd(args, wait)

    def copy_file(self, source, destination):
        if destination[0] != "/":
            destination = os.path.join("/root/", destination)

        args = "lxc file push {source} {name}/{destination}".format(
            source=source,
            name=self.name,
            destination=destination
        )
        status, output = utils.cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)

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
        status, output = self.ns_cmd_output(args)
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


class LxcNode(CoreNode):
    apitype = NodeTypes.LXC.value
    valid_address_types = {"inet", "inet6", "inet6link"}

    def __init__(self, session, _id=None, name=None, nodedir=None, bootsh="boot.sh", start=True, image=None):
        """
        Create a CoreNode instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: object id
        :param str name: object name
        :param str nodedir: node directory
        :param str bootsh: boot shell to use
        :param bool start: start flag
        """
        super(CoreNode, self).__init__(session, _id, name, start=start)
        self.nodedir = nodedir
        self.ctrlchnlname = os.path.abspath(os.path.join(self.session.session_dir, self.name))
        if image is None:
            image = "ubuntu"
        self.client = LxdClient(self.name, image)
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
        return self.client.is_alive()

    def startup(self):
        """
        Startup logic.

        :return: nothing
        """
        with self.lock:
            if self.up:
                raise ValueError("starting a node that is already up")
            self.makenodedir()
            self.pid = self.client.create_container()
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
        return self.client.run_cmd(args, wait)

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        return self.client.run_cmd_output(args)

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        status, output = self.client.run_cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)
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
        logging.info("creating node dir: %s", path)
        args = "mkdir -p {path}".format(path=path)
        status, output = self.client.run_cmd_output(args)
        if status:
            raise CoreCommandError(status, args, output)

    def mount(self, source, target):
        """
        Create and mount a directory.

        :param str source: source directory to mount
        :param str target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.info("mounting source(%s) target(%s)", source, target)
        raise Exception("you found a lxc node")

    def nodefile(self, filename, contents, mode=0o644):
        """
        Create a node file with a given mode.

        :param str filename: name of file to create
        :param contents: contents of file
        :param int mode: mode for file
        :return: nothing
        """
        logging.info("node dir(%s) ctrlchannel(%s)", self.nodedir, self.ctrlchnlname)
        logging.info("nodefile filename(%s) mode(%s)", filename, mode)
        file_path = os.path.join(self.nodedir, filename)
        with open(file_path, "w") as f:
            os.chmod(f.name, mode)
            f.write(contents)
        self.client.copy_file(file_path, filename)

    def nodefilecopy(self, filename, srcfilename, mode=None):
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param str filename: file name to copy file to
        :param str srcfilename: file to copy
        :param int mode: mode to copy to
        :return: nothing
        """
        logging.info("node file copy file(%s) source(%s) mode(%s)", filename, srcfilename, mode)
        raise Exception("you found a lxc node")

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

            # delay required for lxc nodes
            time.sleep(0.5)

            for address in utils.make_tuple(addrlist):
                self.addaddr(ifindex, address)

            self.ifup(ifindex)
            return ifindex
