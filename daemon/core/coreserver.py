"""
Defines server classes and request handlers for TCP and UDP.
"""

import SocketServer
import os
import threading
import time

from core import logger
from core.api import coreapi
from core.enumerations import EventTypes
from core.enumerations import SessionTlvs
from core.session import Session


class CoreServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """
    TCP server class, manages sessions and spawns request handlers for
    incoming connections.
    """
    daemon_threads = True
    allow_reuse_address = True
    servers = set()

    def __init__(self, server_address, handler_class, config=None):
        """
        Server class initialization takes configuration data and calls
        the SocketServer constructor

        :param tuple[str, int] server_address: server host and port to use
        :param class handler_class: request handler
        :param dict config: configuration setting
        :return:
        """
        self.config = config
        self.sessions = {}
        self.udpserver = None
        self.udpthread = None
        self._sessions_lock = threading.Lock()
        CoreServer.add_server(self)
        SocketServer.TCPServer.__init__(self, server_address, handler_class)

    @classmethod
    def add_server(cls, server):
        """
        Add a core server to the known servers set.

        :param CoreServer server: server to add
        :return: nothing
        """
        cls.servers.add(server)

    @classmethod
    def remove_server(cls, server):
        """
        Remove a core server from the known servers set.

        :param CoreServer server: server to remove
        :return: nothing
        """
        if server in cls.servers:
            cls.servers.remove(server)

    def shutdown(self):
        """
        Shutdown the server, all known sessions, and remove server from known servers set.

        :return: nothing
        """
        # shutdown all known sessions
        for session in self.sessions.values():
            session.shutdown()

        # if we are a daemon remove pid file
        if self.config["daemonize"]:
            pid_file = self.config["pidfile"]
            try:
                os.unlink(pid_file)
            except OSError:
                logger.exception("error daemon pid file: %s", pid_file)

        # remove server from server list
        CoreServer.remove_server(self)

    def add_session(self, session):
        """
        Add a session to our dictionary of sessions, ensuring a unique session number.

        :param core.session.Session session: session to add
        :return: added session
        :raise KeyError: when a session with the same id already exists
        """
        with self._sessions_lock:
            if session.session_id in self.sessions:
                raise KeyError("non-unique session id %s for %s" % (session.session_id, session))
            self.sessions[session.session_id] = session

        return session

    def remove_session(self, session):
        """
        Remove a session from our dictionary of sessions.

        :param core.session.Session session: session to remove
        :return: removed session
        :rtype: core.session.Session
        """
        with self._sessions_lock:
            if session.session_id not in self.sessions:
                logger.info("session id %s not found (sessions=%s)", session.session_id, self.sessions.keys())
            else:
                del self.sessions[session.session_id]

        return session

    def get_session_ids(self):
        """
        Return a list of active session numbers.

        :return: known session ids
        :rtype: list
        """
        with self._sessions_lock:
            session_ids = self.sessions.keys()

        return session_ids

    def create_session(self, session_id=None):
        """
        Convenience method for creating sessions with the servers config.

        :param int session_id: session id for new session
        :return: create session
        :rtype: core.session.Session
        """

        # create random id when necessary, seems to be 1 case wanted, based on legacy code
        # creating a value so high, typical client side generation schemes hopefully wont collide
        if not session_id:
            session_id = next(
                session_id for session_id in xrange(60000, 65000)
                if session_id not in self.sessions
            )

        # create and add session to local manager
        session = Session(session_id, config=self.config)
        self.add_session(session)

        # add shutdown handler to remove session from manager
        session.shutdown_handlers.append(self.session_shutdown)

        return session

    def get_session(self, session_id=None):
        """
        Create a new session or retrieve an existing one from our
        dictionary of sessions. When the session_id=0 and the use_existing
        flag is set, return on of the existing sessions.

        :param int session_id: session id of session to retrieve, defaults to returning random session
        :return: session
        :rtype: core.session.Session
        """

        with self._sessions_lock:
            # return specified session or none
            if session_id:
                return self.sessions.get(session_id)

            # retrieving known session
            session = None

            # find runtime session with highest node count
            for known_session in filter(lambda x: x.state == EventTypes.RUNTIME_STATE.value,
                                        self.sessions.itervalues()):
                if not session or known_session.get_node_count() > session.get_node_count():
                    session = known_session

            # return first known session otherwise
            if not session:
                for known_session in self.sessions.itervalues():
                    session = known_session
                    break

            return session

    def session_shutdown(self, session):
        """
        Handler method to be used as a callback when a session has shutdown.

        :param core.session.Session session: session shutting down
        :return: nothing
        """
        self.remove_session(session)

    def to_session_message(self, flags=0):
        """
        Build CORE API Sessions message based on current session info.

        :param int flags: message flags
        :return: session message
        """
        id_list = []
        name_list = []
        file_list = []
        node_count_list = []
        date_list = []
        thumb_list = []
        num_sessions = 0

        with self._sessions_lock:
            for session_id in self.sessions:
                session = self.sessions[session_id]
                # debug: session.dumpsession()
                num_sessions += 1
                id_list.append(str(session_id))

                name = session.name
                if not name:
                    name = ""
                name_list.append(name)

                file = session.file_name
                if not file:
                    file = ""
                file_list.append(file)

                node_count_list.append(str(session.get_node_count()))

                date_list.append(time.ctime(session._state_time))

                thumb = session.thumbnail
                if not thumb:
                    thumb = ""
                thumb_list.append(thumb)

        session_ids = "|".join(id_list)
        names = "|".join(name_list)
        files = "|".join(file_list)
        node_counts = "|".join(node_count_list)
        dates = "|".join(date_list)
        thumbs = "|".join(thumb_list)

        if num_sessions > 0:
            tlv_data = ""
            if len(session_ids) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.NUMBER.value, session_ids)
            if len(names) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.NAME.value, names)
            if len(files) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.FILE.value, files)
            if len(node_counts) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.NODE_COUNT.value, node_counts)
            if len(dates) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.DATE.value, dates)
            if len(thumbs) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.THUMB.value, thumbs)
            message = coreapi.CoreSessionMessage.pack(flags, tlv_data)
        else:
            message = None

        return message

    def dump_sessions(self):
        """
        Log currently known session information.
        """
        logger.info("sessions:")
        with self._sessions_lock:
            for session_id in self.sessions:
                logger.info(session_id)


class CoreUdpServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
    """
    UDP server class, manages sessions and spawns request handlers for
    incoming connections.
    """
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, main_server):
        """
        Server class initialization takes configuration data and calls
        the SocketServer constructor

        :param tuple[str, int] server_address: server address
        :param class handler_class: class for handling requests
        :param main_server: main server to associate with
        """
        self.mainserver = main_server
        SocketServer.UDPServer.__init__(self, server_address, handler_class)

    def start(self):
        """
        Thread target to run concurrently with the TCP server.

        :return: nothing
        """
        self.serve_forever()
