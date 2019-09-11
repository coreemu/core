"""
Defines core server for handling TCP connections.
"""

import socketserver

from core.emulator.coreemu import CoreEmu


class CoreServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    TCP server class, manages sessions and spawns request handlers for
    incoming connections.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, config=None):
        """
        Server class initialization takes configuration data and calls
        the socketserver constructor.

        :param tuple[str, int] server_address: server host and port to use
        :param class handler_class: request handler
        :param dict config: configuration setting
        """
        self.coreemu = CoreEmu(config)
        self.config = config
        socketserver.TCPServer.__init__(self, server_address, handler_class)


class CoreUdpServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    """
    UDP server class, manages sessions and spawns request handlers for
    incoming connections.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, mainserver):
        """
        Server class initialization takes configuration data and calls
        the SocketServer constructor

        :param server_address:
        :param class handler_class: request handler
        :param mainserver:
        """
        self.mainserver = mainserver
        socketserver.UDPServer.__init__(self, server_address, handler_class)

    def start(self):
        """
        Thread target to run concurrently with the TCP server.

        :return: nothing
        """
        self.serve_forever()
