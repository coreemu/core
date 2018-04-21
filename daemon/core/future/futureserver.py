"""
Defines server classes and request handlers for TCP and UDP.
"""

import SocketServer

from core.future.coreemu import CoreEmu


class FutureServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """
    TCP server class, manages sessions and spawns request handlers for
    incoming connections.
    """
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, config=None):
        """
        Server class initialization takes configuration data and calls
        the SocketServer constructor

        :param tuple[str, int] server_address: server host and port to use
        :param class handler_class: request handler
        :param dict config: configuration setting
        :return:
        """
        self.coreemu = CoreEmu(config)
        self.config = config
        SocketServer.TCPServer.__init__(self, server_address, handler_class)

    def shutdown(self):
        """
        Shutdown the server, all known sessions, and remove server from known servers set.

        :return: nothing
        """
        # shutdown all known sessions
        for session in self.coreemu.sessions.itervalues():
            session.shutdown()
