import json
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Callable, Dict, Optional

from core import utils
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError
from core.nodes.base import CoreNode
from core.nodes.netclient import LinuxNetClient, get_net_client

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session


class DockerClient:
    def __init__(self, name: str, image: str, run: Callable[..., str]) -> None:
        self.name: str = name
        self.image: str = image
        self.run: Callable[..., str] = run
        self.pid: Optional[str] = None

    def create_container(self) -> str:
        self.run(
            f"docker run -td --init --net=none --hostname {self.name} "
            f"--name {self.name} --sysctl net.ipv6.conf.all.disable_ipv6=0 "
            f"--privileged {self.image} /bin/bash"
        )
        self.pid = self.get_pid()
        return self.pid

    def get_info(self) -> Dict:
        args = f"docker inspect {self.name}"
        output = self.run(args)
        data = json.loads(output)
        if not data:
            raise CoreCommandError(1, args, f"docker({self.name}) not present")
        return data[0]

    def is_alive(self) -> bool:
        try:
            data = self.get_info()
            return data["State"]["Running"]
        except CoreCommandError:
            return False

    def stop_container(self) -> None:
        self.run(f"docker rm -f {self.name}")

    def check_cmd(self, cmd: str, wait: bool = True, shell: bool = False) -> str:
        logger.info("docker cmd output: %s", cmd)
        return utils.cmd(f"docker exec {self.name} {cmd}", wait=wait, shell=shell)

    def create_ns_cmd(self, cmd: str) -> str:
        return f"nsenter -t {self.pid} -a {cmd}"

    def get_pid(self) -> str:
        args = f"docker inspect -f '{{{{.State.Pid}}}}' {self.name}"
        output = self.run(args)
        self.pid = output
        logger.debug("node(%s) pid: %s", self.name, self.pid)
        return output

    def copy_file(self, src_path: Path, dst_path: Path) -> str:
        args = f"docker cp {src_path} {self.name}:{dst_path}"
        return self.run(args)


class DockerNode(CoreNode):
    apitype = NodeTypes.DOCKER

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        directory: str = None,
        server: DistributedServer = None,
        image: str = None,
    ) -> None:
        """
        Create a DockerNode instance.

        :param session: core session instance
        :param _id: object id
        :param name: object name
        :param directory: node directory
        :param server: remote server node
            will run on, default is None for localhost
        :param image: image to start container with
        """
        if image is None:
            image = "ubuntu"
        self.image: str = image
        super().__init__(session, _id, name, directory, server)

    def create_node_net_client(self, use_ovs: bool) -> LinuxNetClient:
        """
        Create node network client for running network commands within the nodes
        container.

        :param use_ovs: True for OVS bridges, False for Linux bridges
        :return:node network client
        """
        return get_net_client(use_ovs, self.nsenter_cmd)

    def alive(self) -> bool:
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        """
        return self.client.is_alive()

    def startup(self) -> None:
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

    def shutdown(self) -> None:
        """
        Shutdown logic.

        :return: nothing
        """
        # nothing to do if node is not up
        if not self.up:
            return

        with self.lock:
            self.ifaces.clear()
            self.client.stop_container()
            self.up = False

    def nsenter_cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        if self.server is None:
            args = self.client.create_ns_cmd(args)
            return utils.cmd(args, wait=wait, shell=shell)
        else:
            args = self.client.create_ns_cmd(args)
            return self.server.remote_cmd(args, wait=wait)

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        return f"docker exec -it {self.name} bash"

    def create_dir(self, dir_path: Path) -> None:
        """
        Create a private directory.

        :param dir_path: path to create
        :return: nothing
        """
        logger.debug("creating node dir: %s", dir_path)
        args = f"mkdir -p {dir_path}"
        self.cmd(args)

    def mount(self, src_path: str, target_path: str) -> None:
        """
        Create and mount a directory.

        :param src_path: source directory to mount
        :param target_path: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logger.debug("mounting source(%s) target(%s)", src_path, target_path)
        raise Exception("not supported")

    def create_file(self, file_path: Path, contents: str, mode: int = 0o644) -> None:
        """
        Create a node file with a given mode.

        :param file_path: name of file to create
        :param contents: contents of file
        :param mode: mode for file
        :return: nothing
        """
        logger.debug("node(%s) create file(%s) mode(%o)", self.name, file_path, mode)
        temp = NamedTemporaryFile(delete=False)
        temp.write(contents.encode("utf-8"))
        temp.close()
        temp_path = Path(temp.name)
        directory = file_path.parent
        if str(directory) != ".":
            self.cmd(f"mkdir -m {0o755:o} -p {directory}")
        if self.server is not None:
            self.server.remote_put(temp_path, temp_path)
        self.client.copy_file(temp_path, file_path)
        self.cmd(f"chmod {mode:o} {file_path}")
        if self.server is not None:
            self.host_cmd(f"rm -f {temp_path}")
        temp_path.unlink()

    def copy_file(self, src_path: Path, dst_path: Path, mode: int = None) -> None:
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param dst_path: file name to copy file to
        :param src_path: file to copy
        :param mode: mode to copy to
        :return: nothing
        """
        logger.info(
            "node file copy file(%s) source(%s) mode(%o)", dst_path, src_path, mode or 0
        )
        self.cmd(f"mkdir -p {dst_path.parent}")
        if self.server:
            temp = NamedTemporaryFile(delete=False)
            temp_path = Path(temp.name)
            src_path = temp_path
            self.server.remote_put(src_path, temp_path)
        self.client.copy_file(src_path, dst_path)
        if mode is not None:
            self.cmd(f"chmod {mode:o} {dst_path}")
