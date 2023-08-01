import argparse
import select
import socket

DEFAULT_ADDRESS: str = ""
DEFAULT_PORT: int = 9001
READ_SIZE: int = 4096


class ChatServer:
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.sockets = []

    def broadcast(self, ignore, message):
        for sock in self.sockets:
            if sock not in ignore:
                sock.sendall(message.encode())

    def run(self):
        print(f"chat server listening on: {self.address}:{self.port}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.address, self.port))
            server.listen()
            self.sockets.append(server)
            try:
                while True:
                    read_sockets, write_sockets, error_sockets = select.select(
                        self.sockets, [], []
                    )
                    for sock in read_sockets:
                        if sock == server:
                            client_sock, addr = server.accept()
                            self.sockets.append(client_sock)
                            name = f"{addr[0]}:{addr[1]}"
                            print(f"[server] {name} joining")
                            self.broadcast(
                                {server, client_sock}, f"[server] {name} entered room\n"
                            )
                        else:
                            peer = sock.getpeername()
                            name = f"{peer[0]}:{peer[1]}"
                            try:
                                data = sock.recv(READ_SIZE).decode().strip()
                                if data:
                                    print(f"[{name}] {data}")
                                    self.broadcast({server, sock}, f"[{name}] {data}\n")
                                else:
                                    print(f"[server] {name} leaving")
                                    self.broadcast(
                                        {server, sock}, f"[server] {name} leaving\n"
                                    )
                                    sock.close()
                                    self.sockets.remove(sock)
                            except socket.error:
                                print(f"[server] {name} leaving")
                                self.broadcast(
                                    {server, sock}, f"[server] {name} leaving\n"
                                )
                                sock.close()
                                self.sockets.remove(sock)
            except KeyboardInterrupt:
                print("closing server")


def main():
    parser = argparse.ArgumentParser(
        description="chat app server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-a", "--address", help="address to listen on", default=DEFAULT_ADDRESS
    )
    parser.add_argument(
        "-p", "--port", type=int, help="port to listen on", default=DEFAULT_PORT
    )
    args = parser.parse_args()
    server = ChatServer(args.address, args.port)
    server.run()


if __name__ == "__main__":
    main()
