"""
mobility.py: mobility helpers for moving nodes and calculating wireless range.
"""

import heapq
import logging
import math
import os
import threading
import time
from functools import total_ordering
from typing import TYPE_CHECKING, Dict, List, Tuple

from core import utils
from core.config import ConfigGroup, ConfigurableOptions, Configuration, ModelManager
from core.emulator.data import EventData, LinkData
from core.emulator.enumerations import (
    ConfigDataTypes,
    EventTypes,
    LinkTypes,
    MessageFlags,
    RegisterTlvs,
)
from core.errors import CoreError
from core.nodes.base import CoreNode, NodeBase
from core.nodes.interface import CoreInterface

if TYPE_CHECKING:
    from core.emulator.session import Session


class MobilityManager(ModelManager):
    """
    Member of session class for handling configuration data for mobility and
    range models.
    """

    name = "MobilityManager"
    config_type = RegisterTlvs.WIRELESS

    def __init__(self, session: "Session") -> None:
        """
        Creates a MobilityManager instance.

        :param session: session this manager is tied to
        """
        super().__init__()
        self.session = session
        self.models[BasicRangeModel.name] = BasicRangeModel
        self.models[Ns2ScriptedMobility.name] = Ns2ScriptedMobility

    def reset(self) -> None:
        """
        Clear out all current configurations.

        :return: nothing
        """
        self.config_reset()

    def startup(self, node_ids: List[int] = None) -> None:
        """
        Session is transitioning from instantiation to runtime state.
        Instantiate any mobility models that have been configured for a WLAN.

        :param node_ids: node ids to startup
        :return: nothing
        """
        if node_ids is None:
            node_ids = self.nodes()

        for node_id in node_ids:
            logging.debug("checking mobility startup for node: %s", node_id)
            logging.debug(
                "node mobility configurations: %s", self.get_all_configs(node_id)
            )

            try:
                node = self.session.get_node(node_id)
            except CoreError:
                logging.warning(
                    "skipping mobility configuration for unknown node: %s", node_id
                )
                continue

            for model_name in self.models:
                config = self.get_configs(node_id, model_name)
                if not config:
                    continue
                model_class = self.models[model_name]
                self.set_model(node, model_class, config)

            if node.mobility:
                self.session.event_loop.add_event(0.0, node.mobility.startup)

    def handleevent(self, event_data: EventData) -> None:
        """
        Handle an Event Message used to start, stop, or pause
        mobility scripts for a given WlanNode.

        :param event_data: event data to handle
        :return: nothing
        """
        event_type = event_data.event_type
        node_id = event_data.node
        name = event_data.name

        try:
            node = self.session.get_node(node_id)
        except CoreError:
            logging.exception(
                "Ignoring event for model '%s', unknown node '%s'", name, node_id
            )
            return

        # name is e.g. "mobility:ns2script"
        models = name[9:].split(",")
        for model in models:
            try:
                cls = self.models[model]
            except KeyError:
                logging.warning("Ignoring event for unknown model '%s'", model)
                continue

            if cls.config_type in [RegisterTlvs.WIRELESS, RegisterTlvs.MOBILITY]:
                model = node.mobility
            else:
                continue

            if model is None:
                logging.warning("Ignoring event, %s has no model", node.name)
                continue

            if cls.name != model.name:
                logging.warning(
                    "Ignoring event for %s wrong model %s,%s",
                    node.name,
                    cls.name,
                    model.name,
                )
                continue

            if event_type in [EventTypes.STOP, EventTypes.RESTART]:
                model.stop(move_initial=True)
            if event_type in [EventTypes.START, EventTypes.RESTART]:
                model.start()
            if event_type == EventTypes.PAUSE:
                model.pause()

    def sendevent(self, model: "WayPointMobility") -> None:
        """
        Send an event message on behalf of a mobility model.
        This communicates the current and end (max) times to the GUI.

        :param model: mobility model to send event for
        :return: nothing
        """
        event_type = EventTypes.NONE
        if model.state == model.STATE_STOPPED:
            event_type = EventTypes.STOP
        elif model.state == model.STATE_RUNNING:
            event_type = EventTypes.START
        elif model.state == model.STATE_PAUSED:
            event_type = EventTypes.PAUSE

        start_time = int(model.lasttime - model.timezero)
        end_time = int(model.endtime)
        data = f"start={start_time} end={end_time}"

        event_data = EventData(
            node=model.id,
            event_type=event_type,
            name=f"mobility:{model.name}",
            data=data,
            time=str(time.monotonic()),
        )

        self.session.broadcast_event(event_data)

    def updatewlans(
        self, moved: List[NodeBase], moved_netifs: List[CoreInterface]
    ) -> None:
        """
        A mobility script has caused nodes in the 'moved' list to move.
        Update every WlanNode. This saves range calculations if the model
        were to recalculate for each individual node movement.

        :param moved: moved nodes
        :param moved_netifs: moved network interfaces
        :return: nothing
        """
        for node_id in self.nodes():
            try:
                node = self.session.get_node(node_id)
            except CoreError:
                continue
            if node.model:
                node.model.update(moved, moved_netifs)


