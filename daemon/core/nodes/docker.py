import json
import logging
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Optional

from mako.template import Template

from core import utils
from core.emulator.distributed import DistributedServer
from core.errors import CoreCommandError, CoreError
from core.executables import BASH
from core.nodes.base import CoreNode, CoreNodeOptions

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

DOCKER: str = "docker"
DOCKER_COMPOSE: str = os.environ.get("DOCKER_COMPOSE", "docker compose")


@dataclass
class DockerOptions(CoreNodeOptions):
    image: str = "ubuntu"
    """image used when creating container"""
    binds: list[tuple[str, str]] = field(default_factory=list)
    """bind mount source and destinations to setup within container"""
    volumes: list[tuple[str, str, bool, bool]] = field(default_factory=list)
    """
    volume mount source, destination, unique, delete to setup within container

    unique is True for node unique volume naming
    delete is True for deleting volume mount during shutdown
    """
    compose: str = None
    """
    Path to a compose file, if one should be used for this node.
    """
    compose_name: str = None
    """
    Service name to start, within the provided compose file.
    """


@dataclass
class DockerVolume:
    src: str
    """volume mount name"""
    dst: str
    """volume mount destination directory"""
    unique: bool = True
    """True to create a node unique prefixed name for this volume"""
    delete: bool = True
    """True to delete the volume during shutdown"""
    path: str = None
    """path to the volume on the host"""


class DockerNode(CoreNode):
    """
    Provides logic for creating a Docker based node.
    """

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: DistributedServer = None,
        options: DockerOptions = None,
    ) -> None:
        """
        Create a DockerNode instance.

        :param session: core session instance
        :param _id: node id
        :param name: node name
        :param server: remote server node
            will run on, default is None for localhost
        :param options: options for creating node
        """
        options = options or DockerOptions()
        super().__init__(session, _id, name, server, options)
        self.image: str = options.image
        self.compose: Optional[str] = options.compose
        self.compose_name: Optional[str] = options.compose_name
        self.binds: list[tuple[str, str]] = options.binds
        self.volumes: dict[str, DockerVolume] = {}
        self.env: dict[str, str] = {}
        for src, dst, unique, delete in options.volumes:
            src_name = self._unique_name(src) if unique else src
            self.volumes[src] = DockerVolume(src_name, dst, unique, delete)

    @classmethod
    def create_options(cls) -> DockerOptions:
        """
        Return default creation options, which can be used during node creation.

        :return: docker options
        """
        return DockerOptions()

    def create_cmd(self, args: str, shell: bool = False) -> str:
        """
        Create command used to run commands within the context of a node.

        :param args: command arguments
        :param shell: True to run shell like, False otherwise
        :return: node command
        """
        if shell:
            args = f"{BASH} -c {shlex.quote(args)}"
        return f"{DOCKER} exec {self.name} {args}"

    def cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        """
        Runs a command within the context of the Docker node.

        :param args: command to run
        :param wait: True to wait for status, False otherwise
        :param shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        args = self.create_cmd(args, shell)
        if self.server is None:
            return utils.cmd(args, wait=wait, shell=shell, env=self.env)
        else:
            return self.server.remote_cmd(args, wait=wait, env=self.env)

    def cmd_perf(self, args: str, wait: bool = True, shell: bool = False) -> str:
        """
        Runs a command within the Docker node using nsenter to avoid
        client/server overhead.

        :param args: command to run
        :param wait: True to wait for status, False otherwise
        :param shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        if shell:
            args = f"{BASH} -c {shlex.quote(args)}"
        args = f"nsenter -t {self.pid} -m -u -i -p -n -- {args}"
        if self.server is None:
            return utils.cmd(args, wait=wait, shell=shell, env=self.env)
        else:
            return self.server.remote_cmd(args, wait=wait, env=self.env)

    def create_net_cmd(self, args: str, shell: bool = False) -> str:
        """
        Create command used to run network commands within the context of a node.

        :param args: command arguments
        :param shell: True to run shell like, False otherwise
        :return: node command
        """
        if shell:
            args = f"{BASH} -c {shlex.quote(args)}"
        return f"nsenter -t {self.pid} -n -- {args}"

    def net_cmd(self, args: str, wait: bool = True, shell: bool = False) -> str:
        """
        Runs a command that is used to configure and setup the network within a
        node.

        :param args: command to run
        :param wait: True to wait for status, False otherwise
        :param shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        args = self.create_net_cmd(args, shell)
        if self.server is None:
            return utils.cmd(args, wait=wait, shell=shell, env=self.env)
        else:
            return self.server.remote_cmd(args, wait=wait, env=self.env)

    def _unique_name(self, name: str) -> str:
        """
        Creates a session/node unique prefixed name for the provided input.

        :param name: name to make unique
        :return: unique session/node prefixed name
        """
        return f"{self.session.id}.{self.id}.{name}"

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
            # create node directory
            self.makenodedir()
            hostname = self.name.replace("_", "-")
            if self.compose:
                if not self.compose_name:
                    raise CoreError(
                        "a compose name is required when using a compose file"
                    )
                compose_path = os.path.expandvars(self.compose)
                data = self.host_cmd(f"cat {compose_path}")
                template = Template(data)
                rendered = template.render_unicode(node=self, hostname=hostname)
                rendered = rendered.replace('"', r"\"")
                rendered = "\\n".join(rendered.splitlines())
                compose_path = self.directory / "docker-compose.yml"
                self.host_cmd(f'printf "{rendered}" >> {compose_path}', shell=True)
                self.host_cmd(
                    f"{DOCKER_COMPOSE} up -d {self.compose_name}",
                    cwd=self.directory,
                )
            else:
                # setup commands for creating bind/volume mounts
                binds = ""
                for src, dst in self.binds:
                    binds += f"--mount type=bind,source={src},target={dst} "
                volumes = ""
                for volume in self.volumes.values():
                    volumes += (
                        f"--mount type=volume,"
                        f"source={volume.src},target={volume.dst} "
                    )
                # create container and retrieve the created containers PID
                self.host_cmd(
                    f"{DOCKER} run -td --init --net=none --hostname {hostname} "
                    f"--name {self.name} --sysctl net.ipv6.conf.all.disable_ipv6=0 "
                    f"{binds} {volumes} "
                    f"--privileged {self.image} tail -f /dev/null"
                )
                # setup symlinks for bind and volume mounts within
                for src, dst in self.binds:
                    link_path = self.host_path(Path(dst), True)
                    self.host_cmd(f"ln -s {src} {link_path}")
                for volume in self.volumes.values():
                    volume.path = self.host_cmd(
                        f"{DOCKER} volume inspect -f '{{{{.Mountpoint}}}}' {volume.src}"
                    )
                    link_path = self.host_path(Path(volume.dst), True)
                    self.host_cmd(f"ln -s {volume.path} {link_path}")
            # retrieve pid and process environment for use in nsenter commands
            self.pid = self.host_cmd(
                f"{DOCKER} inspect -f '{{{{.State.Pid}}}}' {self.name}"
            )
            output = self.host_cmd(f"cat /proc/{self.pid}/environ")
            for line in output.split("\x00"):
                if not line:
                    continue
                key, value = line.split("=")
                self.env[key] = value
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
                if volume.delete:
                    self.host_cmd(f"{DOCKER} volume rm {volume.src}")
            self.up = False

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        terminal = f"{DOCKER} exec -it {self.name} {sh}"
        if self.server is None:
            return terminal
        else:
            return f"ssh -X -f {self.server.host} xterm -e {terminal}"

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
        temp.write(contents.encode())
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
