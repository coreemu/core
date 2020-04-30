"""
Defines distributed server functionality.
"""

import logging
import os
import threading
from collections import OrderedDict
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Callable, Dict, Tuple

import netaddr
from fabric import Connection
from invoke import UnexpectedExit

from core import utils
from core.errors import CoreCommandError
from core.nodes.interface import GreTap
from core.nodes.network import CoreNetwork, CtrlNet

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
        self.name = name
        self.host = host
        self.conn = Connection(host, user="root")
        self.lock = threading.Lock()

    def remote_cmd(
        self, cmd: str, env: Dict[str, str] = None, cwd: str = None, wait: bool = True
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
        logging.debug(
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

    def remote_put(self, source: str, destination: str) -> None:
        """
        Push file to remote server.

        :param source: source file to push
        :param destination: destination file location
        :return: nothing
        """
        with self.lock:
            self.conn.put(source, destination)

    def remote_put_temp(self, destination: str, data: str) -> None:
        """
        Remote push file contents to a remote server, using a temp file as an
        intermediate step.

        :param destination: file destination for data
        :param data: data to store in remote file
        :return: nothing
        """
        with self.lock:
            temp = NamedTemporaryFile(delete=False)
            temp.write(data.encode("utf-8"))
            temp.close()
            self.conn.put(temp.name, destination)
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
        self.session = session
        self.servers = OrderedDict()
        self.tunnels = {}
        self.address = self.session.options.get_config(
            "distributed_address", default=None
        )

    def add_server(self, name: str, host: str) -> None:
        """
        Add distributed server configuration.

        :param name: distributed server name
        :param host: distributed server host address
        :return: nothing
        """
        server = DistributedServer(name, host)
        self.servers[name] = server
        cmd = f"mkdir -p {self.session.session_dir}"
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
            cmd = f"rm -rf {self.session.session_dir}"
            server.remote_cmd(cmd)

        # clear tunnels
        self.tunnels.clear()

    def start(self) -> None:
        """
        Start distributed network tunnels.

        :return: nothing
        """
        for node_id in self.session.nodes:
            node = self.session.nodes[node_id]

            if not isinstance(node, CoreNetwork):
                continue

            if isinstance(node, CtrlNet) and node.serverintf is not None:
                continue

            for name in self.servers:
                server = self.servers[name]
                self.create_gre_tunnel(node, server)

    def create_gre_tunnel(
        self, node: CoreNetwork, server: DistributedServer
    ) -> Tuple[GreTap, GreTap]:
        """
        Create gre tunnel using a pair of gre taps between the local and remote server.


        :param node: node to create gre tunnel for
        :param server: server to create
            tunnel for
        :return: local and remote gre taps created for tunnel
        """
        host = server.host
        key = self.tunnel_key(node.id, netaddr.IPAddress(host).value)
        tunnel = self.tunnels.get(key)
        if tunnel is not None:
            return tunnel

        # local to server
        logging.info(
            "local tunnel node(%s) to remote(%s) key(%s)", node.name, host, key
        )
        local_tap = GreTap(session=self.session, remoteip=host, key=key)
        local_tap.net_client.create_interface(node.brname, local_tap.localname)

        # server to local
        logging.info(
            "remote tunnel node(%s) to local(%s) key(%s)", node.name, self.address, key
        )
        remote_tap = GreTap(
            session=self.session, remoteip=self.address, key=key, server=server
        )
        remote_tap.net_client.create_interface(node.brname, remote_tap.localname)

        # save tunnels for shutdown
        tunnel = (local_tap, remote_tap)
        self.tunnels[key] = tunnel
        return tunnel

    def tunnel_key(self, n1_id: int, n2_id: int) -> int:
        """
        Compute a 32-bit key used to uniquely identify a GRE tunnel.
        The hash(n1num), hash(n2num) values are used, so node numbers may be
        None or string values (used for e.g. "ctrlnet").

        :param n1_id: node one id
        :param n2_id: node two id
        :return: tunnel key for the node pair
        """
        logging.debug("creating tunnel key for: %s, %s", n1_id, n2_id)
        key = (
            (self.session.id << 16) ^ utils.hashkey(n1_id) ^ (utils.hashkey(n2_id) << 8)
        )
        return key & 0xFFFFFFFF

    def get_tunnel(self, n1_id: int, n2_id: int) -> Tuple[GreTap, GreTap]:
        """
        Return the GreTap between two nodes if it exists.

        :param n1_id: node one id
        :param n2_id: node two id
        :return: gre tap between nodes or None
        """
        key = self.tunnel_key(n1_id, n2_id)
        logging.debug("checking for tunnel key(%s) in: %s", key, self.tunnels)
        return self.tunnels.get(key)
