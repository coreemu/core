"""
socket server request handlers leveraged by core servers.
"""

import logging
import shlex
import shutil
import socketserver
import sys
import threading
import time
from itertools import repeat
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from core import utils
from core.api.tlv import coreapi, dataconversion, structutils
from core.api.tlv.dataconversion import ConfigShim
from core.api.tlv.enumerations import (
    ConfigFlags,
    ConfigTlvs,
    EventTlvs,
    ExceptionTlvs,
    ExecuteTlvs,
    FileTlvs,
    LinkTlvs,
    MessageTypes,
    NodeTlvs,
    SessionTlvs,
)
from core.emane.modelmanager import EmaneModelManager
from core.emulator.data import (
    ConfigData,
    EventData,
    ExceptionData,
    FileData,
    InterfaceData,
    LinkOptions,
    NodeOptions,
)
from core.emulator.enumerations import (
    ConfigDataTypes,
    EventTypes,
    ExceptionLevels,
    LinkTypes,
    MessageFlags,
    NodeTypes,
    RegisterTlvs,
)
from core.emulator.session import Session
from core.errors import CoreCommandError, CoreError
from core.location.mobility import BasicRangeModel
from core.nodes.base import CoreNode, CoreNodeBase, NodeBase
from core.nodes.network import WlanNode
from core.nodes.physical import Rj45Node
from core.services.coreservices import ServiceManager, ServiceShim

logger = logging.getLogger(__name__)


