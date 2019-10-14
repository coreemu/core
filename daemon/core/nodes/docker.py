import json
import logging
import os
from tempfile import NamedTemporaryFile

from core import utils
from core.emulator import distributed
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError
from core.nodes.base import CoreNode
from core.nodes.netclient import LinuxNetClient, OvsNetClient


class DockerClient(object):
    def __init__(self, name, image, run):
        self.name = name
        self.image = image
        self.run = run
        self.pid = None

    def create_container(self):
        self.run(
            "docker run -td --init --net=none --hostname {name} --name {name} "
            "--sysctl net.ipv6.conf.all.disable_ipv6=0 "
            "{image} /bin/bash".format(
                name=self.name,
                image=self.image
            ))
        self.pid = self.get_pid()
        return self.pid

    def get_info(self):
        args = "docker inspect {name}".format(name=self.name)
        output = self.run(args)
        data = json.loads(output)
        if not data:
            raise CoreCommandError(
                -1, args, "docker({name}) not present".format(name=self.name)
            )
        return data[0]

    def is_alive(self):
        try:
            data = self.get_info()
            return data["State"]["Running"]
        except CoreCommandError:
            return False

    def stop_container(self):
        self.run("docker rm -f {name}".format(
            name=self.name
        ))

    def check_cmd(self, cmd):
        logging.info("docker cmd output: %s", cmd)
        return utils.check_cmd("docker exec {name} {cmd}".format(
            name=self.name,
            cmd=cmd
        ))

    def create_ns_cmd(self, cmd):
        return "nsenter -t {pid} -u -i -p -n {cmd}".format(
            pid=self.pid,
            cmd=cmd
        )

    def ns_cmd(self, cmd, wait):
        args = "nsenter -t {pid} -u -i -p -n {cmd}".format(
            pid=self.pid,
            cmd=cmd
        )
        return utils.check_cmd(args, wait=wait)

    def get_pid(self):
        args = "docker inspect -f '{{{{.State.Pid}}}}' {name}".format(name=self.name)
        output = self.run(args)
        self.pid = output
        logging.debug("node(%s) pid: %s", self.name, self.pid)
        return output

    def copy_file(self, source, destination):
        args = "docker cp {source} {name}:{destination}".format(
            source=source,
            name=self.name,
            destination=destination
        )
        return self.run(args)


class DockerNode(CoreNode):
    apitype = NodeTypes.DOCKER.value

    def __init__(self, session, _id=None, name=None, nodedir=None, bootsh="boot.sh", start=True, image=None):
        """
        Create a DockerNode instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: object id
        :param str name: object name
        :param str nodedir: node directory
        :param str bootsh: boot shell to use
        :param bool start: start flag
        :param str image: image to start container with
        """
        if image is None:
            image = "ubuntu"
        self.image = image
        super(DockerNode, self).__init__(session, _id, name, nodedir, bootsh, start)

    def create_node_net_client(self, use_ovs):
        if use_ovs:
            return OvsNetClient(self.nsenter_cmd)
        else:
            return LinuxNetClient(self.nsenter_cmd)

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
            self.makenodedir()
            self.client = DockerClient(self.name, self.image, self.net_cmd)
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

    def nsenter_cmd(self, args, wait=True):
        if self.server is None:
            args = self.client.create_ns_cmd(args)
            return utils.check_cmd(args, wait=wait)
        else:
            args = self.client.create_ns_cmd(args)
            return distributed.remote_cmd(self.server, args, wait=wait)

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return "docker exec -it {name} bash".format(name=self.name)

    def privatedir(self, path):
        """
        Create a private directory.

        :param str path: path to create
        :return: nothing
        """
        logging.debug("creating node dir: %s", path)
        args = "mkdir -p {path}".format(path=path)
        self.node_net_cmd(args)

    def mount(self, source, target):
        """
        Create and mount a directory.

        :param str source: source directory to mount
        :param str target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.debug("mounting source(%s) target(%s)", source, target)
        raise Exception("not supported")

    def nodefile(self, filename, contents, mode=0o644):
        """
        Create a node file with a given mode.

        :param str filename: name of file to create
        :param contents: contents of file
        :param int mode: mode for file
        :return: nothing
        """
        logging.debug("nodefile filename(%s) mode(%s)", filename, mode)
        directory = os.path.dirname(filename)
        temp = NamedTemporaryFile(delete=False)
        temp.write(contents.encode("utf-8"))
        temp.close()

        if directory:
            self.node_net_cmd("mkdir -m %o -p %s" % (0o755, directory))
        if self.server is not None:
            distributed.remote_put(self.server, temp.name, temp.name)
        self.client.copy_file(temp.name, filename)
        self.node_net_cmd("chmod %o %s" % (mode, filename))
        if self.server is not None:
            self.net_cmd("rm -f %s" % temp.name)
        os.unlink(temp.name)
        logging.debug(
            "node(%s) added file: %s; mode: 0%o", self.name, filename, mode
        )

    def nodefilecopy(self, filename, srcfilename, mode=None):
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param str filename: file name to copy file to
        :param str srcfilename: file to copy
        :param int mode: mode to copy to
        :return: nothing
        """
        logging.info(
            "node file copy file(%s) source(%s) mode(%s)", filename, srcfilename, mode
        )
        directory = os.path.dirname(filename)
        self.node_net_cmd("mkdir -p %s" % directory)

        if self.server is None:
            source = srcfilename
        else:
            temp = NamedTemporaryFile(delete=False)
            source = temp.name
            distributed.remote_put(self.server, source, temp.name)

        self.client.copy_file(source, filename)
        self.node_net_cmd("chmod %o %s" % (mode, filename))
