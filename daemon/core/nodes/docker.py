import json
import logging
import os
from tempfile import NamedTemporaryFile

from core import utils
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError
from core.nodes.base import CoreNode
from core.nodes.netclient import get_net_client


class DockerClient:
    def __init__(self, name, image, run):
        self.name = name
        self.image = image
        self.run = run
        self.pid = None

    def create_container(self):
        self.run(
            f"docker run -td --init --net=none --hostname {self.name} --name {self.name} "
            f"--sysctl net.ipv6.conf.all.disable_ipv6=0 {self.image} /bin/bash"
        )
        self.pid = self.get_pid()
        return self.pid

    def get_info(self):
        args = f"docker inspect {self.name}"
        output = self.run(args)
        data = json.loads(output)
        if not data:
            raise CoreCommandError(-1, args, f"docker({self.name}) not present")
        return data[0]

    def is_alive(self):
        try:
            data = self.get_info()
            return data["State"]["Running"]
        except CoreCommandError:
            return False

    def stop_container(self):
        self.run(f"docker rm -f {self.name}")

    def check_cmd(self, cmd):
        logging.info("docker cmd output: %s", cmd)
        return utils.cmd(f"docker exec {self.name} {cmd}")

    def create_ns_cmd(self, cmd):
        return f"nsenter -t {self.pid} -u -i -p -n {cmd}"

    def ns_cmd(self, cmd, wait):
        args = f"nsenter -t {self.pid} -u -i -p -n {cmd}"
        return utils.cmd(args, wait=wait)

    def get_pid(self):
        args = f"docker inspect -f '{{{{.State.Pid}}}}' {self.name}"
        output = self.run(args)
        self.pid = output
        logging.debug("node(%s) pid: %s", self.name, self.pid)
        return output

    def copy_file(self, source, destination):
        args = f"docker cp {source} {self.name}:{destination}"
        return self.run(args)


class DockerNode(CoreNode):
    apitype = NodeTypes.DOCKER.value

    def __init__(
        self,
        session,
        _id=None,
        name=None,
        nodedir=None,
        bootsh="boot.sh",
        start=True,
        server=None,
        image=None
    ):
        """
        Create a DockerNode instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: object id
        :param str name: object name
        :param str nodedir: node directory
        :param str bootsh: boot shell to use
        :param bool start: start flag
        :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
        :param str image: image to start container with
        """
        if image is None:
            image = "ubuntu"
        self.image = image
        super(DockerNode, self).__init__(
            session, _id, name, nodedir, bootsh, start, server
        )

    def create_node_net_client(self, use_ovs):
        """
        Create node network client for running network commands within the nodes
        container.

        :param bool use_ovs: True for OVS bridges, False for Linux bridges
        :return:node network client
        """
        return get_net_client(use_ovs, self.nsenter_cmd)

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
            self.client = DockerClient(self.name, self.image, self.host_cmd)
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
            return utils.cmd(args, wait=wait)
        else:
            args = self.client.create_ns_cmd(args)
            return self.server.remote_cmd(args, wait=wait)

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return f"docker exec -it {self.name} bash"

    def privatedir(self, path):
        """
        Create a private directory.

        :param str path: path to create
        :return: nothing
        """
        logging.debug("creating node dir: %s", path)
        args = f"mkdir -p {path}"
        self.cmd(args)

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
            self.cmd(f"mkdir -m {0o755:o} -p {directory}")
        if self.server is not None:
            self.server.remote_put(temp.name, temp.name)
        self.client.copy_file(temp.name, filename)
        self.cmd(f"chmod {mode:o} {filename}")
        if self.server is not None:
            self.host_cmd(f"rm -f {temp.name}")
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
        self.cmd(f"mkdir -p {directory}")

        if self.server is None:
            source = srcfilename
        else:
            temp = NamedTemporaryFile(delete=False)
            source = temp.name
            self.server.remote_put(source, temp.name)

        self.client.copy_file(source, filename)
        self.cmd(f"chmod {mode:o} {filename}")
