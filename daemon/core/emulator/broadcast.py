from collections.abc import Callable
from typing import TypeVar, Union

from core.emulator.data import (
    ConfigData,
    EventData,
    ExceptionData,
    FileData,
    LinkData,
    NodeData,
)
from core.errors import CoreError

T = TypeVar(
    "T", bound=Union[EventData, ExceptionData, NodeData, LinkData, FileData, ConfigData]
)


class BroadcastManager:
    def __init__(self) -> None:
        """
        Creates a BroadcastManager instance.
        """
        self.handlers: dict[type[T], set[Callable[[T], None]]] = {}

    def send(self, data: T) -> None:
        """
        Retrieve handlers for data, and run all current handlers.

        :param data: data to provide to handlers
        :return: nothing
        """
        handlers = self.handlers.get(type(data), set())
        for handler in handlers:
            handler(data)

    def add_handler(self, data_type: type[T], handler: Callable[[T], None]) -> None:
        """
        Add a handler for a given data type.

        :param data_type: type of data to add handler for
        :param handler: handler to add
        :return: nothing
        """
        handlers = self.handlers.setdefault(data_type, set())
        if handler in handlers:
            raise CoreError(
                f"cannot add data({data_type}) handler({repr(handler)}), "
                f"already exists"
            )
        handlers.add(handler)

    def remove_handler(self, data_type: type[T], handler: Callable[[T], None]) -> None:
        """
        Remove a handler for a given data type.

        :param data_type: type of data to remove handler for
        :param handler: handler to remove
        :return: nothing
        """
        handlers = self.handlers.get(data_type, set())
        if handler not in handlers:
            raise CoreError(
                f"cannot remove data({data_type}) handler({repr(handler)}), "
                f"does not exist"
            )
        handlers.remove(handler)
