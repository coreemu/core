import json
import logging
import os

from core import utils
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError
from core.nodes.base import CoreNode


class DockerClient(object):
    def __init__(self, name, image):
        self.name = name
        self.image = image
        self.pid = None

    def create_container(self):
        utils.check_cmd(
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
        output = utils.check_cmd(args)
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
        utils.check_cmd("docker rm -f {name}".format(
            name=self.name
        ))

    def check_cmd(self, cmd):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        logging.info("docker cmd output: %s", cmd)
        return utils.check_cmd("docker exec {name} {cmd}".format(
            name=self.name,
            cmd=cmd
        ))

    def ns_cmd(self, cmd, wait):
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        args = "nsenter -t {pid} -u -i -p -n {cmd}".format(
            pid=self.pid,
            cmd=cmd
        )
        return utils.check_cmd(args, wait=wait)

    def get_pid(self):
        args = "docker inspect -f '{{{{.State.Pid}}}}' {name}".format(name=self.name)
        output = utils.check_cmd(args)
        self.pid = output
        logging.debug("node(%s) pid: %s", self.name, self.pid)
        return output

    def copy_file(self, source, destination):
        args = "docker cp {source} {name}:{destination}".format(
            source=source,
            name=self.name,
            destination=destination
        )
        return utils.check_cmd(args)


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
            self.client = DockerClient(self.name, self.image)
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

    def node_net_cmd(self, args, wait=True):
        if not self.up:
            logging.debug("node down, not running network command: %s", args)
            return ""

        return self.client.ns_cmd(args, wait)

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
        self.client.check_cmd(args)

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
        logging.debug("node dir(%s) ctrlchannel(%s)", self.nodedir, self.ctrlchnlname)
        logging.debug("nodefile filename(%s) mode(%s)", filename, mode)
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
        raise Exception("not supported")
