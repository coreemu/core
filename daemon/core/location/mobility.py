"""
mobility.py: mobility helpers for moving nodes and calculating wireless range.
"""

import heapq
import logging
import math
import threading
import time
from functools import total_ordering
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Union

from core import utils
from core.config import (
    ConfigBool,
    ConfigFloat,
    ConfigGroup,
    ConfigInt,
    ConfigString,
    ConfigurableOptions,
    Configuration,
    ModelManager,
)
from core.emane.nodes import EmaneNet
from core.emulator.data import EventData, LinkData, LinkOptions
from core.emulator.enumerations import EventTypes, LinkTypes, MessageFlags, RegisterTlvs
from core.errors import CoreError
from core.executables import BASH
from core.nodes.base import CoreNode
from core.nodes.interface import CoreInterface
from core.nodes.network import WlanNode

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

LEARNING_DISABLED: int = 0
LEARNING_ENABLED: int = 30000


def get_mobility_node(session: "Session", node_id: int) -> Union[WlanNode, EmaneNet]:
    try:
        return session.get_node(node_id, WlanNode)
    except CoreError:
        return session.get_node(node_id, EmaneNet)


def get_config_int(current: int, config: dict[str, str], name: str) -> Optional[int]:
    """
    Convenience function to get config values as int.

    :param current: current config value to use when one is not provided
    :param config: config to get values from
    :param name: name of config value to get
    :return: current config value when not provided, new value otherwise
    """
    value = get_config_float(current, config, name)
    if value is not None:
        value = int(value)
    return value


