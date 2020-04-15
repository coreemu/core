import logging
from queue import Empty, Queue
from typing import Iterable

from core.api.grpc import core_pb2
from core.api.grpc.grpcutils import convert_value
from core.emulator.data import (
    ConfigData,
    EventData,
    ExceptionData,
    FileData,
    LinkData,
    NodeData,
)
from core.emulator.session import Session


def handle_node_event(event: NodeData) -> core_pb2.NodeEvent:
    """
    Handle node event when there is a node event

    :param event: node data
    :return: node event that contains node id, name, model, position, and services
    """
    position = core_pb2.Position(x=event.x_position, y=event.y_position)
    node_proto = core_pb2.Node(
        id=event.id,
        name=event.name,
        model=event.model,
        position=position,
        services=event.services,
    )
    return core_pb2.NodeEvent(node=node_proto, source=event.source)


def handle_link_event(event: LinkData) -> core_pb2.LinkEvent:
    """
    Handle link event when there is a link event

    :param event: link data
    :return: link event that has message type and link information
    """
    interface_one = None
    if event.interface1_id is not None:
        interface_one = core_pb2.Interface(
            id=event.interface1_id,
            name=event.interface1_name,
            mac=convert_value(event.interface1_mac),
            ip4=convert_value(event.interface1_ip4),
            ip4mask=event.interface1_ip4_mask,
            ip6=convert_value(event.interface1_ip6),
            ip6mask=event.interface1_ip6_mask,
        )

    interface_two = None
    if event.interface2_id is not None:
        interface_two = core_pb2.Interface(
            id=event.interface2_id,
            name=event.interface2_name,
            mac=convert_value(event.interface2_mac),
            ip4=convert_value(event.interface2_ip4),
            ip4mask=event.interface2_ip4_mask,
            ip6=convert_value(event.interface2_ip6),
            ip6mask=event.interface2_ip6_mask,
        )

    options = core_pb2.LinkOptions(
        opaque=event.opaque,
        jitter=event.jitter,
        key=event.key,
        mburst=event.mburst,
        mer=event.mer,
        per=event.per,
        bandwidth=event.bandwidth,
        burst=event.burst,
        delay=event.delay,
        dup=event.dup,
        unidirectional=event.unidirectional,
    )
    link = core_pb2.Link(
        type=event.link_type.value,
        node_one_id=event.node1_id,
        node_two_id=event.node2_id,
        interface_one=interface_one,
        interface_two=interface_two,
        options=options,
        network_id=event.network_id,
        label=event.label,
        color=event.color,
    )
    return core_pb2.LinkEvent(message_type=event.message_type.value, link=link)


def handle_session_event(event: EventData) -> core_pb2.SessionEvent:
    """
    Handle session event when there is a session event

    :param event: event data
    :return: session event
    """
    event_time = event.time
    if event_time is not None:
        event_time = float(event_time)
    return core_pb2.SessionEvent(
        node_id=event.node,
        event=event.event_type.value,
        name=event.name,
        data=event.data,
        time=event_time,
    )


def handle_config_event(event: ConfigData) -> core_pb2.ConfigEvent:
    """
    Handle configuration event when there is configuration event

    :param event: configuration data
    :return: configuration event
    """
    return core_pb2.ConfigEvent(
        message_type=event.message_type,
        node_id=event.node,
        object=event.object,
        type=event.type,
        captions=event.captions,
        bitmap=event.bitmap,
        data_values=event.data_values,
        possible_values=event.possible_values,
        groups=event.groups,
        interface=event.interface_number,
        network_id=event.network_id,
        opaque=event.opaque,
        data_types=event.data_types,
    )


def handle_exception_event(event: ExceptionData) -> core_pb2.ExceptionEvent:
    """
    Handle exception event when there is exception event

    :param event: exception data
    :return: exception event
    """
    return core_pb2.ExceptionEvent(
        node_id=event.node,
        level=event.level.value,
        source=event.source,
        date=event.date,
        text=event.text,
        opaque=event.opaque,
    )


def handle_file_event(event: FileData) -> core_pb2.FileEvent:
    """
    Handle file event

    :param event: file data
    :return: file event
    """
    return core_pb2.FileEvent(
        message_type=event.message_type.value,
        node_id=event.node,
        name=event.name,
        mode=event.mode,
        number=event.number,
        type=event.type,
        source=event.source,
        data=event.data,
        compressed_data=event.compressed_data,
    )


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
        self.session = session
        self.event_types = event_types
        self.queue = Queue()
        self.add_handlers()

    def add_handlers(self) -> None:
        """
        Add a session event handler for desired event types.

        :return: nothing
        """
        if core_pb2.EventType.NODE in self.event_types:
            self.session.node_handlers.append(self.queue.put)
        if core_pb2.EventType.LINK in self.event_types:
            self.session.link_handlers.append(self.queue.put)
        if core_pb2.EventType.CONFIG in self.event_types:
            self.session.config_handlers.append(self.queue.put)
        if core_pb2.EventType.FILE in self.event_types:
            self.session.file_handlers.append(self.queue.put)
        if core_pb2.EventType.EXCEPTION in self.event_types:
            self.session.exception_handlers.append(self.queue.put)
        if core_pb2.EventType.SESSION in self.event_types:
            self.session.event_handlers.append(self.queue.put)

    def process(self) -> core_pb2.Event:
        """
        Process the next event in the queue.

        :return: grpc event, or None when invalid event or queue timeout
        """
        event = core_pb2.Event(session_id=self.session.id)
        try:
            data = self.queue.get(timeout=1)
            if isinstance(data, NodeData):
                event.node_event.CopyFrom(handle_node_event(data))
            elif isinstance(data, LinkData):
                event.link_event.CopyFrom(handle_link_event(data))
            elif isinstance(data, EventData):
                event.session_event.CopyFrom(handle_session_event(data))
            elif isinstance(data, ConfigData):
                event.config_event.CopyFrom(handle_config_event(data))
            elif isinstance(data, ExceptionData):
                event.exception_event.CopyFrom(handle_exception_event(data))
            elif isinstance(data, FileData):
                event.file_event.CopyFrom(handle_file_event(data))
            else:
                logging.error("unknown event: %s", data)
                event = None
        except Empty:
            event = None
        return event

    def remove_handlers(self) -> None:
        """
        Remove session event handlers for events being watched.

        :return: nothing
        """
        if core_pb2.EventType.NODE in self.event_types:
            self.session.node_handlers.remove(self.queue.put)
        if core_pb2.EventType.LINK in self.event_types:
            self.session.link_handlers.remove(self.queue.put)
        if core_pb2.EventType.CONFIG in self.event_types:
            self.session.config_handlers.remove(self.queue.put)
        if core_pb2.EventType.FILE in self.event_types:
            self.session.file_handlers.remove(self.queue.put)
        if core_pb2.EventType.EXCEPTION in self.event_types:
            self.session.exception_handlers.remove(self.queue.put)
        if core_pb2.EventType.SESSION in self.event_types:
            self.session.event_handlers.remove(self.queue.put)
