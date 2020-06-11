import json
import logging
import os
import time
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Callable, Dict, Optional

from core import utils
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import NodeTypes
from core.errors import CoreCommandError
from core.nodes.base import CoreNode
from core.nodes.interface import CoreInterface

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

    def copy_file(self, source: str, destination: str) -> None:
        if destination[0] != "/":
            destination = os.path.join("/root/", destination)

        args = f"lxc file push {source} {self.name}/{destination}"
        self.run(args)


class LxcNode(CoreNode):
    apitype = NodeTypes.LXC

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        nodedir: str = None,
        start: bool = True,
        server: DistributedServer = None,
        image: str = None,
    ) -> None:
        """
        Create a LxcNode instance.

        :param session: core session instance
        :param _id: object id
        :param name: object name
        :param nodedir: node directory
        :param start: start flag
        :param server: remote server node
            will run on, default is None for localhost
        :param image: image to start container with
        """
        if image is None:
            image = "ubuntu"
        self.image: str = image
        super().__init__(session, _id, name, nodedir, start, server)

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
            self._netif.clear()
            self.client.stop_container()
            self.up = False

    def termcmdstring(self, sh: str = "/bin/sh") -> str:
        """
        Create a terminal command string.

        :param sh: shell to execute command in
        :return: str
        """
        return f"lxc exec {self.name} -- {sh}"

    def privatedir(self, path: str) -> None:
        """
        Create a private directory.

        :param path: path to create
        :return: nothing
        """
        logging.info("creating node dir: %s", path)
        args = f"mkdir -p {path}"
        self.cmd(args)

    def mount(self, source: str, target: str) -> None:
        """
        Create and mount a directory.

        :param source: source directory to mount
        :param target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.debug("mounting source(%s) target(%s)", source, target)
        raise Exception("not supported")

    def nodefile(self, filename: str, contents: str, mode: int = 0o644) -> None:
        """
        Create a node file with a given mode.

        :param filename: name of file to create
        :param contents: contents of file
        :param mode: mode for file
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
        logging.debug("node(%s) added file: %s; mode: 0%o", self.name, filename, mode)

    def nodefilecopy(self, filename: str, srcfilename: str, mode: int = None) -> None:
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param filename: file name to copy file to
        :param srcfilename: file to copy
        :param mode: mode to copy to
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

    def addnetif(self, netif: CoreInterface, ifindex: int) -> None:
        super().addnetif(netif, ifindex)
        # adding small delay to allow time for adding addresses to work correctly
        time.sleep(0.5)
