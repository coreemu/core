"""
sdt.py: Scripted Display Tool (SDT3D) helper
"""

import logging
import socket
import threading
from typing import TYPE_CHECKING, Optional, Tuple
from urllib.parse import urlparse

from core import constants
from core.constants import CORE_DATA_DIR
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData, NodeData
from core.emulator.enumerations import EventTypes, LinkTypes, MessageFlags
from core.errors import CoreError
from core.nodes.base import CoreNetworkBase, NodeBase
from core.nodes.network import WlanNode

if TYPE_CHECKING:
    from core.emulator.session import Session


def link_data_params(link_data: LinkData) -> Tuple[int, int, bool]:
    node_one = link_data.node1_id
    node_two = link_data.node2_id
    is_wireless = link_data.link_type == LinkTypes.WIRELESS.value
    return node_one, node_two, is_wireless


class Sdt:
    """
    Helper class for exporting session objects to NRL"s SDT3D.
    The connect() method initializes the display, and can be invoked
    when a node position or link has changed.
    """

    DEFAULT_SDT_URL = "tcp://127.0.0.1:50000/"
    # default altitude (in meters) for flyto view
    DEFAULT_ALT = 2500
    # TODO: read in user"s nodes.conf here; below are default node types from the GUI
    DEFAULT_SPRITES = [
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
        self.session = session
        self.lock = threading.Lock()
        self.sock = None
        self.connected = False
        self.showerror = True
        self.url = self.DEFAULT_SDT_URL
        self.address = None
        self.protocol = None
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

    def connect(self, flags: int = 0) -> bool:
        """
        Connect to the SDT address/port if enabled.

        :return: True if connected, False otherwise
        """
        if not self.is_enabled():
            return False
        if self.connected:
            return True
        if self.session.state == EventTypes.SHUTDOWN_STATE.value:
            return False

        self.seturl()
        logging.info("connecting to SDT at %s://%s", self.protocol, self.address)
        if self.sock is None:
            try:
                if self.protocol.lower() == "udp":
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.sock.connect(self.address)
                else:
                    # Default to tcp
                    self.sock = socket.create_connection(self.address, 5)
            except IOError:
                logging.exception("SDT socket connect error")
                return False

        if not self.initialize():
            return False

        self.connected = True
        # refresh all objects in SDT3D when connecting after session start
        if not flags & MessageFlags.ADD.value and not self.sendobjs():
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
                logging.error("error closing socket")
            finally:
                self.sock = None

        self.connected = False

    def shutdown(self) -> None:
        """
        Invoked from Session.shutdown() and Session.checkshutdown().

        :return: nothing
        """
        self.cmd("clear all")
        self.disconnect()
        self.showerror = True

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
            logging.debug("sdt cmd: %s", cmd)
            self.sock.sendall(cmd)
            return True
        except IOError:
            logging.exception("SDT connection error")
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
        with self.session._nodes_lock:
            for node_id in self.session.nodes:
                node = self.session.nodes[node_id]
                if isinstance(node, CoreNetworkBase):
                    nets.append(node)
                if not isinstance(node, NodeBase):
                    continue
                self.add_node(node)

            for net in nets:
                all_links = net.all_link_data(flags=MessageFlags.ADD.value)
                for link_data in all_links:
                    is_wireless = isinstance(net, (WlanNode, EmaneNet))
                    if is_wireless and link_data.node1_id == net.id:
                        continue
                    params = link_data_params(link_data)
                    self.add_link(*params)

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
        logging.debug("sdt add node: %s - %s", node.id, node.name)
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
            icon = icon.replace("$CORE_DATA_DIR", constants.CORE_DATA_DIR)
            icon = icon.replace("$CORE_CONF_DIR", constants.CORE_CONF_DIR)
            self.cmd(f"sprite {node_type} image {icon}")
        self.cmd(f'node {node.id} type {node_type} label on,"{node.name}" {pos}')

    def edit_node(self, node: NodeBase) -> None:
        """
        Handle updating a node in SDT.

        :param node: node to update
        :return: nothing
        """
        logging.debug("sdt update node: %s - %s", node.id, node.name)
        if not self.connect():
            return
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
        logging.debug("sdt delete node: %s", node_id)
        if not self.connect():
            return
        self.cmd(f"delete node,{node_id}")

    def handle_node_update(self, node_data: NodeData) -> None:
        """
        Handler for node updates, specifically for updating their location.

        :param node_data: node data being updated
        :return: nothing
        """
        logging.debug("sdt handle node update: %s - %s", node_data.id, node_data.name)
        if not self.connect():
            return

        # delete node
        if node_data.message_type == MessageFlags.DELETE.value:
            self.cmd(f"delete node,{node_data.id}")
        else:
            x = node_data.x_position
            y = node_data.y_position
            lat = node_data.latitude
            lon = node_data.longitude
            alt = node_data.altitude
            if all([lat is not None, lon is not None, alt is not None]):
                pos = f"pos {lon:.6f},{lat:.6f},{alt:.6f}"
                self.cmd(f"node {node_data.id} {pos}")
            elif node_data.message_type == 0:
                lat, lon, alt = self.session.location.getgeo(x, y, 0)
                pos = f"pos {lon:.6f},{lat:.6f},{alt:.6f}"
                self.cmd(f"node {node_data.id} {pos}")

    def wireless_net_check(self, node_id: int) -> bool:
        """
        Determines if a node is either a wireless node type.

        :param node_id: node id to check
        :return: True is a wireless node type, False otherwise
        """
        result = False
        try:
            node = self.session.get_node(node_id)
            result = isinstance(node, (WlanNode, EmaneNet))
        except CoreError:
            pass
        return result

    def add_link(self, node_one: int, node_two: int, is_wireless: bool) -> None:
        """
        Handle adding a link in SDT.

        :param node_one: node one id
        :param node_two: node two id
        :param is_wireless: True if link is wireless, False otherwise
        :return: nothing
        """
        logging.debug("sdt add link: %s, %s, %s", node_one, node_two, is_wireless)
        if not self.connect():
            return
        if self.wireless_net_check(node_one) or self.wireless_net_check(node_two):
            return
        if is_wireless:
            attr = "green,2"
        else:
            attr = "red,2"
        self.cmd(f"link {node_one},{node_two} line {attr}")

    def delete_link(self, node_one: int, node_two: int) -> None:
        """
        Handle deleting a node in SDT.

        :param node_one: node one id
        :param node_two: node two id
        :return: nothing
        """
        logging.debug("sdt delete link: %s, %s", node_one, node_two)
        if not self.connect():
            return
        if self.wireless_net_check(node_one) or self.wireless_net_check(node_two):
            return
        self.cmd(f"delete link,{node_one},{node_two}")

    def handle_link_update(self, link_data: LinkData) -> None:
        """
        Handle link broadcast messages and push changes to SDT.

        :param link_data: link data to handle
        :return: nothing
        """
        if link_data.message_type == MessageFlags.ADD.value:
            params = link_data_params(link_data)
            self.add_link(*params)
        elif link_data.message_type == MessageFlags.DELETE.value:
            params = link_data_params(link_data)
            self.delete_link(*params[:2])
