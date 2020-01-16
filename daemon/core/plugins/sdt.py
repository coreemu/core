"""
sdt.py: Scripted Display Tool (SDT3D) helper
"""

import logging
import socket
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse

from core import constants
from core.api.tlv.coreapi import CoreLinkMessage, CoreMessage, CoreNodeMessage
from core.constants import CORE_DATA_DIR
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData, NodeData
from core.emulator.enumerations import (
    EventTypes,
    LinkTlvs,
    LinkTypes,
    MessageFlags,
    NodeTlvs,
    NodeTypes,
)
from core.errors import CoreError
from core.nodes.base import CoreNetworkBase, NodeBase
from core.nodes.network import WlanNode

if TYPE_CHECKING:
    from core.emulator.session import Session


# TODO: A named tuple may be more appropriate, than abusing a class dict like this
class Bunch:
    """
    Helper class for recording a collection of attributes.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Create a Bunch instance.

        :param kwargs: keyword arguments
        """
        self.__dict__.update(kwargs)


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
        self.sock = None
        self.connected = False
        self.showerror = True
        self.url = self.DEFAULT_SDT_URL
        # node information for remote nodes not in session._objs
        # local nodes also appear here since their obj may not exist yet
        self.remotes = {}

        # add handler for node updates
        self.session.node_handlers.append(self.handle_node_update)

        # add handler for link updates
        self.session.link_handlers.append(self.handle_link_update)

    def handle_node_update(self, node_data: NodeData) -> None:
        """
        Handler for node updates, specifically for updating their location.

        :param node_data: node data being updated
        :return: nothing
        """
        x = node_data.x_position
        y = node_data.y_position
        lat = node_data.latitude
        lon = node_data.longitude
        alt = node_data.altitude

        if all([lat, lon, alt]):
            self.updatenodegeo(
                node_data.id,
                node_data.latitude,
                node_data.longitude,
                node_data.altitude,
            )

        if node_data.message_type == 0:
            # TODO: z is not currently supported by node messages
            self.updatenode(node_data.id, 0, x, y, 0)

    def handle_link_update(self, link_data: LinkData) -> None:
        """
        Handler for link updates, checking for wireless link/unlink messages.

        :param link_data: link data being updated
        :return: nothing
        """
        if link_data.link_type == LinkTypes.WIRELESS.value:
            self.updatelink(
                link_data.node1_id,
                link_data.node2_id,
                link_data.message_type,
                wireless=True,
            )

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
        url = self.session.options.get_config("stdurl")
        if not url:
            url = self.DEFAULT_SDT_URL
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
            logging.info("sdt: %s", cmdstr)
            self.sock.sendall(f"{cmdstr}\n")
            return True
        except IOError:
            logging.exception("SDT connection error")
            self.sock = None
            self.connected = False
            return False

    def updatenode(
        self,
        nodenum: int,
        flags: int,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        name: str = None,
        node_type: str = None,
        icon: str = None,
    ) -> None:
        """
        Node is updated from a Node Message or mobility script.

        :param nodenum: node id to update
        :param flags: update flags
        :param x: x position
        :param y: y position
        :param z: z position
        :param name: node name
        :param node_type: node type
        :param icon: node icon
        :return: nothing
        """
        if not self.connect():
            return
        if flags & MessageFlags.DELETE.value:
            self.cmd(f"delete node,{nodenum}")
            return
        if x is None or y is None:
            return
        lat, lon, alt = self.session.location.getgeo(x, y, z)
        pos = f"pos {lon:.6f},{lat:.6f},{alt:.6f}"
        if flags & MessageFlags.ADD.value:
            if icon is not None:
                node_type = name
                icon = icon.replace("$CORE_DATA_DIR", constants.CORE_DATA_DIR)
                icon = icon.replace("$CORE_CONF_DIR", constants.CORE_CONF_DIR)
                self.cmd(f"sprite {node_type} image {icon}")
            self.cmd(f'node {nodenum} type {node_type} label on,"{name}" {pos}')
        else:
            self.cmd(f"node {nodenum} {pos}")

    def updatenodegeo(self, nodenum: int, lat: float, lon: float, alt: float) -> None:
        """
        Node is updated upon receiving an EMANE Location Event.

        :param nodenum: node id to update geospatial for
        :param lat: latitude
        :param lon: longitude
        :param alt: altitude
        :return: nothing
        """

        # TODO: received Node Message with lat/long/alt.
        if not self.connect():
            return
        pos = f"pos {lon:.6f},{lat:.6f},{alt:.6f}"
        self.cmd(f"node {nodenum} {pos}")

    def updatelink(
        self, node1num: int, node2num: int, flags: int, wireless: bool = False
    ) -> None:
        """
        Link is updated from a Link Message or by a wireless model.

        :param node1num: node one id
        :param node2num: node two id
        :param flags: link flags
        :param wireless: flag to check if wireless or not
        :return: nothing
        """
        if node1num is None or node2num is None:
            return
        if not self.connect():
            return
        if flags & MessageFlags.DELETE.value:
            self.cmd(f"delete link,{node1num},{node2num}")
        elif flags & MessageFlags.ADD.value:
            if wireless:
                attr = " line green,2"
            else:
                attr = " line red,2"
            self.cmd(f"link {node1num},{node2num}{attr}")

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
                (x, y, z) = node.getposition()
                if x is None or y is None:
                    continue
                self.updatenode(
                    node.id,
                    MessageFlags.ADD.value,
                    x,
                    y,
                    z,
                    node.name,
                    node.type,
                    node.icon,
                )
            for nodenum in sorted(self.remotes.keys()):
                r = self.remotes[nodenum]
                x, y, z = r.pos
                self.updatenode(
                    nodenum, MessageFlags.ADD.value, x, y, z, r.name, r.type, r.icon
                )

            for net in nets:
                all_links = net.all_link_data(flags=MessageFlags.ADD.value)
                for link_data in all_links:
                    is_wireless = isinstance(net, (WlanNode, EmaneNet))
                    wireless_link = link_data.message_type == LinkTypes.WIRELESS.value
                    if is_wireless and link_data.node1_id == net.id:
                        continue

                    self.updatelink(
                        link_data.node1_id,
                        link_data.node2_id,
                        MessageFlags.ADD.value,
                        wireless_link,
                    )

            for n1num in sorted(self.remotes.keys()):
                r = self.remotes[n1num]
                for n2num, wireless_link in r.links:
                    self.updatelink(n1num, n2num, MessageFlags.ADD.value, wireless_link)

    def handle_distributed(self, message: CoreMessage) -> None:
        """
        Broker handler for processing CORE API messages as they are
        received. This is used to snoop the Node messages and update
        node positions.

        :param message: message to handle
        :return: nothing
        """
        if isinstance(message, CoreLinkMessage):
            self.handlelinkmsg(message)
        elif isinstance(message, CoreNodeMessage):
            self.handlenodemsg(message)

    def handlenodemsg(self, msg: CoreNodeMessage) -> None:
        """
        Process a Node Message to add/delete or move a node on
        the SDT display. Node properties are found in a session or
        self.remotes for remote nodes (or those not yet instantiated).

        :param msg: node message to handle
        :return: nothing
        """
        # for distributed sessions to work properly, the SDT option should be
        # enabled prior to starting the session
        if not self.is_enabled():
            return
        # node.(_id, type, icon, name) are used.
        nodenum = msg.get_tlv(NodeTlvs.NUMBER.value)
        if not nodenum:
            return
        x = msg.get_tlv(NodeTlvs.X_POSITION.value)
        y = msg.get_tlv(NodeTlvs.Y_POSITION.value)
        z = None
        name = msg.get_tlv(NodeTlvs.NAME.value)

        nodetype = msg.get_tlv(NodeTlvs.TYPE.value)
        model = msg.get_tlv(NodeTlvs.MODEL.value)
        icon = msg.get_tlv(NodeTlvs.ICON.value)

        net = False
        if nodetype == NodeTypes.DEFAULT.value or nodetype == NodeTypes.PHYSICAL.value:
            if model is None:
                model = "router"
            nodetype = model
        elif nodetype is not None:
            nodetype = NodeTypes(nodetype)
            nodetype = self.session.get_node_class(nodetype).type
            net = True
        else:
            nodetype = None

        try:
            node = self.session.get_node(nodenum)
        except CoreError:
            node = None
        if node:
            self.updatenode(
                node.id, msg.flags, x, y, z, node.name, node.type, node.icon
            )
        else:
            if nodenum in self.remotes:
                remote = self.remotes[nodenum]
                if name is None:
                    name = remote.name
                if nodetype is None:
                    nodetype = remote.type
                if icon is None:
                    icon = remote.icon
            else:
                remote = Bunch(
                    _id=nodenum,
                    type=nodetype,
                    icon=icon,
                    name=name,
                    net=net,
                    links=set(),
                )
                self.remotes[nodenum] = remote
            remote.pos = (x, y, z)
            self.updatenode(nodenum, msg.flags, x, y, z, name, nodetype, icon)

    def handlelinkmsg(self, msg: CoreLinkMessage) -> None:
        """
        Process a Link Message to add/remove links on the SDT display.
        Links are recorded in the remotes[nodenum1].links set for updating
        the SDT display at a later time.

        :param msg: link message to handle
        :return: nothing
        """
        if not self.is_enabled():
            return
        nodenum1 = msg.get_tlv(LinkTlvs.N1_NUMBER.value)
        nodenum2 = msg.get_tlv(LinkTlvs.N2_NUMBER.value)
        link_msg_type = msg.get_tlv(LinkTlvs.TYPE.value)
        # this filters out links to WLAN and EMANE nodes which are not drawn
        if self.wlancheck(nodenum1):
            return
        wl = link_msg_type == LinkTypes.WIRELESS.value
        if nodenum1 in self.remotes:
            r = self.remotes[nodenum1]
            if msg.flags & MessageFlags.DELETE.value:
                if (nodenum2, wl) in r.links:
                    r.links.remove((nodenum2, wl))
            else:
                r.links.add((nodenum2, wl))
        self.updatelink(nodenum1, nodenum2, msg.flags, wireless=wl)

    def wlancheck(self, nodenum: int) -> bool:
        """
        Helper returns True if a node number corresponds to a WLAN or EMANE node.

        :param nodenum: node id to check
        :return: True if node is wlan or emane, False otherwise
"""
        if nodenum in self.remotes:
            node_type = self.remotes[nodenum].type
            if node_type in ("wlan", "emane"):
                return True
        else:
            try:
                n = self.session.get_node(nodenum)
            except CoreError:
                return False
            if isinstance(n, (WlanNode, EmaneNet)):
                return True
        return False