class CoreHandler(socketserver.BaseRequestHandler):
    """
    The CoreHandler class uses the RequestHandler class for servicing requests.
    """

    session_clients = {}

    def __init__(self, request, client_address, server):
        """
        Create a CoreRequestHandler instance.

        :param request: request object
        :param str client_address: client address
        :param CoreServer server: core server instance
        """
        self.done = False
        self.message_handlers = {
            MessageTypes.NODE.value: self.handle_node_message,
            MessageTypes.LINK.value: self.handle_link_message,
            MessageTypes.EXECUTE.value: self.handle_execute_message,
            MessageTypes.REGISTER.value: self.handle_register_message,
            MessageTypes.CONFIG.value: self.handle_config_message,
            MessageTypes.FILE.value: self.handle_file_message,
            MessageTypes.INTERFACE.value: self.handle_iface_message,
            MessageTypes.EVENT.value: self.handle_event_message,
            MessageTypes.SESSION.value: self.handle_session_message,
        }
        self.message_queue = Queue()
        self.node_status_request = {}
        self._shutdown_lock = threading.Lock()
        self._sessions_lock = threading.Lock()

        self.handler_threads = []
        thread = threading.Thread(target=self.handler_thread, daemon=True)
        thread.start()
        self.handler_threads.append(thread)

        self.session: Optional[Session] = None
        self.coreemu = server.coreemu
        utils.close_onexec(request.fileno())
        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        """
        Client has connected, set up a new connection.

        :return: nothing
        """
        logger.debug("new TCP connection: %s", self.client_address)

    def finish(self):
        """
        Client has disconnected, end this request handler and disconnect
        from the session. Shutdown sessions that are not running.

        :return: nothing
        """
        logger.debug("finishing request handler")
        logger.debug("remaining message queue size: %s", self.message_queue.qsize())

        # give some time for message queue to deplete
        timeout = 10
        wait = 0
        while not self.message_queue.empty():
            logger.debug("waiting for message queue to empty: %s seconds", wait)
            time.sleep(1)
            wait += 1
            if wait == timeout:
                logger.warning("queue failed to be empty, finishing request handler")
                break

        logger.info("client disconnected: notifying threads")
        self.done = True
        for thread in self.handler_threads:
            logger.info("waiting for thread: %s", thread.getName())
            thread.join(timeout)
            if thread.is_alive():
                logger.warning(
                    "joining %s failed: still alive after %s sec",
                    thread.getName(),
                    timeout,
                )

        logger.info("connection closed: %s", self.client_address)
        if self.session:
            # remove client from session broker and shutdown if there are no clients
            self.remove_session_handlers()
            clients = self.session_clients[self.session.id]
            clients.remove(self)
            if not clients and not self.session.is_active():
                logger.info(
                    "no session clients left and not active, initiating shutdown"
                )
                self.coreemu.delete_session(self.session.id)

        return socketserver.BaseRequestHandler.finish(self)

    def session_message(self, flags=0):
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
            for _id in self.coreemu.sessions:
                session = self.coreemu.sessions[_id]
                num_sessions += 1
                id_list.append(str(_id))
                name = session.name
                if not name:
                    name = ""
                name_list.append(name)
                file_name = str(session.file_path) if session.file_path else ""
                file_list.append(str(file_name))
                node_count_list.append(str(session.get_node_count()))
                date_list.append(time.ctime(session.state_time))
                thumb = str(session.thumbnail) if session.thumbnail else ""
                thumb_list.append(thumb)
        session_ids = "|".join(id_list)
        names = "|".join(name_list)
        files = "|".join(file_list)
        node_counts = "|".join(node_count_list)
        dates = "|".join(date_list)
        thumbs = "|".join(thumb_list)
        if num_sessions > 0:
            tlv_data = b""
            if len(session_ids) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(
                    SessionTlvs.NUMBER.value, session_ids
                )
            if len(names) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.NAME.value, names)
            if len(files) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.FILE.value, files)
            if len(node_counts) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(
                    SessionTlvs.NODE_COUNT.value, node_counts
                )
            if len(dates) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.DATE.value, dates)
            if len(thumbs) > 0:
                tlv_data += coreapi.CoreSessionTlv.pack(SessionTlvs.THUMB.value, thumbs)
            message = coreapi.CoreSessionMessage.pack(flags, tlv_data)
        else:
            message = None
        return message

    def handle_broadcast_event(self, event_data):
        """
        Callback to handle an event broadcast out from a session.

        :param core.emulator.data.EventData event_data: event data to handle
        :return: nothing
        """
        logger.debug("handling broadcast event: %s", event_data)

        tlv_data = structutils.pack_values(
            coreapi.CoreEventTlv,
            [
                (EventTlvs.NODE, event_data.node),
                (EventTlvs.TYPE, event_data.event_type.value),
                (EventTlvs.NAME, event_data.name),
                (EventTlvs.DATA, event_data.data),
                (EventTlvs.TIME, event_data.time),
                (EventTlvs.SESSION, event_data.session),
            ],
        )
        message = coreapi.CoreEventMessage.pack(0, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending event message")

    def handle_broadcast_file(self, file_data):
        """
        Callback to handle a file broadcast out from a session.

        :param core.emulator.data.FileData file_data: file data to handle
        :return: nothing
        """
        logger.debug("handling broadcast file: %s", file_data)

        tlv_data = structutils.pack_values(
            coreapi.CoreFileTlv,
            [
                (FileTlvs.NODE, file_data.node),
                (FileTlvs.NAME, file_data.name),
                (FileTlvs.MODE, file_data.mode),
                (FileTlvs.NUMBER, file_data.number),
                (FileTlvs.TYPE, file_data.type),
                (FileTlvs.SOURCE_NAME, file_data.source),
                (FileTlvs.SESSION, file_data.session),
                (FileTlvs.DATA, file_data.data),
                (FileTlvs.COMPRESSED_DATA, file_data.compressed_data),
            ],
        )
        message = coreapi.CoreFileMessage.pack(file_data.message_type.value, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending file message")

    def handle_broadcast_config(self, config_data):
        """
        Callback to handle a config broadcast out from a session.

        :param core.emulator.data.ConfigData config_data: config data to handle
        :return: nothing
        """
        logger.debug("handling broadcast config: %s", config_data)
        message = dataconversion.convert_config(config_data)
        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending config message")

    def handle_broadcast_exception(self, exception_data):
        """
        Callback to handle an exception broadcast out from a session.

        :param core.emulator.data.ExceptionData exception_data: exception data to handle
        :return: nothing
        """
        logger.debug("handling broadcast exception: %s", exception_data)
        tlv_data = structutils.pack_values(
            coreapi.CoreExceptionTlv,
            [
                (ExceptionTlvs.NODE, exception_data.node),
                (ExceptionTlvs.SESSION, str(exception_data.session)),
                (ExceptionTlvs.LEVEL, exception_data.level.value),
                (ExceptionTlvs.SOURCE, exception_data.source),
                (ExceptionTlvs.DATE, exception_data.date),
                (ExceptionTlvs.TEXT, exception_data.text),
            ],
        )
        message = coreapi.CoreExceptionMessage.pack(0, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending exception message")

    def handle_broadcast_node(self, node_data):
        """
        Callback to handle an node broadcast out from a session.

        :param core.emulator.data.NodeData node_data: node data to handle
        :return: nothing
        """
        logger.debug("handling broadcast node: %s", node_data)
        message = dataconversion.convert_node(node_data)
        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending node message")

    def handle_broadcast_link(self, link_data):
        """
        Callback to handle an link broadcast out from a session.

        :param core.emulator.data.LinkData link_data: link data to handle
        :return: nothing
        """
        logger.debug("handling broadcast link: %s", link_data)
        options_data = link_data.options
        loss = ""
        if options_data.loss is not None:
            loss = str(options_data.loss)
        dup = ""
        if options_data.dup is not None:
            dup = str(options_data.dup)
        iface1 = link_data.iface1
        if iface1 is None:
            iface1 = InterfaceData()
        iface2 = link_data.iface2
        if iface2 is None:
            iface2 = InterfaceData()

        tlv_data = structutils.pack_values(
            coreapi.CoreLinkTlv,
            [
                (LinkTlvs.N1_NUMBER, link_data.node1_id),
                (LinkTlvs.N2_NUMBER, link_data.node2_id),
                (LinkTlvs.DELAY, options_data.delay),
                (LinkTlvs.BANDWIDTH, options_data.bandwidth),
                (LinkTlvs.LOSS, loss),
                (LinkTlvs.DUP, dup),
                (LinkTlvs.JITTER, options_data.jitter),
                (LinkTlvs.MER, options_data.mer),
                (LinkTlvs.BURST, options_data.burst),
                (LinkTlvs.MBURST, options_data.mburst),
                (LinkTlvs.TYPE, link_data.type.value),
                (LinkTlvs.UNIDIRECTIONAL, options_data.unidirectional),
                (LinkTlvs.NETWORK_ID, link_data.network_id),
                (LinkTlvs.KEY, options_data.key),
                (LinkTlvs.IFACE1_NUMBER, iface1.id),
                (LinkTlvs.IFACE1_IP4, iface1.ip4),
                (LinkTlvs.IFACE1_IP4_MASK, iface1.ip4_mask),
                (LinkTlvs.IFACE1_MAC, iface1.mac),
                (LinkTlvs.IFACE1_IP6, iface1.ip6),
                (LinkTlvs.IFACE1_IP6_MASK, iface1.ip6_mask),
                (LinkTlvs.IFACE2_NUMBER, iface2.id),
                (LinkTlvs.IFACE2_IP4, iface2.ip4),
                (LinkTlvs.IFACE2_IP4_MASK, iface2.ip4_mask),
                (LinkTlvs.IFACE2_MAC, iface2.mac),
                (LinkTlvs.IFACE2_IP6, iface2.ip6),
                (LinkTlvs.IFACE2_IP6_MASK, iface2.ip6_mask),
            ],
        )

        message = coreapi.CoreLinkMessage.pack(link_data.message_type.value, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending Event Message")

    def register(self):
        """
        Return a Register Message

        :return: register message data
        """
        logger.info(
            "GUI has connected to session %d at %s", self.session.id, time.ctime()
        )
        tlv_data = b""
        tlv_data += coreapi.CoreRegisterTlv.pack(
            RegisterTlvs.EXECUTE_SERVER.value, "core-daemon"
        )
        tlv_data += coreapi.CoreRegisterTlv.pack(
            RegisterTlvs.EMULATION_SERVER.value, "core-daemon"
        )
        tlv_data += coreapi.CoreRegisterTlv.pack(RegisterTlvs.UTILITY.value, "broker")
        tlv_data += coreapi.CoreRegisterTlv.pack(
            self.session.location.config_type.value, self.session.location.name
        )
        tlv_data += coreapi.CoreRegisterTlv.pack(
            self.session.mobility.config_type.value, self.session.mobility.name
        )
        for model_name in self.session.mobility.models:
            model_class = self.session.mobility.models[model_name]
            tlv_data += coreapi.CoreRegisterTlv.pack(
                model_class.config_type.value, model_class.name
            )
        tlv_data += coreapi.CoreRegisterTlv.pack(
            self.session.services.config_type.value, self.session.services.name
        )
        tlv_data += coreapi.CoreRegisterTlv.pack(
            self.session.emane.config_type.value, self.session.emane.name
        )
        for model_name, model_class in EmaneModelManager.models.items():
            tlv_data += coreapi.CoreRegisterTlv.pack(
                model_class.config_type.value, model_class.name
            )
        tlv_data += coreapi.CoreRegisterTlv.pack(
            self.session.options.config_type.value, self.session.options.name
        )
        tlv_data += coreapi.CoreRegisterTlv.pack(RegisterTlvs.UTILITY.value, "metadata")

        return coreapi.CoreRegMessage.pack(MessageFlags.ADD.value, tlv_data)

    def sendall(self, data):
        """
        Send raw data to the other end of this TCP connection
        using socket"s sendall().

        :param data: data to send over request socket
        :return: data sent
        """
        return self.request.sendall(data)

    def receive_message(self):
        """
        Receive data and return a CORE API message object.

        :return: received message
        :rtype: core.api.tlv.coreapi.CoreMessage
        """
        try:
            header = self.request.recv(coreapi.CoreMessage.header_len)
        except IOError as e:
            raise IOError(f"error receiving header ({e})")

        if len(header) != coreapi.CoreMessage.header_len:
            if len(header) == 0:
                raise EOFError("client disconnected")
            else:
                raise IOError("invalid message header size")

        message_type, message_flags, message_len = coreapi.CoreMessage.unpack_header(
            header
        )
        if message_len == 0:
            logger.warning("received message with no data")

        data = b""
        while len(data) < message_len:
            data += self.request.recv(message_len - len(data))
            if len(data) > message_len:
                error_message = f"received message length does not match received data ({len(data)} != {message_len})"
                logger.error(error_message)
                raise IOError(error_message)

        try:
            message_class = coreapi.CLASS_MAP[message_type]
            message = message_class(message_flags, header, data)
        except KeyError:
            message = coreapi.CoreMessage(message_flags, header, data)
            message.message_type = message_type
            logger.exception("unimplemented core message type: %s", message.type_str())

        return message

    def queue_message(self, message):
        """
        Queue an API message for later processing.

        :param message: message to queue
        :return: nothing
        """
        logger.debug(
            "queueing msg (queuedtimes = %s): type %s",
            message.queuedtimes,
            MessageTypes(message.message_type),
        )
        self.message_queue.put(message)

    def handler_thread(self):
        """
        CORE API message handling loop that is spawned for each server
        thread; get CORE API messages from the incoming message queue,
        and call handlemsg() for processing.

        :return: nothing
        """
        while not self.done:
            try:
                message = self.message_queue.get(timeout=1)
                self.handle_message(message)
            except Empty:
                pass

    def handle_message(self, message):
        """
        Handle an incoming message; dispatch based on message type,
        optionally sending replies.

        :param message: message to handle
        :return: nothing
        """
        logger.debug(
            "%s handling message:\n%s", threading.currentThread().getName(), message
        )
        if message.message_type not in self.message_handlers:
            logger.error("no handler for message type: %s", message.type_str())
            return

        message_handler = self.message_handlers[message.message_type]
        try:
            # TODO: this needs to be removed, make use of the broadcast message methods
            replies = message_handler(message)
            self.dispatch_replies(replies, message)
        except Exception as e:
            self.send_exception(ExceptionLevels.ERROR, "corehandler", str(e))
            logger.exception(
                "%s: exception while handling message: %s",
                threading.currentThread().getName(),
                message,
            )

    def dispatch_replies(self, replies, message):
        """
        Dispatch replies by CORE to message msg previously received from the client.

        :param list replies: reply messages to dispatch
        :param message: message for replies
        :return: nothing
        """
        for reply in replies:
            message_type, message_flags, message_length = coreapi.CoreMessage.unpack_header(
                reply
            )
            try:
                reply_message = coreapi.CLASS_MAP[message_type](
                    message_flags,
                    reply[: coreapi.CoreMessage.header_len],
                    reply[coreapi.CoreMessage.header_len :],
                )
            except KeyError:
                # multiple TLVs of same type cause KeyError exception
                reply_message = f"CoreMessage (type {message_type} flags {message_flags} length {message_length})"

            logger.debug("sending reply:\n%s", reply_message)

            try:
                self.sendall(reply)
            except IOError:
                logger.exception("error dispatching reply")

    def handle(self):
        """
        Handle a new connection request from a client. Dispatch to the
        recvmsg() method for receiving data into CORE API messages, and
        add them to an incoming message queue.

        :return: nothing
        """
        # use port as session id
        port = self.request.getpeername()[1]

        # TODO: add shutdown handler for session
        self.session = self.coreemu.create_session(port)
        logger.debug("created new session for client: %s", self.session.id)
        clients = self.session_clients.setdefault(self.session.id, [])
        clients.append(self)

        # add handlers for various data
        self.add_session_handlers()

        # set initial session state
        self.session.set_state(EventTypes.DEFINITION_STATE)

        while True:
            try:
                message = self.receive_message()
            except EOFError:
                logger.info("client disconnected")
                break
            except IOError:
                logger.exception("error receiving message")
                break

            message.queuedtimes = 0
            self.queue_message(message)

            # delay is required for brief connections, allow session joining
            if message.message_type == MessageTypes.SESSION.value:
                time.sleep(0.125)

            # broadcast node/link messages to other connected clients
            if message.message_type not in [
                MessageTypes.NODE.value,
                MessageTypes.LINK.value,
            ]:
                continue

            clients = self.session_clients[self.session.id]
            for client in clients:
                if client == self:
                    continue

                logger.debug("BROADCAST TO OTHER CLIENT: %s", client)
                client.sendall(message.raw_message)

    def send_exception(self, level, source, text, node=None):
        """
        Sends an exception for display within the GUI.

        :param core.emulator.enumerations.ExceptionLevel level: level for exception
        :param str source: source where exception came from
        :param str text: details about exception
        :param int node: node id, if related to a specific node
        :return: nothing
        """
        exception_data = ExceptionData(
            session=self.session.id,
            node=node,
            date=time.ctime(),
            level=level,
            source=source,
            text=text,
        )
        self.handle_broadcast_exception(exception_data)

    def add_session_handlers(self):
        logger.debug("adding session broadcast handlers")
        self.session.event_handlers.append(self.handle_broadcast_event)
        self.session.exception_handlers.append(self.handle_broadcast_exception)
        self.session.node_handlers.append(self.handle_broadcast_node)
        self.session.link_handlers.append(self.handle_broadcast_link)
        self.session.file_handlers.append(self.handle_broadcast_file)
        self.session.config_handlers.append(self.handle_broadcast_config)

    def remove_session_handlers(self):
        logger.debug("removing session broadcast handlers")
        self.session.event_handlers.remove(self.handle_broadcast_event)
        self.session.exception_handlers.remove(self.handle_broadcast_exception)
        self.session.node_handlers.remove(self.handle_broadcast_node)
        self.session.link_handlers.remove(self.handle_broadcast_link)
        self.session.file_handlers.remove(self.handle_broadcast_file)
        self.session.config_handlers.remove(self.handle_broadcast_config)

    def handle_node_message(self, message):
        """
        Node Message handler

        :param core.api.tlv.coreapi.CoreNodeMessage message: node message
        :return: replies to node message
        """
        replies = []
        if (
            message.flags & MessageFlags.ADD.value
            and message.flags & MessageFlags.DELETE.value
        ):
            logger.warning("ignoring invalid message: add and delete flag both set")
            return ()

        _class = CoreNode
        node_type_value = message.get_tlv(NodeTlvs.TYPE.value)
        if node_type_value is not None:
            node_type = NodeTypes(node_type_value)
            _class = self.session.get_node_class(node_type)

        node_id = message.get_tlv(NodeTlvs.NUMBER.value)

        options = NodeOptions(
            name=message.get_tlv(NodeTlvs.NAME.value),
            model=message.get_tlv(NodeTlvs.MODEL.value),
            legacy=True,
        )
        options.set_position(
            x=message.get_tlv(NodeTlvs.X_POSITION.value),
            y=message.get_tlv(NodeTlvs.Y_POSITION.value),
        )

        lat = message.get_tlv(NodeTlvs.LATITUDE.value)
        if lat is not None:
            lat = float(lat)
        lon = message.get_tlv(NodeTlvs.LONGITUDE.value)
        if lon is not None:
            lon = float(lon)
        alt = message.get_tlv(NodeTlvs.ALTITUDE.value)
        if alt is not None:
            alt = float(alt)
        options.set_location(lat=lat, lon=lon, alt=alt)

        options.icon = message.get_tlv(NodeTlvs.ICON.value)
        options.canvas = message.get_tlv(NodeTlvs.CANVAS.value)
        options.server = message.get_tlv(NodeTlvs.EMULATION_SERVER.value)

        services = message.get_tlv(NodeTlvs.SERVICES.value)
        if services:
            options.services = services.split("|")

        if message.flags & MessageFlags.ADD.value:
            node = self.session.add_node(_class, node_id, options)
            has_geo = all(
                i is not None for i in [options.lon, options.lat, options.alt]
            )
            if has_geo:
                self.session.broadcast_node(node)
            if message.flags & MessageFlags.STRING.value:
                self.node_status_request[node.id] = True
            if self.session.state == EventTypes.RUNTIME_STATE:
                self.send_node_emulation_id(node.id)
        elif message.flags & MessageFlags.DELETE.value:
            with self._shutdown_lock:
                result = self.session.delete_node(node_id)
                if result and self.session.get_node_count() == 0:
                    self.session.set_state(EventTypes.SHUTDOWN_STATE)
                    self.session.delete_nodes()
                    self.session.distributed.shutdown()
                    self.session.sdt.shutdown()

                # if we deleted a node broadcast out its removal
                if result and message.flags & MessageFlags.STRING.value:
                    tlvdata = b""
                    tlvdata += coreapi.CoreNodeTlv.pack(NodeTlvs.NUMBER.value, node_id)
                    flags = MessageFlags.DELETE.value | MessageFlags.LOCAL.value
                    replies.append(coreapi.CoreNodeMessage.pack(flags, tlvdata))
        # node update
        else:
            node = self.session.get_node(node_id, NodeBase)
            node.icon = options.icon
            has_geo = all(
                i is not None for i in [options.lon, options.lat, options.alt]
            )
            if has_geo:
                self.session.set_node_geo(node, options.lon, options.lat, options.alt)
                self.session.broadcast_node(node)
            else:
                self.session.set_node_pos(node, options.x, options.y)

        return replies

    def handle_link_message(self, message):
        """
        Link Message handler

        :param core.api.tlv.coreapi.CoreLinkMessage message: link message to handle
        :return: link message replies
        """
        node1_id = message.get_tlv(LinkTlvs.N1_NUMBER.value)
        node2_id = message.get_tlv(LinkTlvs.N2_NUMBER.value)
        iface1_data = InterfaceData(
            id=message.get_tlv(LinkTlvs.IFACE1_NUMBER.value),
            name=message.get_tlv(LinkTlvs.IFACE1_NAME.value),
            mac=message.get_tlv(LinkTlvs.IFACE1_MAC.value),
            ip4=message.get_tlv(LinkTlvs.IFACE1_IP4.value),
            ip4_mask=message.get_tlv(LinkTlvs.IFACE1_IP4_MASK.value),
            ip6=message.get_tlv(LinkTlvs.IFACE1_IP6.value),
            ip6_mask=message.get_tlv(LinkTlvs.IFACE1_IP6_MASK.value),
        )
        iface2_data = InterfaceData(
            id=message.get_tlv(LinkTlvs.IFACE2_NUMBER.value),
            name=message.get_tlv(LinkTlvs.IFACE2_NAME.value),
            mac=message.get_tlv(LinkTlvs.IFACE2_MAC.value),
            ip4=message.get_tlv(LinkTlvs.IFACE2_IP4.value),
            ip4_mask=message.get_tlv(LinkTlvs.IFACE2_IP4_MASK.value),
            ip6=message.get_tlv(LinkTlvs.IFACE2_IP6.value),
            ip6_mask=message.get_tlv(LinkTlvs.IFACE2_IP6_MASK.value),
        )
        link_type = LinkTypes.WIRED
        link_type_value = message.get_tlv(LinkTlvs.TYPE.value)
        if link_type_value is not None:
            link_type = LinkTypes(link_type_value)
        options = LinkOptions()
        options.delay = message.get_tlv(LinkTlvs.DELAY.value)
        options.bandwidth = message.get_tlv(LinkTlvs.BANDWIDTH.value)
        options.jitter = message.get_tlv(LinkTlvs.JITTER.value)
        options.mer = message.get_tlv(LinkTlvs.MER.value)
        options.burst = message.get_tlv(LinkTlvs.BURST.value)
        options.mburst = message.get_tlv(LinkTlvs.MBURST.value)
        options.unidirectional = message.get_tlv(LinkTlvs.UNIDIRECTIONAL.value)
        options.key = message.get_tlv(LinkTlvs.KEY.value)
        loss = message.get_tlv(LinkTlvs.LOSS.value)
        dup = message.get_tlv(LinkTlvs.DUP.value)
        if loss is not None:
            options.loss = float(loss)
        if dup is not None:
            options.dup = int(dup)

        # fix for rj45 nodes missing iface id
        node1 = self.session.get_node(node1_id, NodeBase)
        node2 = self.session.get_node(node2_id, NodeBase)
        if isinstance(node1, Rj45Node) and iface1_data.id is None:
            iface1_data.id = 0
        if isinstance(node2, Rj45Node) and iface2_data.id is None:
            iface2_data.id = 0

        if message.flags & MessageFlags.ADD.value:
            self.session.add_link(
                node1_id, node2_id, iface1_data, iface2_data, options, link_type
            )
        elif message.flags & MessageFlags.DELETE.value:
            if isinstance(node1, Rj45Node):
                iface1_data.id = node1.iface_id
            if isinstance(node2, Rj45Node):
                iface2_data.id = node2.iface_id
            self.session.delete_link(
                node1_id, node2_id, iface1_data.id, iface2_data.id, link_type
            )
        else:
            self.session.update_link(
                node1_id, node2_id, iface1_data.id, iface2_data.id, options, link_type
            )
        return ()

    def handle_execute_message(self, message):
        """
        Execute Message handler

        :param core.api.tlv.coreapi.CoreExecMessage message: execute message to handle
        :return: reply messages
        """
        node_id = message.get_tlv(ExecuteTlvs.NODE.value)
        execute_num = message.get_tlv(ExecuteTlvs.NUMBER.value)
        execute_time = message.get_tlv(ExecuteTlvs.TIME.value)
        command = message.get_tlv(ExecuteTlvs.COMMAND.value)

        # local flag indicates command executed locally, not on a node
        if node_id is None and not message.flags & MessageFlags.LOCAL.value:
            raise ValueError("Execute Message is missing node number.")

        if execute_num is None:
            raise ValueError("Execute Message is missing execution number.")

        if execute_time is not None:
            self.session.add_event(
                float(execute_time), node_id=node_id, name=None, data=command
            )
            return ()

        try:
            node = self.session.get_node(node_id, CoreNodeBase)

            # build common TLV items for reply
            tlv_data = b""
            if node_id is not None:
                tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node_id)
            tlv_data += coreapi.CoreExecuteTlv.pack(
                ExecuteTlvs.NUMBER.value, execute_num
            )
            tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, command)

            if message.flags & MessageFlags.TTY.value:
                if node_id is None:
                    raise NotImplementedError
                # echo back exec message with cmd for spawning interactive terminal
                if command == "bash":
                    command = "/bin/bash"
                res = node.termcmdstring(command)
                tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.RESULT.value, res)
                reply = coreapi.CoreExecMessage.pack(MessageFlags.TTY.value, tlv_data)
                return (reply,)
            else:
                # execute command and send a response
                if (
                    message.flags & MessageFlags.STRING.value
                    or message.flags & MessageFlags.TEXT.value
                ):
                    if message.flags & MessageFlags.LOCAL.value:
                        try:
                            res = utils.cmd(command)
                            status = 0
                        except CoreCommandError as e:
                            res = e.stderr
                            status = e.returncode
                    else:
                        try:
                            res = node.cmd(command)
                            status = 0
                        except CoreCommandError as e:
                            res = e.stderr
                            status = e.returncode
                    if message.flags & MessageFlags.TEXT.value:
                        tlv_data += coreapi.CoreExecuteTlv.pack(
                            ExecuteTlvs.RESULT.value, res
                        )
                    if message.flags & MessageFlags.STRING.value:
                        tlv_data += coreapi.CoreExecuteTlv.pack(
                            ExecuteTlvs.STATUS.value, status
                        )
                    reply = coreapi.CoreExecMessage.pack(0, tlv_data)
                    return (reply,)
                # execute the command with no response
                else:
                    if message.flags & MessageFlags.LOCAL.value:
                        utils.mute_detach(command)
                    else:
                        node.cmd(command, wait=False)
        except CoreError:
            logger.exception("error getting object: %s", node_id)
            # XXX wait and queue this message to try again later
            # XXX maybe this should be done differently
            if not message.flags & MessageFlags.LOCAL.value:
                time.sleep(0.125)
                self.queue_message(message)

        return ()

    def handle_register_message(self, message):
        """
        Register Message Handler

        :param core.api.tlv.coreapi.CoreRegMessage message: register message to handle
        :return: reply messages
        """
        replies = []

        # execute a Python script or XML file
        execute_server = message.get_tlv(RegisterTlvs.EXECUTE_SERVER.value)
        if execute_server:
            try:
                logger.info("executing: %s", execute_server)
                old_session_ids = set()
                if message.flags & MessageFlags.STRING.value:
                    old_session_ids = set(self.coreemu.sessions.keys())
                sys.argv = shlex.split(execute_server)
                file_path = Path(sys.argv[0])
                if file_path.suffix == ".xml":
                    session = self.coreemu.create_session()
                    try:
                        session.open_xml(file_path)
                    except Exception:
                        self.coreemu.delete_session(session.id)
                        raise
                else:
                    utils.execute_script(self.coreemu, file_path, execute_server)

                if message.flags & MessageFlags.STRING.value:
                    new_session_ids = set(self.coreemu.sessions.keys())
                    new_sid = new_session_ids.difference(old_session_ids)
                    try:
                        sid = new_sid.pop()
                        logger.info("executed: %s as session %d", execute_server, sid)
                    except KeyError:
                        logger.info(
                            "executed %s with unknown session ID", execute_server
                        )
                        return replies

                    logger.debug("checking session %d for RUNTIME state", sid)
                    session = self.coreemu.sessions.get(sid)
                    retries = 10
                    # wait for session to enter RUNTIME state, to prevent GUI from
                    # connecting while nodes are still being instantiated
                    while session.state != EventTypes.RUNTIME_STATE:
                        logger.debug(
                            "waiting for session %d to enter RUNTIME state", sid
                        )
                        time.sleep(1)
                        retries -= 1
                        if retries <= 0:
                            logger.debug("session %d did not enter RUNTIME state", sid)
                            return replies

                    tlv_data = coreapi.CoreRegisterTlv.pack(
                        RegisterTlvs.EXECUTE_SERVER.value, execute_server
                    )
                    tlv_data += coreapi.CoreRegisterTlv.pack(
                        RegisterTlvs.SESSION.value, str(sid)
                    )
                    message = coreapi.CoreRegMessage.pack(0, tlv_data)
                    replies.append(message)
            except Exception as e:
                logger.exception("error executing: %s", execute_server)
                tlv_data = coreapi.CoreExceptionTlv.pack(ExceptionTlvs.LEVEL.value, 2)
                tlv_data += coreapi.CoreExceptionTlv.pack(
                    ExceptionTlvs.TEXT.value, str(e)
                )
                message = coreapi.CoreExceptionMessage.pack(0, tlv_data)
                replies.append(message)

            return replies

        gui = message.get_tlv(RegisterTlvs.GUI.value)
        if gui is None:
            logger.debug("ignoring Register message")
        else:
            # register capabilities with the GUI
            replies.append(self.register())
            replies.append(self.session_message())

        return replies

    def handle_config_message(self, message):
        """
        Configuration Message handler

        :param core.api.tlv.coreapi.CoreConfMessage message: configuration message to handle
        :return: reply messages
        """
        # convert config message to standard config data object
        config_data = ConfigData(
            node=message.get_tlv(ConfigTlvs.NODE.value),
            object=message.get_tlv(ConfigTlvs.OBJECT.value),
            type=message.get_tlv(ConfigTlvs.TYPE.value),
            data_types=message.get_tlv(ConfigTlvs.DATA_TYPES.value),
            data_values=message.get_tlv(ConfigTlvs.VALUES.value),
            captions=message.get_tlv(ConfigTlvs.CAPTIONS.value),
            bitmap=message.get_tlv(ConfigTlvs.BITMAP.value),
            possible_values=message.get_tlv(ConfigTlvs.POSSIBLE_VALUES.value),
            groups=message.get_tlv(ConfigTlvs.GROUPS.value),
            session=message.get_tlv(ConfigTlvs.SESSION.value),
            iface_id=message.get_tlv(ConfigTlvs.IFACE_ID.value),
            network_id=message.get_tlv(ConfigTlvs.NETWORK_ID.value),
            opaque=message.get_tlv(ConfigTlvs.OPAQUE.value),
        )
        logger.debug(
            "configuration message for %s node %s", config_data.object, config_data.node
        )
        message_type = ConfigFlags(config_data.type)

        replies = []

        # handle session configuration
        if config_data.object == "all":
            replies = self.handle_config_all(message_type, config_data)
        elif config_data.object == self.session.options.name:
            replies = self.handle_config_session(message_type, config_data)
        elif config_data.object == self.session.location.name:
            self.handle_config_location(message_type, config_data)
        elif config_data.object == "metadata":
            replies = self.handle_config_metadata(message_type, config_data)
        elif config_data.object == "broker":
            self.handle_config_broker(message_type, config_data)
        elif config_data.object == self.session.services.name:
            replies = self.handle_config_services(message_type, config_data)
        elif config_data.object == self.session.mobility.name:
            self.handle_config_mobility(message_type, config_data)
        elif config_data.object in self.session.mobility.models:
            replies = self.handle_config_mobility_models(message_type, config_data)
        elif config_data.object in EmaneModelManager.models:
            replies = self.handle_config_emane_models(message_type, config_data)
        else:
            raise Exception("no handler for configuration: %s", config_data.object)

        for reply in replies:
            self.handle_broadcast_config(reply)

        return []

    def handle_config_all(self, message_type, config_data):
        replies = []

        if message_type == ConfigFlags.RESET:
            node_id = config_data.node
            if node_id is not None:
                self.session.mobility.config_reset(node_id)
                self.session.emane.config_reset(node_id)
            else:
                self.session.location.reset()
                self.session.services.reset()
                self.session.mobility.config_reset()
                self.session.emane.config_reset()
        else:
            raise Exception(f"cant handle config all: {message_type}")

        return replies

    def handle_config_session(self, message_type, config_data):
        replies = []
        if message_type == ConfigFlags.REQUEST:
            type_flags = ConfigFlags.NONE.value
            config = self.session.options.get_configs()
            config_response = ConfigShim.config_data(
                0, None, type_flags, self.session.options, config
            )
            replies.append(config_response)
        elif message_type != ConfigFlags.RESET and config_data.data_values:
            values = ConfigShim.str_to_dict(config_data.data_values)
            for key in values:
                value = values[key]
                self.session.options.set_config(key, value)
        return replies

    def handle_config_location(self, message_type, config_data):
        if message_type == ConfigFlags.RESET:
            self.session.location.reset()
        else:
            if not config_data.data_values:
                logger.warning("location data missing")
            else:
                values = [float(x) for x in config_data.data_values.split("|")]

                # Cartesian coordinate reference point
                refx, refy = values[0], values[1]
                refz = 0.0
                lat, lon, alt = values[2], values[3], values[4]
                # xyz point
                self.session.location.refxyz = (refx, refy, refz)
                # geographic reference point
                self.session.location.setrefgeo(lat, lon, alt)
                self.session.location.refscale = values[5]
                logger.info(
                    "location configured: %s = %s scale=%s",
                    self.session.location.refxyz,
                    self.session.location.refgeo,
                    self.session.location.refscale,
                )

    def handle_config_metadata(self, message_type, config_data):
        replies = []
        if message_type == ConfigFlags.REQUEST:
            node_id = config_data.node
            metadata_configs = self.session.metadata
            if metadata_configs is None:
                metadata_configs = {}
            data_values = "|".join(
                [f"{x}={metadata_configs[x]}" for x in metadata_configs]
            )
            data_types = tuple(ConfigDataTypes.STRING.value for _ in metadata_configs)
            config_response = ConfigData(
                message_type=0,
                node=node_id,
                object="metadata",
                type=ConfigFlags.NONE.value,
                data_types=data_types,
                data_values=data_values,
            )
            replies.append(config_response)
        elif message_type != ConfigFlags.RESET and config_data.data_values:
            values = ConfigShim.str_to_dict(config_data.data_values)
            for key in values:
                value = values[key]
                self.session.metadata[key] = value
        return replies

    def handle_config_broker(self, message_type, config_data):
        if message_type not in [ConfigFlags.REQUEST, ConfigFlags.RESET]:
            if not config_data.data_values:
                logger.info("emulation server data missing")
            else:
                values = config_data.data_values.split("|")

                # string of "server:ip:port,server:ip:port,..."
                server_strings = values[0]
                server_list = server_strings.split(",")

                for server in server_list:
                    server_items = server.split(":")
                    name, host, _ = server_items[:3]
                    self.session.distributed.add_server(name, host)
        elif message_type == ConfigFlags.RESET:
            self.session.distributed.shutdown()

    def handle_config_services(self, message_type, config_data):
        replies = []
        node_id = config_data.node
        opaque = config_data.opaque

        if message_type == ConfigFlags.REQUEST:
            session_id = config_data.session
            opaque = config_data.opaque

            logger.debug(
                "configuration request: node(%s) session(%s) opaque(%s)",
                node_id,
                session_id,
                opaque,
            )

            # send back a list of available services
            if opaque is None:
                type_flag = ConfigFlags.NONE.value
                data_types = tuple(
                    repeat(ConfigDataTypes.BOOL.value, len(ServiceManager.services))
                )

                # sort groups by name and map services to groups
                groups = set()
                group_map = {}
                for name in ServiceManager.services:
                    service_name = ServiceManager.services[name]
                    group = service_name.group
                    groups.add(group)
                    group_map.setdefault(group, []).append(service_name)
                groups = sorted(groups, key=lambda x: x.lower())

                # define tlv values in proper order
                captions = []
                possible_values = []
                values = []
                group_strings = []
                start_index = 1
                logger.debug("sorted groups: %s", groups)
                for group in groups:
                    services = sorted(group_map[group], key=lambda x: x.name.lower())
                    logger.debug("sorted services for group(%s): %s", group, services)
                    end_index = start_index + len(services) - 1
                    group_strings.append(f"{group}:{start_index}-{end_index}")
                    start_index += len(services)
                    for service_name in services:
                        captions.append(service_name.name)
                        values.append("0")
                        if service_name.custom_needed:
                            possible_values.append("1")
                        else:
                            possible_values.append("")

                # format for tlv
                captions = "|".join(captions)
                possible_values = "|".join(possible_values)
                values = "|".join(values)
                groups = "|".join(group_strings)
            # send back the properties for this service
            else:
                if not node_id:
                    return replies

                node = self.session.get_node(node_id, CoreNodeBase)
                if node is None:
                    logger.warning(
                        "request to configure service for unknown node %s", node_id
                    )
                    return replies

                services = ServiceShim.servicesfromopaque(opaque)
                if not services:
                    return replies

                servicesstring = opaque.split(":")
                if len(servicesstring) == 3:
                    # a file request: e.g. "service:zebra:quagga.conf"
                    file_name = servicesstring[2]
                    service_name = services[0]
                    file_data = self.session.services.get_service_file(
                        node, service_name, file_name
                    )
                    self.session.broadcast_file(file_data)
                    # short circuit this request early to avoid returning response below
                    return replies

                # the first service in the list is the one being configured
                service_name = services[0]
                # send back:
                # dirs, configs, startindex, startup, shutdown, metadata, config
                type_flag = ConfigFlags.UPDATE.value
                data_types = tuple(
                    repeat(ConfigDataTypes.STRING.value, len(ServiceShim.keys))
                )
                service = self.session.services.get_service(
                    node_id, service_name, default_service=True
                )
                values = ServiceShim.tovaluelist(node, service)
                captions = None
                possible_values = None
                groups = None

            config_response = ConfigData(
                message_type=0,
                node=node_id,
                object=self.session.services.name,
                type=type_flag,
                data_types=data_types,
                data_values=values,
                captions=captions,
                possible_values=possible_values,
                groups=groups,
                session=session_id,
                opaque=opaque,
            )
            replies.append(config_response)
        elif message_type == ConfigFlags.RESET:
            self.session.services.reset()
        else:
            data_types = config_data.data_types
            values = config_data.data_values

            error_message = "services config message that I don't know how to handle"
            if values is None:
                logger.error(error_message)
            else:
                if opaque is None:
                    values = values.split("|")
                    # store default services for a node type in self.defaultservices[]
                    if (
                        data_types is None
                        or data_types[0] != ConfigDataTypes.STRING.value
                    ):
                        logger.info(error_message)
                        return None
                    key = values.pop(0)
                    self.session.services.default_services[key] = values
                    logger.debug("default services for type %s set to %s", key, values)
                elif node_id:
                    services = ServiceShim.servicesfromopaque(opaque)
                    if services:
                        service_name = services[0]

                        # set custom service for node
                        self.session.services.set_service(node_id, service_name)

                        # set custom values for custom service
                        service = self.session.services.get_service(
                            node_id, service_name
                        )
                        if not service:
                            raise ValueError(
                                "custom service(%s) for node(%s) does not exist",
                                service_name,
                                node_id,
                            )

                        values = ConfigShim.str_to_dict(values)
                        for name in values:
                            value = values[name]
                            ServiceShim.setvalue(service, name, value)

        return replies

    def handle_config_mobility(self, message_type, _):
        if message_type == ConfigFlags.RESET:
            self.session.mobility.reset()

    def handle_config_mobility_models(self, message_type, config_data):
        replies = []
        node_id = config_data.node
        object_name = config_data.object
        iface_id = config_data.iface_id
        values_str = config_data.data_values

        node_id = utils.iface_config_id(node_id, iface_id)
        logger.debug(
            "received configure message for %s nodenum: %s", object_name, node_id
        )
        if message_type == ConfigFlags.REQUEST:
            logger.info("replying to configure request for model: %s", object_name)
            typeflags = ConfigFlags.NONE.value

            model_class = self.session.mobility.models.get(object_name)
            if not model_class:
                logger.warning("model class does not exist: %s", object_name)
                return []

            config = self.session.mobility.get_model_config(node_id, object_name)
            config_response = ConfigShim.config_data(
                0, node_id, typeflags, model_class, config
            )
            replies.append(config_response)
        elif message_type != ConfigFlags.RESET:
            # store the configuration values for later use, when the node
            if not object_name:
                logger.warning("no configuration object for node: %s", node_id)
                return []

            parsed_config = {}
            if values_str:
                parsed_config = ConfigShim.str_to_dict(values_str)

            self.session.mobility.set_model_config(node_id, object_name, parsed_config)
            if self.session.state == EventTypes.RUNTIME_STATE and parsed_config:
                try:
                    node = self.session.get_node(node_id, WlanNode)
                    if object_name == BasicRangeModel.name:
                        node.updatemodel(parsed_config)
                except CoreError:
                    logger.error(
                        "skipping mobility configuration for unknown node: %s", node_id
                    )

        return replies

    def handle_config_emane_models(self, message_type, config_data):
        replies = []
        node_id = config_data.node
        object_name = config_data.object
        iface_id = config_data.iface_id
        values_str = config_data.data_values

        node_id = utils.iface_config_id(node_id, iface_id)
        logger.debug(
            "received configure message for %s nodenum: %s", object_name, node_id
        )
        if message_type == ConfigFlags.REQUEST:
            logger.info("replying to configure request for model: %s", object_name)
            typeflags = ConfigFlags.NONE.value

            model_class = self.session.emane.get_model(object_name)
            if not model_class:
                logger.warning("model class does not exist: %s", object_name)
                return []

            config = self.session.emane.get_config(node_id, object_name)
            config_response = ConfigShim.config_data(
                0, node_id, typeflags, model_class, config
            )
            replies.append(config_response)
        elif message_type != ConfigFlags.RESET:
            # store the configuration values for later use, when the node
            if not object_name:
                logger.warning("no configuration object for node: %s", node_id)
                return []
            parsed_config = {}
            if values_str:
                parsed_config = ConfigShim.str_to_dict(values_str)
            self.session.emane.node_models[node_id] = object_name
            self.session.emane.set_config(node_id, object_name, parsed_config)

        return replies

    def handle_file_message(self, message):
        """
        File Message handler

        :param core.api.tlv.coreapi.CoreFileMessage message: file message to handle
        :return: reply messages
        """
        if message.flags & MessageFlags.ADD.value:
            node_id = message.get_tlv(FileTlvs.NODE.value)
            file_name = message.get_tlv(FileTlvs.NAME.value)
            file_type = message.get_tlv(FileTlvs.TYPE.value)
            src_path = message.get_tlv(FileTlvs.SOURCE_NAME.value)
            if src_path:
                src_path = Path(src_path)
            data = message.get_tlv(FileTlvs.DATA.value)
            compressed_data = message.get_tlv(FileTlvs.COMPRESSED_DATA.value)

            if compressed_data:
                logger.warning("Compressed file data not implemented for File message.")
                return ()

            if src_path and data:
                logger.warning(
                    "ignoring invalid File message: source and data TLVs are both present"
                )
                return ()

            # some File Messages store custom files in services,
            # prior to node creation
            if file_type is not None:
                if file_type.startswith("service:"):
                    _, service_name = file_type.split(":")[:2]
                    self.session.services.set_service_file(
                        node_id, service_name, file_name, data
                    )
                    return ()
                elif file_type.startswith("hook:"):
                    _, state = file_type.split(":")[:2]
                    if not state.isdigit():
                        logger.error("error setting hook having state '%s'", state)
                        return ()
                    state = int(state)
                    state = EventTypes(state)
                    self.session.add_hook(state, file_name, data, src_path)
                    return ()

            # writing a file to the host
            if node_id is None:
                if src_path is not None:
                    shutil.copy2(src_path, file_name)
                else:
                    with file_name.open("w") as f:
                        f.write(data)
                return ()

            file_path = Path(file_name)
            self.session.add_node_file(node_id, src_path, file_path, data)
        else:
            raise NotImplementedError

        return ()

    def handle_iface_message(self, message):
        """
        Interface Message handler.

        :param message: interface message to handle
        :return: reply messages
        """
        logger.info("ignoring Interface message")
        return ()

    def handle_event_message(self, message):
        """
        Event Message handler

        :param core.api.tlv.coreapi.CoreEventMessage message: event message to handle
        :return: reply messages
        :raises core.CoreError: when event type <= SHUTDOWN_STATE and not a known node id
        """
        event_type_value = message.get_tlv(EventTlvs.TYPE.value)
        event_type = EventTypes(event_type_value)
        event_data = EventData(
            node=message.get_tlv(EventTlvs.NODE.value),
            event_type=event_type,
            name=message.get_tlv(EventTlvs.NAME.value),
            data=message.get_tlv(EventTlvs.DATA.value),
            time=message.get_tlv(EventTlvs.TIME.value),
            session=message.get_tlv(EventTlvs.SESSION.value),
        )

        if event_data.event_type is None:
            raise NotImplementedError("Event message missing event type")
        node_id = event_data.node

        logger.debug("handling event %s at %s", event_type.name, time.ctime())
        if event_type.value <= EventTypes.SHUTDOWN_STATE.value:
            if node_id is not None:
                node = self.session.get_node(node_id, NodeBase)

                # configure mobility models for WLAN added during runtime
                if event_type == EventTypes.INSTANTIATION_STATE and isinstance(
                    node, WlanNode
                ):
                    self.session.start_mobility(node_ids=[node.id])
                    return ()

                logger.warning(
                    "dropping unhandled event message for node: %s", node.name
                )
                return ()

        if event_type == EventTypes.DEFINITION_STATE:
            self.session.set_state(event_type)
            # clear all session objects in order to receive new definitions
            self.session.clear()
        elif event_type == EventTypes.CONFIGURATION_STATE:
            self.session.set_state(event_type)
        elif event_type == EventTypes.INSTANTIATION_STATE:
            self.session.set_state(event_type)
            if len(self.handler_threads) > 1:
                # TODO: sync handler threads here before continuing
                time.sleep(2.0)  # XXX
            # done receiving node/link configuration, ready to instantiate
            self.session.instantiate()

            # after booting nodes attempt to send emulation id for nodes
            # waiting on status
            for _id in self.session.nodes:
                self.send_node_emulation_id(_id)
        elif event_type == EventTypes.RUNTIME_STATE:
            self.session.set_state(event_type)
            logger.warning("Unexpected event message: RUNTIME state received")
        elif event_type == EventTypes.DATACOLLECT_STATE:
            self.session.data_collect()
        elif event_type == EventTypes.SHUTDOWN_STATE:
            self.session.set_state(event_type)
            logger.warning("Unexpected event message: SHUTDOWN state received")
        elif event_type in {
            EventTypes.START,
            EventTypes.STOP,
            EventTypes.RESTART,
            EventTypes.PAUSE,
            EventTypes.RECONFIGURE,
        }:
            handled = False
            name = event_data.name
            if name:
                # TODO: register system for event message handlers,
                # like confobjs
                if name.startswith("service:"):
                    self.handle_service_event(event_data)
                    handled = True
                elif name.startswith("mobility:"):
                    self.session.mobility_event(event_data)
                    handled = True
            if not handled:
                logger.warning(
                    "unhandled event message: event type %s, name %s ",
                    event_type.name,
                    name,
                )
        elif event_type == EventTypes.FILE_OPEN:
            file_path = Path(event_data.name)
            self.session.open_xml(file_path, start=False)
            self.send_objects()
            return ()
        elif event_type == EventTypes.FILE_SAVE:
            file_path = Path(event_data.name)
            self.session.save_xml(file_path)
        elif event_type == EventTypes.SCHEDULED:
            etime = event_data.time
            node_id = event_data.node
            name = event_data.name
            data = event_data.data
            if etime is None:
                logger.warning("Event message scheduled event missing start time")
                return ()
            if message.flags & MessageFlags.ADD.value:
                self.session.add_event(
                    float(etime), node_id=node_id, name=name, data=data
                )
            else:
                raise NotImplementedError

        return ()

    def handle_service_event(self, event_data):
        """
        Handle an Event Message used to start, stop, restart, or validate
        a service on a given node.

        :param core.emulator.enumerations.EventData event_data: event data to handle
        :return: nothing
        """
        event_type = event_data.event_type
        node_id = event_data.node
        name = event_data.name

        try:
            node = self.session.get_node(node_id, CoreNodeBase)
        except CoreError:
            logger.warning(
                "ignoring event for service '%s', unknown node '%s'", name, node_id
            )
            return

        fail = ""
        unknown = []
        services = ServiceShim.servicesfromopaque(name)
        for service_name in services:
            service = self.session.services.get_service(
                node_id, service_name, default_service=True
            )
            if not service:
                unknown.append(service_name)
                continue

            if event_type in [EventTypes.STOP, EventTypes.RESTART]:
                status = self.session.services.stop_service(node, service)
                if status:
                    fail += f"Stop {service.name},"
            if event_type in [EventTypes.START, EventTypes.RESTART]:
                status = self.session.services.startup_service(node, service)
                if status:
                    fail += f"Start ({service.name}),"
            if event_type == EventTypes.PAUSE:
                status = self.session.services.validate_service(node, service)
                if status:
                    fail += f"{service.name},"
            if event_type == EventTypes.RECONFIGURE:
                self.session.services.service_reconfigure(node, service)

        fail_data = ""
        if len(fail) > 0:
            fail_data += f"Fail:{fail}"
        unknown_data = ""
        num = len(unknown)
        if num > 0:
            for u in unknown:
                unknown_data += u
                if num > 1:
                    unknown_data += ", "
                num -= 1
            logger.warning("Event requested for unknown service(s): %s", unknown_data)
            unknown_data = f"Unknown:{unknown_data}"

        event_data = EventData(
            node=node_id,
            event_type=event_type,
            name=name,
            data=fail_data + ";" + unknown_data,
            time=str(time.monotonic()),
        )

        self.session.broadcast_event(event_data)

    def handle_session_message(self, message):
        """
        Session Message handler

        :param core.api.tlv.coreapi.CoreSessionMessage message: session message to handle
        :return: reply messages
        """
        session_id_str = message.get_tlv(SessionTlvs.NUMBER.value)
        session_ids = coreapi.str_to_list(session_id_str)
        name_str = message.get_tlv(SessionTlvs.NAME.value)
        names = coreapi.str_to_list(name_str)
        file_str = message.get_tlv(SessionTlvs.FILE.value)
        files = coreapi.str_to_list(file_str)
        thumb = message.get_tlv(SessionTlvs.THUMB.value)
        user = message.get_tlv(SessionTlvs.USER.value)
        logger.debug(
            "SESSION message flags=0x%x sessions=%s", message.flags, session_id_str
        )

        if message.flags == 0:
            for index, session_id in enumerate(session_ids):
                session_id = int(session_id)
                if session_id == 0:
                    session = self.session
                else:
                    session = self.coreemu.sessions.get(session_id)
                if session is None:
                    logger.warning("session %s not found", session_id)
                    continue
                if names is not None:
                    session.name = names[index]
                if files is not None:
                    session.file_path = Path(files[index])
                if thumb:
                    thumb = Path(thumb)
                    session.set_thumbnail(thumb)
                if user:
                    session.set_user(user)
        elif (
            message.flags & MessageFlags.STRING.value
            and not message.flags & MessageFlags.ADD.value
        ):
            # status request flag: send list of sessions
            return (self.session_message(),)
        else:
            # handle ADD or DEL flags
            for session_id in session_ids:
                session_id = int(session_id)
                session = self.coreemu.sessions.get(session_id)

                if session is None:
                    logger.info(
                        "session %s not found (flags=0x%x)", session_id, message.flags
                    )
                    continue

                if message.flags & MessageFlags.ADD.value:
                    # connect to the first session that exists
                    logger.info("request to connect to session %s", session_id)

                    # remove client from session broker and shutdown if needed
                    self.remove_session_handlers()
                    clients = self.session_clients[self.session.id]
                    clients.remove(self)
                    if not clients and not self.session.is_active():
                        self.coreemu.delete_session(self.session.id)

                    # set session to join
                    self.session = session

                    # add client to session broker
                    clients = self.session_clients.setdefault(self.session.id, [])
                    clients.append(self)

                    # add broadcast handlers
                    logger.info("adding session broadcast handlers")
                    self.add_session_handlers()

                    if user:
                        self.session.set_user(user)

                    if message.flags & MessageFlags.STRING.value:
                        self.send_objects()
                elif message.flags & MessageFlags.DELETE.value:
                    # shut down the specified session(s)
                    logger.info("request to terminate session %s", session_id)
                    self.coreemu.delete_session(session_id)
                else:
                    logger.warning("unhandled session flags for session %s", session_id)

        return ()

    def send_node_emulation_id(self, node_id):
        """
        Node emulation id to send.

        :param int node_id: node id to send
        :return: nothing
        """
        if node_id in self.node_status_request:
            tlv_data = b""
            tlv_data += coreapi.CoreNodeTlv.pack(NodeTlvs.NUMBER.value, node_id)
            tlv_data += coreapi.CoreNodeTlv.pack(NodeTlvs.EMULATION_ID.value, node_id)
            reply = coreapi.CoreNodeMessage.pack(
                MessageFlags.ADD.value | MessageFlags.LOCAL.value, tlv_data
            )

            try:
                self.sendall(reply)
            except IOError:
                logger.exception("error sending node emulation id message: %s", node_id)

            del self.node_status_request[node_id]

    def send_objects(self):
        """
        Return API messages that describe the current session.
        """
        # find all nodes and links
        all_links = []
        with self.session.nodes_lock:
            for node_id in self.session.nodes:
                node = self.session.nodes[node_id]
                self.session.broadcast_node(node, MessageFlags.ADD)
                links = node.links(flags=MessageFlags.ADD)
                all_links.extend(links)

        for link in all_links:
            self.session.broadcast_link(link)

        # send mobility model info
        for node_id in self.session.mobility.nodes():
            mobility_configs = self.session.mobility.get_all_configs(node_id)
            for model_name in mobility_configs:
                config = mobility_configs[model_name]
                model_class = self.session.mobility.models[model_name]
                logger.debug(
                    "mobility config: node(%s) class(%s) values(%s)",
                    node_id,
                    model_class,
                    config,
                )
                config_data = ConfigShim.config_data(
                    0, node_id, ConfigFlags.UPDATE.value, model_class, config
                )
                self.session.broadcast_config(config_data)

        # send emane model configs
        for node_id, model_configs in self.session.emane.node_configs.items():
            for model_name, config in model_configs.items():
                model_class = self.session.emane.get_model(model_name)
                logger.debug(
                    "emane config: node(%s) class(%s) values(%s)",
                    node_id,
                    model_class,
                    config,
                )
                config_data = ConfigShim.config_data(
                    0, node_id, ConfigFlags.UPDATE.value, model_class, config
                )
                self.session.broadcast_config(config_data)

        # service customizations
        service_configs = self.session.services.all_configs()
        for node_id, service in service_configs:
            opaque = f"service:{service.name}"
            data_types = tuple(
                repeat(ConfigDataTypes.STRING.value, len(ServiceShim.keys))
            )
            node = self.session.get_node(node_id, CoreNodeBase)
            values = ServiceShim.tovaluelist(node, service)
            config_data = ConfigData(
                message_type=0,
                node=node_id,
                object=self.session.services.name,
                type=ConfigFlags.UPDATE.value,
                data_types=data_types,
                data_values=values,
                session=self.session.id,
                opaque=opaque,
            )
            self.session.broadcast_config(config_data)

            for file_name, config_data in self.session.services.all_files(service):
                file_data = FileData(
                    message_type=MessageFlags.ADD,
                    node=node_id,
                    name=str(file_name),
                    type=opaque,
                    data=str(config_data),
                )
                self.session.broadcast_file(file_data)

        # TODO: send location info

        # send hook scripts
        for state in sorted(self.session.hooks):
            for file_name, config_data in self.session.hooks[state]:
                file_data = FileData(
                    message_type=MessageFlags.ADD,
                    name=str(file_name),
                    type=f"hook:{state.value}",
                    data=str(config_data),
                )
                self.session.broadcast_file(file_data)

        # send session configuration
        session_config = self.session.options.get_configs()
        config_data = ConfigShim.config_data(
            0, None, ConfigFlags.UPDATE.value, self.session.options, session_config
        )
        self.session.broadcast_config(config_data)

        # send session metadata
        metadata_configs = self.session.metadata
        if metadata_configs:
            data_values = "|".join(
                [f"{x}={metadata_configs[x]}" for x in metadata_configs]
            )
            data_types = tuple(
                ConfigDataTypes.STRING.value for _ in self.session.metadata
            )
            config_data = ConfigData(
                message_type=0,
                object="metadata",
                type=ConfigFlags.NONE.value,
                data_types=data_types,
                data_values=data_values,
            )
            self.session.broadcast_config(config_data)

        node_count = self.session.get_node_count()
        logger.info(
            "informed GUI about %d nodes and %d links", node_count, len(all_links)
        )


class CoreUdpHandler(CoreHandler):
    def __init__(self, request, client_address, server):
        self.message_handlers = {
            MessageTypes.NODE.value: self.handle_node_message,
            MessageTypes.LINK.value: self.handle_link_message,
            MessageTypes.EXECUTE.value: self.handle_execute_message,
            MessageTypes.REGISTER.value: self.handle_register_message,
            MessageTypes.CONFIG.value: self.handle_config_message,
            MessageTypes.FILE.value: self.handle_file_message,
            MessageTypes.INTERFACE.value: self.handle_iface_message,
            MessageTypes.EVENT.value: self.handle_event_message,
            MessageTypes.SESSION.value: self.handle_session_message,
        }
        self.session = None
        self.coreemu = server.mainserver.coreemu
        self.tcp_handler = server.RequestHandlerClass
        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        """
        Client has connected, set up a new connection.
        :return: nothing
        """
        pass

    def receive_message(self):
        data = self.request[0]
        header = data[: coreapi.CoreMessage.header_len]
        if len(header) < coreapi.CoreMessage.header_len:
            raise IOError(f"error receiving header (received {len(header)} bytes)")

        message_type, message_flags, message_len = coreapi.CoreMessage.unpack_header(
            header
        )
        if message_len == 0:
            logger.warning("received message with no data")
            return

        if len(data) != coreapi.CoreMessage.header_len + message_len:
            logger.error(
                "received message length does not match received data (%s != %s)",
                len(data),
                coreapi.CoreMessage.header_len + message_len,
            )
            raise IOError

        try:
            message_class = coreapi.CLASS_MAP[message_type]
            message = message_class(
                message_flags, header, data[coreapi.CoreMessage.header_len :]
            )
            return message
        except KeyError:
            message = coreapi.CoreMessage(
                message_flags, header, data[coreapi.CoreMessage.header_len :]
            )
            message.msgtype = message_type
            logger.exception("unimplemented core message type: %s", message.type_str())

    def handle(self):
        message = self.receive_message()
        sessions = message.session_numbers()
        message.queuedtimes = 0
        if sessions:
            for session_id in sessions:
                session = self.server.mainserver.coreemu.sessions.get(session_id)
                if session:
                    logger.debug("session handling message: %s", session.id)
                    self.session = session
                    self.handle_message(message)
                    self.broadcast(message)
                else:
                    logger.error(
                        "session %d in %s message not found.",
                        session_id,
                        message.type_str(),
                    )
        else:
            # no session specified, find an existing one
            session = None
            node_count = 0
            for session_id in self.server.mainserver.coreemu.sessions:
                current_session = self.server.mainserver.coreemu.sessions[session_id]
                current_node_count = current_session.get_node_count()
                if (
                    current_session.state == EventTypes.RUNTIME_STATE
                    and current_node_count > node_count
                ):
                    node_count = current_node_count
                    session = current_session

            if session or message.message_type == MessageTypes.REGISTER.value:
                self.session = session
                self.handle_message(message)
                self.broadcast(message)
            else:
                logger.error(
                    "no active session, dropping %s message.", message.type_str()
                )

    def broadcast(self, message):
        if not isinstance(message, (coreapi.CoreNodeMessage, coreapi.CoreLinkMessage)):
            return

        clients = self.tcp_handler.session_clients.get(self.session.id, [])
        for client in clients:
            try:
                client.sendall(message.raw_message)
            except IOError:
                logger.error("error broadcasting")

    def finish(self):
        return socketserver.BaseRequestHandler.finish(self)

    def queuemsg(self, msg):
        """
        UDP handlers are short-lived and do not have message queues.

        :param bytes msg: message to queue
        :return:
        """
        raise Exception(
            f"Unable to queue {msg} message for later processing using UDP!"
        )

    def sendall(self, data):
        """
        Use sendto() on the connectionless UDP socket.

        :param data:
        :return:
        """
        self.request[1].sendto(data, self.client_address)
