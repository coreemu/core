"""
sdt.py: Scripted Display Tool (SDT3D) helper
"""

import logging
import socket
from typing import IO, TYPE_CHECKING, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from core.constants import CORE_CONF_DIR, CORE_DATA_DIR
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData, NodeData
from core.emulator.enumerations import EventTypes, MessageFlags
from core.errors import CoreError
from core.nodes.base import CoreNetworkBase, NodeBase
from core.nodes.network import WlanNode

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session


def get_link_id(node1_id: int, node2_id: int, network_id: int) -> str:
    link_id = f"{node1_id}-{node2_id}"
    if network_id is not None:
        link_id = f"{link_id}-{network_id}"
    return link_id


CORE_LAYER: str = "CORE"
NODE_LAYER: str = "CORE::Nodes"
LINK_LAYER: str = "CORE::Links"
WIRED_LINK_LAYER: str = f"{LINK_LAYER}::wired"
CORE_LAYERS: List[str] = [CORE_LAYER, LINK_LAYER, NODE_LAYER, WIRED_LINK_LAYER]
DEFAULT_LINK_COLOR: str = "red"


class Sdt:
    """
    Helper class for exporting session objects to NRL"s SDT3D.
    The connect() method initializes the display, and can be invoked
    when a node position or link has changed.
    """

    DEFAULT_SDT_URL: str = "tcp://127.0.0.1:50000/"
    # default altitude (in meters) for flyto view
    DEFAULT_ALT: int = 2500
    # TODO: read in user"s nodes.conf here; below are default node types from the GUI
    DEFAULT_SPRITES: Dict[str, str] = [
        ("router", "router.gif"),
        ("host", "host.gif"),
        ("PC", "pc.gif"),
        ("mdr", "mdr.gif"),
        ("prouter", "router_green.gif"),
        ("hub", "hub.gif"),
        ("lanswitch", "lanswitch.gif"),
        ("wlan", "wlan.gif"),
        ("rj45", "rj45.gif"),
        ("tunnel", "tunnel.gif"),
    ]

    def __init__(self, session: "Session") -> None:
        """
        Creates a Sdt instance.

        :param session: session this manager is tied to
        """
        self.session: "Session" = session
        self.sock: Optional[IO] = None
        self.connected: bool = False
        self.url: str = self.DEFAULT_SDT_URL
        self.address: Optional[Tuple[Optional[str], Optional[int]]] = None
        self.protocol: Optional[str] = None
        self.network_layers: Set[str] = set()
        self.session.node_handlers.append(self.handle_node_update)
        self.session.link_handlers.append(self.handle_link_update)

    def is_enabled(self) -> bool:
        """
        Check for "enablesdt" session option. Return False by default if
        the option is missing.

        :return: True if enabled, False otherwise
        """
        return self.session.options.get_config("enablesdt") == "1"

    def seturl(self) -> None:
        """
        Read "sdturl" from session options, or use the default value.
        Set self.url, self.address, self.protocol

        :return: nothing
        """
        url = self.session.options.get_config("stdurl", default=self.DEFAULT_SDT_URL)
        self.url = urlparse(url)
        self.address = (self.url.hostname, self.url.port)
        self.protocol = self.url.scheme

    def connect(self) -> bool:
        """
        Connect to the SDT address/port if enabled.

        :return: True if connected, False otherwise
        """
        if not self.is_enabled():
            return False
        if self.connected:
            return True
        if self.session.state == EventTypes.SHUTDOWN_STATE:
            return False

        self.seturl()
        logger.info("connecting to SDT at %s://%s", self.protocol, self.address)
        if self.sock is None:
            try:
                if self.protocol.lower() == "udp":
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.sock.connect(self.address)
                else:
                    # Default to tcp
                    self.sock = socket.create_connection(self.address, 5)
            except IOError:
                logger.exception("SDT socket connect error")
                return False

        if not self.initialize():
            return False

        self.connected = True
        # refresh all objects in SDT3D when connecting after session start
        if not self.sendobjs():
            return False
        return True

    def initialize(self) -> bool:
        """
        Load icon sprites, and fly to the reference point location on
        the virtual globe.

        :return: initialize command status
        """
        if not self.cmd(f'path "{CORE_DATA_DIR}/icons/normal"'):
            return False
        # send node type to icon mappings
        for node_type, icon in self.DEFAULT_SPRITES:
            if not self.cmd(f"sprite {node_type} image {icon}"):
                return False
        lat, long = self.session.location.refgeo[:2]
        return self.cmd(f"flyto {long:.6f},{lat:.6f},{self.DEFAULT_ALT}")

    def disconnect(self) -> None:
        """
        Disconnect from SDT.

        :return: nothing
        """
        if self.sock:
            try:
                self.sock.close()
            except IOError:
                logger.error("error closing socket")
            finally:
                self.sock = None

        self.connected = False

    def shutdown(self) -> None:
        """
        Invoked from Session.shutdown() and Session.checkshutdown().

        :return: nothing
        """
        self.cmd("clear all")
        for layer in self.network_layers:
            self.cmd(f"delete layer,{layer}")
        for layer in CORE_LAYERS[::-1]:
            self.cmd(f"delete layer,{layer}")
        self.disconnect()
        self.network_layers.clear()

    def cmd(self, cmdstr: str) -> bool:
        """
        Send an SDT command over a UDP socket. socket.sendall() is used
        as opposed to socket.sendto() because an exception is raised when
        there is no socket listener.

        :param cmdstr: command to send
        :return: True if command was successful, False otherwise
        """
        if self.sock is None:
            return False

        try:
            cmd = f"{cmdstr}\n".encode()
            logger.debug("sdt cmd: %s", cmd)
            self.sock.sendall(cmd)
            return True
        except IOError:
            logger.exception("SDT connection error")
            self.sock = None
            self.connected = False
            return False

    def sendobjs(self) -> None:
        """
        Session has already started, and the SDT3D GUI later connects.
        Send all node and link objects for display. Otherwise, nodes and
        links will only be drawn when they have been updated (e.g. moved).

        :return: nothing
        """
        nets = []
        # create layers
        for layer in CORE_LAYERS:
            self.cmd(f"layer {layer}")

        with self.session.nodes_lock:
            for node_id in self.session.nodes:
                node = self.session.nodes[node_id]
                if isinstance(node, CoreNetworkBase):
                    nets.append(node)
                if not isinstance(node, NodeBase):
                    continue
                self.add_node(node)

            for net in nets:
                all_links = net.links(flags=MessageFlags.ADD)
                for link_data in all_links:
                    is_wireless = isinstance(net, (WlanNode, EmaneNet))
                    if is_wireless and link_data.node1_id == net.id:
                        continue
                    self.handle_link_update(link_data)

    def get_node_position(self, node: NodeBase) -> Optional[str]:
        """
        Convenience to generate an SDT position string, given a node.

        :param node:
        :return:
        """
        x, y, z = node.position.get()
        if x is None or y is None:
            return None
        lat, lon, alt = self.session.location.getgeo(x, y, z)
        return f"pos {lon:.6f},{lat:.6f},{alt:.6f}"

    def add_node(self, node: NodeBase) -> None:
        """
        Handle adding a node in SDT.

        :param node: node to add
        :return: nothing
        """
        logger.debug("sdt add node: %s - %s", node.id, node.name)
        if not self.connect():
            return
        pos = self.get_node_position(node)
        if not pos:
            return
        node_type = node.type
        if node_type is None:
            node_type = type(node).type
        icon = node.icon
        if icon:
            node_type = node.name
            icon = icon.replace("$CORE_DATA_DIR", str(CORE_DATA_DIR))
            icon = icon.replace("$CORE_CONF_DIR", str(CORE_CONF_DIR))
            self.cmd(f"sprite {node_type} image {icon}")
        self.cmd(
            f'node {node.id} nodeLayer "{NODE_LAYER}" '
            f'type {node_type} label on,"{node.name}" {pos}'
        )

    def edit_node(self, node: NodeBase, lon: float, lat: float, alt: float) -> None:
        """
        Handle updating a node in SDT.

        :param node: node to update
        :param lon: node longitude
        :param lat: node latitude
        :param alt: node altitude
        :return: nothing
        """
        logger.debug("sdt update node: %s - %s", node.id, node.name)
        if not self.connect():
            return

        if all([lat is not None, lon is not None, alt is not None]):
            pos = f"pos {lon:.6f},{lat:.6f},{alt:.6f}"
            self.cmd(f"node {node.id} {pos}")
        else:
            pos = self.get_node_position(node)
            if not pos:
                return
            self.cmd(f"node {node.id} {pos}")

    def delete_node(self, node_id: int) -> None:
        """
        Handle deleting a node in SDT.

        :param node_id: node id to delete
        :return: nothing
        """
        logger.debug("sdt delete node: %s", node_id)
        if not self.connect():
            return
        self.cmd(f"delete node,{node_id}")

    def handle_node_update(self, node_data: NodeData) -> None:
        """
        Handler for node updates, specifically for updating their location.

        :param node_data: node data being updated
        :return: nothing
        """
        if not self.connect():
            return
        node = node_data.node
        logger.debug("sdt handle node update: %s - %s", node.id, node.name)
        if node_data.message_type == MessageFlags.DELETE:
            self.cmd(f"delete node,{node.id}")
        else:
            x, y, _ = node.position.get()
            lon, lat, alt = node.position.get_geo()
            if all([lat is not None, lon is not None, alt is not None]):
                pos = f"pos {lon:.6f},{lat:.6f},{alt:.6f}"
                self.cmd(f"node {node.id} {pos}")
            elif node_data.message_type == MessageFlags.NONE:
                lat, lon, alt = self.session.location.getgeo(x, y, 0)
                pos = f"pos {lon:.6f},{lat:.6f},{alt:.6f}"
                self.cmd(f"node {node.id} {pos}")

    def wireless_net_check(self, node_id: int) -> bool:
        """
        Determines if a node is either a wireless node type.

        :param node_id: node id to check
        :return: True is a wireless node type, False otherwise
        """
        result = False
        try:
            node = self.session.get_node(node_id, NodeBase)
            result = isinstance(node, (WlanNode, EmaneNet))
        except CoreError:
            pass
        return result

    def add_link(
        self, node1_id: int, node2_id: int, network_id: int = None, label: str = None
    ) -> None:
        """
        Handle adding a link in SDT.

        :param node1_id: node one id
        :param node2_id: node two id
        :param network_id: network link is associated with, None otherwise
        :param label: label for link
        :return: nothing
        """
        logger.debug("sdt add link: %s, %s, %s", node1_id, node2_id, network_id)
        if not self.connect():
            return
        if self.wireless_net_check(node1_id) or self.wireless_net_check(node2_id):
            return
        color = DEFAULT_LINK_COLOR
        if network_id:
            color = self.session.get_link_color(network_id)
        line = f"{color},2"
        link_id = get_link_id(node1_id, node2_id, network_id)
        if network_id:
            layer = self.get_network_layer(network_id)
        else:
            layer = WIRED_LINK_LAYER
        link_label = ""
        if label:
            link_label = f'linklabel on,"{label}"'
        self.cmd(
            f"link {node1_id},{node2_id},{link_id} linkLayer {layer} line {line} "
            f"{link_label}"
        )

    def get_network_layer(self, network_id: int) -> str:
        node = self.session.nodes.get(network_id)
        if node:
            layer = f"{LINK_LAYER}::{node.name}"
            self.network_layers.add(layer)
        else:
            layer = WIRED_LINK_LAYER
        return layer

    def delete_link(self, node1_id: int, node2_id: int, network_id: int = None) -> None:
        """
        Handle deleting a link in SDT.

        :param node1_id: node one id
        :param node2_id: node two id
        :param network_id: network link is associated with, None otherwise
        :return: nothing
        """
        logger.debug("sdt delete link: %s, %s, %s", node1_id, node2_id, network_id)
        if not self.connect():
            return
        if self.wireless_net_check(node1_id) or self.wireless_net_check(node2_id):
            return
        link_id = get_link_id(node1_id, node2_id, network_id)
        self.cmd(f"delete link,{node1_id},{node2_id},{link_id}")

    def edit_link(
        self, node1_id: int, node2_id: int, network_id: int, label: str
    ) -> None:
        """
        Handle editing a link in SDT.

        :param node1_id: node one id
        :param node2_id: node two id
        :param network_id: network link is associated with, None otherwise
        :param label: label to update
        :return: nothing
        """
        logger.debug("sdt edit link: %s, %s, %s", node1_id, node2_id, network_id)
        if not self.connect():
            return
        if self.wireless_net_check(node1_id) or self.wireless_net_check(node2_id):
            return
        link_id = get_link_id(node1_id, node2_id, network_id)
        link_label = f'linklabel on,"{label}"'
        self.cmd(f"link {node1_id},{node2_id},{link_id} {link_label}")

    def handle_link_update(self, link_data: LinkData) -> None:
        """
        Handle link broadcast messages and push changes to SDT.

        :param link_data: link data to handle
        :return: nothing
        """
        node1_id = link_data.node1_id
        node2_id = link_data.node2_id
        network_id = link_data.network_id
        label = link_data.label
        if link_data.message_type == MessageFlags.ADD:
            self.add_link(node1_id, node2_id, network_id, label)
        elif link_data.message_type == MessageFlags.DELETE:
            self.delete_link(node1_id, node2_id, network_id)
        elif link_data.message_type == MessageFlags.NONE and label:
            self.edit_link(node1_id, node2_id, network_id, label)
