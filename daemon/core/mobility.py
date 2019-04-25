"""
mobility.py: mobility helpers for moving nodes and calculating wireless range.
"""

import heapq
import logging
import math
import os
import threading
import time

from core.conf import ConfigGroup
from core.conf import ConfigurableOptions
from core.conf import Configuration
from core.conf import ModelManager
from core.coreobj import PyCoreNode
from core.data import EventData
from core.data import LinkData
from core.enumerations import ConfigDataTypes
from core.enumerations import EventTypes
from core.enumerations import LinkTypes
from core.enumerations import MessageFlags
from core.enumerations import MessageTypes
from core.enumerations import NodeTlvs
from core.enumerations import RegisterTlvs
from core.misc import utils
from core.misc.ipaddress import IpAddress


class MobilityManager(ModelManager):
    """
    Member of session class for handling configuration data for mobility and
    range models.
    """
    name = "MobilityManager"
    config_type = RegisterTlvs.WIRELESS.value

    def __init__(self, session):
        """
        Creates a MobilityManager instance.

        :param core.session.Session session: session this manager is tied to
        """
        super(MobilityManager, self).__init__()
        self.session = session
        self.models[BasicRangeModel.name] = BasicRangeModel
        self.models[Ns2ScriptedMobility.name] = Ns2ScriptedMobility

        # dummy node objects for tracking position of nodes on other servers
        self.phys = {}
        self.physnets = {}
        self.session.broker.handlers.add(self.physnodehandlelink)

    def startup(self, node_ids=None):
        """
        Session is transitioning from instantiation to runtime state.
        Instantiate any mobility models that have been configured for a WLAN.

        :param list node_ids: node ids to startup
        :return: nothing
        """
        if node_ids is None:
            node_ids = self.nodes()

        for node_id in node_ids:
            logging.info("checking mobility startup for node: %s", node_id)
            logging.info("node mobility configurations: %s", self.get_all_configs(node_id))

            try:
                node = self.session.get_object(node_id)
            except KeyError:
                logging.warn("skipping mobility configuration for unknown node: %s", node_id)
                continue

            for model_name in self.models.iterkeys():
                config = self.get_configs(node_id, model_name)
                if not config:
                    continue
                model_class = self.models[model_name]
                self.set_model(node, model_class, config)

            if self.session.master:
                self.installphysnodes(node)

            if node.mobility:
                self.session.event_loop.add_event(0.0, node.mobility.startup)

    def handleevent(self, event_data):
        """
        Handle an Event Message used to start, stop, or pause
        mobility scripts for a given WlanNode.

        :param EventData event_data: event data to handle
        :return: nothing
        """
        event_type = event_data.event_type
        node_id = event_data.node
        name = event_data.name

        try:
            node = self.session.get_object(node_id)
        except KeyError:
            logging.exception("Ignoring event for model '%s', unknown node '%s'", name, node_id)
            return

        # name is e.g. "mobility:ns2script"
        models = name[9:].split(',')
        for model in models:
            try:
                cls = self.models[model]
            except KeyError:
                logging.warn("Ignoring event for unknown model '%s'", model)
                continue

            if cls.config_type in [RegisterTlvs.WIRELESS.value, RegisterTlvs.MOBILITY.value]:
                model = node.mobility
            else:
                continue

            if model is None:
                logging.warn("Ignoring event, %s has no model", node.name)
                continue

            if cls.name != model.name:
                logging.warn("Ignoring event for %s wrong model %s,%s", node.name, cls.name, model.name)
                continue

            if event_type == EventTypes.STOP.value or event_type == EventTypes.RESTART.value:
                model.stop(move_initial=True)
            if event_type == EventTypes.START.value or event_type == EventTypes.RESTART.value:
                model.start()
            if event_type == EventTypes.PAUSE.value:
                model.pause()

    def sendevent(self, model):
        """
        Send an event message on behalf of a mobility model.
        This communicates the current and end (max) times to the GUI.

        :param WayPointMobility model: mobility model to send event for
        :return: nothing
        """
        event_type = EventTypes.NONE.value
        if model.state == model.STATE_STOPPED:
            event_type = EventTypes.STOP.value
        elif model.state == model.STATE_RUNNING:
            event_type = EventTypes.START.value
        elif model.state == model.STATE_PAUSED:
            event_type = EventTypes.PAUSE.value

        data = "start=%d" % int(model.lasttime - model.timezero)
        data += " end=%d" % int(model.endtime)

        event_data = EventData(
            node=model.object_id,
            event_type=event_type,
            name="mobility:%s" % model.name,
            data=data,
            time="%s" % time.time()
        )

        self.session.broadcast_event(event_data)

    def updatewlans(self, moved, moved_netifs):
        """
        A mobility script has caused nodes in the 'moved' list to move.
        Update every WlanNode. This saves range calculations if the model
        were to recalculate for each individual node movement.

        :param list moved: moved nodes
        :param list moved_netifs: moved network interfaces
        :return: nothing
        """
        for node_id in self.nodes():
            try:
                node = self.session.get_object(node_id)
            except KeyError:
                continue
            if node.model:
                node.model.update(moved, moved_netifs)

    def addphys(self, netnum, node):
        """
        Keep track of PhysicalNodes and which network they belong to.

        :param int netnum: network number
        :param core.coreobj.PyCoreNode node: node to add physical network to
        :return: nothing
        """
        node_id = node.objid
        self.phys[node_id] = node
        if netnum not in self.physnets:
            self.physnets[netnum] = [node_id, ]
        else:
            self.physnets[netnum].append(node_id)

            # TODO: remove need for handling old style message

    def physnodehandlelink(self, message):
        """
        Broker handler. Snoop Link add messages to get
        node numbers of PhyiscalNodes and their nets.
        Physical nodes exist only on other servers, but a shadow object is
        created here for tracking node position.

        :param message: link message to handle
        :return: nothing
        """
        if message.message_type == MessageTypes.LINK.value and message.flags & MessageFlags.ADD.value:
            nn = message.node_numbers()
            # first node is always link layer node in Link add message
            if nn[0] not in self.session.broker.network_nodes:
                return
            if nn[1] in self.session.broker.physical_nodes:
                # record the fact that this PhysicalNode is linked to a net
                dummy = PyCoreNode(session=self.session, objid=nn[1], name="n%d" % nn[1], start=False)
                self.addphys(nn[0], dummy)

    # TODO: remove need to handling old style messages
    def physnodeupdateposition(self, message):
        """
        Snoop node messages belonging to physical nodes. The dummy object
        in self.phys[] records the node position.

        :param message: message to handle
        :return: nothing
        """
        nodenum = message.node_numbers()[0]
        try:
            dummy = self.phys[nodenum]
            nodexpos = message.get_tlv(NodeTlvs.X_POSITION.value)
            nodeypos = message.get_tlv(NodeTlvs.Y_POSITION.value)
            dummy.setposition(nodexpos, nodeypos, None)
        except KeyError:
            logging.exception("error retrieving physical node: %s", nodenum)

    def installphysnodes(self, net):
        """
        After installing a mobility model on a net, include any physical
        nodes that we have recorded. Use the GreTap tunnel to the physical node
        as the node's interface.

        :param net: network to install
        :return: nothing
        """
        nodenums = self.physnets.get(net.objid, [])
        for nodenum in nodenums:
            node = self.phys[nodenum]
            # TODO: fix this bad logic, relating to depending on a break to get a valid server
            for server in self.session.broker.getserversbynode(nodenum):
                break
            netif = self.session.broker.gettunnel(net.objid, IpAddress.to_int(server.host))
            node.addnetif(netif, 0)
            netif.node = node
            x, y, z = netif.node.position.get()
            netif.poshook(netif, x, y, z)