class WirelessModel(ConfigurableOptions):
    """
    Base class used by EMANE models and the basic range model.
    Used for managing arbitrary configuration parameters.
    """

    config_type = RegisterTlvs.WIRELESS
    bitmap = None
    position_callback = None

    def __init__(self, session: "Session", _id: int):
        """
        Create a WirelessModel instance.

        :param session: core session we are tied to
        :param _id: object id
        """
        self.session = session
        self.id = _id

    def all_link_data(self, flags: MessageFlags = MessageFlags.NONE) -> List:
        """
        May be used if the model can populate the GUI with wireless (green)
        link lines.

        :param flags: link data flags
        :return: link data
        """
        return []

    def update(self, moved: bool, moved_netifs: List[CoreInterface]) -> None:
        """
        Update this wireless model.

        :param moved: flag is it was moved
        :param moved_netifs: moved network interfaces
        :return: nothing
        """
        raise NotImplementedError

    def update_config(self, config: Dict[str, str]) -> None:
        """
        For run-time updates of model config. Returns True when position callback and
        set link parameters should be invoked.

        :param config: configuration values to update
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
        Configuration(
            _id="range",
            _type=ConfigDataTypes.UINT32,
            default="275",
            label="wireless range (pixels)",
        ),
        Configuration(
            _id="bandwidth",
            _type=ConfigDataTypes.UINT64,
            default="54000000",
            label="bandwidth (bps)",
        ),
        Configuration(
            _id="jitter",
            _type=ConfigDataTypes.UINT64,
            default="0",
            label="transmission jitter (usec)",
        ),
        Configuration(
            _id="delay",
            _type=ConfigDataTypes.UINT64,
            default="5000",
            label="transmission delay (usec)",
        ),
        Configuration(
            _id="error", _type=ConfigDataTypes.STRING, default="0", label="loss (%)"
        ),
    ]

    @classmethod
    def config_groups(cls):
        return [ConfigGroup("Basic Range Parameters", 1, len(cls.configurations()))]

    def __init__(self, session: "Session", _id: int) -> None:
        """
        Create a BasicRangeModel instance.

        :param session: related core session
        :param _id: object id
        """
        super().__init__(session, _id)
        self.session = session
        self.wlan = session.get_node(_id)
        self._netifs = {}
        self._netifslock = threading.Lock()
        self.range = 0
        self.bw = None
        self.delay = None
        self.loss = None
        self.jitter = None

    def _get_config(self, current_value: int, config: Dict[str, str], name: str) -> int:
        """
        Convenience for updating value to use from a provided configuration.

        :param current_value: current config value to use when one is not provided
        :param config: config to get values from
        :param name: name of config value to get
        :return: current config value when not provided, new value otherwise
        """
        value = config.get(name)
        if value is not None:
            if value == "":
                value = None
            else:
                value = int(float(value))
        else:
            value = current_value
        return value

    def setlinkparams(self) -> None:
        """
        Apply link parameters to all interfaces. This is invoked from
        WlanNode.setmodel() after the position callback has been set.
        """
        with self._netifslock:
            for netif in self._netifs:
                self.wlan.linkconfig(
                    netif,
                    bw=self.bw,
                    delay=self.delay,
                    loss=self.loss,
                    duplicate=None,
                    jitter=self.jitter,
                )

    def get_position(self, netif: CoreInterface) -> Tuple[float, float, float]:
        """
        Retrieve network interface position.

        :param netif: network interface position to retrieve
        :return: network interface position
        """
        with self._netifslock:
            return self._netifs[netif]

    def set_position(self, netif: CoreInterface) -> None:
        """
        A node has moved; given an interface, a new (x,y,z) position has
        been set; calculate the new distance between other nodes and link or
        unlink node pairs based on the configured range.

        :param netif: network interface to set position for
        :return: nothing
        """
        x, y, z = netif.node.position.get()
        with self._netifslock:
            self._netifs[netif] = (x, y, z)
            if x is None or y is None:
                return
            for netif2 in self._netifs:
                self.calclink(netif, netif2)

    position_callback = set_position

    def update(self, moved: bool, moved_netifs: List[CoreInterface]) -> None:
        """
        Node positions have changed without recalc. Update positions from
        node.position, then re-calculate links for those that have moved.
        Assumes bidirectional links, with one calculation per node pair, where
        one of the nodes has moved.

        :param moved: flag is it was moved
        :param moved_netifs: moved network interfaces
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

    def calclink(self, netif: CoreInterface, netif2: CoreInterface) -> None:
        """
        Helper used by set_position() and update() to
        calculate distance between two interfaces and perform
        linking/unlinking. Sends link/unlink messages and updates the
        WlanNode's linked dict.

        :param netif: interface one
        :param netif2: interface two
        :return: nothing
        """
        if not self.range:
            return

        if netif == netif2:
            return
        try:
            x, y, z = self._netifs[netif]
            x2, y2, z2 = self._netifs[netif2]
            if x2 is None or y2 is None:
                return
            d = self.calcdistance((x, y, z), (x2, y2, z2))

            # calculate loss
            start_point = self.range / 2
            start_value = max(d - start_point, 0)
            loss = max(start_value / start_point, 0.001)
            loss = min(loss, 1.0) * 100
            self.wlan.change_loss(netif, netif2, loss)
            self.wlan.change_loss(netif2, netif, loss)

            # # ordering is important, to keep the wlan._linked dict organized
            a = min(netif, netif2)
            b = max(netif, netif2)
            with self.wlan._linked_lock:
                linked = self.wlan.linked(a, b)
            if d > self.range:
                if linked:
                    logging.debug("was linked, unlinking")
                    self.wlan.unlink(a, b)
                    self.sendlinkmsg(MessageFlags.DELETE, a, b)
            else:
                if not linked:
                    logging.debug("was not linked, linking")
                    self.wlan.link(a, b)
                    self.sendlinkmsg(MessageFlags.ADD, a, b, loss=loss)
                else:
                    self.sendlinkmsg(MessageFlags.NONE, a, b, loss=loss)
        except KeyError:
            logging.exception("error getting interfaces during calclinkS")

    @staticmethod
    def calcdistance(
        p1: Tuple[float, float, float], p2: Tuple[float, float, float]
    ) -> float:
        """
        Calculate the distance between two three-dimensional points.

        :param p1: point one
        :param p2: point two
        :return: distance petween the points
        """
        a = p1[0] - p2[0]
        b = p1[1] - p2[1]
        c = 0
        if p1[2] is not None and p2[2] is not None:
            c = p1[2] - p2[2]
        return math.hypot(math.hypot(a, b), c)

    def update_config(self, config: Dict[str, str]) -> None:
        """
        Configuration has changed during runtime.

        :param config: values to update configuration
        :return: nothing
        """
        self.range = self._get_config(self.range, config, "range")
        if self.range is None:
            self.range = 0
        logging.debug("wlan %s set range to %s", self.wlan.name, self.range)
        self.bw = self._get_config(self.bw, config, "bandwidth")
        self.delay = self._get_config(self.delay, config, "delay")
        self.loss = self._get_config(self.loss, config, "error")
        self.jitter = self._get_config(self.jitter, config, "jitter")

    def create_link_data(
        self,
        interface1: CoreInterface,
        interface2: CoreInterface,
        message_type: MessageFlags,
    ) -> LinkData:
        """
        Create a wireless link/unlink data message.

        :param interface1: interface one
        :param interface2: interface two
        :param message_type: link message type
        :return: link data
        """
        color = self.session.get_link_color(self.wlan.id)
        return LinkData(
            message_type=message_type,
            node1_id=interface1.node.id,
            node2_id=interface2.node.id,
            network_id=self.wlan.id,
            link_type=LinkTypes.WIRELESS,
            color=color,
        )

    def sendlinkmsg(
        self,
        message_type: MessageFlags,
        netif: CoreInterface,
        netif2: CoreInterface,
        loss: float = None,
    ) -> None:
        """
        Send a wireless link/unlink API message to the GUI.

        :param message_type: type of link message to send
        :param netif: interface one
        :param netif2: interface two
        :param loss: link loss value
        :return: nothing
        """
        label = None
        if loss is not None:
            label = f"{loss:.2f}%"
        link_data = self.create_link_data(netif, netif2, message_type)
        link_data.label = label
        self.session.broadcast_link(link_data)

    def all_link_data(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        """
        Return a list of wireless link messages for when the GUI reconnects.

        :param flags: link flags
        :return: all link data
        """
        all_links = []
        with self.wlan._linked_lock:
            for a in self.wlan._linked:
                for b in self.wlan._linked[a]:
                    if self.wlan._linked[a][b]:
                        all_links.append(self.create_link_data(a, b, flags))
        return all_links


@total_ordering
class WayPoint:
    """
    Maintains information regarding waypoints.
    """

    def __init__(self, time: float, nodenum: int, coords, speed: float):
        """
        Creates a WayPoint instance.

        :param time: waypoint time
        :param nodenum: node id
        :param coords: waypoint coordinates
        :param speed: waypoint speed
        """
        self.time = time
        self.nodenum = nodenum
        self.coords = coords
        self.speed = speed

    def __eq__(self, other: "WayPoint") -> bool:
        return (self.time, self.nodenum) == (other.time, other.nodenum)

    def __ne__(self, other: "WayPoint") -> bool:
        return not self == other

    def __lt__(self, other: "WayPoint") -> bool:
        if self.time == other.time:
            return self.nodenum < other.nodenum
        else:
            return self.time < other.time


class WayPointMobility(WirelessModel):
    """
    Abstract class for mobility models that set node waypoints.
    """

    name = "waypoint"
    config_type = RegisterTlvs.MOBILITY

    STATE_STOPPED = 0
    STATE_RUNNING = 1
    STATE_PAUSED = 2

    def __init__(self, session: "Session", _id: int) -> None:
        """
        Create a WayPointMobility instance.

        :param session: CORE session instance
        :param _id: object id
        :return:
        """
        super().__init__(session=session, _id=_id)
        self.state = self.STATE_STOPPED
        self.queue = []
        self.queue_copy = []
        self.points = {}
        self.initial = {}
        self.lasttime = None
        self.endtime = None
        self.wlan = session.get_node(_id)
        # these are really set in child class via confmatrix
        self.loop = False
        self.refresh_ms = 50
        # flag whether to stop scheduling when queue is empty
        #  (ns-3 sets this to False as new waypoints may be added from trace)
        self.empty_queue_stop = True

    def runround(self) -> None:
        """
        Advance script time and move nodes.

        :return: nothing
        """
        if self.state != self.STATE_RUNNING:
            return
        t = self.lasttime
        self.lasttime = time.monotonic()
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
                    self.session.event_loop.add_event(
                        0.001 * self.refresh_ms, self.runround
                    )
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

    def run(self) -> None:
        """
        Run the waypoint mobility scenario.

        :return: nothing
        """
        logging.info("running mobility scenario")
        self.timezero = time.monotonic()
        self.lasttime = self.timezero - (0.001 * self.refresh_ms)
        self.movenodesinitial()
        self.runround()
        self.session.mobility.sendevent(self)

    def movenode(self, node: CoreNode, dt: float) -> bool:
        """
        Calculate next node location and update its coordinates.
        Returns True if the node's position has changed.

        :param node: node to move
        :param dt: move factor
        :return: True if node was moved, False otherwise
        """
        if node.id not in self.points:
            return False
        x1, y1, z1 = node.getposition()
        x2, y2, z2 = self.points[node.id].coords
        speed = self.points[node.id].speed
        # instantaneous move (prevents dx/dy == 0.0 below)
        if speed == 0:
            self.setnodeposition(node, x2, y2, z2)
            del self.points[node.id]
            return True
        # speed can be a velocity vector or speed value
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
            del self.points[node.id]
            return False
        if (x1 + dx) < 0.0:
            dx = 0.0 - x1
        if (y1 + dy) < 0.0:
            dy = 0.0 - y1
        self.setnodeposition(node, x1 + dx, y1 + dy, z1)
        return True

    def movenodesinitial(self) -> None:
        """
        Move nodes to their initial positions. Then calculate the ranges.

        :return: nothing
        """
        moved = []
        moved_netifs = []
        for netif in self.wlan.netifs():
            node = netif.node
            if node.id not in self.initial:
                continue
            x, y, z = self.initial[node.id].coords
            self.setnodeposition(node, x, y, z)
            moved.append(node)
            moved_netifs.append(netif)
        self.session.mobility.updatewlans(moved, moved_netifs)

    def addwaypoint(
        self, _time: float, nodenum: int, x: float, y: float, z: float, speed: float
    ) -> None:
        """
        Waypoints are pushed to a heapq, sorted by time.

        :param _time: waypoint time
        :param nodenum: node id
        :param x: x position
        :param y: y position
        :param z: z position
        :param speed: speed
        :return: nothing
        """
        wp = WayPoint(_time, nodenum, coords=(x, y, z), speed=speed)
        heapq.heappush(self.queue, wp)

    def addinitial(self, nodenum: int, x: float, y: float, z: float) -> None:
        """
        Record initial position in a dict.

        :param nodenum: node id
        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        wp = WayPoint(0, nodenum, coords=(x, y, z), speed=0)
        self.initial[nodenum] = wp

    def updatepoints(self, now: float) -> None:
        """
        Move items from self.queue to self.points when their time has come.

        :param now: current timestamp
        :return: nothing
        """
        while len(self.queue):
            if self.queue[0].time > now:
                break
            wp = heapq.heappop(self.queue)
            self.points[wp.nodenum] = wp

    def copywaypoints(self) -> None:
        """
        Store backup copy of waypoints for looping and stopping.

        :return: nothing
        """
        self.queue_copy = list(self.queue)

    def loopwaypoints(self) -> bool:
        """
        Restore backup copy of waypoints when looping.

        :return: nothing
        """
        self.queue = list(self.queue_copy)
        return self.loop

    def setnodeposition(self, node: CoreNode, x: float, y: float, z: float) -> None:
        """
        Helper to move a node, notify any GUI (connected session handlers),
        without invoking the interface poshook callback that may perform
        range calculation.

        :param node: node to set position for
        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        node.position.set(x, y, z)
        self.session.broadcast_node(node)

    def setendtime(self) -> None:
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

    def start(self) -> None:
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
            now = time.monotonic()
            self.timezero += now - self.lasttime
            self.lasttime = now - (0.001 * self.refresh_ms)
            self.runround()

    def stop(self, move_initial: bool = True) -> None:
        """
        Stop the script and move nodes to initial positions.

        :param move_initial: flag to check if we should move nodes to initial
            position
        :return: nothing
        """
        self.state = self.STATE_STOPPED
        self.loopwaypoints()
        self.timezero = 0
        self.lasttime = 0
        if move_initial:
            self.movenodesinitial()
        self.session.mobility.sendevent(self)

    def pause(self) -> None:
        """
        Pause the script; pause time is stored to self.lasttime.

        :return: nothing
        """
        self.state = self.STATE_PAUSED
        self.lasttime = time.monotonic()


class Ns2ScriptedMobility(WayPointMobility):
    """
    Handles the ns-2 script format, generated by scengen/setdest or
    BonnMotion.
    """

    name = "ns2script"
    options = [
        Configuration(
            _id="file", _type=ConfigDataTypes.STRING, label="mobility script file"
        ),
        Configuration(
            _id="refresh_ms",
            _type=ConfigDataTypes.UINT32,
            default="50",
            label="refresh time (ms)",
        ),
        Configuration(
            _id="loop", _type=ConfigDataTypes.BOOL, default="1", label="loop"
        ),
        Configuration(
            _id="autostart",
            _type=ConfigDataTypes.STRING,
            label="auto-start seconds (0.0 for runtime)",
        ),
        Configuration(
            _id="map",
            _type=ConfigDataTypes.STRING,
            label="node mapping (optional, e.g. 0:1,1:2,2:3)",
        ),
        Configuration(
            _id="script_start",
            _type=ConfigDataTypes.STRING,
            label="script file to run upon start",
        ),
        Configuration(
            _id="script_pause",
            _type=ConfigDataTypes.STRING,
            label="script file to run upon pause",
        ),
        Configuration(
            _id="script_stop",
            _type=ConfigDataTypes.STRING,
            label="script file to run upon stop",
        ),
    ]

    @classmethod
    def config_groups(cls) -> List[ConfigGroup]:
        return [
            ConfigGroup("ns-2 Mobility Script Parameters", 1, len(cls.configurations()))
        ]

    def __init__(self, session: "Session", _id: int):
        """
        Creates a Ns2ScriptedMobility instance.

        :param session: CORE session instance
        :param _id: object id
        """
        super().__init__(session, _id)
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

    def update_config(self, config: Dict[str, str]) -> None:
        self.file = config["file"]
        logging.info(
            "ns-2 scripted mobility configured for WLAN %d using file: %s",
            self.id,
            self.file,
        )
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

    def readscriptfile(self) -> None:
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
            logging.exception(
                "ns-2 scripted mobility failed to load file: %s", self.file
            )
            return
        logging.info("reading ns-2 script file: %s", filename)
        ln = 0
        ix = iy = iz = None
        inodenum = None
        for line in f:
            ln += 1
            if line[:2] != "$n":
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
                    nodenum = parts[3][1 + parts[3].index("(") : parts[3].index(")")]
                    x = float(parts[5])
                    y = float(parts[6])
                    z = None
                    speed = float(parts[7].strip('"'))
                    self.addwaypoint(time, self.map(nodenum), x, y, z, speed)
                elif line[:7] == "$node_(":
                    # initial position (time=0, speed=0):
                    #    $node_(6) set X_ 780.0
                    parts = line.split()
                    nodenum = parts[0][1 + parts[0].index("(") : parts[0].index(")")]
                    if parts[2] == "X_":
                        if ix is not None and iy is not None:
                            self.addinitial(self.map(inodenum), ix, iy, iz)
                            ix = iy = iz = None
                        ix = float(parts[3])
                    elif parts[2] == "Y_":
                        iy = float(parts[3])
                    elif parts[2] == "Z_":
                        iz = float(parts[3])
                        self.addinitial(self.map(nodenum), ix, iy, iz)
                        ix = iy = iz = None
                    inodenum = nodenum
                else:
                    raise ValueError
            except ValueError:
                logging.exception(
                    "skipping line %d of file %s '%s'", ln, self.file, line
                )
                continue
        if ix is not None and iy is not None:
            self.addinitial(self.map(inodenum), ix, iy, iz)

    def findfile(self, file_name: str) -> str:
        """
        Locate a script file. If the specified file doesn't exist, look in the
        same directory as the scenario file, or in the default
        configs directory (~/.core/configs). This allows for sample files without
        absolute path names.

        :param file_name: file name to find
        :return: absolute path to the file
        """
        if os.path.exists(file_name):
            return file_name

        if self.session.file_name is not None:
            d = os.path.dirname(self.session.file_name)
            sessfn = os.path.join(d, file_name)
            if os.path.exists(sessfn):
                return sessfn

        if self.session.user is not None:
            userfn = os.path.join(
                "/home", self.session.user, ".core", "configs", file_name
            )
            if os.path.exists(userfn):
                return userfn

        return file_name

    def parsemap(self, mapstr: str) -> None:
        """
        Parse a node mapping string, given as a configuration parameter.

        :param mapstr: mapping string to parse
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

    def map(self, nodenum: str) -> int:
        """
        Map one node number (from a script file) to another.

        :param nodenum: node id to map
        :return: mapped value or the node id itself
        """
        nodenum = int(nodenum)
        return self.nodemap.get(nodenum, nodenum)

    def startup(self) -> None:
        """
        Start running the script if autostart is enabled.
        Move node to initial positions when any autostart time is specified.
        Ignore the script if autostart is an empty string (can still be
        started via GUI controls).

        :return: nothing
        """
        if self.autostart == "":
            logging.info("not auto-starting ns-2 script for %s", self.wlan.name)
            return
        try:
            t = float(self.autostart)
        except ValueError:
            logging.exception(
                "Invalid auto-start seconds specified '%s' for %s",
                self.autostart,
                self.wlan.name,
            )
            return
        self.movenodesinitial()
        logging.info("scheduling ns-2 script for %s autostart at %s", self.wlan.name, t)
        self.state = self.STATE_RUNNING
        self.session.event_loop.add_event(t, self.run)

    def start(self) -> None:
        """
        Handle the case when un-paused.

        :return: nothing
        """
        logging.info("starting script")
        laststate = self.state
        super().start()
        if laststate == self.STATE_PAUSED:
            self.statescript("unpause")

    def run(self) -> None:
        """
        Start is pressed or autostart is triggered.

        :return: nothing
        """
        super().run()
        self.statescript("run")

    def pause(self) -> None:
        """
        Pause the mobility script.

        :return: nothing
        """
        super().pause()
        self.statescript("pause")

    def stop(self, move_initial: bool = True) -> None:
        """
        Stop the mobility script.

        :param move_initial: flag to check if we should move node to initial
            position
        :return: nothing
        """
        super().stop(move_initial=move_initial)
        self.statescript("stop")

    def statescript(self, typestr: str) -> None:
        """
        State of the mobility script.

        :param typestr: state type string
        :return: nothing
        """
        filename = None
        if typestr == "run" or typestr == "unpause":
            filename = self.script_start
        elif typestr == "pause":
            filename = self.script_pause
        elif typestr == "stop":
            filename = self.script_stop
        if filename is None or filename == "":
            return
        filename = self.findfile(filename)
        args = f"/bin/sh {filename} {typestr}"
        utils.cmd(
            args, cwd=self.session.session_dir, env=self.session.get_environment()
        )
