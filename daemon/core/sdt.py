"""
sdt.py: Scripted Display Tool (SDT3D) helper
"""

import logging
import socket
from urlparse import urlparse

from core import constants
from core.coreobj import PyCoreNet
from core.coreobj import PyCoreObj
from core.enumerations import EventTypes
from core.enumerations import LinkTlvs
from core.enumerations import LinkTypes
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.enumerations import NodeTlvs
from core.enumerations import NodeTypes
from core.misc import nodeutils


# TODO: A named tuple may be more appropriate, than abusing a class dict like this
class Bunch(object):
    """
    Helper class for recording a collection of attributes.
    """

    def __init__(self, **kwds):
        """
        Create a Bunch instance.

        :param dict kwds: keyword arguments
        :return:
        """
        self.__dict__.update(kwds)


class Sdt(object):
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

    def __init__(self, session):
        """
        Creates a Sdt instance.

        :param core.session.Session session: session this manager is tied to
        """
        self.session = session
        self.sock = None
        self.connected = False
        self.showerror = True
        self.url = self.DEFAULT_SDT_URL
        # node information for remote nodes not in session._objs
        # local nodes also appear here since their obj may not exist yet
        self.remotes = {}
        session.broker.handlers.add(self.handle_distributed)

        # add handler for node updates
        self.session.node_handlers.append(self.handle_node_update)

        # add handler for link updates
        self.session.link_handlers.append(self.handle_link_update)

    def handle_node_update(self, node_data):
        """
        Handler for node updates, specifically for updating their location.

        :param core.data.NodeData node_data: node data being updated
        :return: nothing
        """
        x = node_data.x_position
        y = node_data.y_position
        lat = node_data.latitude
        lon = node_data.longitude
        alt = node_data.altitude

        if all([lat, lon, alt]):
            self.updatenodegeo(node_data.id, node_data.latitude, node_data.longitude, node_data.altitude)

        if node_data.message_type == 0:
            # TODO: z is not currently supported by node messages
            self.updatenode(node_data.id, 0, x, y, 0)

    def handle_link_update(self, link_data):
        """
        Handler for link updates, checking for wireless link/unlink messages.

        :param core.data.LinkData link_data: link data being updated
        :return: nothing
        """
        if link_data.link_type == LinkTypes.WIRELESS.value:
            self.updatelink(link_data.node1_id, link_data.node2_id, link_data.message_type, wireless=True)

    def is_enabled(self):
        """
        Check for "enablesdt" session option. Return False by default if
        the option is missing.

        :return: True if enabled, False otherwise
        :rtype: bool
        """
        return self.session.options.get_config("enablesdt") == "1"

    def seturl(self):
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

    def connect(self, flags=0):
        """
        Connect to the SDT address/port if enabled.

        :return: True if connected, False otherwise
        :rtype: bool
        """
        if not self.is_enabled():
            return False
        if self.connected:
            return True
        if self.session.state == EventTypes.SHUTDOWN_STATE.value:
            return False

        self.seturl()
        logging.info("connecting to SDT at %s://%s" % (self.protocol, self.address))
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

    def initialize(self):
        """
        Load icon sprites, and fly to the reference point location on
        the virtual globe.

        :return: initialize command status
        :rtype: bool
        """
        if not self.cmd("path \"%s/icons/normal\"" % constants.CORE_DATA_DIR):
            return False
        # send node type to icon mappings
        for node_type, icon in self.DEFAULT_SPRITES:
            if not self.cmd("sprite %s image %s" % (node_type, icon)):
                return False
        lat, long = self.session.location.refgeo[:2]
        return self.cmd("flyto %.6f,%.6f,%d" % (long, lat, self.DEFAULT_ALT))

    def disconnect(self):
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

    def shutdown(self):
        """
        Invoked from Session.shutdown() and Session.checkshutdown().

        :return: nothing
        """
        logging.info("SDT shutdown!")
        self.cmd("clear all")
        self.disconnect()
        self.showerror = True

    def cmd(self, cmdstr):
        """
        Send an SDT command over a UDP socket. socket.sendall() is used
        as opposed to socket.sendto() because an exception is raised when
        there is no socket listener.

        :param str cmdstr: command to send
        :return: True if command was successful, False otherwise
        :rtype: bool
        """
        if self.sock is None:
            return False
        try:
            logging.info("sdt: %s" % cmdstr)
            self.sock.sendall("%s\n" % cmdstr)
            return True
        except IOError:
            logging.exception("SDT connection error")
            self.sock = None
            self.connected = False
            return False

    def updatenode(self, nodenum, flags, x, y, z, name=None, node_type=None, icon=None):
        """
        Node is updated from a Node Message or mobility script.

        :param int nodenum: node id to update
        :param flags: update flags
        :param x: x position
        :param y: y position
        :param z: z position
        :param str name: node name
        :param node_type: node type
        :param icon: node icon
        :return: nothing
        """
        if not self.connect():
            return
        if flags & MessageFlags.DELETE.value:
            self.cmd("delete node,%d" % nodenum)
            return
        if x is None or y is None:
            return
        lat, lon, alt = self.session.location.getgeo(x, y, z)
        pos = "pos %.6f,%.6f,%.6f" % (lon, lat, alt)
        if flags & MessageFlags.ADD.value:
            if icon is not None:
                node_type = name
                icon = icon.replace("$CORE_DATA_DIR", constants.CORE_DATA_DIR)
                icon = icon.replace("$CORE_CONF_DIR", constants.CORE_CONF_DIR)
                self.cmd("sprite %s image %s" % (type, icon))
            self.cmd("node %d type %s label on,\"%s\" %s" % (nodenum, node_type, name, pos))
        else:
            self.cmd("node %d %s" % (nodenum, pos))

    def updatenodegeo(self, nodenum, lat, long, alt):
        """
        Node is updated upon receiving an EMANE Location Event.

        :param int nodenum: node id to update geospatial for
        :param lat: latitude
        :param long: longitude
        :param alt: altitude
        :return: nothing
        """

        # TODO: received Node Message with lat/long/alt.
        if not self.connect():
            return
        pos = "pos %.6f,%.6f,%.6f" % (long, lat, alt)
        self.cmd("node %d %s" % (nodenum, pos))

    def updatelink(self, node1num, node2num, flags, wireless=False):
        """
        Link is updated from a Link Message or by a wireless model.

        :param int node1num: node one id
        :param int node2num: node two id
        :param flags: link flags
        :param bool wireless: flag to check if wireless or not
        :return: nothing
        """
        if node1num is None or node2num is None:
            return
        if not self.connect():
            return
        if flags & MessageFlags.DELETE.value:
            self.cmd("delete link,%s,%s" % (node1num, node2num))
        elif flags & MessageFlags.ADD.value:
            attr = ""
            if wireless:
                attr = " line green,2"
            else:
                attr = " line red,2"
            self.cmd("link %s,%s%s" % (node1num, node2num, attr))

    def sendobjs(self):
        """
        Session has already started, and the SDT3D GUI later connects.
        Send all node and link objects for display. Otherwise, nodes and
        links will only be drawn when they have been updated (e.g. moved).

        :return: nothing
        """
        nets = []
        with self.session._objects_lock:
            for obj in self.session.objects.itervalues():
                if isinstance(obj, PyCoreNet):
                    nets.append(obj)
                if not isinstance(obj, PyCoreObj):
                    continue
                (x, y, z) = obj.getposition()
                if x is None or y is None:
                    continue
                self.updatenode(obj.objid, MessageFlags.ADD.value, x, y, z,
                                obj.name, obj.type, obj.icon)
            for nodenum in sorted(self.remotes.keys()):
                r = self.remotes[nodenum]
                x, y, z = r.pos
                self.updatenode(nodenum, MessageFlags.ADD.value, x, y, z,
                                r.name, r.type, r.icon)

            for net in nets:
                all_links = net.all_link_data(flags=MessageFlags.ADD.value)
                for link_data in all_links:
                    is_wireless = nodeutils.is_node(net, (NodeTypes.WIRELESS_LAN, NodeTypes.EMANE))
                    wireless_link = link_data.message_type == LinkTypes.WIRELESS.value
                    if is_wireless and link_data.node1_id == net.objid:
                        continue

                    self.updatelink(
                        link_data.node1_id,
                        link_data.node2_id,
                        MessageFlags.ADD.value,
                        wireless_link
                    )

            for n1num in sorted(self.remotes.keys()):
                r = self.remotes[n1num]
                for n2num, wireless_link in r.links:
                    self.updatelink(n1num, n2num, MessageFlags.ADD.value, wireless_link)

    def handle_distributed(self, message):
        """
        Broker handler for processing CORE API messages as they are
        received. This is used to snoop the Node messages and update
        node positions.

        :param message: message to handle
        :return: replies
        """
        if message.message_type == MessageTypes.LINK.value:
            return self.handlelinkmsg(message)
        elif message.message_type == MessageTypes.NODE.value:
            return self.handlenodemsg(message)

    def handlenodemsg(self, msg):
        """
        Process a Node Message to add/delete or move a node on
        the SDT display. Node properties are found in session._objs or
        self.remotes for remote nodes (or those not yet instantiated).

        :param msg: node message to handle
        :return: nothing
        """
        # for distributed sessions to work properly, the SDT option should be
        # enabled prior to starting the session
        if not self.is_enabled():
            return False
        # node.(objid, type, icon, name) are used.
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
        if nodetype == NodeTypes.DEFAULT.value or \
                nodetype == NodeTypes.PHYSICAL.value:
            if model is None:
                model = "router"
            nodetype = model
        elif nodetype is not None:
            nodetype = nodeutils.get_node_class(NodeTypes(nodetype)).type
            net = True
        else:
            nodetype = None

        try:
            node = self.session.get_object(nodenum)
        except KeyError:
            node = None
        if node:
            self.updatenode(node.objid, msg.flags, x, y, z, node.name, node.type, node.icon)
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
                remote = Bunch(objid=nodenum, type=nodetype, icon=icon, name=name, net=net, links=set())
                self.remotes[nodenum] = remote
            remote.pos = (x, y, z)
            self.updatenode(nodenum, msg.flags, x, y, z, name, nodetype, icon)

    def handlelinkmsg(self, msg):
        """
        Process a Link Message to add/remove links on the SDT display.
        Links are recorded in the remotes[nodenum1].links set for updating
        the SDT display at a later time.

        :param msg: link message to handle
        :return: nothing
        """
        if not self.is_enabled():
            return False
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

    def wlancheck(self, nodenum):
        """
        Helper returns True if a node number corresponds to a WlanNode or EmaneNode.

        :param int nodenum: node id to check
        :return: True if node is wlan or emane, False otherwise
        :rtype: bool
        """
        if nodenum in self.remotes:
            node_type = self.remotes[nodenum].type
            if node_type in ("wlan", "emane"):
                return True
        else:
            try:
                n = self.session.get_object(nodenum)
            except KeyError:
                return False
            if nodeutils.is_node(n, (NodeTypes.WIRELESS_LAN, NodeTypes.EMANE)):
                return True
        return False
