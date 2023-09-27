import logging
from collections.abc import Iterable
from queue import Empty, Queue
from typing import Optional

from core.api.grpc import core_pb2, grpcutils
from core.api.grpc.grpcutils import convert_link_data
from core.emulator.data import EventData, ExceptionData, LinkData, NodeData
from core.emulator.session import Session

logger = logging.getLogger(__name__)


def handle_node_event(session: Session, node_data: NodeData) -> core_pb2.Event:
    """
    Handle node event when there is a node event

    :param session: session node is from
    :param node_data: node data
    :return: node event that contains node id, name, model, position, and services
    """
    node = node_data.node
    emane_configs = grpcutils.get_emane_model_configs_dict(session)
    node_emane_configs = emane_configs.get(node.id, [])
    node_proto = grpcutils.get_node_proto(session, node, node_emane_configs)
    message_type = node_data.message_type.value
    node_event = core_pb2.NodeEvent(message_type=message_type, node=node_proto)
    return core_pb2.Event(node_event=node_event, source=node_data.source)


def handle_link_event(link_data: LinkData) -> core_pb2.Event:
    """
    Handle link event when there is a link event

    :param link_data: link data
    :return: link event that has message type and link information
    """
    link = convert_link_data(link_data)
    message_type = link_data.message_type.value
    link_event = core_pb2.LinkEvent(message_type=message_type, link=link)
    return core_pb2.Event(link_event=link_event, source=link_data.source)


def handle_session_event(event_data: EventData) -> core_pb2.Event:
    """
    Handle session event when there is a session event

    :param event_data: event data
    :return: session event
    """
    event_time = event_data.time
    if event_time is not None:
        event_time = float(event_time)
    session_event = core_pb2.SessionEvent(
        node_id=event_data.node,
        event=event_data.event_type.value,
        name=event_data.name,
        data=event_data.data,
        time=event_time,
    )
    return core_pb2.Event(session_event=session_event)


def handle_exception_event(exception_data: ExceptionData) -> core_pb2.Event:
    """
    Handle exception event when there is exception event

    :param exception_data: exception data
    :return: exception event
    """
    exception_event = core_pb2.ExceptionEvent(
        node_id=exception_data.node,
        level=exception_data.level.value,
        source=exception_data.source,
        date=exception_data.date,
        text=exception_data.text,
        opaque=exception_data.opaque,
    )
    return core_pb2.Event(exception_event=exception_event)


class EventStreamer:
    """
    Processes session events to generate grpc events.
    """

    def __init__(
        self, session: Session, event_types: Iterable[core_pb2.EventType]
    ) -> None:
        """
        Create a EventStreamer instance.

        :param session: session to process events for
        :param event_types: types of events to process
        """
        self.session: Session = session
        self.event_types: Iterable[core_pb2.EventType] = event_types
        self.queue: Queue = Queue()
        self.add_handlers()

    def add_handlers(self) -> None:
        """
        Add a session event handler for desired event types.

        :return: nothing
        """
        if core_pb2.EventType.NODE in self.event_types:
            self.session.broadcast_manager.add_handler(NodeData, self.queue.put)
        if core_pb2.EventType.LINK in self.event_types:
            self.session.broadcast_manager.add_handler(LinkData, self.queue.put)
        if core_pb2.EventType.EXCEPTION in self.event_types:
            self.session.broadcast_manager.add_handler(ExceptionData, self.queue.put)
        if core_pb2.EventType.SESSION in self.event_types:
            self.session.broadcast_manager.add_handler(EventData, self.queue.put)

    def process(self) -> Optional[core_pb2.Event]:
        """
        Process the next event in the queue.

        :return: grpc event, or None when invalid event or queue timeout
        """
        event = None
        try:
            data = self.queue.get(timeout=1)
            if isinstance(data, NodeData):
                event = handle_node_event(self.session, data)
            elif isinstance(data, LinkData):
                event = handle_link_event(data)
            elif isinstance(data, EventData):
                event = handle_session_event(data)
            elif isinstance(data, ExceptionData):
                event = handle_exception_event(data)
            else:
                logger.error("unknown event: %s", data)
        except Empty:
            pass
        if event:
            event.session_id = self.session.id
        return event

    def remove_handlers(self) -> None:
        """
        Remove session event handlers for events being watched.

        :return: nothing
        """
        if core_pb2.EventType.NODE in self.event_types:
            self.session.broadcast_manager.remove_handler(NodeData, self.queue.put)
        if core_pb2.EventType.LINK in self.event_types:
            self.session.broadcast_manager.remove_handler(LinkData, self.queue.put)
        if core_pb2.EventType.EXCEPTION in self.event_types:
            self.session.broadcast_manager.remove_handler(ExceptionData, self.queue.put)
        if core_pb2.EventType.SESSION in self.event_types:
            self.session.broadcast_manager.remove_handler(EventData, self.queue.put)
