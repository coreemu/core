import json
import logging
import shlex
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Dict

from core.emulator.distributed import DistributedServer
from core.errors import CoreCommandError, CoreError
from core.executables import BASH
from core.nodes.base import CoreNode

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

DOCKER: str = "docker"


@dataclass
class DockerVolume:
    src: str
    dst: str
    path: str = None


class DockerNode(CoreNode):
    """
    Provides logic for creating a Docker based node.
    """

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        directory: str = None,
        server: DistributedServer = None,
        image: str = None,
        binds: Dict[str, str] = None,
        volumes: Dict[str, str] = None,
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
        :param binds: bind mounts to set for the created container
        :param volumes: volume mounts to set for the created container
        """
        super().__init__(session, _id, name, directory, server)
        self.image: str = image if image is not None else "ubuntu"
        self.binds: Dict[str, str] = binds or {}
        volumes = volumes or {}
        self.volumes: Dict[str, DockerVolume] = {
            k: DockerVolume(k, v) for k, v in volumes.items()
        }

    def _create_cmd(self, args: str, shell: bool = False) -> str:
        """
        Create command used to run commands within the context of a node.

        :param args: command arguments
        :param shell: True to run shell like, False otherwise
        :return: node command
        """
        if shell:
            args = f"{BASH} -c {shlex.quote(args)}"
        return f"nsenter -t {self.pid} -m -u -i -p -n {args}"

    def alive(self) -> bool:
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        """
        try:
            running = self.host_cmd(
                f"{DOCKER} inspect -f '{{{{.State.Running}}}}' {self.name}"
            )
            return json.loads(running)
        except CoreCommandError:
            return False

    def startup(self) -> None:
        """
        Create a docker container instance for the specified image.

        :return: nothing
        """
        with self.lock:
            if self.up:
                raise CoreError(f"starting node({self.name}) that is already up")
            self.makenodedir()
            binds = ""
            for src, dst in self.binds.items():
                binds += f"--mount type=bind,source={src},target={dst} "
            volumes = ""
            for volume in self.volumes.values():
                volumes += (
                    f"--mount type=volume," f"source={volume.src},target={volume.dst} "
                )
            self.host_cmd(
                f"{DOCKER} run -td --init --net=none --hostname {self.name} "
                f"--name {self.name} --sysctl net.ipv6.conf.all.disable_ipv6=0 "
                f"{binds} {volumes} "
                f"--privileged {self.image} /bin/bash"
            )
            self.pid = self.host_cmd(
                f"{DOCKER} inspect -f '{{{{.State.Pid}}}}' {self.name}"
            )
            for volume in self.volumes.values():
                volume.path = self.host_cmd(
                    f"{DOCKER} volume inspect -f '{{{{.Mountpoint}}}}' {volume.src}"
                )
            logger.debug("node(%s) pid: %s", self.name, self.pid)
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
            self.host_cmd(f"{DOCKER} rm -f {self.name}")
            for volume in self.volumes.values():
                self.host_cmd(f"{DOCKER} volume rm {volume.src}")
            self.up = False

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        return f"{DOCKER} exec -it {self.name} {sh}"

    def create_dir(self, dir_path: Path) -> None:
        """
        Create a private directory.

        :param dir_path: path to create
        :return: nothing
        """
        logger.debug("creating node dir: %s", dir_path)
        self.cmd(f"mkdir -p {dir_path}")

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
        self.host_cmd(f"{DOCKER} cp {temp_path} {self.name}:{file_path}")
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
        self.host_cmd(f"{DOCKER} cp {src_path} {self.name}:{dst_path}")
        if mode is not None:
            self.cmd(f"chmod {mode:o} {dst_path}")
