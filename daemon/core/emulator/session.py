"""
session.py: defines the Session class used by the core-daemon daemon program
that manages a CORE session.
"""

import logging
import math
import os
import pwd
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, TypeVar

from core import constants, utils
from core.emane.emanemanager import EmaneManager, EmaneState
from core.emane.nodes import EmaneNet
from core.emulator.broadcast import BroadcastManager
from core.emulator.controlnets import ControlNetManager
from core.emulator.data import (
    AlertData,
    EventData,
    InterfaceData,
    LinkData,
    LinkOptions,
    NodeData,
)
from core.emulator.distributed import DistributedController
from core.emulator.enumerations import AlertLevels, EventTypes, MessageFlags, NodeTypes
from core.emulator.hooks import HookManager
from core.emulator.links import CoreLink, LinkManager
from core.emulator.sessionconfig import SessionConfig
from core.errors import CoreError
from core.location.event import EventLoop
from core.location.geo import GeoLocation
from core.location.mobility import BasicRangeModel, MobilityManager
from core.nodes.base import CoreNode, CoreNodeBase, NodeBase, NodeOptions, Position
from core.nodes.docker import DockerNode
from core.nodes.interface import DEFAULT_MTU, CoreInterface
from core.nodes.network import (
    CtrlNet,
    GreTapBridge,
    HubNode,
    PtpNet,
    SwitchNode,
    TunnelNode,
    WlanNode,
)
from core.nodes.physical import PhysicalNode, Rj45Node
from core.nodes.podman import PodmanNode
from core.nodes.wireless import WirelessNode
from core.plugins.sdt import Sdt
from core.services.manager import ServiceManager
from core.xml import corexml, corexmldeployment
from core.xml.corexml import CoreXmlReader, CoreXmlWriter

logger = logging.getLogger(__name__)

# maps for converting from API call node type values to classes and vice versa
NODES: dict[NodeTypes, type[NodeBase]] = {
    NodeTypes.DEFAULT: CoreNode,
    NodeTypes.PHYSICAL: PhysicalNode,
    NodeTypes.SWITCH: SwitchNode,
    NodeTypes.HUB: HubNode,
    NodeTypes.WIRELESS_LAN: WlanNode,
    NodeTypes.RJ45: Rj45Node,
    NodeTypes.TUNNEL: TunnelNode,
    NodeTypes.EMANE: EmaneNet,
    NodeTypes.TAP_BRIDGE: GreTapBridge,
    NodeTypes.DOCKER: DockerNode,
    NodeTypes.WIRELESS: WirelessNode,
    NodeTypes.PODMAN: PodmanNode,
}
NODES_TYPE: dict[type[NodeBase], NodeTypes] = {NODES[x]: x for x in NODES}
CTRL_NET_ID: int = 9001
LINK_COLORS: list[str] = ["green", "blue", "orange", "purple", "turquoise"]
NT: TypeVar = TypeVar("NT", bound=NodeBase)
WIRELESS_TYPE: tuple[type[WlanNode], type[EmaneNet], type[WirelessNode]] = (
    WlanNode,
    EmaneNet,
    WirelessNode,
)


