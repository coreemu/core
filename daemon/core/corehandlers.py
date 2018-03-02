"""
socket server request handlers leveraged by core servers.
"""

import Queue
import SocketServer
import os
import shlex
import shutil
import sys
import threading
import time

from core import coreobj
from core import logger
from core.api import coreapi
from core.coreserver import CoreServer
from core.data import ConfigData
from core.data import EventData
from core.data import NodeData
from core.enumerations import ConfigTlvs
from core.enumerations import EventTlvs
from core.enumerations import EventTypes
from core.enumerations import ExceptionTlvs
from core.enumerations import ExecuteTlvs
from core.enumerations import FileTlvs
from core.enumerations import LinkTlvs
from core.enumerations import LinkTypes
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.enumerations import NodeTlvs
from core.enumerations import NodeTypes
from core.enumerations import RegisterTlvs
from core.enumerations import SessionTlvs
from core.misc import nodeutils
from core.misc import structutils
from core.misc import utils
from core.netns import nodes
from core.xml.xmlsession import open_session_xml
from core.xml.xmlsession import save_session_xml


class CoreRequestHandler(SocketServer.BaseRequestHandler):
    """
    The SocketServer class uses the RequestHandler class for servicing
    requests, mainly through the handle() method. The CoreRequestHandler
    has the following basic flow:
       1. Client connects and request comes in via handle().
       2. handle() calls recvmsg() in a loop.
       3. recvmsg() does a recv() call on the socket performs basic
          checks that this we received a CoreMessage, returning it.
       4. The message data is queued using queuemsg().
       5. The handlerthread() thread pops messages from the queue and uses
          handlemsg() to invoke the appropriate handler for that message type.
    """

    def __init__(self, request, client_address, server):
        """
        Create a CoreRequestHandler instance.

        :param request: request object
        :param str client_address: client address
        :param CoreServer server: core server instance
        :return:
        """
        self.done = False
        self.message_handlers = {
            MessageTypes.NODE.value: self.handle_node_message,
            MessageTypes.LINK.value: self.handle_link_message,
            MessageTypes.EXECUTE.value: self.handle_execute_message,
            MessageTypes.REGISTER.value: self.handle_register_message,
            MessageTypes.CONFIG.value: self.handle_config_message,
            MessageTypes.FILE.value: self.handle_file_message,
            MessageTypes.INTERFACE.value: self.handle_interface_message,
            MessageTypes.EVENT.value: self.handle_event_message,
            MessageTypes.SESSION.value: self.handle_session_message,
        }
        self.message_queue = Queue.Queue()
        self.node_status_request = {}
        self._shutdown_lock = threading.Lock()

        self.handler_threads = []
        num_threads = int(server.config["numthreads"])
        if num_threads < 1:
            raise ValueError("invalid number of threads: %s" % num_threads)

        logger.info("launching core server handler threads: %s", num_threads)
        for _ in xrange(num_threads):
            thread = threading.Thread(target=self.handler_thread)
            self.handler_threads.append(thread)
            thread.start()

        self.master = False
        self.session = None

        utils.close_onexec(request.fileno())
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        """
        Client has connected, set up a new connection.

        :return: nothing
        """
        logger.info("new TCP connection: %s", self.client_address)
        # self.register()

    def finish(self):
        """
        Client has disconnected, end this request handler and disconnect
        from the session. Shutdown sessions that are not running.

        :return: nothing
        """
        logger.info("finishing request handler")
        self.done = True

        logger.info("remaining message queue size: %s", self.message_queue.qsize())
        # seconds
        timeout = 10.0
        logger.info("client disconnected: notifying threads")
        for thread in self.handler_threads:
            logger.info("waiting for thread: %s", thread.getName())
            thread.join(timeout)
            if thread.isAlive():
                logger.warn("joining %s failed: still alive after %s sec", thread.getName(), timeout)

        logger.info("connection closed: %s", self.client_address)
        if self.session:
            self.remove_session_handlers()

            # remove client from session broker and shutdown if there are no clients
            self.session.broker.session_clients.remove(self)
            if not self.session.broker.session_clients:
                logger.info("no session clients left, initiating shutdown")
                self.session.shutdown()

        return SocketServer.BaseRequestHandler.finish(self)

    def handle_broadcast_event(self, event_data):
        """
        Callback to handle an event broadcast out from a session.

        :param core.data.EventData event_data: event data to handle
        :return: nothing
        """
        logger.info("handling broadcast event: %s", event_data)

        tlv_data = structutils.pack_values(coreapi.CoreEventTlv, [
            (EventTlvs.NODE, event_data.node),
            (EventTlvs.TYPE, event_data.event_type),
            (EventTlvs.NAME, event_data.name),
            (EventTlvs.DATA, event_data.data),
            (EventTlvs.TIME, event_data.time),
            (EventTlvs.TIME, event_data.session)
        ])
        message = coreapi.CoreEventMessage.pack(0, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending event message")

    def handle_broadcast_file(self, file_data):
        """
        Callback to handle a file broadcast out from a session.

        :param core.data.FileData file_data: file data to handle
        :return: nothing
        """
        logger.info("handling broadcast file: %s", file_data)

        tlv_data = structutils.pack_values(coreapi.CoreFileTlv, [
            (FileTlvs.NODE, file_data.node),
            (FileTlvs.NAME, file_data.name),
            (FileTlvs.MODE, file_data.mode),
            (FileTlvs.NUMBER, file_data.number),
            (FileTlvs.TYPE, file_data.type),
            (FileTlvs.SOURCE_NAME, file_data.source),
            (FileTlvs.SESSION, file_data.session),
            (FileTlvs.DATA, file_data.data),
            (FileTlvs.COMPRESSED_DATA, file_data.compressed_data),
        ])
        message = coreapi.CoreFileMessage.pack(file_data.message_type, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending file message")

    def handle_broadcast_config(self, config_data):
        """
        Callback to handle a config broadcast out from a session.

        :param core.data.ConfigData config_data: config data to handle
        :return: nothing
        """
        logger.info("handling broadcast config: %s", config_data)

        tlv_data = structutils.pack_values(coreapi.CoreConfigTlv, [
            (ConfigTlvs.NODE, config_data.node),
            (ConfigTlvs.OBJECT, config_data.object),
            (ConfigTlvs.TYPE, config_data.type),
            (ConfigTlvs.DATA_TYPES, config_data.data_types),
            (ConfigTlvs.VALUES, config_data.data_values),
            (ConfigTlvs.CAPTIONS, config_data.captions),
            (ConfigTlvs.BITMAP, config_data.bitmap),
            (ConfigTlvs.POSSIBLE_VALUES, config_data.possible_values),
            (ConfigTlvs.GROUPS, config_data.groups),
            (ConfigTlvs.SESSION, config_data.session),
            (ConfigTlvs.INTERFACE_NUMBER, config_data.interface_number),
            (ConfigTlvs.NETWORK_ID, config_data.network_id),
            (ConfigTlvs.OPAQUE, config_data.opaque),
        ])
        message = coreapi.CoreConfMessage.pack(config_data.message_type, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending config message")

    def handle_broadcast_exception(self, exception_data):
        """
        Callback to handle an exception broadcast out from a session.

        :param core.data.ExceptionData exception_data: exception data to handle
        :return: nothing
        """
        logger.info("handling broadcast exception: %s", exception_data)
        tlv_data = structutils.pack_values(coreapi.CoreExceptionTlv, [
            (ExceptionTlvs.NODE, exception_data.node),
            (ExceptionTlvs.SESSION, exception_data.session),
            (ExceptionTlvs.LEVEL, exception_data.level),
            (ExceptionTlvs.SOURCE, exception_data.source),
            (ExceptionTlvs.DATE, exception_data.date),
            (ExceptionTlvs.TEXT, exception_data.text)
        ])
        message = coreapi.CoreExceptionMessage.pack(0, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending exception message")

    def handle_broadcast_node(self, node_data):
        """
        Callback to handle an node broadcast out from a session.

        :param core.data.NodeData node_data: node data to handle
        :return: nothing
        """
        logger.info("handling broadcast node: %s", node_data)

        tlv_data = structutils.pack_values(coreapi.CoreNodeTlv, [
            (NodeTlvs.NUMBER, node_data.id),
            (NodeTlvs.TYPE, node_data.node_type),
            (NodeTlvs.NAME, node_data.name),
            (NodeTlvs.IP_ADDRESS, node_data.ip_address),
            (NodeTlvs.MAC_ADDRESS, node_data.mac_address),
            (NodeTlvs.IP6_ADDRESS, node_data.ip6_address),
            (NodeTlvs.MODEL, node_data.model),
            (NodeTlvs.EMULATION_ID, node_data.emulation_id),
            (NodeTlvs.EMULATION_SERVER, node_data.emulation_server),
            (NodeTlvs.SESSION, node_data.session),
            (NodeTlvs.X_POSITION, node_data.x_position),
            (NodeTlvs.Y_POSITION, node_data.y_position),
            (NodeTlvs.CANVAS, node_data.canvas),
            (NodeTlvs.NETWORK_ID, node_data.network_id),
            (NodeTlvs.SERVICES, node_data.services),
            (NodeTlvs.LATITUDE, node_data.latitude),
            (NodeTlvs.LONGITUDE, node_data.longitude),
            (NodeTlvs.ALTITUDE, node_data.altitude),
            (NodeTlvs.ICON, node_data.icon),
            (NodeTlvs.OPAQUE, node_data.opaque)
        ])
        message = coreapi.CoreNodeMessage.pack(node_data.message_type, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending node message")

    def handle_broadcast_link(self, link_data):
        """
        Callback to handle an link broadcast out from a session.

        :param core.data.LinkData link_data: link data to handle
        :return: nothing
        """
        logger.info("handling broadcast link: %s", link_data)

        tlv_data = structutils.pack_values(coreapi.CoreLinkTlv, [
            (LinkTlvs.N1_NUMBER, link_data.node1_id),
            (LinkTlvs.N2_NUMBER, link_data.node2_id),
            (LinkTlvs.DELAY, link_data.delay),
            (LinkTlvs.BANDWIDTH, link_data.bandwidth),
            (LinkTlvs.PER, link_data.per),
            (LinkTlvs.DUP, link_data.dup),
            (LinkTlvs.JITTER, link_data.jitter),
            (LinkTlvs.MER, link_data.mer),
            (LinkTlvs.BURST, link_data.burst),
            (LinkTlvs.SESSION, link_data.session),
            (LinkTlvs.MBURST, link_data.mburst),
            (LinkTlvs.TYPE, link_data.link_type),
            (LinkTlvs.GUI_ATTRIBUTES, link_data.gui_attributes),
            (LinkTlvs.UNIDIRECTIONAL, link_data.unidirectional),
            (LinkTlvs.EMULATION_ID, link_data.emulation_id),
            (LinkTlvs.NETWORK_ID, link_data.network_id),
            (LinkTlvs.KEY, link_data.key),
            (LinkTlvs.INTERFACE1_NUMBER, link_data.interface1_id),
            (LinkTlvs.INTERFACE1_NAME, link_data.interface1_name),
            (LinkTlvs.INTERFACE1_IP4, link_data.interface1_ip4),
            (LinkTlvs.INTERFACE1_IP4_MASK, link_data.interface1_ip4_mask),
            (LinkTlvs.INTERFACE1_MAC, link_data.interface1_mac),
            (LinkTlvs.INTERFACE1_IP6, link_data.interface1_ip6),
            (LinkTlvs.INTERFACE1_IP6_MASK, link_data.interface1_ip6_mask),
            (LinkTlvs.INTERFACE2_NUMBER, link_data.interface2_id),
            (LinkTlvs.INTERFACE2_NAME, link_data.interface2_name),
            (LinkTlvs.INTERFACE2_IP4, link_data.interface2_ip4),
            (LinkTlvs.INTERFACE2_IP4_MASK, link_data.interface2_ip4_mask),
            (LinkTlvs.INTERFACE2_MAC, link_data.interface2_mac),
            (LinkTlvs.INTERFACE2_IP6, link_data.interface2_ip6),
            (LinkTlvs.INTERFACE2_IP6_MASK, link_data.interface2_ip6_mask),
            (LinkTlvs.OPAQUE, link_data.opaque)
        ])

        message = coreapi.CoreLinkMessage.pack(link_data.message_type, tlv_data)

        try:
            self.sendall(message)
        except IOError:
            logger.exception("error sending Event Message")

    def register(self):
        """
        Return a Register Message

        :return: register message data
        """
        logger.info("GUI has connected to session %d at %s", self.session.session_id, time.ctime())

        tlv_data = ""
        tlv_data += coreapi.CoreRegisterTlv.pack(RegisterTlvs.EXECUTE_SERVER.value, "core-daemon")
        tlv_data += coreapi.CoreRegisterTlv.pack(RegisterTlvs.EMULATION_SERVER.value, "core-daemon")

        # get config objects for session
        for name in self.session.config_objects:
            config_type, callback = self.session.config_objects[name]
            # type must be in coreapi.reg_tlvs
            tlv_data += coreapi.CoreRegisterTlv.pack(config_type, name)

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
        :rtype: coreapi.CoreMessage
        """
        try:
            header = self.request.recv(coreapi.CoreMessage.header_len)
            if len(header) > 0:
                logger.debug("received message header: %s", utils.hex_dump(header))
        except IOError as e:
            raise IOError("error receiving header (%s)" % e)

        if len(header) != coreapi.CoreMessage.header_len:
            if len(header) == 0:
                raise EOFError("client disconnected")
            else:
                raise IOError("invalid message header size")

        message_type, message_flags, message_len = coreapi.CoreMessage.unpack_header(header)
        if message_len == 0:
            logger.warn("received message with no data")

        data = ""
        while len(data) < message_len:
            data += self.request.recv(message_len - len(data))
            logger.debug("received message data: %s" % utils.hex_dump(data))
            if len(data) > message_len:
                error_message = "received message length does not match received data (%s != %s)" % (
                    len(data), message_len)
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
        logger.info("queueing msg (queuedtimes = %s): type %s",
                    message.queuedtimes, MessageTypes(message.message_type))
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
                message = self.message_queue.get(timeout=5)
                self.handle_message(message)
            except Queue.Empty:
                logger.debug("timeout getting message")

    def handle_message(self, message):
        """
        Handle an incoming message; dispatch based on message type,
        optionally sending replies.

        :param message: message to handle
        :return: nothing
        """
        if self.session and self.session.broker.handle_message(message):
            logger.info("message not being handled locally")
            return

        logger.info("%s handling message:\n%s", threading.currentThread().getName(), message)

        if message.message_type not in self.message_handlers:
            logger.warn("no handler for message type: %s", message.type_str())
            return

        message_handler = self.message_handlers[message.message_type]

        try:
            # TODO: this needs to be removed, make use of the broadcast message methods
            replies = message_handler(message)
            self.dispatch_replies(replies, message)
        except:
            logger.exception("%s: exception while handling message: %s",
                             threading.currentThread().getName(), message)

    # Added to allow the auxiliary handlers to define a different behavior when replying
    # to messages from clients
    def dispatch_replies(self, replies, message):
        """
        Dispatch replies by CORE to message msg previously received from the client.

        :param list replies: reply messages to dispatch
        :param message: message for replies
        :return: nothing
        """
        logger.info("replies to dispatch: %s", replies)
        for reply in replies:
            message_type, message_flags, message_length = coreapi.CoreMessage.unpack_header(reply)
            try:
                reply_message = coreapi.CLASS_MAP[message_type](
                    message_flags,
                    reply[:coreapi.CoreMessage.header_len],
                    reply[coreapi.CoreMessage.header_len:]
                )
            except KeyError:
                # multiple TLVs of same type cause KeyError exception
                reply_message = "CoreMessage (type %d flags %d length %d)" % (
                    message_type, message_flags, message_length)

            logger.info("reply to %s: \n%s", self.request.getpeername(), reply_message)

            try:
                self.sendall(reply)
            except IOError:
                logger.exception("Error sending reply data")

    def handle(self):
        """
        Handle a new connection request from a client. Dispatch to the
        recvmsg() method for receiving data into CORE API messages, and
        add them to an incoming message queue.

        :return: nothing
        """
        # use port as session id
        port = self.request.getpeername()[1]

        logger.info("creating new session for client: %s", port)
        self.session = self.server.create_session(session_id=port)

        # TODO: hack to associate this handler with this sessions broker for broadcasting
        # TODO: broker needs to be pulled out of session to the server/handler level
        if self.master:
            logger.info("SESSION SET TO MASTER!")
            self.session.master = True
        self.session.broker.session_clients.append(self)

        # add handlers for various data
        logger.info("adding session broadcast handlers")
        self.add_session_handlers()

        # set initial session state
        self.session.set_state(state=EventTypes.DEFINITION_STATE.value)

        while True:
            try:
                message = self.receive_message()
            except (IOError, EOFError):
                logger.exception("error receiving message")
                break

            message.queuedtimes = 0
            self.queue_message(message)

            # delay is required for brief connections, allow session joining
            if message.message_type == MessageTypes.SESSION.value:
                time.sleep(0.125)

            # broadcast node/link messages to other connected clients
            if message.message_type not in [MessageTypes.NODE.value, MessageTypes.LINK.value]:
                continue

            for client in self.session.broker.session_clients:
                if client == self:
                    continue

                logger.info("BROADCAST TO OTHER CLIENT: %s", client)
                client.sendall(message.raw_message)

    def add_session_handlers(self):
        logger.info("adding session broadcast handlers")
        self.session.event_handlers.append(self.handle_broadcast_event)
        self.session.exception_handlers.append(self.handle_broadcast_exception)
        self.session.node_handlers.append(self.handle_broadcast_node)
        self.session.link_handlers.append(self.handle_broadcast_link)
        self.session.file_handlers.append(self.handle_broadcast_file)
        self.session.config_handlers.append(self.handle_broadcast_config)

    def remove_session_handlers(self):
        logger.info("removing session broadcast handlers")
        self.session.event_handlers.remove(self.handle_broadcast_event)
        self.session.exception_handlers.remove(self.handle_broadcast_exception)
        self.session.node_handlers.remove(self.handle_broadcast_node)
        self.session.link_handlers.remove(self.handle_broadcast_link)
        self.session.file_handlers.remove(self.handle_broadcast_file)
        self.session.config_handlers.remove(self.handle_broadcast_config)

    def handle_node_message(self, message):
        """
        Node Message handler

        :param coreapi.CoreNodeMessage message: node message
        :return: replies to node message
        """
        replies = []
        if message.flags & MessageFlags.ADD.value and message.flags & MessageFlags.DELETE.value:
            logger.warn("ignoring invalid message: add and delete flag both set")
            return ()

        node_id = message.tlv_data[NodeTlvs.NUMBER.value]
        x_position = message.get_tlv(NodeTlvs.X_POSITION.value)
        y_position = message.get_tlv(NodeTlvs.Y_POSITION.value)
        canvas = message.get_tlv(NodeTlvs.CANVAS.value)
        icon = message.get_tlv(NodeTlvs.ICON.value)
        lat = message.get_tlv(NodeTlvs.LATITUDE.value)
        lng = message.get_tlv(NodeTlvs.LONGITUDE.value)
        alt = message.get_tlv(NodeTlvs.ALTITUDE.value)

        if x_position is None and y_position is None and \
                lat is not None and lng is not None and alt is not None:
            x, y, z = self.session.location.getxyz(float(lat), float(lng), float(alt))
            x_position = int(x)
            y_position = int(y)

            # GUI can"t handle lat/long, so generate another X/Y position message
            node_data = NodeData(
                id=node_id,
                x_position=x_position,
                y_position=y_position
            )

            self.session.broadcast_node(node_data)

        if message.flags & MessageFlags.ADD.value:
            node_type = message.tlv_data[NodeTlvs.TYPE.value]
            try:
                node_class = nodeutils.get_node_class(NodeTypes(node_type))
            except KeyError:
                try:
                    node_type_str = " (%s)" % NodeTypes(node_type).name
                except KeyError:
                    node_type_str = ""

                logger.warn("warning: unimplemented node type: %s%s" % (node_type, node_type_str))
                return ()

            start = False
            if self.session.state > EventTypes.DEFINITION_STATE.value:
                start = True

            node_name = message.tlv_data[NodeTlvs.NAME.value]
            model = message.get_tlv(NodeTlvs.MODEL.value)
            class_args = {"start": start}

            if node_type == NodeTypes.XEN.value:
                class_args["model"] = model

            if node_type == NodeTypes.RJ45.value and hasattr(
                self.session.options, "enablerj45") and self.session.options.enablerj45 == "0":
                class_args["start"] = False

            # this instantiates an object of class nodecls, creating the node or network
            node = self.session.add_object(cls=node_class, objid=node_id, name=node_name, **class_args)
            if x_position is not None and y_position is not None:
                node.setposition(x_position, y_position, None)
            if canvas is not None:
                node.canvas = canvas
            if icon is not None:
                node.icon = icon
            opaque = message.get_tlv(NodeTlvs.OPAQUE.value)
            if opaque is not None:
                node.opaque = opaque

            # add services to a node, either from its services TLV or
            # through the configured defaults for this node type
            if node_type in [NodeTypes.DEFAULT.value, NodeTypes.PHYSICAL.value, NodeTypes.XEN.value]:
                if model is None:
                    # TODO: default model from conf file?
                    model = "router"
                node.type = model
                services_str = message.get_tlv(NodeTlvs.SERVICES.value)
                logger.info("setting model (%s) with services (%s)", model, services_str)
                self.session.services.addservicestonode(node, model, services_str)

            # boot nodes if they are added after runtime (like
            # session.bootnodes())
            if self.session.state == EventTypes.RUNTIME_STATE.value:
                if isinstance(node, nodes.PyCoreNode) and not nodeutils.is_node(node, NodeTypes.RJ45):
                    self.session.write_objects()
                    self.session.add_remove_control_interface(node=node, remove=False)
                    node.boot()

                if message.flags & MessageFlags.STRING.value:
                    self.node_status_request[node_id] = True
                    self.send_node_emulation_id(node_id)
            elif message.flags & MessageFlags.STRING.value:
                self.node_status_request[node_id] = True

        elif message.flags & MessageFlags.DELETE.value:
            with self._shutdown_lock:
                self.session.delete_object(node_id)

                if message.flags & MessageFlags.STRING.value:
                    tlvdata = ""
                    tlvdata += coreapi.CoreNodeTlv.pack(NodeTlvs.NUMBER.value, node_id)
                    flags = MessageFlags.DELETE.value | MessageFlags.LOCAL.value
                    replies.append(coreapi.CoreNodeMessage.pack(flags, tlvdata))

                if self.session.check_shutdown():
                    tlvdata = ""
                    tlvdata += coreapi.CoreEventTlv.pack(EventTlvs.TYPE.value, self.session.state)
                    replies.append(coreapi.CoreEventMessage.pack(0, tlvdata))
        # Node modify message (no add/del flag)
        else:
            try:
                node = self.session.get_object(node_id)

                if x_position is not None and y_position is not None:
                    node.setposition(x_position, y_position, None)

                if canvas is not None:
                    node.canvas = canvas

                if icon is not None:
                    node.icon = icon
            except KeyError:
                logger.exception("ignoring node message: unknown node number %s", node_id)

        return replies

    def handle_link_message(self, message):
        """
        Link Message handler

        :param coreapi.CoreLinkMessage message: link message to handle
        :return: link message replies
        """
        # get node classes
        ptp_class = nodeutils.get_node_class(NodeTypes.PEER_TO_PEER)

        node_num1 = message.get_tlv(LinkTlvs.N1_NUMBER.value)
        interface_index1 = message.get_tlv(LinkTlvs.INTERFACE1_NUMBER.value)
        ipv41 = message.get_tlv(LinkTlvs.INTERFACE1_IP4.value)
        ipv4_mask1 = message.get_tlv(LinkTlvs.INTERFACE1_IP4_MASK.value)
        mac1 = message.get_tlv(LinkTlvs.INTERFACE1_MAC.value)
        ipv61 = message.get_tlv(LinkTlvs.INTERFACE1_IP6.value)
        ipv6_mask1 = message.get_tlv(LinkTlvs.INTERFACE1_IP6_MASK.value)
        interface_name1 = message.get_tlv(LinkTlvs.INTERFACE1_NAME.value)

        node_num2 = message.get_tlv(LinkTlvs.N2_NUMBER.value)
        interface_index2 = message.get_tlv(LinkTlvs.INTERFACE2_NUMBER.value)
        ipv42 = message.get_tlv(LinkTlvs.INTERFACE2_IP4.value)
        ipv4_mask2 = message.get_tlv(LinkTlvs.INTERFACE2_IP4_MASK.value)
        mac2 = message.get_tlv(LinkTlvs.INTERFACE2_MAC.value)
        ipv62 = message.get_tlv(LinkTlvs.INTERFACE2_IP6.value)
        ipv6_mask2 = message.get_tlv(LinkTlvs.INTERFACE2_IP6_MASK.value)
        interface_name2 = message.get_tlv(LinkTlvs.INTERFACE2_NAME.value)

        node1 = None
        node2 = None
        net = None
        net2 = None

        unidirectional_value = message.get_tlv(LinkTlvs.UNIDIRECTIONAL.value)
        if unidirectional_value == 1:
            unidirectional = True
        else:
            unidirectional = False

        # one of the nodes may exist on a remote server
        logger.info("link message between node1(%s:%s) and node2(%s:%s)",
                    node_num1, interface_index1, node_num2, interface_index2)
        if node_num1 is not None and node_num2 is not None:
            tunnel = self.session.broker.gettunnel(node_num1, node_num2)
            logger.info("tunnel between nodes: %s", tunnel)
            if isinstance(tunnel, coreobj.PyCoreNet):
                net = tunnel
                if tunnel.remotenum == node_num1:
                    node_num1 = None
                else:
                    node_num2 = None
            # PhysicalNode connected via GreTap tunnel; uses adoptnetif() below
            elif tunnel is not None:
                if tunnel.remotenum == node_num1:
                    node_num1 = None
                else:
                    node_num2 = None

        if node_num1 is not None:
            try:
                n = self.session.get_object(node_num1)
            except KeyError:
                # XXX wait and queue this message to try again later
                # XXX maybe this should be done differently
                time.sleep(0.125)
                self.queue_message(message)
                return ()
            if isinstance(n, nodes.PyCoreNode):
                node1 = n
            elif isinstance(n, coreobj.PyCoreNet):
                if net is None:
                    net = n
                else:
                    net2 = n
            else:
                raise ValueError("unexpected object class: %s" % n)

        if node_num2 is not None:
            try:
                n = self.session.get_object(node_num2)
            except KeyError:
                # XXX wait and queue this message to try again later
                # XXX maybe this should be done differently
                time.sleep(0.125)
                self.queue_message(message)
                return ()
            if isinstance(n, nodes.PyCoreNode):
                node2 = n
            elif isinstance(n, coreobj.PyCoreNet):
                if net is None:
                    net = n
                else:
                    net2 = n
            else:
                raise ValueError("unexpected object class: %s" % n)

        link_msg_type = message.get_tlv(LinkTlvs.TYPE.value)

        if node1:
            node1.lock.acquire()
        if node2:
            node2.lock.acquire()

        try:
            if link_msg_type == LinkTypes.WIRELESS.value:
                """
                Wireless link/unlink event
                """
                numwlan = 0
                objs = [node1, node2, net, net2]
                objs = filter(lambda (x): x is not None, objs)
                if len(objs) < 2:
                    raise ValueError("wireless link/unlink message between unknown objects")

                nets = objs[0].commonnets(objs[1])
                for netcommon, netif1, netif2 in nets:
                    if not nodeutils.is_node(netcommon, (NodeTypes.WIRELESS_LAN, NodeTypes.EMANE)):
                        continue
                    if message.flags & MessageFlags.ADD.value:
                        netcommon.link(netif1, netif2)
                    elif message.flags & MessageFlags.DELETE.value:
                        netcommon.unlink(netif1, netif2)
                    else:
                        raise ValueError("invalid flags for wireless link/unlink message")
                    numwlan += 1
                if numwlan == 0:
                    raise ValueError("no common network found for wireless link/unlink")

            elif message.flags & MessageFlags.ADD.value:
                """
                Add a new link.
                """
                start = False
                if self.session.state > EventTypes.DEFINITION_STATE.value:
                    start = True

                if node1 and node2 and not net:
                    # a new wired link
                    net = self.session.add_object(cls=ptp_class, start=start)

                bw = message.get_tlv(LinkTlvs.BANDWIDTH.value)
                delay = message.get_tlv(LinkTlvs.DELAY.value)
                loss = message.get_tlv(LinkTlvs.PER.value)
                duplicate = message.get_tlv(LinkTlvs.DUP.value)
                jitter = message.get_tlv(LinkTlvs.JITTER.value)
                key = message.get_tlv(LinkTlvs.KEY.value)

                netaddrlist = []
                if node1 and net:
                    addrlist = []
                    if ipv41 is not None and ipv4_mask1 is not None:
                        addrlist.append("%s/%s" % (ipv41, ipv4_mask1))
                    if ipv61 is not None and ipv6_mask1 is not None:
                        addrlist.append("%s/%s" % (ipv61, ipv6_mask1))
                    if ipv42 is not None and ipv4_mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv42, ipv4_mask2))
                    if ipv62 is not None and ipv6_mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv62, ipv6_mask2))
                    interface_index1 = node1.newnetif(
                        net, addrlist=addrlist,
                        hwaddr=mac1, ifindex=interface_index1, ifname=interface_name1
                    )
                    net.linkconfig(
                        node1.netif(interface_index1, net), bw=bw,
                        delay=delay, loss=loss,
                        duplicate=duplicate, jitter=jitter
                    )
                if node1 is None and net:
                    if ipv41 is not None and ipv4_mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv41, ipv4_mask1))
                        # don"t add this address again if node2 and net
                        ipv41 = None
                    if ipv61 is not None and ipv6_mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv61, ipv6_mask1))
                        # don"t add this address again if node2 and net
                        ipv61 = None
                if node2 and net:
                    addrlist = []
                    if ipv42 is not None and ipv4_mask2 is not None:
                        addrlist.append("%s/%s" % (ipv42, ipv4_mask2))
                    if ipv62 is not None and ipv6_mask2 is not None:
                        addrlist.append("%s/%s" % (ipv62, ipv6_mask2))
                    if ipv41 is not None and ipv4_mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv41, ipv4_mask1))
                    if ipv61 is not None and ipv6_mask1 is not None:
                        netaddrlist.append("%s/%s" % (ipv61, ipv6_mask1))
                    interface_index2 = node2.newnetif(
                        net, addrlist=addrlist,
                        hwaddr=mac2, ifindex=interface_index2, ifname=interface_name2
                    )
                    if not unidirectional:
                        net.linkconfig(
                            node2.netif(interface_index2, net), bw=bw,
                            delay=delay, loss=loss,
                            duplicate=duplicate, jitter=jitter
                        )
                if node2 is None and net2:
                    if ipv42 is not None and ipv4_mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv42, ipv4_mask2))
                    if ipv62 is not None and ipv6_mask2 is not None:
                        netaddrlist.append("%s/%s" % (ipv62, ipv6_mask2))

                # tunnel node finalized with this link message
                if key and nodeutils.is_node(net, NodeTypes.TUNNEL):
                    net.setkey(key)
                    if len(netaddrlist) > 0:
                        net.addrconfig(netaddrlist)
                if key and nodeutils.is_node(net2, NodeTypes.TUNNEL):
                    net2.setkey(key)
                    if len(netaddrlist) > 0:
                        net2.addrconfig(netaddrlist)

                if net and net2:
                    # two layer-2 networks linked together
                    if nodeutils.is_node(net2, NodeTypes.RJ45):
                        # RJ45 nodes have different linknet()
                        netif = net2.linknet(net)
                    else:
                        netif = net.linknet(net2)
                    net.linkconfig(netif, bw=bw, delay=delay, loss=loss,
                                   duplicate=duplicate, jitter=jitter)
                    if not unidirectional:
                        netif.swapparams("_params_up")
                        net2.linkconfig(netif, bw=bw, delay=delay, loss=loss,
                                        duplicate=duplicate, jitter=jitter,
                                        devname=netif.name)
                        netif.swapparams("_params_up")
                elif net is None and net2 is None and (node1 is None or node2 is None):
                    # apply address/parameters to PhysicalNodes
                    fx = (bw, delay, loss, duplicate, jitter)
                    addrlist = []
                    if node1 and nodeutils.is_node(node1, NodeTypes.PHYSICAL):
                        if ipv41 is not None and ipv4_mask1 is not None:
                            addrlist.append("%s/%s" % (ipv41, ipv4_mask1))
                        if ipv61 is not None and ipv6_mask1 is not None:
                            addrlist.append("%s/%s" % (ipv61, ipv6_mask1))
                        node1.adoptnetif(tunnel, interface_index1, mac1, addrlist)
                        node1.linkconfig(tunnel, bw, delay, loss, duplicate, jitter)
                    elif node2 and nodeutils.is_node(node2, NodeTypes.PHYSICAL):
                        if ipv42 is not None and ipv4_mask2 is not None:
                            addrlist.append("%s/%s" % (ipv42, ipv4_mask2))
                        if ipv62 is not None and ipv6_mask2 is not None:
                            addrlist.append("%s/%s" % (ipv62, ipv6_mask2))
                        node2.adoptnetif(tunnel, interface_index2, mac2, addrlist)
                        node2.linkconfig(tunnel, bw, delay, loss, duplicate, jitter)
            # delete a link
            elif message.flags & MessageFlags.DELETE.value:
                """
                Remove a link.
                """
                if node1 and node2:
                    # TODO: fix this for the case where ifindex[1,2] are not specified
                    # a wired unlink event, delete the connecting bridge
                    netif1 = node1.netif(interface_index1)
                    netif2 = node2.netif(interface_index2)
                    if netif1 is None and netif2 is None:
                        nets = node1.commonnets(node2)
                        for netcommon, tmp1, tmp2 in nets:
                            if (net and netcommon == net) or net is None:
                                netif1 = tmp1
                                netif2 = tmp2
                                break

                    if all([netif1, netif2]) and any([netif1.net, netif2.net]):
                        if netif1.net != netif2.net and all([netif1.up, netif2.up]):
                            raise ValueError("no common network found")
                        net = netif1.net
                        netif1.detachnet()
                        netif2.detachnet()
                        if net.numnetif() == 0:
                            self.session.delete_object(net.objid)
                        node1.delnetif(interface_index1)
                        node2.delnetif(interface_index2)
            else:
                """
                Modify a link.
                """
                bw = message.get_tlv(LinkTlvs.BANDWIDTH.value)
                delay = message.get_tlv(LinkTlvs.DELAY.value)
                loss = message.get_tlv(LinkTlvs.PER.value)
                duplicate = message.get_tlv(LinkTlvs.DUP.value)
                jitter = message.get_tlv(LinkTlvs.JITTER.value)
                numnet = 0
                # TODO: clean up all this logic. Having the add flag or not
                #       should use the same code block.
                if node1 is None and node2 is None:
                    if net and net2:
                        # modify link between nets
                        netif = net.getlinknetif(net2)
                        upstream = False
                        if netif is None:
                            upstream = True
                            netif = net2.getlinknetif(net)
                        if netif is None:
                            raise ValueError("modify unknown link between nets")
                        if upstream:
                            netif.swapparams("_params_up")
                            net.linkconfig(netif, bw=bw, delay=delay,
                                           loss=loss, duplicate=duplicate,
                                           jitter=jitter, devname=netif.name)
                            netif.swapparams("_params_up")
                        else:
                            net.linkconfig(netif, bw=bw, delay=delay,
                                           loss=loss, duplicate=duplicate,
                                           jitter=jitter)
                        if not unidirectional:
                            if upstream:
                                net2.linkconfig(netif, bw=bw, delay=delay,
                                                loss=loss,
                                                duplicate=duplicate,
                                                jitter=jitter)
                            else:
                                netif.swapparams("_params_up")
                                net2.linkconfig(netif, bw=bw, delay=delay,
                                                loss=loss,
                                                duplicate=duplicate,
                                                jitter=jitter,
                                                devname=netif.name)
                                netif.swapparams("_params_up")
                    else:
                        raise ValueError("modify link for unknown nodes")
                elif node1 is None:
                    # node1 = layer 2node, node2 = layer3 node
                    net.linkconfig(node2.netif(interface_index2, net), bw=bw,
                                   delay=delay, loss=loss,
                                   duplicate=duplicate, jitter=jitter)
                elif node2 is None:
                    # node2 = layer 2node, node1 = layer3 node
                    net.linkconfig(node1.netif(interface_index1, net), bw=bw,
                                   delay=delay, loss=loss,
                                   duplicate=duplicate, jitter=jitter)
                else:
                    nets = node1.commonnets(node2)
                    for net, netif1, netif2 in nets:
                        if interface_index1 is not None and interface_index1 != node1.getifindex(netif1):
                            continue
                        net.linkconfig(netif1, bw=bw, delay=delay,
                                       loss=loss, duplicate=duplicate,
                                       jitter=jitter, netif2=netif2)
                        if not unidirectional:
                            net.linkconfig(netif2, bw=bw, delay=delay,
                                           loss=loss, duplicate=duplicate,
                                           jitter=jitter, netif2=netif1)
                        numnet += 1
                    if numnet == 0:
                        raise ValueError("no common network found")
        finally:
            if node1:
                node1.lock.release()
            if node2:
                node2.lock.release()

        return ()

    def handle_execute_message(self, message):
        """
        Execute Message handler

        :param coreapi.CoreExecMessage message: execute message to handle
        :return: reply messages
        """
        node_num = message.get_tlv(ExecuteTlvs.NODE.value)
        execute_num = message.get_tlv(ExecuteTlvs.NUMBER.value)
        execute_time = message.get_tlv(ExecuteTlvs.TIME.value)
        command = message.get_tlv(ExecuteTlvs.COMMAND.value)

        # local flag indicates command executed locally, not on a node
        if node_num is None and not message.flags & MessageFlags.LOCAL.value:
            raise ValueError("Execute Message is missing node number.")

        if execute_num is None:
            raise ValueError("Execute Message is missing execution number.")

        if execute_time is not None:
            self.session.add_event(execute_time, node=node_num, name=None, data=command)
            return ()

        try:
            node = self.session.get_object(node_num)

            # build common TLV items for reply
            tlv_data = ""
            if node_num is not None:
                tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.NODE.value, node_num)
            tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.NUMBER.value, execute_num)
            tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.COMMAND.value, command)

            if message.flags & MessageFlags.TTY.value:
                if node_num is None:
                    raise NotImplementedError
                # echo back exec message with cmd for spawning interactive terminal
                if command == "bash":
                    command = "/bin/bash"
                res = node.termcmdstring(command)
                tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.RESULT.value, res)
                reply = coreapi.CoreExecMessage.pack(MessageFlags.TTY.value, tlv_data)
                return reply,
            else:
                logger.info("execute message with cmd=%s", command)
                # execute command and send a response
                if message.flags & MessageFlags.STRING.value or message.flags & MessageFlags.TEXT.value:
                    # shlex.split() handles quotes within the string
                    if message.flags & MessageFlags.LOCAL.value:
                        status, res = utils.cmd_output(command)
                    else:
                        status, res = node.cmd_output(command)
                    logger.info("done exec cmd=%s with status=%d res=(%d bytes)", command, status, len(res))
                    if message.flags & MessageFlags.TEXT.value:
                        tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.RESULT.value, res)
                    if message.flags & MessageFlags.STRING.value:
                        tlv_data += coreapi.CoreExecuteTlv.pack(ExecuteTlvs.STATUS.value, status)
                    reply = coreapi.CoreExecMessage.pack(0, tlv_data)
                    return reply,
                # execute the command with no response
                else:
                    if message.flags & MessageFlags.LOCAL.value:
                        utils.mute_detach(command)
                    else:
                        node.cmd(command, wait=False)
        except KeyError:
            logger.exception("error getting object: %s", node_num)
            # XXX wait and queue this message to try again later
            # XXX maybe this should be done differently
            if not message.flags & MessageFlags.LOCAL.value:
                time.sleep(0.125)
                self.queue_message(message)

        return ()

    def handle_register_message(self, message):
        """
        Register Message Handler

        :param coreapi.CoreRegMessage message: register message to handle
        :return: reply messages
        """
        replies = []

        # execute a Python script or XML file
        execute_server = message.get_tlv(RegisterTlvs.EXECUTE_SERVER.value)
        if execute_server:
            try:
                logger.info("executing: %s", execute_server)
                # TODO: remove this, unless we want to support udp/aux at any level
                if not isinstance(self.server, CoreServer):  # CoreUdpServer):
                    server = self.server.mainserver
                else:
                    server = self.server
                if message.flags & MessageFlags.STRING.value:
                    old_session_ids = set(server.get_session_ids())
                sys.argv = shlex.split(execute_server)
                file_name = sys.argv[0]
                if os.path.splitext(file_name)[1].lower() == ".xml":
                    session = server.create_session()
                    try:
                        open_session_xml(session, file_name, start=True)
                    except:
                        session.shutdown()
                        server.remove_session(session)
                        raise
                else:
                    thread = threading.Thread(
                        target=execfile,
                        args=(file_name, {"__file__": file_name, "server": server})
                    )
                    thread.daemon = True
                    thread.start()
                    # allow time for session creation
                    time.sleep(0.25)
                if message.flags & MessageFlags.STRING.value:
                    new_session_ids = set(server.get_session_ids())
                    new_sid = new_session_ids.difference(old_session_ids)
                    try:
                        sid = new_sid.pop()
                        logger.info("executed: %s as session %d", execute_server, sid)
                    except KeyError:
                        logger.info("executed %s with unknown session ID", execute_server)
                        return replies
                    logger.info("checking session %d for RUNTIME state" % sid)
                    session = self.server.get_session(session_id=sid)
                    retries = 10
                    # wait for session to enter RUNTIME state, to prevent GUI from
                    # connecting while nodes are still being instantiated
                    while session.state != EventTypes.RUNTIME_STATE.value:
                        logger.info("waiting for session %d to enter RUNTIME state" % sid)
                        time.sleep(1)
                        retries -= 1
                        if retries <= 0:
                            logger.info("session %d did not enter RUNTIME state" % sid)
                            return replies
                    tlv_data = coreapi.CoreRegisterTlv.pack(RegisterTlvs.EXECUTE_SERVER.value, execute_server)
                    tlv_data += coreapi.CoreRegisterTlv.pack(RegisterTlvs.SESSION.value, "%s" % sid)
                    message = coreapi.CoreRegMessage.pack(0, tlv_data)
                    replies.append(message)
            except Exception as e:
                logger.exception("error executing: %s", execute_server)
                tlv_data = coreapi.CoreExceptionTlv.pack(ExceptionTlvs.LEVEL.value, 2)
                tlv_data += coreapi.CoreExceptionTlv.pack(ExceptionTlvs.TEXT.value, str(e))
                message = coreapi.CoreExceptionMessage.pack(0, tlv_data)
                replies.append(message)

            return replies

        gui = message.get_tlv(RegisterTlvs.GUI.value)
        if gui is None:
            logger.info("ignoring Register message")
        else:
            # register capabilities with the GUI
            self.master = True

            # TODO: need to replicate functionality?
            # self.server.set_session_master(self)
            # find the session containing this client and set the session to master
            for session in self.server.sessions.itervalues():
                if self in session.broker.session_clients:
                    logger.info("setting session to master: %s", session.session_id)
                    session.master = True
                    break

            replies.append(self.register())
            replies.append(self.server.to_session_message())

        return replies

    def handle_config_message(self, message):
        """
        Configuration Message handler

        :param coreapi.CoreConfMessage message: configuration message to handle
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
            interface_number=message.get_tlv(ConfigTlvs.INTERFACE_NUMBER.value),
            network_id=message.get_tlv(ConfigTlvs.NETWORK_ID.value),
            opaque=message.get_tlv(ConfigTlvs.OPAQUE.value)
        )
        logger.info("Configuration message for %s node %s", config_data.object, config_data.node)

        # dispatch to any registered callback for this object type
        replies = self.session.config_object(config_data)

        for reply in replies:
            self.handle_broadcast_config(reply)

        return []

    def handle_file_message(self, message):
        """
        File Message handler

        :param coreapi.CoreFileMessage message: file message to handle
        :return: reply messages
        """
        if message.flags & MessageFlags.ADD.value:
            node_num = message.get_tlv(NodeTlvs.NUMBER.value)
            file_name = message.get_tlv(FileTlvs.NAME.value)
            file_type = message.get_tlv(FileTlvs.TYPE.value)
            source_name = message.get_tlv(FileTlvs.SOURCE_NAME.value)
            data = message.get_tlv(FileTlvs.DATA.value)
            compressed_data = message.get_tlv(FileTlvs.COMPRESSED_DATA.value)

            if compressed_data:
                logger.warn("Compressed file data not implemented for File message.")
                return ()

            if source_name and data:
                logger.warn("ignoring invalid File message: source and data TLVs are both present")
                return ()

            # some File Messages store custom files in services,
            # prior to node creation
            if file_type is not None:
                if file_type[:8] == "service:":
                    self.session.services.setservicefile(node_num, file_type, file_name, source_name, data)
                    return ()
                elif file_type[:5] == "hook:":
                    self.session.set_hook(file_type, file_name, source_name, data)
                    return ()

            # writing a file to the host
            if node_num is None:
                if source_name is not None:
                    shutil.copy2(source_name, file_name)
                else:
                    with open(file_name, "w") as open_file:
                        open_file.write(data)
                return ()

            try:
                node = self.session.get_object(node_num)
                if source_name is not None:
                    node.addfile(source_name, file_name)
                elif data is not None:
                    node.nodefile(file_name, data)
            except KeyError:
                # XXX wait and queue this message to try again later
                # XXX maybe this should be done differently
                logger.warn("File message for %s for node number %s queued." % (file_name, node_num))
                time.sleep(0.125)
                self.queue_message(message)
                return ()
        else:
            raise NotImplementedError

        return ()

    def handle_interface_message(self, message):
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

        :param coreapi.CoreEventMessage message: event message to handle
        :return: reply messages
        """
        event_data = EventData(
            node=message.get_tlv(EventTlvs.NODE.value),
            event_type=message.get_tlv(EventTlvs.TYPE.value),
            name=message.get_tlv(EventTlvs.NAME.value),
            data=message.get_tlv(EventTlvs.DATA.value),
            time=message.get_tlv(EventTlvs.TIME.value),
            session=message.get_tlv(EventTlvs.SESSION.value)
        )

        event_type = event_data.event_type
        if event_type is None:
            raise NotImplementedError("Event message missing event type")
        node_id = event_data.node

        logger.info("EVENT %d: %s at %s", event_type, EventTypes(event_type).name, time.ctime())
        if event_type <= EventTypes.SHUTDOWN_STATE.value:
            if node_id is not None:
                try:
                    node = self.session.get_object(node_id)
                except KeyError:
                    raise KeyError("Event message for unknown node %d" % node_id)

                # configure mobility models for WLAN added during runtime
                if event_type == EventTypes.INSTANTIATION_STATE.value and nodeutils.is_node(node,
                                                                                            NodeTypes.WIRELESS_LAN):
                    self.session.mobility.startup(node_ids=(node.objid,))
                    return ()

                logger.warn("dropping unhandled Event message with node number")
                return ()
            self.session.set_state(state=event_type)

        if event_type == EventTypes.DEFINITION_STATE.value:
            # clear all session objects in order to receive new definitions
            self.session.delete_objects()
            self.session.del_hooks()
            self.session.broker.reset()
        elif event_type == EventTypes.INSTANTIATION_STATE.value:
            if len(self.handler_threads) > 1:
                # TODO: sync handler threads here before continuing
                time.sleep(2.0)  # XXX
            # done receiving node/link configuration, ready to instantiate
            self.session.instantiate()

            # after booting nodes attempt to send emulation id for nodes waiting on status
            for obj in self.session.objects.itervalues():
                self.send_node_emulation_id(obj.objid)
        elif event_type == EventTypes.RUNTIME_STATE.value:
            if self.session.master:
                logger.warn("Unexpected event message: RUNTIME state received at session master")
            else:
                # master event queue is started in session.checkruntime()
                self.session.event_loop.run()
        elif event_type == EventTypes.DATACOLLECT_STATE.value:
            self.session.data_collect()
        elif event_type == EventTypes.SHUTDOWN_STATE.value:
            if self.session.master:
                logger.warn("Unexpected event message: SHUTDOWN state received at session master")
        elif event_type in (EventTypes.START.value, EventTypes.STOP.value,
                            EventTypes.RESTART.value,
                            EventTypes.PAUSE.value,
                            EventTypes.RECONFIGURE.value):
            handled = False
            name = event_data.name
            if name:
                # TODO: register system for event message handlers,
                # like confobjs
                if name.startswith("service:"):
                    self.session.services.handleevent(event_data)
                    handled = True
                elif name.startswith("mobility:"):
                    self.session.mobility.handleevent(event_data)
                    handled = True
            if not handled:
                logger.warn("Unhandled event message: event type %s (%s)",
                            event_type, coreapi.state_name(event_type))
        elif event_type == EventTypes.FILE_OPEN.value:
            self.session.delete_objects()
            self.session.del_hooks()
            self.session.broker.reset()
            filename = event_data.name
            open_session_xml(self.session, filename)

            # trigger session to send out messages out itself
            self.session.send_objects()
            return ()
        elif event_type == EventTypes.FILE_SAVE.value:
            filename = event_data.name
            save_session_xml(self.session, filename, self.session.config["xmlfilever"])
        elif event_type == EventTypes.SCHEDULED.value:
            etime = event_data.time
            node = event_data.node
            name = event_data.name
            data = event_data.data
            if etime is None:
                logger.warn("Event message scheduled event missing start time")
                return ()
            if message.flags & MessageFlags.ADD.value:
                self.session.add_event(float(etime), node=node, name=name, data=data)
            else:
                raise NotImplementedError
        else:
            logger.warn("Unhandled event message: event type %d", event_type)

        return ()

    def handle_session_message(self, message):
        """
        Session Message handler

        :param coreapi.CoreSessionMessage message: session message to handle
        :return: reply messages
        """
        session_id_str = message.get_tlv(SessionTlvs.NUMBER.value)
        name_str = message.get_tlv(SessionTlvs.NAME.value)
        file_str = message.get_tlv(SessionTlvs.FILE.value)
        node_count_str = message.get_tlv(SessionTlvs.NODE_COUNT.value)
        thumb = message.get_tlv(SessionTlvs.THUMB.value)
        user = message.get_tlv(SessionTlvs.USER.value)
        session_ids = coreapi.str_to_list(session_id_str)
        names = coreapi.str_to_list(name_str)
        files = coreapi.str_to_list(file_str)
        node_counts = coreapi.str_to_list(node_count_str)
        logger.info("SESSION message flags=0x%x sessions=%s" % (message.flags, session_id_str))

        if message.flags == 0:
            # modify a session
            i = 0
            for session_id in session_ids:
                session_id = int(session_id)
                if session_id == 0:
                    session = self.session
                else:
                    session = self.server.get_session(session_id=session_id)

                if session is None:
                    logger.info("session %s not found", session_id)
                    i += 1
                    continue

                logger.info("request to modify to session %s", session.session_id)
                if names is not None:
                    session.name = names[i]
                if files is not None:
                    session.file_name = files[i]
                if node_counts is not None:
                    pass
                    # session.node_count = ncs[i]
                if thumb is not None:
                    session.set_thumbnail(thumb)
                if user is not None:
                    session.set_user(user)
                i += 1
        else:
            if message.flags & MessageFlags.STRING.value and not message.flags & MessageFlags.ADD.value:
                # status request flag: send list of sessions
                return self.server.to_session_message(),

            # handle ADD or DEL flags
            for session_id in session_ids:
                session_id = int(session_id)
                session = self.server.get_session(session_id=session_id)

                if session is None:
                    logger.info("session %s not found (flags=0x%x)", session_id, message.flags)
                    continue

                if message.flags & MessageFlags.ADD.value:
                    # connect to the first session that exists
                    logger.info("request to connect to session %s" % session_id)

                    # remove client from session broker and shutdown if needed
                    self.session.broker.session_clients.remove(self)
                    active_states = [
                        EventTypes.RUNTIME_STATE.value,
                        EventTypes.RUNTIME_STATE.value,
                        EventTypes.DATACOLLECT_STATE.value
                    ]
                    if not self.session.broker.session_clients and self.session.state not in active_states:
                        self.session.shutdown()

                    # set session to join
                    self.session = session

                    # add client to session broker and set master if needed
                    if self.master:
                        self.session.master = True
                    self.session.broker.session_clients.append(self)

                    # add broadcast handlers
                    logger.info("adding session broadcast handlers")
                    self.add_session_handlers()

                    if user is not None:
                        self.session.set_user(user)

                    if message.flags & MessageFlags.STRING.value:
                        self.session.send_objects()
                elif message.flags & MessageFlags.DELETE.value:
                    # shut down the specified session(s)
                    logger.info("request to terminate session %s" % session_id)
                    session.set_state(state=EventTypes.DATACOLLECT_STATE.value, send_event=True)
                    session.set_state(state=EventTypes.SHUTDOWN_STATE.value, send_event=True)
                    session.shutdown()
                else:
                    logger.warn("unhandled session flags for session %s", session_id)

        return ()

    def send_node_emulation_id(self, node_id):
        """
        Node emulation id to send.

        :param int node_id: node id to send
        :return: nothing
        """
        if node_id in self.node_status_request:
            tlv_data = ""
            tlv_data += coreapi.CoreNodeTlv.pack(NodeTlvs.NUMBER.value, node_id)
            tlv_data += coreapi.CoreNodeTlv.pack(NodeTlvs.EMULATION_ID.value, node_id)
            reply = coreapi.CoreNodeMessage.pack(MessageFlags.ADD.value | MessageFlags.LOCAL.value, tlv_data)

            try:
                self.sendall(reply)
            except IOError:
                logger.exception("error sending node emulation id message: %s", node_id)

            del self.node_status_request[node_id]


class CoreDatagramRequestHandler(CoreRequestHandler):
    """
    A child of the CoreRequestHandler class for handling connectionless
    UDP messages. No new session is created; messages are handled immediately or
    sometimes queued on existing session handlers.
    """

    def __init__(self, request, client_address, server):
        """
        Create a CoreDatagramRequestHandler instance.

        :param request: request object
        :param str client_address: client address
        :param CoreServer server: core server instance
        """
        # TODO: decide which messages cannot be handled with connectionless UDP
        self.message_handlers = {
            MessageTypes.NODE.value: self.handle_node_message,
            MessageTypes.LINK.value: self.handle_link_message,
            MessageTypes.EXECUTE.value: self.handle_execute_message,
            MessageTypes.REGISTER.value: self.handle_register_message,
            MessageTypes.CONFIG.value: self.handle_config_message,
            MessageTypes.FILE.value: self.handle_file_message,
            MessageTypes.INTERFACE.value: self.handle_interface_message,
            MessageTypes.EVENT.value: self.handle_event_message,
            MessageTypes.SESSION.value: self.handle_session_message,
        }
        self.node_status_request = {}
        self.master = False
        self.session = None
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        """
        Client has connected, set up a new connection.

        :return: nothing
        """
        logger.info("new UDP connection: %s:%s" % self.client_address)

    def handle(self):
        """
        Receive a message.

        :return: nothing
        """
        self.receive_message()

    def finish(self):
        """
        Handle the finish state of a client.

        :return: nothing
        """
        return SocketServer.BaseRequestHandler.finish(self)

    def receive_message(self):
        """
        Receive data, parse a CoreMessage and queue it onto an existing
        session handler"s queue, if available.

        :return: nothing
        """
        data = self.request[0]
        sock = self.request[1]

        header = data[:coreapi.CoreMessage.header_len]
        if len(header) < coreapi.CoreMessage.header_len:
            raise IOError("error receiving header (received %d bytes)" % len(header))
        message_type, message_flags, message_len = coreapi.CoreMessage.unpack_header(header)
        if message_len == 0:
            logger.warn("received message with no data")
            return

        if len(data) != coreapi.CoreMessage.header_len + message_len:
            logger.warn("received message length does not match received data (%s != %s)",
                        len(data), coreapi.CoreMessage.header_len + message_len)
            raise IOError
        else:
            logger.info("UDP socket received message type=%d len=%d", message_type, message_len)

        try:
            message_class = coreapi.CLASS_MAP[message_type]
            message = message_class(message_flags, header, data[coreapi.CoreMessage.header_len:])
        except KeyError:
            message = coreapi.CoreMessage(message_flags, header, data[coreapi.CoreMessage.header_len:])
            message.message_type = message_type
            logger.warn("unimplemented core message type: %s" % message.type_str())
            return

        session_ids = message.session_numbers()
        message.queuedtimes = 0
        # logger.info("UDP message has session numbers: %s" % sids)

        if len(session_ids) > 0:
            for session_id in session_ids:
                session = self.server.mainserver.get_session(session_id=session_id)
                if session:
                    self.session = session
                    session.broadcast(self, message)
                    self.handle_message(message)
                else:
                    logger.warn("Session %d in %s message not found." % (session_id, message.type_str()))
        else:
            # no session specified, find an existing one
            session = self.server.mainserver.get_session()
            if session or message.message_type == MessageTypes.REGISTER.value:
                self.session = session
                if session:
                    session.broadcast(self, message)
                self.handle_message(message)
            else:
                logger.warn("No active session, dropping %s message.", message.type_str())

    def queue_message(self, message):
        """
        UDP handlers are short-lived and do not have message queues.

        :return: nothing
        """
        raise Exception("Unable to queue %s message for later processing using UDP!" % message.type_str())

    def sendall(self, data):
        """
        Use sendto() on the connectionless UDP socket.

        :return: nothing
        """
        self.request[1].sendto(data, self.client_address)


class BaseAuxRequestHandler(CoreRequestHandler):
    """
    This is the superclass for auxiliary handlers in CORE. A concrete auxiliary handler class
    must, at a minimum, define the recvmsg(), sendall(), and dispatchreplies() methods.
    See SockerServer.BaseRequestHandler for parameter details.
    """

    def __init__(self, request, client_address, server):
        """
        Create a BaseAuxRequestHandler instance.

        :param request: request client
        :param str client_address: client address
        :param CoreServer server: core server instance
        """
        self.message_handlers = {
            MessageTypes.NODE.value: self.handle_node_message,
            MessageTypes.LINK.value: self.handle_link_message,
            MessageTypes.EXECUTE.value: self.handle_execute_message,
            MessageTypes.REGISTER.value: self.handle_register_message,
            MessageTypes.CONFIG.value: self.handle_config_message,
            MessageTypes.FILE.value: self.handle_file_message,
            MessageTypes.INTERFACE.value: self.handle_interface_message,
            MessageTypes.EVENT.value: self.handle_event_message,
            MessageTypes.SESSION.value: self.handle_session_message,
        }
        self.handler_threads = []
        self.node_status_request = {}
        self.master = False
        self.session = None
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        """
        New client has connected to the auxiliary server.

        :return: nothing
        """
        logger.info("new auxiliary server client: %s:%s" % self.client_address)

    def handle(self):
        """
        The handler main loop

        :return: nothing
        """
        port = self.request.getpeername()[1]
        self.session = self.server.mainserver.create_session(session_id=port)
        self.session.connect(self)

        while True:
            try:
                messages = self.receive_message()
                if messages:
                    for message in messages:
                        self.handle_message(message)
            except EOFError:
                break
            except IOError:
                logger.exception("IOError in CoreAuxRequestHandler")
                break

    def finish(self):
        """
        Disconnect the client

        :return: nothing
        """
        if self.session:
            self.remove_session_handlers()
            self.session.shutdown()
        return SocketServer.BaseRequestHandler.finish(self)

    def receive_message(self):
        """
        Receive data from the client in the supported format. Parse, transform to CORE API format and
        return transformed messages.

        EXAMPLE:
        return self.handler.request.recv(siz)

        :return: nothing
        """
        raise NotImplemented

    def dispatch_replies(self, replies, message):
        """
        Dispatch CORE replies to a previously received message msg from a client.
        Replies passed to this method follow the CORE API. This method allows transformation to
        the form supported by the auxiliary handler and within the context of "msg".
        Add transformation and transmission code here.

        :param list replies: replies to dispatch
        :param message: message being replied to
        :return: nothing
        """
        raise NotImplemented

    def sendall(self, data):
        """
        CORE calls this method when data needs to be asynchronously sent to a client. The data is
        in CORE API format. This method allows transformation to the required format supported by this
        handler prior to transmission.

        :param data: data to send
        :return: nothing
        """
        raise NotImplemented
