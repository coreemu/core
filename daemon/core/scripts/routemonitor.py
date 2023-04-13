import argparse
import enum
import select
import socket
import subprocess
import sys
import time
from argparse import ArgumentDefaultsHelpFormatter
from functools import cmp_to_key
from queue import Queue
from threading import Thread

import grpc

from core import utils
from core.api.grpc.client import CoreGrpcClient
from core.api.grpc.wrappers import NodeType

SDT_HOST = "127.0.0.1"
SDT_PORT = 50000
ROUTE_LAYER = "CORE Route"
DEAD_TIME = 3
ROUTE_TIME = 3
PACKET_CHOICES = ["udp", "tcp", "icmp"]


class RouteEnum(enum.Enum):
    ADD = 0
    DEL = 1


class SdtClient:
    def __init__(self, address: tuple[str, int]) -> None:
        self.sock = socket.create_connection(address)
        self.links = []
        self.send(f'layer "{ROUTE_LAYER}"')

    def close(self) -> None:
        self.sock.close()

    def send(self, cmd: str) -> None:
        sdt_cmd = f"{cmd}\n".encode()
        self.sock.sendall(sdt_cmd)

    def add_link(self, node1, node2) -> None:
        route_id = f"{node1}-{node2}-r"
        link_id = f"{node1},{node2},{route_id}"
        cmd = f'link {link_id} linkLayer "{ROUTE_LAYER}" line yellow,2'
        self.send(cmd)
        self.links.append(link_id)

    def delete_links(self) -> None:
        for link_id in self.links:
            cmd = f"delete link,{link_id}"
            self.send(cmd)
        self.links.clear()


class RouterMonitor:
    def __init__(
        self,
        session: int,
        src: str,
        dst: str,
        pkt: str,
        rate: int,
        dead: int,
        sdt_host: str,
        sdt_port: int,
    ) -> None:
        self.queue = Queue()
        self.core = CoreGrpcClient()
        self.session = session
        self.src_id = None
        self.src = src
        self.dst = dst
        self.pkt = pkt
        self.rate = rate
        self.dead = dead
        self.seen = {}
        self.running = False
        self.route_time = None
        self.listeners = []
        self.sdt = SdtClient((sdt_host, sdt_port))
        self.nodes = self.get_nodes()

    def get_nodes(self) -> dict[int, str]:
        with self.core.context_connect():
            if self.session is None:
                self.session = self.get_session()
            print("session: ", self.session)
            try:
                session = self.core.get_session(self.session)
                node_map = {}
                for node in session.nodes.values():
                    if node.type != NodeType.DEFAULT:
                        continue
                    node_map[node.id] = node.channel
                    if self.src_id is None:
                        _, ifaces, _ = self.core.get_node(self.session, node.id)
                        for iface in ifaces:
                            if self.src == iface.ip4:
                                self.src_id = node.id
                                break
            except grpc.RpcError:
                print(f"invalid session: {self.session}")
                sys.exit(1)
        if self.src_id is None:
            print(f"could not find node with source address: {self.src}")
            sys.exit(1)
        print(
            f"monitoring src_id ({self.src_id}) src({self.src}) dst({self.dst}) pkt({self.pkt})"
        )
        return node_map

    def get_session(self) -> int:
        sessions = self.core.get_sessions()
        session = None
        if sessions:
            session = sessions[0]
        if not session:
            print("no current core sessions")
            sys.exit(1)
        return session.id

    def start(self) -> None:
        self.running = True
        for node_id, node in self.nodes.items():
            print("listening on node: ", node)
            thread = Thread(target=self.listen, args=(node_id, node), daemon=True)
            thread.start()
            self.listeners.append(thread)
        self.manage()

    def manage(self) -> None:
        self.route_time = time.monotonic()
        while self.running:
            route_enum, node, seen = self.queue.get()
            if route_enum == RouteEnum.ADD:
                self.seen[node] = seen
            elif node in self.seen:
                del self.seen[node]

            if (time.monotonic() - self.route_time) >= self.rate:
                self.manage_routes()
                self.route_time = time.monotonic()

    def route_sort(self, x: tuple[str, int], y: tuple[str, int]) -> int:
        x_node = x[0]
        y_node = y[0]
        if x_node == self.src_id:
            return 1
        if y_node == self.src_id:
            return -1
        x_ttl, y_ttl = x[1], y[1]
        return x_ttl - y_ttl

    def manage_routes(self) -> None:
        self.sdt.delete_links()
        if not self.seen:
            return
        values = sorted(
            self.seen.items(), key=cmp_to_key(self.route_sort), reverse=True
        )
        print("current route:")
        for index, node_data in enumerate(values):
            next_index = index + 1
            if next_index == len(values):
                break
            next_node_id = values[next_index][0]
            node_id, ttl = node_data
            print(f"{node_id} -> {next_node_id}")
            self.sdt.add_link(node_id, next_node_id)

    def stop(self) -> None:
        self.running = False
        self.sdt.delete_links()
        self.sdt.close()
        for thread in self.listeners:
            thread.join()
        self.listeners.clear()

    def listen(self, node_id, node) -> None:
        cmd = f"tcpdump -lnvi any src host {self.src} and dst host {self.dst} and {self.pkt}"
        node_cmd = f"vcmd -c {node} -- {cmd}"
        p = subprocess.Popen(
            node_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        current = time.monotonic()
        try:
            while not p.poll() and self.running:
                ready, _, _ = select.select([p.stdout], [], [], 1)
                if ready:
                    line = p.stdout.readline().strip().decode()
                    if line:
                        line = line.split("ttl", 1)[1]
                        ttl = int(line.split(",", 1)[0])
                        p.stdout.readline()
                        self.queue.put((RouteEnum.ADD, node_id, ttl))
                        current = time.monotonic()
                else:
                    if (time.monotonic() - current) >= self.dead:
                        self.queue.put((RouteEnum.DEL, node_id, None))
        except Exception as e:
            print(f"listener error: {e}")


def main() -> None:
    if not utils.which("tcpdump", required=False):
        print("core-route-monitor requires tcpdump to be installed")
        return

    desc = "core route monitor leverages tcpdump to monitor traffic and find route using TTL"
    parser = argparse.ArgumentParser(
        description=desc, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--src", required=True, help="source address for route monitoring"
    )
    parser.add_argument(
        "--dst", required=True, help="destination address for route monitoring"
    )
    parser.add_argument("--session", type=int, help="session to monitor route")
    parser.add_argument(
        "--pkt", default="icmp", choices=PACKET_CHOICES, help="packet type"
    )
    parser.add_argument(
        "--rate", type=int, default=ROUTE_TIME, help="rate to update route, in seconds"
    )
    parser.add_argument(
        "--dead",
        type=int,
        default=DEAD_TIME,
        help="timeout to declare path dead, in seconds",
    )
    parser.add_argument("--sdt-host", default=SDT_HOST, help="sdt host address")
    parser.add_argument("--sdt-port", type=int, default=SDT_PORT, help="sdt port")
    args = parser.parse_args()

    monitor = RouterMonitor(
        args.session,
        args.src,
        args.dst,
        args.pkt,
        args.rate,
        args.dead,
        args.sdt_host,
        args.sdt_port,
    )
    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.stop()
        print("ending route monitor")


if __name__ == "__main__":
    main()
