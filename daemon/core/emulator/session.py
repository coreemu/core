"""
session.py: defines the Session class used by the core-daemon daemon program
that manages a CORE session.
"""

import logging
import math
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union

from core import constants, utils
from core.configservice.manager import ConfigServiceManager
from core.emane.emanemanager import EmaneManager, EmaneState
from core.emane.nodes import EmaneNet
from core.emulator.data import (
    ConfigData,
    EventData,
    ExceptionData,
    FileData,
    InterfaceData,
    LinkData,
    LinkOptions,
    NodeData,
    NodeOptions,
)
from core.emulator.distributed import DistributedController
from core.emulator.enumerations import (
    EventTypes,
    ExceptionLevels,
    LinkTypes,
    MessageFlags,
    NodeTypes,
)
from core.emulator.sessionconfig import SessionConfig
from core.errors import CoreError
from core.location.event import EventLoop
from core.location.geo import GeoLocation
from core.location.mobility import BasicRangeModel, MobilityManager
from core.nodes.base import CoreNetworkBase, CoreNode, CoreNodeBase, NodeBase
from core.nodes.docker import DockerNode
from core.nodes.interface import DEFAULT_MTU, CoreInterface
from core.nodes.lxd import LxcNode
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
from core.plugins.sdt import Sdt
from core.services.coreservices import CoreServices
from core.xml import corexml, corexmldeployment
from core.xml.corexml import CoreXmlReader, CoreXmlWriter

logger = logging.getLogger(__name__)

# maps for converting from API call node type values to classes and vice versa
NODES: Dict[NodeTypes, Type[NodeBase]] = {
    NodeTypes.DEFAULT: CoreNode,
    NodeTypes.PHYSICAL: PhysicalNode,
    NodeTypes.SWITCH: SwitchNode,
    NodeTypes.HUB: HubNode,
    NodeTypes.WIRELESS_LAN: WlanNode,
    NodeTypes.RJ45: Rj45Node,
    NodeTypes.TUNNEL: TunnelNode,
    NodeTypes.EMANE: EmaneNet,
    NodeTypes.TAP_BRIDGE: GreTapBridge,
    NodeTypes.PEER_TO_PEER: PtpNet,
    NodeTypes.CONTROL_NET: CtrlNet,
    NodeTypes.DOCKER: DockerNode,
    NodeTypes.LXC: LxcNode,
}
NODES_TYPE: Dict[Type[NodeBase], NodeTypes] = {NODES[x]: x for x in NODES}
CONTAINER_NODES: Set[Type[NodeBase]] = {DockerNode, LxcNode}
CTRL_NET_ID: int = 9001
LINK_COLORS: List[str] = ["green", "blue", "orange", "purple", "turquoise"]
NT: TypeVar = TypeVar("NT", bound=NodeBase)