class Session:
    """
    CORE session manager.
    """

    def __init__(
        self, _id: int, config: dict[str, str] = None, mkdir: bool = True
    ) -> None:
        """
        Create a Session instance.

        :param _id: session id
        :param config: session configuration
        :param mkdir: flag to determine if a directory should be made
        """
        self.id: int = _id

        # define and create session directory when desired
        self.directory: Path = Path(tempfile.gettempdir()) / f"pycore.{self.id}"
        if mkdir:
            self.directory.mkdir()

        self.name: str | None = None
        self.file_path: Path | None = None
        self.thumbnail: Path | None = None
        self.user: str | None = None
        self.event_loop: EventLoop = EventLoop()
        self.link_colors: dict[int, str] = {}

        # dict of nodes: all nodes and nets
        self.nodes: dict[int, NodeBase] = {}
        self.ptp_nodes: dict[int, PtpNet] = {}
        self.control_nodes: dict[int, CtrlNet] = {}
        self.nodes_lock: threading.Lock = threading.Lock()
        self.link_manager: LinkManager = LinkManager()

        # states and hooks handlers
        self.state: EventTypes = EventTypes.DEFINITION_STATE
        self.state_time: float = time.monotonic()

        # session options/metadata
        self.options: SessionConfig = SessionConfig(config)
        self.metadata: dict[str, str] = {}

        # distributed support and logic
        self.distributed: DistributedController = DistributedController(self)

        # initialize session feature helpers
        self.control_net_manager: ControlNetManager = ControlNetManager(self)
        self.broadcast_manager: BroadcastManager = BroadcastManager()
        self.hook_manager: HookManager = HookManager()
        self.hook_manager.add_callback_hook(
            EventTypes.RUNTIME_STATE, self.runtime_state_hook
        )
        self.location: GeoLocation = GeoLocation()
        self.mobility: MobilityManager = MobilityManager(self)
        self.emane: EmaneManager = EmaneManager(self)
        self.service_manager: ServiceManager | None = None
        self.sdt: Sdt = Sdt(self)

    @classmethod
    def get_node_class(cls, _type: NodeTypes) -> type[NodeBase]:
        """
        Retrieve the class for a given node type.

        :param _type: node type to get class for
        :return: node class
        """
        node_class = NODES.get(_type)
        if node_class is None:
            raise CoreError(f"invalid node type: {_type}")
        return node_class

    @classmethod
    def get_node_type(cls, _class: type[NodeBase]) -> NodeTypes:
        """
        Retrieve node type for a given node class.

        :param _class: node class to get a node type for
        :return: node type
        :raises CoreError: when node type does not exist
        """
        node_type = NODES_TYPE.get(_class)
        if node_type is None:
            raise CoreError(f"invalid node class: {_class}")
        return node_type

    def use_ovs(self) -> bool:
        return self.options.get_int("ovs") == 1

    def linked(
        self, node1_id: int, node2_id: int, iface1_id: int, iface2_id: int, linked: bool
    ) -> None:
        """
        Links or unlinks wired core link interfaces from being connected to the same
        bridge.

        :param node1_id: first node in link
        :param node2_id: second node in link
        :param iface1_id: node1 interface
        :param iface2_id: node2 interface
        :param linked: True if interfaces should be connected, False for disconnected
        :return: nothing
        """
        node1 = self.get_node(node1_id, NodeBase)
        node2 = self.get_node(node2_id, NodeBase)
        logger.info(
            "link node(%s):interface(%s) node(%s):interface(%s) linked(%s)",
            node1.name,
            iface1_id,
            node2.name,
            iface2_id,
            linked,
        )
        iface1 = node1.get_iface(iface1_id)
        iface2 = node2.get_iface(iface2_id)
        core_link = self.link_manager.get_link(node1, iface1, node2, iface2)
        if not core_link:
            raise CoreError(
                f"there is no link for node({node1.name}):interface({iface1_id}) "
                f"node({node2.name}):interface({iface2_id})"
            )
        if linked:
            core_link.ptp.attach(iface1)
            core_link.ptp.attach(iface2)
        else:
            core_link.ptp.detach(iface1)
            core_link.ptp.detach(iface2)

    def add_link(
        self,
        node1_id: int,
        node2_id: int,
        iface1_data: InterfaceData = None,
        iface2_data: InterfaceData = None,
        options: LinkOptions = None,
    ) -> tuple[CoreInterface | None, CoreInterface | None]:
        """
        Add a link between nodes.

        :param node1_id: node one id
        :param node2_id: node two id
        :param iface1_data: node one interface
            data, defaults to none
        :param iface2_data: node two interface
            data, defaults to none
        :param options: data for creating link,
            defaults to no options
        :return: tuple of created core interfaces, depending on link
        """
        options = options if options else LinkOptions()
        # set mtu
        mtu = self.options.get_int("mtu") or DEFAULT_MTU
        if iface1_data:
            iface1_data.mtu = mtu
        if iface2_data:
            iface2_data.mtu = mtu
        node1 = self.get_node(node1_id, NodeBase)
        node2 = self.get_node(node2_id, NodeBase)
        # check for invalid linking
        if (
            isinstance(node1, WIRELESS_TYPE)
            and isinstance(node2, WIRELESS_TYPE)
            or isinstance(node1, WIRELESS_TYPE)
            and not isinstance(node2, CoreNodeBase)
            or not isinstance(node1, CoreNodeBase)
            and isinstance(node2, WIRELESS_TYPE)
        ):
            raise CoreError(f"cannot link node({type(node1)}) node({type(node2)})")
        # custom links
        iface1 = None
        iface2 = None
        if isinstance(node1, (WlanNode, WirelessNode)):
            iface2 = self._add_wlan_link(node2, iface2_data, node1)
        elif isinstance(node2, (WlanNode, WirelessNode)):
            iface1 = self._add_wlan_link(node1, iface1_data, node2)
        elif isinstance(node1, EmaneNet) and isinstance(node2, CoreNode):
            iface2 = self._add_emane_link(node2, iface2_data, node1)
        elif isinstance(node2, EmaneNet) and isinstance(node1, CoreNode):
            iface1 = self._add_emane_link(node1, iface1_data, node2)
        else:
            iface1, iface2 = self._add_wired_link(
                node1, node2, iface1_data, iface2_data, options
            )
        # configure tunnel nodes
        key = options.key
        if isinstance(node1, TunnelNode):
            logger.info("setting tunnel key for: %s", node1.name)
            node1.setkey(key, iface1_data)
        if isinstance(node2, TunnelNode):
            logger.info("setting tunnel key for: %s", node2.name)
            node2.setkey(key, iface2_data)
        self.sdt.add_link(node1_id, node2_id)
        return iface1, iface2

    def _add_wlan_link(
        self,
        node: NodeBase,
        iface_data: InterfaceData,
        net: WlanNode | WirelessNode,
    ) -> CoreInterface:
        """
        Create a wlan link.

        :param node: node to link to wlan network
        :param iface_data: data to create interface with
        :param net: wlan network to link to
        :return: interface created for node
        """
        # create interface
        iface = node.create_iface(iface_data)
        # attach to wlan
        net.attach(iface)
        # track link
        core_link = CoreLink(node, iface, net, None)
        self.link_manager.add(core_link)
        return iface

    def _add_emane_link(
        self, node: CoreNode, iface_data: InterfaceData, net: EmaneNet
    ) -> CoreInterface:
        """
        Create am emane link.

        :param node: node to link to emane network
        :param iface_data: data to create interface with
        :param net: emane network to link to
        :return: interface created for node
        """
        # create iface tuntap
        iface = net.create_tuntap(node, iface_data)
        # track link
        core_link = CoreLink(node, iface, net, None)
        self.link_manager.add(core_link)
        return iface

    def _add_wired_link(
        self,
        node1: NodeBase,
        node2: NodeBase,
        iface1_data: InterfaceData = None,
        iface2_data: InterfaceData = None,
        options: LinkOptions = None,
    ) -> tuple[CoreInterface, CoreInterface]:
        """
        Create a wired link between two nodes.

        :param node1: first node to be linked
        :param node2: second node to be linked
        :param iface1_data: data to create interface for node1
        :param iface2_data: data to create interface for node2
        :param options: options to configure interfaces with
        :return: interfaces created for both nodes
        """
        # create interfaces
        iface1 = node1.create_iface(iface1_data, options)
        iface2 = node2.create_iface(iface2_data, options)
        # join and attach to ptp bridge
        ptp = self.create_ptp()
        ptp.attach(iface1)
        ptp.attach(iface2)
        # track link
        core_link = CoreLink(node1, iface1, node2, iface2, ptp)
        self.link_manager.add(core_link)
        # setup link for gre tunnels if needed
        if ptp.up:
            self.distributed.create_gre_tunnels(core_link)
        return iface1, iface2

    def delete_link(
        self, node1_id: int, node2_id: int, iface1_id: int = None, iface2_id: int = None
    ) -> None:
        """
        Delete a link between nodes.

        :param node1_id: node one id
        :param node2_id: node two id
        :param iface1_id: interface id for node one
        :param iface2_id: interface id for node two
        :return: nothing
        :raises core.CoreError: when no common network is found for link being deleted
        """
        node1 = self.get_node(node1_id, NodeBase)
        node2 = self.get_node(node2_id, NodeBase)
        logger.info(
            "deleting link node(%s):interface(%s) node(%s):interface(%s)",
            node1.name,
            iface1_id,
            node2.name,
            iface2_id,
        )
        iface1 = None
        iface2 = None
        if isinstance(node1, (WlanNode, WirelessNode)):
            iface2 = node2.delete_iface(iface2_id)
            node1.detach(iface2)
        elif isinstance(node2, (WlanNode, WirelessNode)):
            iface1 = node1.delete_iface(iface1_id)
            node2.detach(iface1)
        elif isinstance(node1, EmaneNet):
            iface2 = node2.delete_iface(iface2_id)
            node1.detach(iface2)
        elif isinstance(node2, EmaneNet):
            iface1 = node1.delete_iface(iface1_id)
            node2.detach(iface1)
        else:
            iface1 = node1.delete_iface(iface1_id)
            iface2 = node2.delete_iface(iface2_id)
        core_link = self.link_manager.delete(node1, iface1, node2, iface2)
        if core_link.ptp:
            self.delete_ptp(core_link.ptp.id)
        self.sdt.delete_link(node1_id, node2_id)

    def update_link(
        self,
        node1_id: int,
        node2_id: int,
        iface1_id: int = None,
        iface2_id: int = None,
        options: LinkOptions = None,
    ) -> None:
        """
        Update link information between nodes.

        :param node1_id: node one id
        :param node2_id: node two id
        :param iface1_id: interface id for node one
        :param iface2_id: interface id for node two
        :param options: data to update link with
        :return: nothing
        :raises core.CoreError: when updating a wireless type link, when there is a
            unknown link between networks
        """
        if not options:
            options = LinkOptions()
        node1 = self.get_node(node1_id, NodeBase)
        node2 = self.get_node(node2_id, NodeBase)
        logger.info(
            "update link node(%s):interface(%s) node(%s):interface(%s)",
            node1.name,
            iface1_id,
            node2.name,
            iface2_id,
        )
        iface1 = node1.get_iface(iface1_id) if iface1_id is not None else None
        iface2 = node2.get_iface(iface2_id) if iface2_id is not None else None
        core_link = self.link_manager.get_link(node1, iface1, node2, iface2)
        if not core_link:
            raise CoreError(
                f"there is no link for node({node1.name}):interface({iface1_id}) "
                f"node({node2.name}):interface({iface2_id})"
            )
        if iface1 and options:
            iface1.update_options(options)
        if iface2 and options and not options.unidirectional:
            iface2.update_options(options)

    def next_node_id(self, start_id: int = 1) -> int:
        """
        Find the next valid node id, starting from 1.

        :return: next node id
        """
        while True:
            if start_id not in self.nodes:
                break
            start_id += 1
        return start_id

    def add_node(
        self,
        _class: type[NT],
        _id: int = None,
        name: str = None,
        server: str = None,
        position: Position = None,
        options: NodeOptions = None,
    ) -> NT:
        """
        Add a node to the session, based on the provided node data.

        :param _class: node class to create
        :param _id: id for node, defaults to None for generated id
        :param name: name to assign to node
        :param server: distributed server for node, if desired
        :param position: geo or x/y/z position to set
        :param options: options to create node with
        :return: created node
        :raises core.CoreError: when an invalid node type is given
        """
        # set node start based on current session state, override and check when rj45
        start = self.state.should_start()
        enable_rj45 = self.options.get_int("enablerj45") == 1
        if _class == Rj45Node and not enable_rj45:
            start = False
        # generate options if not provided
        options = options if options else _class.create_options()
        # verify distributed server
        dist_server = None
        if server is not None:
            dist_server = self.distributed.servers.get(server)
            if not dist_server:
                raise CoreError(f"invalid distributed server: {server}")
        # create node
        node = self.create_node(_class, start, _id, name, dist_server, options)
        # set node position
        position = position or Position()
        if position.has_geo():
            self.set_node_geo(node, position.lon, position.lat, position.alt)
        else:
            self.set_node_pos(node, position.x, position.y)
        # setup default wlan and startup if already running
        if isinstance(node, WlanNode):
            self.mobility.set_model_config(node.id, BasicRangeModel.name)
            if self.is_running():
                self.mobility.startup([node.id])
        # boot core nodes after runtime
        if self.is_running() and isinstance(node, CoreNode):
            self.boot_node(node)
        self.sdt.add_node(node)
        return node

    def set_node_pos(self, node: NodeBase, x: float, y: float) -> None:
        node.setposition(x, y, None)
        self.sdt.edit_node(
            node, node.position.lon, node.position.lat, node.position.alt
        )

    def set_node_geo(self, node: NodeBase, lon: float, lat: float, alt: float) -> None:
        x, y, _ = self.location.getxyz(lat, lon, alt)
        if math.isinf(x) or math.isinf(y):
            raise CoreError(
                f"invalid geo for current reference/scale: {lon},{lat},{alt}"
            )
        node.setposition(x, y, None)
        node.position.set_geo(lon, lat, alt)
        self.sdt.edit_node(node, lon, lat, alt)

    def open_xml(self, file_path: Path, start: bool = False) -> None:
        """
        Import a session from the EmulationScript XML format.

        :param file_path: xml file to load session from
        :param start: instantiate session if true, false for a definition state
        :return: nothing
        """
        logger.info("opening xml: %s", file_path)
        # clear out existing session
        self.clear()
        # set state and read xml
        state = EventTypes.CONFIGURATION_STATE if start else EventTypes.DEFINITION_STATE
        self.set_state(state)
        self.name = file_path.name
        self.file_path = file_path
        CoreXmlReader(self).read(file_path)
        # start session if needed
        if start:
            self.set_state(EventTypes.INSTANTIATION_STATE)
            self.instantiate()

    def save_xml(self, file_path: Path) -> None:
        """
        Export a session to the EmulationScript XML format.

        :param file_path: file name to write session xml to
        :return: nothing
        """
        CoreXmlWriter(self).write(file_path)

    def add_hook(self, state: EventTypes, file_name: str, data: str) -> None:
        """
        Store a hook from a received file message.

        :param state: when to run hook
        :param file_name: file name for hook
        :param data: file data
        :return: nothing
        """
        should_run = self.state == state
        self.hook_manager.add_script_hook(
            state, file_name, data, self.directory, self.get_environment(), should_run
        )

    def clear(self) -> None:
        """
        Clear all CORE session data. (nodes, hooks, etc)

        :return: nothing
        """
        self.emane.shutdown()
        self.delete_nodes()
        self.link_manager.reset()
        self.distributed.shutdown()
        self.hook_manager.reset()
        self.emane.reset()
        self.emane.config_reset()
        self.location.reset()
        self.mobility.config_reset()
        self.link_colors.clear()
        self.control_net_manager.remove_nets()

    def set_location(self, lat: float, lon: float, alt: float, scale: float) -> None:
        """
        Set session geospatial location.

        :param lat: latitude
        :param lon: longitude
        :param alt: altitude
        :param scale: reference scale
        :return: nothing
        """
        self.location.setrefgeo(lat, lon, alt)
        self.location.refscale = scale

    def shutdown(self) -> None:
        """
        Shutdown all session nodes and remove the session directory.
        """
        if self.state == EventTypes.SHUTDOWN_STATE:
            logger.info("session(%s) state(%s) already shutdown", self.id, self.state)
        else:
            logger.info("session(%s) state(%s) shutting down", self.id, self.state)
            self.set_state(EventTypes.SHUTDOWN_STATE, send_event=True)
            # clear out current core session
            self.clear()
            # shutdown sdt
            self.sdt.shutdown()
        # remove this sessions working directory
        preserve = self.options.get_int("preservedir") == 1
        if not preserve:
            shutil.rmtree(self.directory, ignore_errors=True)

    def broadcast_event(
        self,
        event_type: EventTypes,
        *,
        node_id: int = None,
        name: str = None,
        data: str = None,
    ) -> None:
        """
        Handle event data that should be provided to event handler.

        :param event_type: type of event to send
        :param node_id: associated node id, default is None
        :param name: name of event, default is None
        :param data: data for event, default is None
        :return: nothing
        """
        event_data = EventData(
            node=node_id,
            event_type=event_type,
            name=name,
            data=data,
            time=str(time.monotonic()),
            session=self.id,
        )
        self.broadcast_manager.send(event_data)

    def broadcast_alert(
        self, level: AlertLevels, source: str, text: str, node_id: int = None
    ) -> None:
        """
        Generate and broadcast an alert event.

        :param level: alert level
        :param source: source name
        :param text: alert message
        :param node_id: node related to alert, defaults to None
        :return: nothing
        """
        alert_data = AlertData(
            node=node_id,
            session=self.id,
            level=level,
            source=source,
            date=time.ctime(),
            text=text,
        )
        self.broadcast_manager.send(alert_data)

    def broadcast_node(
        self,
        node: NodeBase,
        message_type: MessageFlags = MessageFlags.NONE,
        source: str = None,
    ) -> None:
        """
        Handle node data that should be provided to node handlers.

        :param node: node to broadcast
        :param message_type: type of message to broadcast, None by default
        :param source: source of broadcast, None by default
        :return: nothing
        """
        node_data = NodeData(node=node, message_type=message_type, source=source)
        self.broadcast_manager.send(node_data)

    def broadcast_link(self, link_data: LinkData) -> None:
        """
        Handle link data that should be provided to link handlers.

        :param link_data: link data to send out
        :return: nothing
        """
        self.broadcast_manager.send(link_data)

    def set_state(self, state: EventTypes, send_event: bool = False) -> None:
        """
        Set the session's current state.

        :param state: state to set to
        :param send_event: if true, generate core API event messages
        :return: nothing
        """
        if self.state == state:
            return
        self.state = state
        self.state_time = time.monotonic()
        logger.info("changing session(%s) to state %s", self.id, state.name)
        self.hook_manager.run_hooks(state, self.directory, self.get_environment())
        if send_event:
            self.broadcast_event(state)

    def add_state_hook(
        self, state: EventTypes, hook: Callable[[EventTypes], None]
    ) -> None:
        """
        Add a state hook.

        :param state: state to add hook for
        :param hook: hook callback for the state
        :return: nothing
        """
        should_run = self.state == state
        self.hook_manager.add_callback_hook(state, hook, should_run)

    def del_state_hook(
        self, state: EventTypes, hook: Callable[[EventTypes], None]
    ) -> None:
        """
        Delete a state hook.

        :param state: state to delete hook for
        :param hook: hook to delete
        :return: nothing
        """
        self.hook_manager.delete_callback_hook(state, hook)

    def runtime_state_hook(self, _state: EventTypes) -> None:
        """
        Runtime state hook check.

        :param _state: state to check
        :return: nothing
        """
        self.emane.poststartup()
        # create session deployed xml
        xml_writer = corexml.CoreXmlWriter(self)
        corexmldeployment.CoreXmlDeployment(self, xml_writer.scenario)
        xml_file_path = self.directory / "session-deployed.xml"
        xml_writer.write(xml_file_path)

    def get_environment(self, state: bool = True) -> dict[str, str]:
        """
        Get an environment suitable for a subprocess.Popen call.
        This is the current process environment with some session-specific
        variables.

        :param state: flag to determine if session state should be included
        :return: environment variables
        """
        env = os.environ.copy()
        env["CORE_PYTHON"] = sys.executable
        env["SESSION"] = str(self.id)
        env["SESSION_SHORT"] = self.short_session_id()
        env["SESSION_DIR"] = str(self.directory)
        env["SESSION_NAME"] = str(self.name)
        env["SESSION_FILENAME"] = str(self.file_path)
        env["SESSION_USER"] = str(self.user)
        if state:
            env["SESSION_STATE"] = str(self.state)
        # try reading and merging optional environments from:
        # /opt/core/environment
        # /home/user/.coregui/environment
        # /tmp/pycore.<session id>/environment
        core_env_path = constants.CORE_CONF_DIR / "environment"
        session_env_path = self.directory / "environment"
        if self.user:
            user_home_path = Path(f"~{self.user}").expanduser()
            user_env = user_home_path / ".coregui" / "environment"
            paths = [core_env_path, user_env, session_env_path]
        else:
            paths = [core_env_path, session_env_path]
        for path in paths:
            if path.is_file():
                try:
                    utils.load_config(path, env)
                except OSError:
                    logger.exception("error reading environment file: %s", path)
        return env

    def set_user(self, user: str) -> None:
        """
        Set the username for this session. Update the permissions of the
        session dir to allow the user write access.

        :param user: user to give write permissions to for the session directory
        :return: nothing
        """
        self.user = user
        try:
            uid = pwd.getpwnam(user).pw_uid
            gid = self.directory.stat().st_gid
            os.chown(self.directory, uid, gid)
        except OSError:
            logger.exception("failed to set permission on %s", self.directory)

    def create_ptp(self) -> PtpNet:
        """
        Create node used to link wired nodes together.

        :return: created node
        """
        with self.nodes_lock:
            # get next ptp node id for creation
            _id = 1
            while _id in self.ptp_nodes:
                _id += 1
            node = PtpNet(self, _id=_id)
            self.ptp_nodes[node.id] = node
        logger.debug(
            "created ptp node(%s) name(%s) start(%s)",
            node.id,
            node.name,
            self.state.should_start(),
        )
        if self.state.should_start():
            node.startup()
        return node

    def delete_ptp(self, _id: int) -> None:
        """
        Deletes node used to link wired nodes together.

        :param _id: id of ptp node to delete
        :return: nothing
        """
        with self.nodes_lock:
            try:
                self.ptp_nodes.pop(_id)
            except KeyError:
                raise CoreError(f"failure deleting expected ptp node({_id})")

    def create_control_net(
        self,
        _id: int,
        prefix: str,
        updown_script: str | None,
        server_iface: str | None,
    ) -> CtrlNet:
        """
        Create a control net node, used to provide a common network between
        the host running CORE and created nodes.

        :param _id: id of the control net to create
        :param prefix: network prefix to create control net with
        :param updown_script: updown script for the control net
        :param server_iface: interface name to use for control net
        :return: created control net
        """
        with self.nodes_lock:
            if _id in self.control_nodes:
                raise CoreError(f"control net({_id}) already exists")
            options = CtrlNet.create_options()
            options.prefix = prefix
            options.updown_script = updown_script
            options.serverintf = server_iface
            control_net = CtrlNet(self, _id, options=options)
            self.control_nodes[_id] = control_net
            logger.info(
                "created control net(%s) prefix(%s) updown(%s) server interface(%s)",
                _id,
                prefix,
                updown_script,
                server_iface,
            )
            if self.state.should_start():
                control_net.startup()
        return control_net

    def create_node(
        self,
        _class: type[NT],
        start: bool,
        _id: int = None,
        name: str = None,
        server: str = None,
        options: NodeOptions = None,
    ) -> NT:
        """
        Create an emulation node.

        :param _class: node class to create
        :param start: True to start node, False otherwise
        :param _id: id for node, defaults to None for generated id
        :param name: name to assign to node
        :param server: distributed server for node, if desired
        :param options: options to create node with
        :return: the created node instance
        :raises core.CoreError: when id of the node to create already exists
        """
        with self.nodes_lock:
            _id = _id if _id is not None else self.next_node_id()
            node = _class(self, _id=_id, name=name, server=server, options=options)
            if node.id in self.nodes:
                node.shutdown()
                raise CoreError(f"duplicate node id {node.id} for {node.name}")
            self.nodes[node.id] = node
        if isinstance(node, CoreNode):
            logger.info(
                "created node(%s) id(%s) name(%s) start(%s) services(%s)",
                _class.__name__,
                node.id,
                node.name,
                start,
                ",".join(sorted(node.services)),
            )
        else:
            logger.info(
                "created node(%s) id(%s) name(%s) start(%s)",
                _class.__name__,
                node.id,
                node.name,
                start,
            )
        if start:
            node.startup()
        return node

    def get_node(self, _id: int, _class: type[NT]) -> NT:
        """
        Get a session node.

        :param _id: node id to retrieve
        :param _class: expected node class
        :return: node for the given id
        :raises core.CoreError: when node does not exist
        """
        node = self.nodes.get(_id)
        if node is None:
            raise CoreError(f"unknown node id {_id}")
        if not isinstance(node, _class):
            actual = node.__class__.__name__
            expected = _class.__name__
            raise CoreError(f"node class({actual}) is not expected({expected})")
        return node

    def delete_node(self, _id: int) -> bool:
        """
        Delete a node from the session and check if session should shutdown, if no nodes
        are left.

        :param _id: id of node to delete
        :return: True if node deleted, False otherwise
        """
        # delete node and check for session shutdown if a node was removed
        node = None
        with self.nodes_lock:
            if _id in self.nodes:
                node = self.nodes.pop(_id)
                logger.info("deleted node(%s)", node.name)
        if node:
            node.shutdown()
            self.sdt.delete_node(_id)
        return node is not None

    def delete_nodes(self) -> None:
        """
        Clear the nodes dictionary, and call shutdown for each node.
        """
        nodes_ids = []
        with self.nodes_lock:
            funcs = []
            while self.nodes:
                _, node = self.nodes.popitem()
                nodes_ids.append(node.id)
                funcs.append((node.shutdown, [], {}))
            while self.ptp_nodes:
                _, node = self.ptp_nodes.popitem()
                funcs.append((node.shutdown, [], {}))
            utils.threadpool(funcs)
        for node_id in nodes_ids:
            self.sdt.delete_node(node_id)

    def instantiate(self) -> list[Exception]:
        """
        We have entered the instantiation state, invoke startup methods
        of various managers and boot the nodes. Validate nodes and check
        for transition to the runtime state.

        :return: list of service boot errors during startup
        """
        if self.is_running():
            logger.warning("ignoring instantiate, already in runtime state")
            return []
        # initialize distributed tunnels
        self.distributed.start()
        # instantiate will be invoked again upon emane configure
        if self.emane.startup() == EmaneState.NOT_READY:
            return []
        # boot node services and then start mobility
        exceptions = self.boot_nodes()
        if not exceptions:
            # complete wireless node
            for node in self.nodes.values():
                if isinstance(node, WirelessNode):
                    node.post_startup()
            self.mobility.startup()
            # notify listeners that instantiation is complete
            self.broadcast_event(EventTypes.INSTANTIATION_COMPLETE)
            # startup event loop
            self.event_loop.run()
        self.set_state(EventTypes.RUNTIME_STATE, send_event=True)
        return exceptions

    def get_node_count(self) -> int:
        """
        Returns the number of CoreNodes and CoreNets, except for those
        that are not considered in the GUI's node count.

        :return: created node count
        """
        with self.nodes_lock:
            count = 0
            for node in self.nodes.values():
                is_tap = isinstance(node, GreTapBridge) and not isinstance(
                    node, TunnelNode
                )
                if is_tap:
                    continue
                count += 1
        return count

    def data_collect(self) -> None:
        """
        Tear down a running session. Stop the event loop and any running
        nodes, and perform clean-up.

        :return: nothing
        """
        if self.state.already_collected():
            logger.info(
                "session(%s) state(%s) already data collected", self.id, self.state
            )
            return
        logger.info("session(%s) state(%s) data collection", self.id, self.state)
        self.set_state(EventTypes.DATACOLLECT_STATE, send_event=True)

        # stop event loop
        self.event_loop.stop()

        # stop mobility and node services
        with self.nodes_lock:
            funcs = []
            for node in self.nodes.values():
                if isinstance(node, CoreNodeBase) and node.up:
                    funcs.append((node.stop_services, (), {}))
            utils.threadpool(funcs)

        # shutdown emane
        self.emane.shutdown()

        # update control interface hosts
        self.control_net_manager.clear_etc_hosts()

    def short_session_id(self) -> str:
        """
        Return a shorter version of the session ID, appropriate for
        interface names, where length may be limited.

        :return: short session id
        """
        ssid = (self.id >> 8) ^ (self.id & ((1 << 8) - 1))
        return f"{ssid:x}"

    def boot_node(self, node: CoreNode) -> None:
        """
        Boot node by adding a control interface when necessary and starting
        node services.

        :param node: node to boot
        :return: nothing
        """
        logger.info(
            "booting node(%s): services(%s)", node.name, ", ".join(node.services.keys())
        )
        self.control_net_manager.setup_ifaces(node)
        node.start_services()

    def boot_nodes(self) -> list[Exception]:
        """
        Invoke the boot() procedure for all nodes and send back node
        messages to the GUI for node messages that had the status
        request flag.

        :return: service boot exceptions
        """
        funcs = []
        start = time.monotonic()
        self.control_net_manager.setup_nets()
        for node in self.nodes.values():
            if isinstance(node, CoreNode):
                funcs.append((self.boot_node, (node,), {}))
        results, exceptions = utils.threadpool(funcs)
        total = time.monotonic() - start
        logger.debug("boot run time: %s", total)
        if not exceptions:
            self.control_net_manager.update_etc_hosts()
        return exceptions

    def runtime(self) -> float:
        """
        Return the current time we have been in the runtime state, or zero
        if not in runtime.
        """
        if self.is_running():
            return time.monotonic() - self.state_time
        else:
            return 0.0

    def add_event(
        self, event_time: float, node_id: int = None, name: str = None, data: str = None
    ) -> None:
        """
        Add an event to the event queue, with a start time relative to the
        start of the runtime state.

        :param event_time: event time
        :param node_id: node to add event for
        :param name: name of event
        :param data: data for event
        :return: nothing
        """
        current_time = self.runtime()
        if current_time > 0:
            if event_time <= current_time:
                logger.warning(
                    "could not schedule past event for time %s (run time is now %s)",
                    event_time,
                    current_time,
                )
                return
            event_time = event_time - current_time
        self.event_loop.add_event(
            event_time, self.run_event, node_id=node_id, name=name, data=data
        )
        if not name:
            name = ""
        logger.info(
            "scheduled event %s at time %s data=%s",
            name,
            event_time + current_time,
            data,
        )

    def run_event(
        self, node_id: int = None, name: str = None, data: str = None
    ) -> None:
        """
        Run a scheduled event, executing commands in the data string.

        :param node_id: node id to run event
        :param name: event name
        :param data: event data
        :return: nothing
        """
        if data is None:
            logger.warning("no data for event node(%s) name(%s)", node_id, name)
            return
        now = self.runtime()
        if not name:
            name = ""
        logger.info("running event %s at time %s cmd=%s", name, now, data)
        if not node_id:
            utils.mute_detach(data)
        else:
            node = self.get_node(node_id, CoreNodeBase)
            node.cmd(data, wait=False)

    def get_link_color(self, network_id: int) -> str:
        """
        Assign a color for links associated with a network.

        :param network_id: network to get a link color for
        :return: link color
        """
        color = self.link_colors.get(network_id)
        if not color:
            index = len(self.link_colors) % len(LINK_COLORS)
            color = LINK_COLORS[index]
            self.link_colors[network_id] = color
        return color

    def is_running(self) -> bool:
        """
        Convenience for checking if this session is in the runtime state.

        :return: True if in the runtime state, False otherwise
        """
        return self.state == EventTypes.RUNTIME_STATE

    def parse_options(self) -> None:
        """
        Update configurations from latest session options.

        :return: nothing
        """
        self.control_net_manager.parse_options(self.options)
