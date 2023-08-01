import json
import logging
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from core.emulator.data import InterfaceData, LinkOptions
from core.emulator.distributed import DistributedServer
from core.errors import CoreCommandError
from core.executables import BASH
from core.nodes.base import CoreNode, CoreNodeOptions
from core.nodes.interface import CoreInterface

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session


@dataclass
class LxcOptions(CoreNodeOptions):
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


class LxcNode(CoreNode):
    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: DistributedServer = None,
        options: LxcOptions = None,
    ) -> None:
        """
        Create a LxcNode instance.

        :param session: core session instance
        :param _id: object id
        :param name: object name
        :param server: remote server node
            will run on, default is None for localhost
        :param options: option to create node with
        """
        options = options or LxcOptions()
        super().__init__(session, _id, name, server, options)
        self.image: str = options.image

    @classmethod
    def create_options(cls) -> LxcOptions:
        return LxcOptions()

    def create_cmd(self, args: str, shell: bool = False) -> str:
        """
        Create command used to run commands within the context of a node.

        :param args: command arguments
        :param shell: True to run shell like, False otherwise
        :return: node command
        """
        if shell:
            args = f"{BASH} -c {shlex.quote(args)}"
        return f"nsenter -t {self.pid} -m -u -i -p -n {args}"

    def _get_info(self) -> dict:
        args = f"lxc list {self.name} --format json"
        output = self.host_cmd(args)
        data = json.loads(output)
        if not data:
            raise CoreCommandError(1, args, f"LXC({self.name}) not present")
        return data[0]

    def alive(self) -> bool:
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        """
        try:
            data = self._get_info()
            return data["state"]["status"] == "Running"
        except CoreCommandError:
            return False

    def startup(self) -> None:
        """
        Startup logic.

        :return: nothing
        """
        with self.lock:
            if self.up:
                raise ValueError("starting a node that is already up")
            self.makenodedir()
            self.host_cmd(f"lxc launch {self.image} {self.name}")
            data = self._get_info()
            self.pid = data["state"]["pid"]
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
            self.host_cmd(f"lxc delete --force {self.name}")
            self.up = False

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        terminal = f"lxc exec {self.name} -- {sh}"
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
        logger.info("creating node dir: %s", dir_path)
        args = f"mkdir -p {dir_path}"
        self.cmd(args)

    def mount(self, src_path: Path, target_path: Path) -> None:
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
        if not str(file_path).startswith("/"):
            file_path = Path("/root/") / file_path
        self.host_cmd(f"lxc file push {temp_path} {self.name}/{file_path}")
        self.cmd(f"chmod {mode:o} {file_path}")
        if self.server is not None:
            self.host_cmd(f"rm -f {temp_path}")
        temp_path.unlink()
        logger.debug("node(%s) added file: %s; mode: 0%o", self.name, file_path, mode)

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
        if not str(dst_path).startswith("/"):
            dst_path = Path("/root/") / dst_path
        self.host_cmd(f"lxc file push {src_path} {self.name}/{dst_path}")
        if mode is not None:
            self.cmd(f"chmod {mode:o} {dst_path}")

    def create_iface(
        self, iface_data: InterfaceData = None, options: LinkOptions = None
    ) -> CoreInterface:
        iface = super().create_iface(iface_data, options)
        # adding small delay to allow time for adding addresses to work correctly
        time.sleep(0.5)
        return iface
