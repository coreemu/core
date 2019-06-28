import logging
import os
import threading

from core import utils, CoreCommandError
from core.emulator.enumerations import NodeTypes
from core.nodes.base import CoreNode


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
        self.pid = self.get_pid()
        return self.pid

    def is_alive(self):
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
        return utils.cmd_output("nsenter -t {pid} -m -u -i -p -n {cmd}".format(
            pid=self.pid,
            cmd=cmd
        ))

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


class DockerNode(CoreNode):
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
        super(CoreNode, self).__init__(session, _id, name, start=start)
        self.nodedir = nodedir
        self.ctrlchnlname = os.path.abspath(os.path.join(self.session.session_dir, self.name))
        self.client = DockerClient(self.name)
        self.pid = None
        self.up = False
        self.lock = threading.RLock()
        self._mounts = []
        self.bootsh = bootsh
        logging.debug("docker services: %s", self.services)
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
        Start a new namespace node by invoking the vnoded process that
        allocates a new namespace. Bring up the loopback device and set
        the hostname.

        :return: nothing
        """
        with self.lock:
            if self.up:
                raise ValueError("starting a node that is already up")
            self.pid = self.client.create_container("ubuntu:ifconfig")
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
        status, _ = self.client.ns_cmd(args)
        return status

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        return self.client.ns_cmd(args)

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        status, output = self.client.ns_cmd(args)
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
