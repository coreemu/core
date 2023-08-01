"""
Provides functionality for maintaining information about known links
for a session.
"""

import logging
from collections.abc import ValuesView
from dataclasses import dataclass
from typing import Optional

from core.emulator.data import LinkData, LinkOptions
from core.emulator.enumerations import LinkTypes, MessageFlags
from core.errors import CoreError
from core.nodes.base import NodeBase
from core.nodes.interface import CoreInterface
from core.nodes.network import PtpNet

logger = logging.getLogger(__name__)
LinkKeyType = tuple[int, Optional[int], int, Optional[int]]


def create_key(
    node1: NodeBase,
    iface1: Optional[CoreInterface],
    node2: NodeBase,
    iface2: Optional[CoreInterface],
) -> LinkKeyType:
    """
    Creates a unique key for tracking links.

    :param node1: first node in link
    :param iface1: node1 interface
    :param node2: second node in link
    :param iface2: node2 interface
    :return: link key
    """
    iface1_id = iface1.id if iface1 else None
    iface2_id = iface2.id if iface2 else None
    if node1.id < node2.id:
        return node1.id, iface1_id, node2.id, iface2_id
    else:
        return node2.id, iface2_id, node1.id, iface1_id


@dataclass
class CoreLink:
    """
    Provides a core link data structure.
    """

    node1: NodeBase
    iface1: Optional[CoreInterface]
    node2: NodeBase
    iface2: Optional[CoreInterface]
    ptp: PtpNet = None
    label: str = None
    color: str = None

    def key(self) -> LinkKeyType:
        """
        Retrieve the key for this link.

        :return: link key
        """
        return create_key(self.node1, self.iface1, self.node2, self.iface2)

    def is_unidirectional(self) -> bool:
        """
        Checks if this link is considered unidirectional, due to current
        iface configurations.

        :return: True if unidirectional, False otherwise
        """
        unidirectional = False
        if self.iface1 and self.iface2:
            unidirectional = self.iface1.options != self.iface2.options
        return unidirectional

    def options(self) -> LinkOptions:
        """
        Retrieve the options for this link.

        :return: options for this link
        """
        if self.is_unidirectional():
            options = self.iface1.options
        else:
            if self.iface1:
                options = self.iface1.options
            else:
                options = self.iface2.options
        return options

    def get_data(self, message_type: MessageFlags, source: str = None) -> LinkData:
        """
        Create link data for this link.

        :param message_type: link data message type
        :param source: source for this data
        :return: link data
        """
        iface1_data = self.iface1.get_data() if self.iface1 else None
        iface2_data = self.iface2.get_data() if self.iface2 else None
        return LinkData(
            message_type=message_type,
            type=LinkTypes.WIRED,
            node1_id=self.node1.id,
            node2_id=self.node2.id,
            iface1=iface1_data,
            iface2=iface2_data,
            options=self.options(),
            label=self.label,
            color=self.color,
            source=source,
        )

    def get_data_unidirectional(self, source: str = None) -> LinkData:
        """
        Create other unidirectional link data.

        :param source: source for this data
        :return: unidirectional link data
        """
        iface1_data = self.iface1.get_data() if self.iface1 else None
        iface2_data = self.iface2.get_data() if self.iface2 else None
        return LinkData(
            message_type=MessageFlags.NONE,
            type=LinkTypes.WIRED,
            node1_id=self.node2.id,
            node2_id=self.node1.id,
            iface1=iface2_data,
            iface2=iface1_data,
            options=self.iface2.options,
            label=self.label,
            color=self.color,
            source=source,
        )


class LinkManager:
    """
    Provides core link management.
    """

    def __init__(self) -> None:
        """
        Create a LinkManager instance.
        """
        self._links: dict[LinkKeyType, CoreLink] = {}
        self._node_links: dict[int, dict[LinkKeyType, CoreLink]] = {}

    def add(self, core_link: CoreLink) -> None:
        """
        Add a core link to be tracked.

        :param core_link: link to track
        :return: nothing
        """
        node1, iface1 = core_link.node1, core_link.iface1
        node2, iface2 = core_link.node2, core_link.iface2
        if core_link.key() in self._links:
            raise CoreError(
                f"node1({node1.name}) iface1({iface1.id}) "
                f"node2({node2.name}) iface2({iface2.id}) link already exists"
            )
        logger.info(
            "adding link from node(%s:%s) to node(%s:%s)",
            node1.name,
            iface1.name if iface1 else None,
            node2.name,
            iface2.name if iface2 else None,
        )
        self._links[core_link.key()] = core_link
        node1_links = self._node_links.setdefault(node1.id, {})
        node1_links[core_link.key()] = core_link
        node2_links = self._node_links.setdefault(node2.id, {})
        node2_links[core_link.key()] = core_link

    def delete(
        self,
        node1: NodeBase,
        iface1: Optional[CoreInterface],
        node2: NodeBase,
        iface2: Optional[CoreInterface],
    ) -> CoreLink:
        """
        Remove a link from being tracked.

        :param node1: first node in link
        :param iface1: node1 interface
        :param node2: second node in link
        :param iface2: node2 interface
        :return: removed core link
        """
        key = create_key(node1, iface1, node2, iface2)
        if key not in self._links:
            raise CoreError(
                f"node1({node1.name}) iface1({iface1.id}) "
                f"node2({node2.name}) iface2({iface2.id}) is not linked"
            )
        logger.info(
            "deleting link from node(%s:%s) to node(%s:%s)",
            node1.name,
            iface1.name if iface1 else None,
            node2.name,
            iface2.name if iface2 else None,
        )
        node1_links = self._node_links[node1.id]
        node1_links.pop(key)
        node2_links = self._node_links[node2.id]
        node2_links.pop(key)
        return self._links.pop(key)

    def reset(self) -> None:
        """
        Resets and clears all tracking information.

        :return: nothing
        """
        self._links.clear()
        self._node_links.clear()

    def get_link(
        self,
        node1: NodeBase,
        iface1: Optional[CoreInterface],
        node2: NodeBase,
        iface2: Optional[CoreInterface],
    ) -> Optional[CoreLink]:
        """
        Retrieve a link for provided values.

        :param node1: first node in link
        :param iface1: interface for node1
        :param node2: second node in link
        :param iface2: interface for node2
        :return: core link if present, None otherwise
        """
        key = create_key(node1, iface1, node2, iface2)
        return self._links.get(key)

    def links(self) -> ValuesView[CoreLink]:
        """
        Retrieve all known links

        :return: iterator for all known links
        """
        return self._links.values()

    def node_links(self, node: NodeBase) -> ValuesView[CoreLink]:
        """
        Retrieve all links for a given node.

        :param node: node to get links for
        :return: node links
        """
        return self._node_links.get(node.id, {}).values()
