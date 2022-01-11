import json
import logging
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Callable, Dict, Optional

from core import utils
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError
from core.nodes.base import CoreNode
from core.nodes.interface import CoreInterface

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session


class LxdClient:
    def __init__(self, name: str, image: str, run: Callable[..., str]) -> None:
        self.name: str = name
        self.image: str = image
        self.run: Callable[..., str] = run
        self.pid: Optional[int] = None

    def create_container(self) -> int:
        self.run(f"lxc launch {self.image} {self.name}")
        data = self.get_info()
        self.pid = data["state"]["pid"]
        return self.pid

    def get_info(self) -> Dict:
        args = f"lxc list {self.name} --format json"
        output = self.run(args)
        data = json.loads(output)
        if not data:
            raise CoreCommandError(1, args, f"LXC({self.name}) not present")
        return data[0]

    def is_alive(self) -> bool:
        try:
            data = self.get_info()
            return data["state"]["status"] == "Running"
        except CoreCommandError:
            return False

    def stop_container(self) -> None:
        self.run(f"lxc delete --force {self.name}")

    def create_cmd(self, cmd: str) -> str:
        return f"lxc exec -nT {self.name} -- {cmd}"

    def create_ns_cmd(self, cmd: str) -> str:
        return f"nsenter -t {self.pid} -m -u -i -p -n {cmd}"

    def check_cmd(self, cmd: str, wait: bool = True, shell: bool = False) -> str:
        args = self.create_cmd(cmd)
        return utils.cmd(args, wait=wait, shell=shell)

    def copy_file(self, src_path: Path, dst_path: Path) -> None:
        if not str(dst_path).startswith("/"):
            dst_path = Path("/root/") / dst_path
        args = f"lxc file push {src_path} {self.name}/{dst_path}"
        self.run(args)


class LxcNode(CoreNode):
    apitype = NodeTypes.LXC

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
        Create a LxcNode instance.

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

    def alive(self) -> bool:
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        """
        return self.client.is_alive()

    def startup(self) -> None:
        """
        Startup logic.

        :return: nothing
        """
        with self.lock:
            if self.up:
                raise ValueError("starting a node that is already up")
            self.makenodedir()
            self.client = LxdClient(self.name, self.image, self.host_cmd)
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

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        return f"lxc exec {self.name} -- {sh}"

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
        self.client.copy_file(src_path, dst_path)
        if mode is not None:
            self.cmd(f"chmod {mode:o} {dst_path}")

    def add_iface(self, iface: CoreInterface, iface_id: int) -> None:
        super().add_iface(iface, iface_id)
        # adding small delay to allow time for adding addresses to work correctly
        time.sleep(0.5)
