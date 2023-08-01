"""
Defines distributed server functionality.
"""

import logging
import os
import threading
from collections import OrderedDict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Callable

import netaddr
from fabric import Connection
from invoke import UnexpectedExit

from core import utils
from core.emulator.links import CoreLink
from core.errors import CoreCommandError, CoreError
from core.executables import get_requirements
from core.nodes.interface import GreTap
from core.nodes.network import CoreNetwork, CtrlNet

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

LOCK = threading.Lock()
CMD_HIDE = True


class DistributedServer:
    """
    Provides distributed server interactions.
    """

    def __init__(self, name: str, host: str) -> None:
        """
        Create a DistributedServer instance.

        :param name: convenience name to associate with host
        :param host: host to connect to
        """
        self.name: str = name
        self.host: str = host
        self.conn: Connection = Connection(host, user="root")
        self.lock: threading.Lock = threading.Lock()

    def remote_cmd(
        self, cmd: str, env: dict[str, str] = None, cwd: str = None, wait: bool = True
    ) -> str:
        """
        Run command remotely using server connection.

        :param cmd: command to run
        :param env: environment for remote command, default is None
        :param cwd: directory to run command in, defaults to None, which is the
            user's home directory
        :param wait: True to wait for status, False to background process
        :return: stdout when success
        :raises CoreCommandError: when a non-zero exit status occurs
        """

        replace_env = env is not None
        if not wait:
            cmd += " &"
        logger.debug(
            "remote cmd server(%s) cwd(%s) wait(%s): %s", self.host, cwd, wait, cmd
        )
        try:
            if cwd is None:
                result = self.conn.run(
                    cmd, hide=CMD_HIDE, env=env, replace_env=replace_env
                )
            else:
                with self.conn.cd(cwd):
                    result = self.conn.run(
                        cmd, hide=CMD_HIDE, env=env, replace_env=replace_env
                    )
            return result.stdout.strip()
        except UnexpectedExit as e:
            stdout, stderr = e.streams_for_display()
            raise CoreCommandError(e.result.exited, cmd, stdout, stderr)

    def remote_put(self, src_path: Path, dst_path: Path) -> None:
        """
        Push file to remote server.

        :param src_path: source file to push
        :param dst_path: destination file location
        :return: nothing
        """
        with self.lock:
            self.conn.put(str(src_path), str(dst_path))

    def remote_put_temp(self, dst_path: Path, data: str) -> None:
        """
        Remote push file contents to a remote server, using a temp file as an
        intermediate step.

        :param dst_path: file destination for data
        :param data: data to store in remote file
        :return: nothing
        """
        with self.lock:
            temp = NamedTemporaryFile(delete=False)
            temp.write(data.encode())
            temp.close()
            self.conn.put(temp.name, str(dst_path))
            os.unlink(temp.name)


class DistributedController:
    """
    Provides logic for dealing with remote tunnels and distributed servers.
    """

    def __init__(self, session: "Session") -> None:
        """
        Create

        :param session: session
        """
        self.session: "Session" = session
        self.servers: dict[str, DistributedServer] = OrderedDict()
        self.tunnels: dict[int, tuple[GreTap, GreTap]] = {}
        self.address: str = self.session.options.get("distributed_address")

    def add_server(self, name: str, host: str) -> None:
        """
        Add distributed server configuration.

        :param name: distributed server name
        :param host: distributed server host address
        :return: nothing
        :raises CoreError: when there is an error validating server
        """
        server = DistributedServer(name, host)
        for requirement in get_requirements(self.session.use_ovs()):
            try:
                server.remote_cmd(f"which {requirement}")
            except CoreCommandError:
                raise CoreError(
                    f"server({server.name}) failed validation for "
                    f"command({requirement})"
                )
        self.servers[name] = server
        cmd = f"mkdir -p {self.session.directory}"
        server.remote_cmd(cmd)

    def execute(self, func: Callable[[DistributedServer], None]) -> None:
        """
        Convenience for executing logic against all distributed servers.

        :param func: function to run, that takes a DistributedServer as a parameter
        :return: nothing
        """
        for name in self.servers:
            server = self.servers[name]
            func(server)

    def shutdown(self) -> None:
        """
        Shutdown logic for dealing with distributed tunnels and server session
        directories.

        :return: nothing
        """
        # shutdown all tunnels
        for key in self.tunnels:
            tunnels = self.tunnels[key]
            for tunnel in tunnels:
                tunnel.shutdown()
        # remove all remote session directories
        for name in self.servers:
            server = self.servers[name]
            cmd = f"rm -rf {self.session.directory}"
            server.remote_cmd(cmd)
        # clear tunnels
        self.tunnels.clear()

    def start(self) -> None:
        """
        Start distributed network tunnels for control networks.

        :return: nothing
        """
        mtu = self.session.options.get_int("mtu")
        for node in self.session.nodes.values():
            if not isinstance(node, CtrlNet) or node.serverintf is not None:
                continue
            for name in self.servers:
                server = self.servers[name]
                self.create_gre_tunnel(node, server, mtu, True)

    def create_gre_tunnels(self, core_link: CoreLink) -> None:
        """
        Creates gre tunnels for a core link with a ptp network connection.

        :param core_link: core link to create gre tunnel for
        :return: nothing
        """
        if not self.servers:
            return
        if not core_link.ptp:
            raise CoreError(
                "attempted to create gre tunnel for core link without a ptp network"
            )
        mtu = self.session.options.get_int("mtu")
        for server in self.servers.values():
            self.create_gre_tunnel(core_link.ptp, server, mtu, True)

    def create_gre_tunnel(
        self, node: CoreNetwork, server: DistributedServer, mtu: int, start: bool
    ) -> tuple[GreTap, GreTap]:
        """
        Create gre tunnel using a pair of gre taps between the local and remote server.

        :param node: node to create gre tunnel for
        :param server: server to create tunnel for
        :param mtu: mtu for gre taps
        :param start: True to start gre taps, False otherwise
        :return: local and remote gre taps created for tunnel
        """
        host = server.host
        key = self.tunnel_key(node.id, netaddr.IPAddress(host).value)
        tunnel = self.tunnels.get(key)
        if tunnel is not None:
            return tunnel
        # local to server
        logger.info("local tunnel node(%s) to remote(%s) key(%s)", node.name, host, key)
        local_tap = GreTap(self.session, host, key=key, mtu=mtu)
        if start:
            local_tap.startup()
            local_tap.net_client.set_iface_master(node.brname, local_tap.localname)
        # server to local
        logger.info(
            "remote tunnel node(%s) to local(%s) key(%s)", node.name, self.address, key
        )
        remote_tap = GreTap(self.session, self.address, key=key, server=server, mtu=mtu)
        if start:
            remote_tap.startup()
            remote_tap.net_client.set_iface_master(node.brname, remote_tap.localname)
        # save tunnels for shutdown
        tunnel = (local_tap, remote_tap)
        self.tunnels[key] = tunnel
        return tunnel

    def tunnel_key(self, node1_id: int, node2_id: int) -> int:
        """
        Compute a 32-bit key used to uniquely identify a GRE tunnel.
        The hash(n1num), hash(n2num) values are used, so node numbers may be
        None or string values (used for e.g. "ctrlnet").

        :param node1_id: node one id
        :param node2_id: node two id
        :return: tunnel key for the node pair
        """
        logger.debug("creating tunnel key for: %s, %s", node1_id, node2_id)
        key = (
            (self.session.id << 16)
            ^ utils.hashkey(node1_id)
            ^ (utils.hashkey(node2_id) << 8)
        )
        return key & 0xFFFFFFFF