class Session:
    """
    CORE session manager.
    """

    def __init__(
        self, _id: int, config: Dict[str, str] = None, mkdir: bool = True
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

        self.name: Optional[str] = None
        self.file_path: Optional[Path] = None
        self.thumbnail: Optional[Path] = None
        self.user: Optional[str] = None
        self.event_loop: EventLoop = EventLoop()
        self.link_colors: Dict[int, str] = {}

        # dict of nodes: all nodes and nets
        self.nodes: Dict[int, NodeBase] = {}
        self.nodes_lock = threading.Lock()

        # states and hooks handlers
        self.state: EventTypes = EventTypes.DEFINITION_STATE
        self.state_time: float = time.monotonic()
        self.hooks: Dict[EventTypes, List[Tuple[str, str]]] = {}
        self.state_hooks: Dict[EventTypes, List[Callable[[EventTypes], None]]] = {}
        self.add_state_hook(
            state=EventTypes.RUNTIME_STATE, hook=self.runtime_state_hook
        )

        # handlers for broadcasting information
        self.event_handlers: List[Callable[[EventData], None]] = []
        self.exception_handlers: List[Callable[[ExceptionData], None]] = []
        self.node_handlers: List[Callable[[NodeData], None]] = []
        self.link_handlers: List[Callable[[LinkData], None]] = []
        self.file_handlers: List[Callable[[FileData], None]] = []
        self.config_handlers: List[Callable[[ConfigData], None]] = []

        # session options/metadata
        self.options: SessionConfig = SessionConfig()
        if not config:
            config = {}
        for key in config:
            value = config[key]
            self.options.set_config(key, value)
        self.metadata: Dict[str, str] = {}

        # distributed support and logic
        self.distributed: DistributedController = DistributedController(self)

        # initialize session feature helpers
        self.location: GeoLocation = GeoLocation()
        self.mobility: MobilityManager = MobilityManager(self)
        self.services: CoreServices = CoreServices(self)
        self.emane: EmaneManager = EmaneManager(self)
        self.sdt: Sdt = Sdt(self)

        # config services
        self.service_manager: Optional[ConfigServiceManager] = None

    @classmethod
    def get_node_class(cls, _type: NodeTypes) -> Type[NodeBase]:
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
    def get_node_type(cls, _class: Type[NodeBase]) -> NodeTypes:
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

    def _link_wireless(
        self, node1: CoreNodeBase, node2: CoreNodeBase, connect: bool
    ) -> None:
        """
        Objects to deal with when connecting/disconnecting wireless links.

        :param node1: node one for wireless link
        :param node2: node two for wireless link
        :param connect: link interfaces if True, unlink otherwise
        :return: nothing
        :raises core.CoreError: when objects to link is less than 2, or no common
            networks are found
        """
        logger.info(
            "handling wireless linking node1(%s) node2(%s): %s",
            node1.name,
            node2.name,
            connect,
        )
        common_networks = node1.commonnets(node1)
        if not common_networks:
            raise CoreError("no common network found for wireless link/unlink")
        for common_network, iface1, iface2 in common_networks:
            if not isinstance(common_network, (WlanNode, EmaneNet)):
                logger.info(
                    "skipping common network that is not wireless/emane: %s",
                    common_network,
                )
                continue
            if connect:
                common_network.link(iface1, iface2)
            else:
                common_network.unlink(iface1, iface2)

    def use_ovs(self) -> bool:
        return self.options.get_config("ovs") == "1"

    def add_link(
        self,
        node1_id: int,
        node2_id: int,
        iface1_data: InterfaceData = None,
        iface2_data: InterfaceData = None,
        options: LinkOptions = None,
        link_type: LinkTypes = LinkTypes.WIRED,
    ) -> Tuple[CoreInterface, CoreInterface]:
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
        :param link_type: type of link to add
        :return: tuple of created core interfaces, depending on link
        """
        if not options:
            options = LinkOptions()
        node1 = self.get_node(node1_id, NodeBase)
        node2 = self.get_node(node2_id, NodeBase)
        iface1 = None
        iface2 = None
        # set mtu
        mtu = self.options.get_config_int("mtu") or DEFAULT_MTU
        if iface1_data:
            iface1_data.mtu = mtu
        if iface2_data:
            iface2_data.mtu = mtu
        # wireless link
        if link_type == LinkTypes.WIRELESS:
            if isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNodeBase):
                self._link_wireless(node1, node2, connect=True)
            else:
                raise CoreError(
                    f"cannot wireless link node1({type(node1)}) node2({type(node2)})"
                )
        # wired link
        else:
            # peer to peer link
            if isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNodeBase):
                logger.info("linking ptp: %s - %s", node1.name, node2.name)
                start = self.state.should_start()
                ptp = self.create_node(PtpNet, start)
                iface1 = node1.new_iface(ptp, iface1_data)
                iface2 = node2.new_iface(ptp, iface2_data)
                iface1.config(options)
                if not options.unidirectional:
                    iface2.config(options)
            # link node to net
            elif isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNetworkBase):
                logger.info("linking node to net: %s - %s", node1.name, node2.name)
                iface1 = node1.new_iface(node2, iface1_data)
                if not isinstance(node2, (EmaneNet, WlanNode)):
                    iface1.config(options)
            # link net to node
            elif isinstance(node2, CoreNodeBase) and isinstance(node1, CoreNetworkBase):
                logger.info("linking net to node: %s - %s", node1.name, node2.name)
                iface2 = node2.new_iface(node1, iface2_data)
                wireless_net = isinstance(node1, (EmaneNet, WlanNode))
                if not options.unidirectional and not wireless_net:
                    iface2.config(options)
            # network to network
            elif isinstance(node1, CoreNetworkBase) and isinstance(
                node2, CoreNetworkBase
            ):
                logger.info(
                    "linking network to network: %s - %s", node1.name, node2.name
                )
                iface1 = node1.linknet(node2)
                use_local = iface1.net == node1
                iface1.config(options, use_local=use_local)
                if not options.unidirectional:
                    iface1.config(options, use_local=not use_local)
            else:
                raise CoreError(
                    f"cannot link node1({type(node1)}) node2({type(node2)})"
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

    def delete_link(
        self,
        node1_id: int,
        node2_id: int,
        iface1_id: int = None,
        iface2_id: int = None,
        link_type: LinkTypes = LinkTypes.WIRED,
    ) -> None:
        """
        Delete a link between nodes.

        :param node1_id: node one id
        :param node2_id: node two id
        :param iface1_id: interface id for node one
        :param iface2_id: interface id for node two
        :param link_type: link type to delete
        :return: nothing
        :raises core.CoreError: when no common network is found for link being deleted
        """
        node1 = self.get_node(node1_id, NodeBase)
        node2 = self.get_node(node2_id, NodeBase)
        logger.info(
            "deleting link(%s) node(%s):interface(%s) node(%s):interface(%s)",
            link_type.name,
            node1.name,
            iface1_id,
            node2.name,
            iface2_id,
        )

        # wireless link
        if link_type == LinkTypes.WIRELESS:
            if isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNodeBase):
                self._link_wireless(node1, node2, connect=False)
            else:
                raise CoreError(
                    "cannot delete wireless link "
                    f"node1({type(node1)}) node2({type(node2)})"
                )
        # wired link
        else:
            if isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNodeBase):
                iface1 = node1.get_iface(iface1_id)
                iface2 = node2.get_iface(iface2_id)
                if iface1.net != iface2.net:
                    raise CoreError(
                        f"node1({node1.name}) node2({node2.name}) "
                        "not connected to same net"
                    )
                ptp = iface1.net
                node1.delete_iface(iface1_id)
                node2.delete_iface(iface2_id)
                self.delete_node(ptp.id)
            elif isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNetworkBase):
                node1.delete_iface(iface1_id)
            elif isinstance(node2, CoreNodeBase) and isinstance(node1, CoreNetworkBase):
                node2.delete_iface(iface2_id)
            elif isinstance(node1, CoreNetworkBase) and isinstance(
                node2, CoreNetworkBase
            ):
                iface1 = node1.get_linked_iface(node2)
                if iface1:
                    node1.detach(iface1)
                    iface1.shutdown()
                iface2 = node2.get_linked_iface(node1)
                if iface2:
                    node2.detach(iface2)
                    iface2.shutdown()
                if not iface1 and not iface2:
                    raise CoreError(
                        f"node1({node1.name}) and node2({node2.name}) are not connected"
                    )
        self.sdt.delete_link(node1_id, node2_id)

    def update_link(
        self,
        node1_id: int,
        node2_id: int,
        iface1_id: int = None,
        iface2_id: int = None,
        options: LinkOptions = None,
        link_type: LinkTypes = LinkTypes.WIRED,
    ) -> None:
        """
        Update link information between nodes.

        :param node1_id: node one id
        :param node2_id: node two id
        :param iface1_id: interface id for node one
        :param iface2_id: interface id for node two
        :param options: data to update link with
        :param link_type: type of link to update
        :return: nothing
        :raises core.CoreError: when updating a wireless type link, when there is a
            unknown link between networks
        """
        if not options:
            options = LinkOptions()
        node1 = self.get_node(node1_id, NodeBase)
        node2 = self.get_node(node2_id, NodeBase)
        logger.info(
            "update link(%s) node(%s):interface(%s) node(%s):interface(%s)",
            link_type.name,
            node1.name,
            iface1_id,
            node2.name,
            iface2_id,
        )

        # wireless link
        if link_type == LinkTypes.WIRELESS:
            raise CoreError("cannot update wireless link")
        else:
            if isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNodeBase):
                iface1 = node1.ifaces.get(iface1_id)
                if not iface1:
                    raise CoreError(
                        f"node({node1.name}) missing interface({iface1_id})"
                    )
                iface2 = node2.ifaces.get(iface2_id)
                if not iface2:
                    raise CoreError(
                        f"node({node2.name}) missing interface({iface2_id})"
                    )
                if iface1.net != iface2.net:
                    raise CoreError(
                        f"node1({node1.name}) node2({node2.name}) "
                        "not connected to same net"
                    )
                iface1.config(options)
                if not options.unidirectional:
                    iface2.config(options)
            elif isinstance(node1, CoreNodeBase) and isinstance(node2, CoreNetworkBase):
                iface = node1.get_iface(iface1_id)
                if iface.net != node2:
                    raise CoreError(
                        f"node1({node1.name}) iface1({iface1_id})"
                        f" is not linked to node1({node2.name})"
                    )
                iface.config(options)
            elif isinstance(node2, CoreNodeBase) and isinstance(node1, CoreNetworkBase):
                iface = node2.get_iface(iface2_id)
                if iface.net != node1:
                    raise CoreError(
                        f"node2({node2.name}) iface2({iface2_id})"
                        f" is not linked to node1({node1.name})"
                    )
                iface.config(options)
            elif isinstance(node1, CoreNetworkBase) and isinstance(
                node2, CoreNetworkBase
            ):
                iface = node1.get_linked_iface(node2)
                if not iface:
                    iface = node2.get_linked_iface(node1)
                if iface:
                    use_local = iface.net == node1
                    iface.config(options, use_local=use_local)
                    if not options.unidirectional:
                        iface.config(options, use_local=not use_local)
                else:
                    raise CoreError(
                        f"node1({node1.name}) and node2({node2.name}) are not linked"
                    )
            else:
                raise CoreError(
                    f"cannot update link node1({type(node1)}) node2({type(node2)})"
                )

    def next_node_id(self) -> int:
        """
        Find the next valid node id, starting from 1.

        :return: next node id
        """
        _id = 1
        while True:
            if _id not in self.nodes:
                break
            _id += 1
        return _id

    def add_node(
        self, _class: Type[NT], _id: int = None, options: NodeOptions = None
    ) -> NT:
        """
        Add a node to the session, based on the provided node data.

        :param _class: node class to create
        :param _id: id for node, defaults to None for generated id
        :param options: data to create node with
        :return: created node
        :raises core.CoreError: when an invalid node type is given
        """
        # set node start based on current session state, override and check when rj45
        start = self.state.should_start()
        enable_rj45 = self.options.get_config("enablerj45") == "1"
        if _class == Rj45Node and not enable_rj45:
            start = False

        # determine node id
        if not _id:
            _id = self.next_node_id()

        # generate name if not provided
        if not options:
            options = NodeOptions()
            options.set_position(0, 0)
        name = options.name
        if not name:
            name = f"{_class.__name__}{_id}"

        # verify distributed server
        server = self.distributed.servers.get(options.server)
        if options.server is not None and server is None:
            raise CoreError(f"invalid distributed server: {options.server}")

        # create node
        logger.info(
            "creating node(%s) id(%s) name(%s) start(%s)",
            _class.__name__,
            _id,
            name,
            start,
        )
        kwargs = dict(_id=_id, name=name, server=server)
        if _class in CONTAINER_NODES:
            kwargs["image"] = options.image
        node = self.create_node(_class, start, **kwargs)

        # set node attributes
        node.icon = options.icon
        node.canvas = options.canvas

        # set node position and broadcast it
        has_geo = all(i is not None for i in [options.lon, options.lat, options.alt])
        if has_geo:
            self.set_node_geo(node, options.lon, options.lat, options.alt)
        else:
            self.set_node_pos(node, options.x, options.y)

        # add services to needed nodes
        if isinstance(node, (CoreNode, PhysicalNode)):
            node.type = options.model
            if options.legacy or options.services:
                logger.debug("set node type: %s", node.type)
                self.services.add_services(node, node.type, options.services)

            # add config services
            config_services = options.config_services
            if not options.legacy and not config_services and not node.services:
                config_services = self.services.default_services.get(node.type, [])
            logger.info("setting node config services: %s", config_services)
            for name in config_services:
                service_class = self.service_manager.get_service(name)
                node.add_config_service(service_class)

        # set network mtu, if configured
        mtu = self.options.get_config_int("mtu")
        if isinstance(node, CoreNetworkBase) and mtu > 0:
            node.mtu = mtu

        # ensure default emane configuration
        if isinstance(node, EmaneNet) and options.emane:
            model_class = self.emane.get_model(options.emane)
            node.model = model_class(self, node.id)
            if self.state == EventTypes.RUNTIME_STATE:
                self.emane.add_node(node)

        # set default wlan config if needed
        if isinstance(node, WlanNode):
            self.mobility.set_model_config(_id, BasicRangeModel.name)

        # boot nodes after runtime CoreNodes and PhysicalNodes
        is_boot_node = isinstance(node, (CoreNode, PhysicalNode))
        if self.state == EventTypes.RUNTIME_STATE and is_boot_node:
            self.write_nodes()
            self.add_remove_control_iface(node, remove=False)
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

    def start_mobility(self, node_ids: List[int] = None) -> None:
        """
        Start mobility for the provided node ids.

        :param node_ids: nodes to start mobility for
        :return: nothing
        """
        self.mobility.startup(node_ids)

    def is_active(self) -> bool:
        """
        Determine if this session is considered to be active.
        (Runtime or Data collect states)

        :return: True if active, False otherwise
        """
        result = self.state in {EventTypes.RUNTIME_STATE, EventTypes.DATACOLLECT_STATE}
        logger.info("session(%s) checking if active: %s", self.id, result)
        return result

    def open_xml(self, file_path: Path, start: bool = False) -> None:
        """
        Import a session from the EmulationScript XML format.

        :param file_path: xml file to load session from
        :param start: instantiate session if true, false otherwise
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

    def add_hook(
        self, state: EventTypes, file_name: str, data: str, src_name: str = None
    ) -> None:
        """
        Store a hook from a received file message.

        :param state: when to run hook
        :param file_name: file name for hook
        :param data: hook data
        :param src_name: source name
        :return: nothing
        """
        logger.info(
            "setting state hook: %s - %s source(%s)", state, file_name, src_name
        )
        hook = file_name, data
        state_hooks = self.hooks.setdefault(state, [])
        state_hooks.append(hook)

        # immediately run a hook if it is in the current state
        if self.state == state:
            logger.info("immediately running new state hook")
            self.run_hook(hook)

    def add_node_file(
        self,
        node_id: int,
        src_path: Optional[Path],
        file_path: Path,
        data: Optional[str],
    ) -> None:
        """
        Add a file to a node.

        :param node_id: node to add file to
        :param src_path: source file path
        :param file_path: file path to add
        :param data: file data
        :return: nothing
        """
        node = self.get_node(node_id, CoreNode)
        if src_path is not None:
            node.copy_file(src_path, file_path)
        elif data is not None:
            node.create_file(file_path, data)

    def clear(self) -> None:
        """
        Clear all CORE session data. (nodes, hooks, etc)

        :return: nothing
        """
        self.emane.shutdown()
        self.delete_nodes()
        self.distributed.shutdown()
        self.hooks.clear()
        self.emane.reset()
        self.emane.config_reset()
        self.location.reset()
        self.services.reset()
        self.mobility.config_reset()
        self.link_colors.clear()

    def start_events(self) -> None:
        """
        Start event loop.

        :return: nothing
        """
        self.event_loop.run()

    def mobility_event(self, event_data: EventData) -> None:
        """
        Handle a mobility event.

        :param event_data: event data to handle
        :return: nothing
        """
        self.mobility.handleevent(event_data)

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
        preserve = self.options.get_config("preservedir") == "1"
        if not preserve:
            shutil.rmtree(self.directory, ignore_errors=True)

    def broadcast_event(self, event_data: EventData) -> None:
        """
        Handle event data that should be provided to event handler.

        :param event_data: event data to send out
        :return: nothing
        """
        for handler in self.event_handlers:
            handler(event_data)

    def broadcast_exception(self, exception_data: ExceptionData) -> None:
        """
        Handle exception data that should be provided to exception handlers.

        :param exception_data: exception data to send out
        :return: nothing
        """
        for handler in self.exception_handlers:
            handler(exception_data)

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
        if not node.apitype:
            return
        node_data = NodeData(node=node, message_type=message_type, source=source)
        for handler in self.node_handlers:
            handler(node_data)

    def broadcast_file(self, file_data: FileData) -> None:
        """
        Handle file data that should be provided to file handlers.

        :param file_data: file data to send out
        :return: nothing
        """
        for handler in self.file_handlers:
            handler(file_data)

    def broadcast_config(self, config_data: ConfigData) -> None:
        """
        Handle config data that should be provided to config handlers.

        :param config_data: config data to send out
        :return: nothing
        """
        for handler in self.config_handlers:
            handler(config_data)

    def broadcast_link(self, link_data: LinkData) -> None:
        """
        Handle link data that should be provided to link handlers.

        :param link_data: link data to send out
        :return: nothing
        """
        for handler in self.link_handlers:
            handler(link_data)

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
        self.write_state(state)
        self.run_hooks(state)
        self.run_state_hooks(state)
        if send_event:
            event_data = EventData(event_type=state, time=str(time.monotonic()))
            self.broadcast_event(event_data)

    def write_state(self, state: EventTypes) -> None:
        """
        Write the state to a state file in the session dir.

        :param state: state to write to file
        :return: nothing
        """
        state_file = self.directory / "state"
        try:
            with state_file.open("w") as f:
                f.write(f"{state.value} {state.name}\n")
        except IOError:
            logger.exception("error writing state file: %s", state.name)

    def run_hooks(self, state: EventTypes) -> None:
        """
        Run hook scripts upon changing states. If hooks is not specified, run all hooks
        in the given state.

        :param state: state to run hooks for
        :return: nothing
        """
        hooks = self.hooks.get(state, [])
        for hook in hooks:
            self.run_hook(hook)

    def run_hook(self, hook: Tuple[str, str]) -> None:
        """
        Run a hook.

        :param hook: hook to run
        :return: nothing
        """
        file_name, data = hook
        logger.info("running hook %s", file_name)
        file_path = self.directory / file_name
        log_path = self.directory / f"{file_name}.log"
        try:
            with file_path.open("w") as f:
                f.write(data)
            with log_path.open("w") as f:
                args = ["/bin/sh", file_name]
                subprocess.check_call(
                    args,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                    cwd=self.directory,
                    env=self.get_environment(),
                )
        except (IOError, subprocess.CalledProcessError):
            logger.exception("error running hook: %s", file_path)

    def run_state_hooks(self, state: EventTypes) -> None:
        """
        Run state hooks.

        :param state: state to run hooks for
        :return: nothing
        """
        for hook in self.state_hooks.get(state, []):
            self.run_state_hook(state, hook)

    def run_state_hook(self, state: EventTypes, hook: Callable[[EventTypes], None]):
        try:
            hook(state)
        except Exception:
            message = f"exception occurred when running {state.name} state hook: {hook}"
            logger.exception(message)
            self.exception(ExceptionLevels.ERROR, "Session.run_state_hooks", message)

    def add_state_hook(
        self, state: EventTypes, hook: Callable[[EventTypes], None]
    ) -> None:
        """
        Add a state hook.

        :param state: state to add hook for
        :param hook: hook callback for the state
        :return: nothing
        """
        hooks = self.state_hooks.setdefault(state, [])
        if hook in hooks:
            raise CoreError("attempting to add duplicate state hook")
        hooks.append(hook)
        if self.state == state:
            self.run_state_hook(state, hook)

    def del_state_hook(
        self, state: EventTypes, hook: Callable[[EventTypes], None]
    ) -> None:
        """
        Delete a state hook.

        :param state: state to delete hook for
        :param hook: hook to delete
        :return: nothing
        """
        hooks = self.state_hooks.get(state, [])
        if hook in hooks:
            hooks.remove(hook)

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

    def get_environment(self, state: bool = True) -> Dict[str, str]:
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
        # /etc/core/environment
        # /home/user/.core/environment
        # /tmp/pycore.<session id>/environment
        core_env_path = constants.CORE_CONF_DIR / "environment"
        session_env_path = self.directory / "environment"
        if self.user:
            user_home_path = Path(f"~{self.user}").expanduser()
            user_env1 = user_home_path / ".core" / "environment"
            user_env2 = user_home_path / ".coregui" / "environment"
            paths = [core_env_path, user_env1, user_env2, session_env_path]
        else:
            paths = [core_env_path, session_env_path]
        for path in paths:
            if path.is_file():
                try:
                    utils.load_config(path, env)
                except IOError:
                    logger.exception("error reading environment file: %s", path)
        return env

    def set_thumbnail(self, thumb_file: Path) -> None:
        """
        Set the thumbnail filename. Move files from /tmp to session dir.

        :param thumb_file: tumbnail file to set for session
        :return: nothing
        """
        if not thumb_file.is_file():
            logger.error("thumbnail file to set does not exist: %s", thumb_file)
            self.thumbnail = None
            return
        dst_path = self.directory / thumb_file.name
        shutil.copy(thumb_file, dst_path)
        self.thumbnail = dst_path

    def set_user(self, user: str) -> None:
        """
        Set the username for this session. Update the permissions of the
        session dir to allow the user write access.

        :param user: user to give write permissions to for the session directory
        :return: nothing
        """
        if user:
            try:
                uid = pwd.getpwnam(user).pw_uid
                gid = self.directory.stat().st_gid
                os.chown(self.directory, uid, gid)
            except IOError:
                logger.exception("failed to set permission on %s", self.directory)
        self.user = user

    def create_node(
        self, _class: Type[NT], start: bool, *args: Any, **kwargs: Any
    ) -> NT:
        """
        Create an emulation node.

        :param _class: node class to create
        :param start: True to start node, False otherwise
        :param args: list of arguments for the class to create
        :param kwargs: dictionary of arguments for the class to create
        :return: the created node instance
        :raises core.CoreError: when id of the node to create already exists
        """
        with self.nodes_lock:
            node = _class(self, *args, **kwargs)
            if node.id in self.nodes:
                node.shutdown()
                raise CoreError(f"duplicate node id {node.id} for {node.name}")
            self.nodes[node.id] = node
        if start:
            node.startup()
        return node

    def get_node(self, _id: int, _class: Type[NT]) -> NT:
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
            utils.threadpool(funcs)
        for node_id in nodes_ids:
            self.sdt.delete_node(node_id)

    def write_nodes(self) -> None:
        """
        Write nodes to a 'nodes' file in the session dir.
        The 'nodes' file lists: number, name, api-type, class-type
        """
        file_path = self.directory / "nodes"
        try:
            with self.nodes_lock:
                with file_path.open("w") as f:
                    for _id, node in self.nodes.items():
                        f.write(f"{_id} {node.name} {node.apitype} {type(node)}\n")
        except IOError:
            logger.exception("error writing nodes file")

    def exception(
        self, level: ExceptionLevels, source: str, text: str, node_id: int = None
    ) -> None:
        """
        Generate and broadcast an exception event.

        :param level: exception level
        :param source: source name
        :param text: exception message
        :param node_id: node related to exception
        :return: nothing
        """
        exception_data = ExceptionData(
            node=node_id,
            session=self.id,
            level=level,
            source=source,
            date=time.ctime(),
            text=text,
        )
        self.broadcast_exception(exception_data)

    def instantiate(self) -> List[Exception]:
        """
        We have entered the instantiation state, invoke startup methods
        of various managers and boot the nodes. Validate nodes and check
        for transition to the runtime state.

        :return: list of service boot errors during startup
        """
        if self.state == EventTypes.RUNTIME_STATE:
            logger.warning("ignoring instantiate, already in runtime state")
            return []
        # write current nodes out to session directory file
        self.write_nodes()
        # create control net interfaces and network tunnels
        # which need to exist for emane to sync on location events
        # in distributed scenarios
        self.add_remove_control_net(0, remove=False)
        # initialize distributed tunnels
        self.distributed.start()
        # instantiate will be invoked again upon emane configure
        if self.emane.startup() == EmaneState.NOT_READY:
            return []
        # boot node services and then start mobility
        exceptions = self.boot_nodes()
        if not exceptions:
            self.mobility.startup()
            # notify listeners that instantiation is complete
            event = EventData(event_type=EventTypes.INSTANTIATION_COMPLETE)
            self.broadcast_event(event)
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
                is_p2p_ctrlnet = isinstance(node, (PtpNet, CtrlNet))
                is_tap = isinstance(node, GreTapBridge) and not isinstance(
                    node, TunnelNode
                )
                if is_p2p_ctrlnet or is_tap:
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
                    args = (node,)
                    funcs.append((self.services.stop_services, args, {}))
            utils.threadpool(funcs)

        # shutdown emane
        self.emane.shutdown()

        # update control interface hosts
        self.update_control_iface_hosts(remove=True)

        # remove all four possible control networks
        for i in range(4):
            self.add_remove_control_net(i, remove=True)

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
        logger.info("booting node(%s): %s", node.name, [x.name for x in node.services])
        self.services.boot_services(node)
        node.start_config_services()

    def boot_nodes(self) -> List[Exception]:
        """
        Invoke the boot() procedure for all nodes and send back node
        messages to the GUI for node messages that had the status
        request flag.

        :return: service boot exceptions
        """
        with self.nodes_lock:
            funcs = []
            start = time.monotonic()
            for node in self.nodes.values():
                if isinstance(node, (CoreNode, PhysicalNode)):
                    self.add_remove_control_iface(node, remove=False)
                    funcs.append((self.boot_node, (node,), {}))
            results, exceptions = utils.threadpool(funcs)
            total = time.monotonic() - start
            logger.debug("boot run time: %s", total)
        if not exceptions:
            self.update_control_iface_hosts()
        return exceptions

    def get_control_net_prefixes(self) -> List[str]:
        """
        Retrieve control net prefixes.

        :return: control net prefix list
        """
        p = self.options.get_config("controlnet")
        p0 = self.options.get_config("controlnet0")
        p1 = self.options.get_config("controlnet1")
        p2 = self.options.get_config("controlnet2")
        p3 = self.options.get_config("controlnet3")
        if not p0 and p:
            p0 = p
        return [p0, p1, p2, p3]

    def get_control_net_server_ifaces(self) -> List[str]:
        """
        Retrieve control net server interfaces.

        :return: list of control net server interfaces
        """
        d0 = self.options.get_config("controlnetif0")
        if d0:
            logger.error("controlnet0 cannot be assigned with a host interface")
        d1 = self.options.get_config("controlnetif1")
        d2 = self.options.get_config("controlnetif2")
        d3 = self.options.get_config("controlnetif3")
        return [None, d1, d2, d3]

    def get_control_net_index(self, dev: str) -> int:
        """
        Retrieve control net index.

        :param dev: device to get control net index for
        :return: control net index, -1 otherwise
        """
        if dev[0:4] == "ctrl" and int(dev[4]) in [0, 1, 2, 3]:
            index = int(dev[4])
            if index == 0:
                return index
            if index < 4 and self.get_control_net_prefixes()[index] is not None:
                return index
        return -1

    def get_control_net(self, net_index: int) -> CtrlNet:
        """
        Retrieve a control net based on index.

        :param net_index: control net index
        :return: control net
        :raises CoreError: when control net is not found
        """
        return self.get_node(CTRL_NET_ID + net_index, CtrlNet)

    def add_remove_control_net(
        self, net_index: int, remove: bool = False, conf_required: bool = True
    ) -> Optional[CtrlNet]:
        """
        Create a control network bridge as necessary.
        When the remove flag is True, remove the bridge that connects control
        interfaces. The conf_reqd flag, when False, causes a control network
        bridge to be added even if one has not been configured.

        :param net_index: network index
        :param remove: flag to check if it should be removed
        :param conf_required: flag to check if conf is required
        :return: control net node
        """
        logger.debug(
            "add/remove control net: index(%s) remove(%s) conf_required(%s)",
            net_index,
            remove,
            conf_required,
        )
        prefix_spec_list = self.get_control_net_prefixes()
        prefix_spec = prefix_spec_list[net_index]
        if not prefix_spec:
            if conf_required:
                # no controlnet needed
                return None
            else:
                prefix_spec = CtrlNet.DEFAULT_PREFIX_LIST[net_index]
        logger.debug("prefix spec: %s", prefix_spec)
        server_iface = self.get_control_net_server_ifaces()[net_index]

        # return any existing controlnet bridge
        try:
            control_net = self.get_control_net(net_index)
            if remove:
                self.delete_node(control_net.id)
                return None
            return control_net
        except CoreError:
            if remove:
                return None

        # build a new controlnet bridge
        _id = CTRL_NET_ID + net_index

        # use the updown script for control net 0 only.
        updown_script = None

        if net_index == 0:
            updown_script = self.options.get_config("controlnet_updown_script")
            if not updown_script:
                logger.debug("controlnet updown script not configured")

        prefixes = prefix_spec.split()
        if len(prefixes) > 1:
            # a list of per-host prefixes is provided
            try:
                # split first (master) entry into server and prefix
                prefix = prefixes[0].split(":", 1)[1]
            except IndexError:
                # no server name. possibly only one server
                prefix = prefixes[0]
        else:
            prefix = prefixes[0]

        logger.info(
            "controlnet(%s) prefix(%s) updown(%s) serverintf(%s)",
            _id,
            prefix,
            updown_script,
            server_iface,
        )
        control_net = self.create_node(
            CtrlNet,
            start=False,
            prefix=prefix,
            _id=_id,
            updown_script=updown_script,
            serverintf=server_iface,
        )
        control_net.brname = f"ctrl{net_index}.{self.short_session_id()}"
        control_net.startup()
        return control_net

    def add_remove_control_iface(
        self,
        node: Union[CoreNode, PhysicalNode],
        net_index: int = 0,
        remove: bool = False,
        conf_required: bool = True,
    ) -> None:
        """
        Add a control interface to a node when a 'controlnet' prefix is
        listed in the config file or session options. Uses
        addremovectrlnet() to build or remove the control bridge.
        If conf_reqd is False, the control network may be built even
        when the user has not configured one (e.g. for EMANE.)

        :param node: node to add or remove control interface
        :param net_index: network index
        :param remove: flag to check if it should be removed
        :param conf_required: flag to check if conf is required
        :return: nothing
        """
        control_net = self.add_remove_control_net(net_index, remove, conf_required)
        if not control_net:
            return
        if not node:
            return
        # ctrl# already exists
        if node.ifaces.get(control_net.CTRLIF_IDX_BASE + net_index):
            return
        try:
            ip4 = control_net.prefix[node.id]
            ip4_mask = control_net.prefix.prefixlen
            iface_data = InterfaceData(
                id=control_net.CTRLIF_IDX_BASE + net_index,
                name=f"ctrl{net_index}",
                mac=utils.random_mac(),
                ip4=ip4,
                ip4_mask=ip4_mask,
                mtu=DEFAULT_MTU,
            )
            iface = node.new_iface(control_net, iface_data)
            iface.control = True
        except ValueError:
            msg = f"Control interface not added to node {node.id}. "
            msg += f"Invalid control network prefix ({control_net.prefix}). "
            msg += "A longer prefix length may be required for this many nodes."
            logger.exception(msg)

    def update_control_iface_hosts(
        self, net_index: int = 0, remove: bool = False
    ) -> None:
        """
        Add the IP addresses of control interfaces to the /etc/hosts file.

        :param net_index: network index to update
        :param remove: flag to check if it should be removed
        :return: nothing
        """
        if not self.options.get_config_bool("update_etc_hosts", default=False):
            return

        try:
            control_net = self.get_control_net(net_index)
        except CoreError:
            logger.exception("error retrieving control net node")
            return

        header = f"CORE session {self.id} host entries"
        if remove:
            logger.info("Removing /etc/hosts file entries.")
            utils.file_demunge("/etc/hosts", header)
            return

        entries = []
        for iface in control_net.get_ifaces():
            name = iface.node.name
            for ip in iface.ips():
                entries.append(f"{ip.ip} {name}")

        logger.info("Adding %d /etc/hosts file entries.", len(entries))
        utils.file_munge("/etc/hosts", header, "\n".join(entries) + "\n")

    def runtime(self) -> float:
        """
        Return the current time we have been in the runtime state, or zero
        if not in runtime.
        """
        if self.state == EventTypes.RUNTIME_STATE:
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
