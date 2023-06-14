import argparse
import select
import socket
import sys

DEFAULT_PORT: int = 9001
READ_SIZE: int = 4096


def prompt():
    sys.stdout.write(">> ")
    sys.stdout.flush()


class ChatClient:
    def __init__(self, address, port):
        self.address = address
        self.port = port

    def run(self):
        server = socket.create_connection((self.address, self.port))
        sockname = server.getsockname()
        print(
            f"connected to server({self.address}:{self.port}) as "
            f"client({sockname[0]}:{sockname[1]})"
        )
        sockets = [server]
        prompt()
        try:
            while True:
                read_sockets, write_socket, error_socket = select.select(
                    sockets, [], [], 10
                )
                for sock in read_sockets:
                    if sock == server:
                        message = server.recv(READ_SIZE)
                        if not message:
                            print("server closed")
                            sys.exit(1)
                        else:
                            print("\x1b[2K\r", end="")
                            print(message.decode().strip())
                            prompt()
                # waiting for input
                message = input(".")
                server.sendall(f"{message}\n".encode())
        except KeyboardInterrupt:
            print("client exiting")
            server.close()


def main():
    parser = argparse.ArgumentParser(
        description="chat app client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-a", "--address", help="address to listen on", required=True)
    parser.add_argument(
        "-p", "--port", type=int, help="port to listen on", default=DEFAULT_PORT
    )
    args = parser.parse_args()
    client = ChatClient(args.address, args.port)
    client.run()


if __name__ == "__main__":
    main()