class WirelessModel(ConfigurableOptions):
    """
    Base class used by EMANE models and the basic range model.
    Used for managing arbitrary configuration parameters.
    """
    config_type = RegisterTlvs.WIRELESS.value
    bitmap = None
    position_callback = None

    def __init__(self, session, object_id):
        """
        Create a WirelessModel instance.

        :param core.session.Session session: core session we are tied to
        :param int object_id: object id
        """
        self.session = session
        self.object_id = object_id

    def all_link_data(self, flags):
        """
        May be used if the model can populate the GUI with wireless (green)
        link lines.

        :param flags: link data flags
        :return: link data
        :rtype: list
        """
        return []

    def update(self, moved, moved_netifs):
        """
        Update this wireless model.

        :param bool moved: flag is it was moved
        :param list moved_netifs: moved network interfaces
        :return: nothing
        """
        raise NotImplementedError

    def update_config(self, config):
        """
        For run-time updates of model config. Returns True when position callback and set link
        parameters should be invoked.

        :param dict config: configuration values to update
        :return: nothing
        """
        pass


class BasicRangeModel(WirelessModel):
    """
    Basic Range wireless model, calculates range between nodes and links
    and unlinks nodes based on this distance. This was formerly done from
    the GUI.
    """
    name = "basic_range"
    options = [
        Configuration(_id="range", _type=ConfigDataTypes.UINT32, default="275", label="wireless range (pixels)"),
        Configuration(_id="bandwidth", _type=ConfigDataTypes.UINT32, default="54000000", label="bandwidth (bps)"),
        Configuration(_id="jitter", _type=ConfigDataTypes.FLOAT, default="0.0", label="transmission jitter (usec)"),
        Configuration(_id="delay", _type=ConfigDataTypes.FLOAT, default="5000.0",
                      label="transmission delay (usec)"),
        Configuration(_id="error", _type=ConfigDataTypes.FLOAT, default="0.0", label="error rate (%)")
    ]

    @classmethod
    def config_groups(cls):
        return [
            ConfigGroup("Basic Range Parameters", 1, len(cls.configurations()))
        ]

    def __init__(self, session, object_id):
        """
        Create a BasicRangeModel instance.

        :param core.session.Session session: related core session
        :param int object_id: object id
        :param dict config: values
        """
        super(BasicRangeModel, self).__init__(session=session, object_id=object_id)
        self.session = session
        self.wlan = session.get_object(object_id)
        self._netifs = {}
        self._netifslock = threading.Lock()

        self.range = None
        self.bw = None
        self.delay = None
        self.loss = None
        self.jitter = None

    def values_from_config(self, config):
        """
        Values to convert to link parameters.

        :param dict config: values to convert
        :return: nothing
        """
        self.range = float(config["range"])
        logging.info("basic range model configured for WLAN %d using range %d", self.wlan.objid, self.range)
        self.bw = int(config["bandwidth"])
        if self.bw == 0.0:
            self.bw = None
        self.delay = float(config["delay"])
        if self.delay == 0.0:
            self.delay = None
        self.loss = float(config["error"])
        if self.loss == 0.0:
            self.loss = None
        self.jitter = float(config["jitter"])
        if self.jitter == 0.0:
            self.jitter = None

    def setlinkparams(self):
        """
        Apply link parameters to all interfaces. This is invoked from
        WlanNode.setmodel() after the position callback has been set.
        """
        with self._netifslock:
            for netif in self._netifs:
                self.wlan.linkconfig(netif, bw=self.bw, delay=self.delay, loss=self.loss, duplicate=None,
                                     jitter=self.jitter)

    def get_position(self, netif):
        """
        Retrieve network interface position.

        :param netif: network interface position to retrieve
        :return: network interface position
        """
        with self._netifslock:
            return self._netifs[netif]

    def set_position(self, netif, x=None, y=None, z=None):
        """
        A node has moved; given an interface, a new (x,y,z) position has
        been set; calculate the new distance between other nodes and link or
        unlink node pairs based on the configured range.

        :param netif: network interface to set position for
        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        self._netifslock.acquire()
        self._netifs[netif] = (x, y, z)
        if x is None or y is None:
            self._netifslock.release()
            return
        for netif2 in self._netifs:
            self.calclink(netif, netif2)
        self._netifslock.release()

    position_callback = set_position

    def update(self, moved, moved_netifs):
        """
        Node positions have changed without recalc. Update positions from
        node.position, then re-calculate links for those that have moved.
        Assumes bidirectional links, with one calculation per node pair, where
        one of the nodes has moved.

        :param bool moved: flag is it was moved
        :param list moved_netifs: moved network interfaces
        :return: nothing
        """
        with self._netifslock:
            while len(moved_netifs):
                netif = moved_netifs.pop()
                nx, ny, nz = netif.node.getposition()
                if netif in self._netifs:
                    self._netifs[netif] = (nx, ny, nz)
                for netif2 in self._netifs:
                    if netif2 in moved_netifs:
                        continue
                    self.calclink(netif, netif2)

    def calclink(self, netif, netif2):
        """
        Helper used by set_position() and update() to
        calculate distance between two interfaces and perform
        linking/unlinking. Sends link/unlink messages and updates the
        WlanNode's linked dict.

        :param netif: interface one
        :param netif2: interface two
        :return: nothing
        """
        if netif == netif2:
            return

        try:
            x, y, z = self._netifs[netif]
            x2, y2, z2 = self._netifs[netif2]

            if x2 is None or y2 is None:
                return

            d = self.calcdistance((x, y, z), (x2, y2, z2))

            # ordering is important, to keep the wlan._linked dict organized
            a = min(netif, netif2)
            b = max(netif, netif2)

            with self.wlan._linked_lock:
                linked = self.wlan.linked(a, b)

            logging.debug("checking range netif1(%s) netif2(%s): linked(%s) actual(%s) > config(%s)",
                         a.name, b.name, linked, d, self.range)
            if d > self.range:
                if linked:
                    logging.debug("was linked, unlinking")
                    self.wlan.unlink(a, b)
                    self.sendlinkmsg(a, b, unlink=True)
            else:
                if not linked:
                    logging.debug("was not linked, linking")
                    self.wlan.link(a, b)
                    self.sendlinkmsg(a, b)
        except KeyError:
            logging.exception("error getting interfaces during calclinkS")

    @staticmethod
    def calcdistance(p1, p2):
        """
        Calculate the distance between two three-dimensional points.

        :param tuple p1: point one
        :param tuple p2: point two
        :return: distance petween the points
        :rtype: float
        """
        a = p1[0] - p2[0]
        b = p1[1] - p2[1]
        c = 0
        if p1[2] is not None and p2[2] is not None:
            c = p1[2] - p2[2]
        return math.hypot(math.hypot(a, b), c)

    def update_config(self, config):
        """
        Configuration has changed during runtime.

        :param dict config: values to update configuration
        :return: nothing
        """
        self.values_from_config(config)
        self.setlinkparams()
        return True

    def create_link_data(self, interface1, interface2, message_type):
        """
        Create a wireless link/unlink data message.

        :param core.coreobj.PyCoreNetIf interface1: interface one
        :param core.coreobj.PyCoreNetIf interface2: interface two
        :param message_type: link message type
        :return: link data
        :rtype: LinkData
        """
        return LinkData(
            message_type=message_type,
            node1_id=interface1.node.objid,
            node2_id=interface2.node.objid,
            network_id=self.wlan.objid,
            link_type=LinkTypes.WIRELESS.value
        )

    def sendlinkmsg(self, netif, netif2, unlink=False):
        """
        Send a wireless link/unlink API message to the GUI.

        :param core.coreobj.PyCoreNetIf netif: interface one
        :param core.coreobj.PyCoreNetIf netif2: interface two
        :param bool unlink: unlink or not
        :return: nothing
        """
        if unlink:
            message_type = MessageFlags.DELETE.value
        else:
            message_type = MessageFlags.ADD.value

        link_data = self.create_link_data(netif, netif2, message_type)
        self.session.broadcast_link(link_data)

    def all_link_data(self, flags):
        """
        Return a list of wireless link messages for when the GUI reconnects.

        :param flags: link flags
        :return: all link data
        :rtype: list
        """
        all_links = []
        with self.wlan._linked_lock:
            for a in self.wlan._linked:
                for b in self.wlan._linked[a]:
                    if self.wlan._linked[a][b]:
                        all_links.append(self.create_link_data(a, b, flags))
        return all_links


class WayPoint(object):
    """
    Maintains information regarding waypoints.
    """

    def __init__(self, time, nodenum, coords, speed):
        """
        Creates a WayPoint instance.

        :param time: waypoint time
        :param int nodenum: node id
        :param coords: waypoint coordinates
        :param speed: waypoint speed
        """
        self.time = time
        self.nodenum = nodenum
        self.coords = coords
        self.speed = speed

    def __cmp__(self, other):
        """
        Custom comparison method for waypoints.

        :param WayPoint other: waypoint to compare to
        :return: the comparison result against the other waypoint
        :rtype: int
        """
        tmp = cmp(self.time, other.time)
        if tmp == 0:
            tmp = cmp(self.nodenum, other.nodenum)
        return tmp


class WayPointMobility(WirelessModel):
    """
    Abstract class for mobility models that set node waypoints.
    """
    name = "waypoint"
    config_type = RegisterTlvs.MOBILITY.value

    STATE_STOPPED = 0
    STATE_RUNNING = 1
    STATE_PAUSED = 2

    def __init__(self, session, object_id):
        """
        Create a WayPointMobility instance.

        :param core.session.Session session: CORE session instance
        :param int object_id: object id
        :return:
        """
        super(WayPointMobility, self).__init__(session=session, object_id=object_id)

        self.state = self.STATE_STOPPED
        self.queue = []
        self.queue_copy = []
        self.points = {}
        self.initial = {}
        self.lasttime = None
        self.endtime = None
        self.wlan = session.get_object(object_id)
        # these are really set in child class via confmatrix
        self.loop = False
        self.refresh_ms = 50
        # flag whether to stop scheduling when queue is empty
        #  (ns-3 sets this to False as new waypoints may be added from trace)
        self.empty_queue_stop = True

    def runround(self):
        """
        Advance script time and move nodes.

        :return: nothing
        """
        if self.state != self.STATE_RUNNING:
            return
        t = self.lasttime
        self.lasttime = time.time()
        now = self.lasttime - self.timezero
        dt = self.lasttime - t

        # keep current waypoints up-to-date
        self.updatepoints(now)

        if not len(self.points):
            if len(self.queue):
                # more future waypoints, allow time for self.lasttime update
                nexttime = self.queue[0].time - now
                if nexttime > (0.001 * self.refresh_ms):
                    nexttime -= 0.001 * self.refresh_ms
                self.session.event_loop.add_event(nexttime, self.runround)
                return
            else:
                # no more waypoints or queued items, loop?
                if not self.empty_queue_stop:
                    # keep running every refresh_ms, even with empty queue
                    self.session.event_loop.add_event(0.001 * self.refresh_ms, self.runround)
                    return
                if not self.loopwaypoints():
                    return self.stop(move_initial=False)
                if not len(self.queue):
                    # prevent busy loop
                    return
                return self.run()

        # only move netifs attached to self.wlan, or all nodenum in script?
        moved = []
        moved_netifs = []
        for netif in self.wlan.netifs():
            node = netif.node
            if self.movenode(node, dt):
                moved.append(node)
                moved_netifs.append(netif)

        # calculate all ranges after moving nodes; this saves calculations
        self.session.mobility.updatewlans(moved, moved_netifs)

        # TODO: check session state
        self.session.event_loop.add_event(0.001 * self.refresh_ms, self.runround)

    def run(self):
        """
        Run the waypoint mobility scenario.

        :return: nothing
        """
        logging.info("running mobility scenario")
        self.timezero = time.time()
        self.lasttime = self.timezero - (0.001 * self.refresh_ms)
        self.movenodesinitial()
        self.runround()
        self.session.mobility.sendevent(self)

    def movenode(self, node, dt):
        """
        Calculate next node location and update its coordinates.
        Returns True if the node's position has changed.

        :param core.netns.nodes.CoreNode node: node to move
        :param dt: move factor
        :return: True if node was moved, False otherwise
        :rtype: bool
        """
        if node.objid not in self.points:
            return False
        x1, y1, z1 = node.getposition()
        x2, y2, z2 = self.points[node.objid].coords
        speed = self.points[node.objid].speed
        # instantaneous move (prevents dx/dy == 0.0 below)
        if speed == 0:
            self.setnodeposition(node, x2, y2, z2)
            del self.points[node.objid]
            return True
        # speed can be a velocity vector (ns3 mobility) or speed value
        if isinstance(speed, (float, int)):
            # linear speed value
            alpha = math.atan2(y2 - y1, x2 - x1)
            sx = speed * math.cos(alpha)
            sy = speed * math.sin(alpha)
        else:
            # velocity vector
            sx = speed[0]
            sy = speed[1]

        # calculate dt * speed = distance moved
        dx = sx * dt
        dy = sy * dt
        # prevent overshoot
        if abs(dx) > abs(x2 - x1):
            dx = x2 - x1
        if abs(dy) > abs(y2 - y1):
            dy = y2 - y1
        if dx == 0.0 and dy == 0.0:
            if self.endtime < (self.lasttime - self.timezero):
                # the last node to reach the last waypoint determines this
                # script's endtime
                self.endtime = self.lasttime - self.timezero
            del self.points[node.objid]
            return False
        if (x1 + dx) < 0.0:
            dx = 0.0 - x1
        if (y1 + dy) < 0.0:
            dy = 0.0 - y1
        self.setnodeposition(node, x1 + dx, y1 + dy, z1)
        return True

    def movenodesinitial(self):
        """
        Move nodes to their initial positions. Then calculate the ranges.

        :return: nothing
        """
        moved = []
        moved_netifs = []
        for netif in self.wlan.netifs():
            node = netif.node
            if node.objid not in self.initial:
                continue
            x, y, z = self.initial[node.objid].coords
            self.setnodeposition(node, x, y, z)
            moved.append(node)
            moved_netifs.append(netif)
        self.session.mobility.updatewlans(moved, moved_netifs)

    def addwaypoint(self, time, nodenum, x, y, z, speed):
        """
        Waypoints are pushed to a heapq, sorted by time.

        :param time: waypoint time
        :param int nodenum: node id
        :param x: x position
        :param y: y position
        :param z: z position
        :param speed: speed
        :return: nothing
        """
        wp = WayPoint(time, nodenum, coords=(x, y, z), speed=speed)
        heapq.heappush(self.queue, wp)

    def addinitial(self, nodenum, x, y, z):
        """
        Record initial position in a dict.

        :param int nodenum: node id
        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        wp = WayPoint(0, nodenum, coords=(x, y, z), speed=0)
        self.initial[nodenum] = wp

    def updatepoints(self, now):
        """
        Move items from self.queue to self.points when their time has come.

        :param int now: current timestamp
        :return: nothing
        """
        while len(self.queue):
            if self.queue[0].time > now:
                break
            wp = heapq.heappop(self.queue)
            self.points[wp.nodenum] = wp

    def copywaypoints(self):
        """
        Store backup copy of waypoints for looping and stopping.

        :return: nothing
        """
        self.queue_copy = list(self.queue)

    def loopwaypoints(self):
        """
        Restore backup copy of waypoints when looping.

        :return: nothing
        """
        self.queue = list(self.queue_copy)
        return self.loop

    def setnodeposition(self, node, x, y, z):
        """
        Helper to move a node, notify any GUI (connected session handlers),
        without invoking the interface poshook callback that may perform
        range calculation.

        :param core.netns.nodes.CoreNode node: node to set position for
        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        # this would cause PyCoreNetIf.poshook() callback (range calculation)
        node.position.set(x, y, z)
        node_data = node.data(message_type=0)
        self.session.broadcast_node(node_data)

    def setendtime(self):
        """
        Set self.endtime to the time of the last waypoint in the queue of
        waypoints. This is just an estimate. The endtime will later be
        adjusted, after one round of the script has run, to be the time
        that the last moving node has reached its final waypoint.

        :return: nothing
        """
        try:
            self.endtime = self.queue[-1].time
        except IndexError:
            self.endtime = 0

    def start(self):
        """
        Run the script from the beginning or unpause from where it
        was before.

        :return: nothing
        """
        laststate = self.state
        self.state = self.STATE_RUNNING
        if laststate == self.STATE_STOPPED or laststate == self.STATE_RUNNING:
            self.loopwaypoints()
            self.timezero = 0
            self.lasttime = 0
            self.run()
        elif laststate == self.STATE_PAUSED:
            now = time.time()
            self.timezero += now - self.lasttime
            self.lasttime = now - (0.001 * self.refresh_ms)
            self.runround()

    def stop(self, move_initial=True):
        """
        Stop the script and move nodes to initial positions.

        :param bool move_initial: flag to check if we should move nodes to initial position
        :return: nothing
        """
        self.state = self.STATE_STOPPED
        self.loopwaypoints()
        self.timezero = 0
        self.lasttime = 0
        if move_initial:
            self.movenodesinitial()
        self.session.mobility.sendevent(self)

    def pause(self):
        """
        Pause the script; pause time is stored to self.lasttime.

        :return: nothing
        """
        self.state = self.STATE_PAUSED
        self.lasttime = time.time()


class Ns2ScriptedMobility(WayPointMobility):
    """
    Handles the ns-2 script format, generated by scengen/setdest or
    BonnMotion.
    """
    name = "ns2script"
    options = [
        Configuration(_id="file", _type=ConfigDataTypes.STRING, label="mobility script file"),
        Configuration(_id="refresh_ms", _type=ConfigDataTypes.UINT32, default="50", label="refresh time (ms)"),
        Configuration(_id="loop", _type=ConfigDataTypes.BOOL, default="1", options=["On", "Off"], label="loop"),
        Configuration(_id="autostart", _type=ConfigDataTypes.STRING, label="auto-start seconds (0.0 for runtime)"),
        Configuration(_id="map", _type=ConfigDataTypes.STRING, label="node mapping (optional, e.g. 0:1,1:2,2:3)"),
        Configuration(_id="script_start", _type=ConfigDataTypes.STRING, label="script file to run upon start"),
        Configuration(_id="script_pause", _type=ConfigDataTypes.STRING, label="script file to run upon pause"),
        Configuration(_id="script_stop", _type=ConfigDataTypes.STRING, label="script file to run upon stop")
    ]

    @classmethod
    def config_groups(cls):
        return [
            ConfigGroup("ns-2 Mobility Script Parameters", 1, len(cls.configurations()))
        ]

    def __init__(self, session, object_id):
        """
        Creates a Ns2ScriptedMobility instance.

        :param core.session.Session session: CORE session instance
        :param int object_id: object id
        :param config: values
        """
        super(Ns2ScriptedMobility, self).__init__(session=session, object_id=object_id)
        self._netifs = {}
        self._netifslock = threading.Lock()

        self.file = None
        self.refresh_ms = None
        self.loop = None
        self.autostart = None
        self.nodemap = {}
        self.script_start = None
        self.script_pause = None
        self.script_stop = None

    def update_config(self, config):
        self.file = config["file"]
        logging.info("ns-2 scripted mobility configured for WLAN %d using file: %s", self.object_id, self.file)
        self.refresh_ms = int(config["refresh_ms"])
        self.loop = config["loop"].lower() == "on"
        self.autostart = config["autostart"]
        self.parsemap(config["map"])
        self.script_start = config["script_start"]
        self.script_pause = config["script_pause"]
        self.script_stop = config["script_stop"]
        self.readscriptfile()
        self.copywaypoints()
        self.setendtime()

    def readscriptfile(self):
        """
        Read in mobility script from a file. This adds waypoints to a
        priority queue, sorted by waypoint time. Initial waypoints are
        stored in a separate dict.

        :return: nothing
        """
        filename = self.findfile(self.file)
        try:
            f = open(filename, "r")
        except IOError:
            logging.exception("ns-2 scripted mobility failed to load file: %s", self.file)
            return
        logging.info("reading ns-2 script file: %s" % filename)
        ln = 0
        ix = iy = iz = None
        inodenum = None
        for line in f:
            ln += 1
            if line[:2] != '$n':
                continue
            try:
                if line[:8] == "$ns_ at ":
                    if ix is not None and iy is not None:
                        self.addinitial(self.map(inodenum), ix, iy, iz)
                        ix = iy = iz = None
                    # waypoints:
                    #    $ns_ at 1.00 "$node_(6) setdest 500.0 178.0 25.0"
                    parts = line.split()
                    time = float(parts[2])
                    nodenum = parts[3][1 + parts[3].index('('):parts[3].index(')')]
                    x = float(parts[5])
                    y = float(parts[6])
                    z = None
                    speed = float(parts[7].strip('"'))
                    self.addwaypoint(time, self.map(nodenum), x, y, z, speed)
                elif line[:7] == "$node_(":
                    # initial position (time=0, speed=0):
                    #    $node_(6) set X_ 780.0
                    parts = line.split()
                    time = 0.0
                    nodenum = parts[0][1 + parts[0].index('('):parts[0].index(')')]
                    if parts[2] == 'X_':
                        if ix is not None and iy is not None:
                            self.addinitial(self.map(inodenum), ix, iy, iz)
                            ix = iy = iz = None
                        ix = float(parts[3])
                    elif parts[2] == 'Y_':
                        iy = float(parts[3])
                    elif parts[2] == 'Z_':
                        iz = float(parts[3])
                        self.addinitial(self.map(nodenum), ix, iy, iz)
                        ix = iy = iz = None
                    inodenum = nodenum
                else:
                    raise ValueError
            except ValueError:
                logging.exception("skipping line %d of file %s '%s'", ln, self.file, line)
                continue
        if ix is not None and iy is not None:
            self.addinitial(self.map(inodenum), ix, iy, iz)

    def findfile(self, file_name):
        """
        Locate a script file. If the specified file doesn't exist, look in the
        same directory as the scenario file, or in the default
        configs directory (~/.core/configs). This allows for sample files without
        absolute path names.

        :param str file_name: file name to find
        :return: absolute path to the file
        :rtype: str
        """
        if os.path.exists(file_name):
            return file_name

        if self.session.file_name is not None:
            d = os.path.dirname(self.session.file_name)
            sessfn = os.path.join(d, file_name)
            if os.path.exists(sessfn):
                return sessfn

        if self.session.user is not None:
            userfn = os.path.join('/home', self.session.user, '.core', 'configs', file_name)
            if os.path.exists(userfn):
                return userfn

        return file_name

    def parsemap(self, mapstr):
        """
        Parse a node mapping string, given as a configuration parameter.

        :param str mapstr: mapping string to parse
        :return: nothing
        """
        self.nodemap = {}
        if mapstr.strip() == "":
            return

        for pair in mapstr.split(","):
            parts = pair.split(":")
            try:
                if len(parts) != 2:
                    raise ValueError
                self.nodemap[int(parts[0])] = int(parts[1])
            except ValueError:
                logging.exception("ns-2 mobility node map error")

    def map(self, nodenum):
        """
        Map one node number (from a script file) to another.

        :param str nodenum: node id to map
        :return: mapped value or the node id itself
        :rtype: int
        """
        nodenum = int(nodenum)
        return self.nodemap.get(nodenum, nodenum)

    def startup(self):
        """
        Start running the script if autostart is enabled.
        Move node to initial positions when any autostart time is specified.
        Ignore the script if autostart is an empty string (can still be
        started via GUI controls).

        :return: nothing
        """
        if self.autostart == '':
            logging.info("not auto-starting ns-2 script for %s" % self.wlan.name)
            return
        try:
            t = float(self.autostart)
        except ValueError:
            logging.exception("Invalid auto-start seconds specified '%s' for %s", self.autostart, self.wlan.name)
            return
        self.movenodesinitial()
        logging.info("scheduling ns-2 script for %s autostart at %s" % (self.wlan.name, t))
        self.state = self.STATE_RUNNING
        self.session.event_loop.add_event(t, self.run)

    def start(self):
        """
        Handle the case when un-paused.

        :return: nothing
        """
        logging.info("starting script")
        laststate = self.state
        super(Ns2ScriptedMobility, self).start()
        if laststate == self.STATE_PAUSED:
            self.statescript("unpause")

    def run(self):
        """
        Start is pressed or autostart is triggered.

        :return: nothing
        """
        super(Ns2ScriptedMobility, self).run()
        self.statescript("run")

    def pause(self):
        """
        Pause the mobility script.

        :return: nothing
        """
        super(Ns2ScriptedMobility, self).pause()
        self.statescript("pause")

    def stop(self, move_initial=True):
        """
        Stop the mobility script.

        :param bool move_initial: flag to check if we should move node to initial position
        :return: nothing
        """
        super(Ns2ScriptedMobility, self).stop(move_initial=move_initial)
        self.statescript("stop")

    def statescript(self, typestr):
        """
        State of the mobility script.

        :param str typestr: state type string
        :return: nothing
        """
        filename = None
        if typestr == "run" or typestr == "unpause":
            filename = self.script_start
        elif typestr == "pause":
            filename = self.script_pause
        elif typestr == "stop":
            filename = self.script_stop
        if filename is None or filename == '':
            return
        filename = self.findfile(filename)
        args = ["/bin/sh", filename, typestr]
        utils.check_cmd(args, cwd=self.session.session_dir, env=self.session.get_environment())