def get_config_float(
    current: Union[int, float], config: dict[str, str], name: str
) -> Optional[float]:
    """
    Convenience function to get config values as float.

    :param current: current config value to use when one is not provided
    :param config: config to get values from
    :param name: name of config value to get
    :return: current config value when not provided, new value otherwise
    """
    value = config.get(name)
    if value is not None:
        if value == "":
            value = None
        else:
            value = float(value)
    else:
        value = current
    return value


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
        self.session: "Session" = session
        self.models[BasicRangeModel.name] = BasicRangeModel
        self.models[Ns2ScriptedMobility.name] = Ns2ScriptedMobility

    def reset(self) -> None:
        """
        Clear out all current configurations.

        :return: nothing
        """
        self.config_reset()

    def startup(self, node_ids: list[int] = None) -> None:
        """
        Session is transitioning from instantiation to runtime state.
        Instantiate any mobility models that have been configured for a WLAN.

        :param node_ids: node ids to startup
        :return: nothing
        """
        if node_ids is None:
            node_ids = self.nodes()
        for node_id in node_ids:
            logger.debug(
                "node(%s) mobility startup: %s", node_id, self.get_all_configs(node_id)
            )
            try:
                node = get_mobility_node(self.session, node_id)
                # TODO: may be an issue if there are multiple mobility models
                for model in self.models.values():
                    config = self.get_configs(node_id, model.name)
                    if not config:
                        continue
                    self.set_model(node, model, config)
                if node.mobility:
                    self.session.event_loop.add_event(0.0, node.mobility.startup)
            except CoreError:
                logger.exception("mobility startup error")
                logger.warning(
                    "skipping mobility configuration for unknown node: %s", node_id
                )

    def handleevent(self, event_data: EventData) -> None:
        """
        Handle an Event Message used to start, stop, or pause
        mobility scripts for a given mobility network.

        :param event_data: event data to handle
        :return: nothing
        """
        event_type = event_data.event_type
        node_id = event_data.node
        name = event_data.name
        try:
            node = get_mobility_node(self.session, node_id)
        except CoreError:
            logger.exception(
                "ignoring event for model(%s), unknown node(%s)", name, node_id
            )
            return

        # name is e.g. "mobility:ns2script"
        models = name[9:].split(",")
        for model in models:
            cls = self.models.get(model)
            if not cls:
                logger.warning("ignoring event for unknown model '%s'", model)
                continue
            if cls.config_type in [RegisterTlvs.WIRELESS, RegisterTlvs.MOBILITY]:
                model = node.mobility
            else:
                continue
            if model is None:
                logger.warning("ignoring event, %s has no model", node.name)
                continue
            if cls.name != model.name:
                logger.warning(
                    "ignoring event for %s wrong model %s,%s",
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


class WirelessModel(ConfigurableOptions):
    """
    Base class used by EMANE models and the basic range model.
    Used for managing arbitrary configuration parameters.
    """

    config_type: RegisterTlvs = RegisterTlvs.WIRELESS
    position_callback: Callable[[CoreInterface], None] = None

    def __init__(self, session: "Session", _id: int) -> None:
        """
        Create a WirelessModel instance.

        :param session: core session we are tied to
        :param _id: object id
        """
        self.session: "Session" = session
        self.id: int = _id

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> list[LinkData]:
        """
        May be used if the model can populate the GUI with wireless (green)
        link lines.

        :param flags: link data flags
        :return: link data
        """
        return []

    def update(self, moved_ifaces: list[CoreInterface]) -> None:
        """
        Update this wireless model.

        :param moved_ifaces: moved network interfaces
        :return: nothing
        """
        raise NotImplementedError

    def update_config(self, config: dict[str, str]) -> None:
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

    name: str = "basic_range"
    options: list[Configuration] = [
        ConfigInt(id="range", default="275", label="wireless range (pixels)"),
        ConfigInt(id="bandwidth", default="54000000", label="bandwidth (bps)"),
        ConfigInt(id="jitter", default="0", label="transmission jitter (usec)"),
        ConfigInt(id="delay", default="5000", label="transmission delay (usec)"),
        ConfigFloat(id="error", default="0.0", label="loss (%)"),
        ConfigBool(id="promiscuous", default="0", label="promiscuous mode"),
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
        self.session: "Session" = session
        self.wlan: WlanNode = session.get_node(_id, WlanNode)
        self.iface_to_pos: dict[CoreInterface, tuple[float, float, float]] = {}
        self.iface_lock: threading.Lock = threading.Lock()
        self.range: int = 0
        self.bw: Optional[int] = None
        self.delay: Optional[int] = None
        self.loss: Optional[float] = None
        self.jitter: Optional[int] = None
        self.promiscuous: bool = False

    def setlinkparams(self) -> None:
        """
        Apply link parameters to all interfaces. This is invoked from
        WlanNode.setmodel() after the position callback has been set.
        """
        with self.iface_lock:
            for iface in self.iface_to_pos:
                options = LinkOptions(
                    bandwidth=self.bw,
                    delay=self.delay,
                    loss=self.loss,
                    jitter=self.jitter,
                )
                iface.options.update(options)
                iface.set_config()

    def get_position(self, iface: CoreInterface) -> tuple[float, float, float]:
        """
        Retrieve network interface position.

        :param iface: network interface position to retrieve
        :return: network interface position
        """
        with self.iface_lock:
            return self.iface_to_pos[iface]

    def set_position(self, iface: CoreInterface) -> None:
        """
        A node has moved; given an interface, a new (x,y,z) position has
        been set; calculate the new distance between other nodes and link or
        unlink node pairs based on the configured range.

        :param iface: network interface to set position for
        :return: nothing
        """
        x, y, z = iface.node.position.get()
        with self.iface_lock:
            self.iface_to_pos[iface] = (x, y, z)
            if x is None or y is None:
                return
            for iface2 in self.iface_to_pos:
                self.calclink(iface, iface2)

    position_callback = set_position

    def update(self, moved_ifaces: list[CoreInterface]) -> None:
        """
        Node positions have changed without recalc. Update positions from
        node.position, then re-calculate links for those that have moved.
        Assumes bidirectional links, with one calculation per node pair, where
        one of the nodes has moved.

        :param moved_ifaces: moved network interfaces
        :return: nothing
        """
        with self.iface_lock:
            while len(moved_ifaces):
                iface = moved_ifaces.pop()
                nx, ny, nz = iface.node.getposition()
                if iface in self.iface_to_pos:
                    self.iface_to_pos[iface] = (nx, ny, nz)
                for iface2 in self.iface_to_pos:
                    if iface2 in moved_ifaces:
                        continue
                    self.calclink(iface, iface2)

    def calclink(self, iface: CoreInterface, iface2: CoreInterface) -> None:
        """
        Helper used by set_position() and update() to
        calculate distance between two interfaces and perform
        linking/unlinking. Sends link/unlink messages and updates the
        WlanNode's linked dict.

        :param iface: interface one
        :param iface2: interface two
        :return: nothing
        """
        if iface == iface2:
            return
        try:
            x, y, z = self.iface_to_pos[iface]
            x2, y2, z2 = self.iface_to_pos[iface2]
            if x2 is None or y2 is None:
                return
            d = self.calcdistance((x, y, z), (x2, y2, z2))
            # ordering is important, to keep the wlan._linked dict organized
            a = min(iface, iface2)
            b = max(iface, iface2)
            with self.wlan.linked_lock:
                linked = self.wlan.is_linked(a, b)
            if d > self.range:
                if linked:
                    logger.debug("was linked, unlinking")
                    self.wlan.unlink(a, b)
                    self.sendlinkmsg(a, b, unlink=True)
            else:
                if not linked:
                    logger.debug("was not linked, linking")
                    self.wlan.link(a, b)
                    self.sendlinkmsg(a, b)
        except KeyError:
            logger.exception("error getting interfaces during calclink")

    @staticmethod
    def calcdistance(
        p1: tuple[float, float, float], p2: tuple[float, float, float]
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

    def update_config(self, config: dict[str, str]) -> None:
        """
        Configuration has changed during runtime.

        :param config: values to update configuration
        :return: nothing
        """
        self.range = get_config_int(self.range, config, "range")
        if self.range is None:
            self.range = 0
        logger.debug("wlan %s set range to %s", self.wlan.name, self.range)
        self.bw = get_config_int(self.bw, config, "bandwidth")
        self.delay = get_config_int(self.delay, config, "delay")
        self.loss = get_config_float(self.loss, config, "error")
        self.jitter = get_config_int(self.jitter, config, "jitter")
        promiscuous = config.get("promiscuous", "0") == "1"
        if self.promiscuous and not promiscuous:
            self.wlan.net_client.set_mac_learning(self.wlan.brname, LEARNING_ENABLED)
        elif not self.promiscuous and promiscuous:
            self.wlan.net_client.set_mac_learning(self.wlan.brname, LEARNING_DISABLED)
        self.promiscuous = promiscuous
        self.setlinkparams()

    def create_link_data(
        self, iface1: CoreInterface, iface2: CoreInterface, message_type: MessageFlags
    ) -> LinkData:
        """
        Create a wireless link/unlink data message.

        :param iface1: interface one
        :param iface2: interface two
        :param message_type: link message type
        :return: link data
        """
        color = self.session.get_link_color(self.wlan.id)
        return LinkData(
            message_type=message_type,
            type=LinkTypes.WIRELESS,
            node1_id=iface1.node.id,
            node2_id=iface2.node.id,
            network_id=self.wlan.id,
            color=color,
        )

    def sendlinkmsg(
        self, iface: CoreInterface, iface2: CoreInterface, unlink: bool = False
    ) -> None:
        """
        Send a wireless link/unlink API message to the GUI.

        :param iface: interface one
        :param iface2: interface two
        :param unlink: unlink or not
        :return: nothing
        """
        message_type = MessageFlags.DELETE if unlink else MessageFlags.ADD
        link_data = self.create_link_data(iface, iface2, message_type)
        self.session.broadcast_link(link_data)

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> list[LinkData]:
        """
        Return a list of wireless link messages for when the GUI reconnects.

        :param flags: link flags
        :return: all link data
        """
        all_links = []
        with self.wlan.linked_lock:
            for a in self.wlan.linked:
                for b in self.wlan.linked[a]:
                    if self.wlan.linked[a][b]:
                        all_links.append(self.create_link_data(a, b, flags))
        return all_links


@total_ordering
class WayPoint:
    """
    Maintains information regarding waypoints.
    """

    def __init__(
        self,
        _time: float,
        node_id: int,
        coords: tuple[float, float, Optional[float]],
        speed: float,
    ) -> None:
        """
        Creates a WayPoint instance.

        :param _time: waypoint time
        :param node_id: node id
        :param coords: waypoint coordinates
        :param speed: waypoint speed
        """
        self.time: float = _time
        self.node_id: int = node_id
        self.coords: tuple[float, float, Optional[float]] = coords
        self.speed: float = speed

    def __eq__(self, other: "WayPoint") -> bool:
        return (self.time, self.node_id) == (other.time, other.node_id)

    def __ne__(self, other: "WayPoint") -> bool:
        return not self == other

    def __lt__(self, other: "WayPoint") -> bool:
        if self.time == other.time:
            return self.node_id < other.node_id
        else:
            return self.time < other.time


class WayPointMobility(WirelessModel):
    """
    Abstract class for mobility models that set node waypoints.
    """

    name: str = "waypoint"
    config_type: RegisterTlvs = RegisterTlvs.MOBILITY
    STATE_STOPPED: int = 0
    STATE_RUNNING: int = 1
    STATE_PAUSED: int = 2

    def __init__(self, session: "Session", _id: int) -> None:
        """
        Create a WayPointMobility instance.

        :param session: CORE session instance
        :param _id: object id
        :return:
        """
        super().__init__(session=session, _id=_id)
        self.state: int = self.STATE_STOPPED
        self.queue: list[WayPoint] = []
        self.queue_copy: list[WayPoint] = []
        self.points: dict[int, WayPoint] = {}
        self.initial: dict[int, WayPoint] = {}
        self.lasttime: Optional[float] = None
        self.endtime: Optional[int] = None
        self.timezero: float = 0.0
        self.net: Union[WlanNode, EmaneNet] = get_mobility_node(self.session, self.id)
        # these are really set in child class via confmatrix
        self.loop: bool = False
        self.refresh_ms: int = 50
        # flag whether to stop scheduling when queue is empty
        #  (ns-3 sets this to False as new waypoints may be added from trace)
        self.empty_queue_stop: bool = True

    def startup(self):
        raise NotImplementedError

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

        moved_ifaces = []
        for iface in self.net.get_ifaces():
            node = iface.node
            if self.movenode(node, dt):
                moved_ifaces.append(iface)

        # calculate all ranges after moving nodes; this saves calculations
        self.net.wireless_model.update(moved_ifaces)

        # TODO: check session state
        self.session.event_loop.add_event(0.001 * self.refresh_ms, self.runround)

    def run(self) -> None:
        """
        Run the waypoint mobility scenario.

        :return: nothing
        """
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

        # linear speed value
        alpha = math.atan2(y2 - y1, x2 - x1)
        sx = speed * math.cos(alpha)
        sy = speed * math.sin(alpha)

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
        moved_ifaces = []
        for iface in self.net.get_ifaces():
            node = iface.node
            if node.id not in self.initial:
                continue
            x, y, z = self.initial[node.id].coords
            self.setnodeposition(node, x, y, z)
            moved_ifaces.append(iface)
        self.net.wireless_model.update(moved_ifaces)

    def addwaypoint(
        self,
        _time: float,
        nodenum: int,
        x: float,
        y: float,
        z: Optional[float],
        speed: float,
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
            self.points[wp.node_id] = wp

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

    name: str = "ns2script"
    options: list[Configuration] = [
        ConfigString(id="file", label="mobility script file"),
        ConfigInt(id="refresh_ms", default="50", label="refresh time (ms)"),
        ConfigBool(id="loop", default="1", label="loop"),
        ConfigString(id="autostart", label="auto-start seconds (0.0 for runtime)"),
        ConfigString(id="map", label="node mapping (optional, e.g. 0:1,1:2,2:3)"),
        ConfigString(id="script_start", label="script file to run upon start"),
        ConfigString(id="script_pause", label="script file to run upon pause"),
        ConfigString(id="script_stop", label="script file to run upon stop"),
    ]

    @classmethod
    def config_groups(cls) -> list[ConfigGroup]:
        return [
            ConfigGroup("ns-2 Mobility Script Parameters", 1, len(cls.configurations()))
        ]

    def __init__(self, session: "Session", _id: int) -> None:
        """
        Creates a Ns2ScriptedMobility instance.

        :param session: CORE session instance
        :param _id: object id
        """
        super().__init__(session, _id)
        self.file: Optional[Path] = None
        self.autostart: Optional[str] = None
        self.nodemap: dict[int, int] = {}
        self.script_start: Optional[str] = None
        self.script_pause: Optional[str] = None
        self.script_stop: Optional[str] = None

    def update_config(self, config: dict[str, str]) -> None:
        self.file = Path(config["file"])
        logger.info(
            "ns-2 scripted mobility configured for WLAN %d using file: %s",
            self.id,
            self.file,
        )
        self.refresh_ms = int(config["refresh_ms"])
        self.loop = config["loop"] == "1"
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
        file_path = self.findfile(self.file)
        try:
            f = file_path.open("r")
        except OSError:
            logger.exception(
                "ns-2 scripted mobility failed to load file: %s", self.file
            )
            return
        logger.info("reading ns-2 script file: %s", file_path)
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
                    line_time = float(parts[2])
                    nodenum = parts[3][1 + parts[3].index("(") : parts[3].index(")")]
                    x = float(parts[5])
                    y = float(parts[6])
                    z = None
                    speed = float(parts[7].strip('"'))
                    self.addwaypoint(line_time, self.map(nodenum), x, y, z, speed)
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
                logger.exception(
                    "skipping line %d of file %s '%s'", ln, self.file, line
                )
                continue
        if ix is not None and iy is not None:
            self.addinitial(self.map(inodenum), ix, iy, iz)

    def findfile(self, file_path: Path) -> Path:
        """
        Locate a script file. If the specified file doesn't exist, look in the
        same directory as the scenario file, or in gui directories.

        :param file_path: file name to find
        :return: absolute path to the file
        :raises CoreError: when file is not found
        """
        file_path = file_path.expanduser()
        if file_path.exists():
            return file_path
        if self.session.file_path:
            session_file_path = self.session.file_path.parent / file_path
            if session_file_path.exists():
                return session_file_path
        if self.session.user:
            user_path = Path(f"~{self.session.user}").expanduser()
            configs_path = user_path / ".core" / "configs" / file_path
            if configs_path.exists():
                return configs_path
            mobility_path = user_path / ".coregui" / "mobility" / file_path
            if mobility_path.exists():
                return mobility_path
        raise CoreError(f"invalid file: {file_path}")

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
                logger.exception("ns-2 mobility node map error")

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
            logger.info("not auto-starting ns-2 script for %s", self.net.name)
            return
        try:
            t = float(self.autostart)
        except ValueError:
            logger.exception(
                "Invalid auto-start seconds specified '%s' for %s",
                self.autostart,
                self.net.name,
            )
            return
        self.movenodesinitial()
        logger.info("scheduling ns-2 script for %s autostart at %s", self.net.name, t)
        self.state = self.STATE_RUNNING
        self.session.event_loop.add_event(t, self.run)

    def start(self) -> None:
        """
        Handle the case when un-paused.

        :return: nothing
        """
        logger.info("starting script: %s", self.file)
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
        logger.info("pausing script: %s", self.file)
        super().pause()
        self.statescript("pause")

    def stop(self, move_initial: bool = True) -> None:
        """
        Stop the mobility script.

        :param move_initial: flag to check if we should move node to initial
            position
        :return: nothing
        """
        logger.info("stopping script: %s", self.file)
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
        filename = Path(filename)
        filename = self.findfile(filename)
        args = f"{BASH} {filename} {typestr}"
        utils.cmd(args, cwd=self.session.directory, env=self.session.get_environment())
