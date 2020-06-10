"""
session.py: defines the Session class used by the core-daemon daemon program
that manages a CORE session.
"""

import logging
import os
import pwd
import random
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Type, TypeVar

from core import constants, utils
from core.configservice.manager import ConfigServiceManager
from core.emane.emanemanager import EmaneManager
from core.emane.nodes import EmaneNet
from core.emulator.data import (
    ConfigData,
    EventData,
    ExceptionData,
    FileData,
    LinkData,
    NodeData,
)
from core.emulator.distributed import DistributedController
from core.emulator.emudata import InterfaceData, LinkOptions, NodeOptions
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
from core.nodes.interface import CoreInterface
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

# maps for converting from API call node type values to classes and vice versa
NODES = {
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
NODES_TYPE = {NODES[x]: x for x in NODES}
CONTAINER_NODES = {DockerNode, LxcNode}
CTRL_NET_ID = 9001
LINK_COLORS = ["green", "blue", "orange", "purple", "turquoise"]
NT = TypeVar("NT", bound=NodeBase)


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
        self.session_dir: str = os.path.join(tempfile.gettempdir(), f"pycore.{self.id}")
        if mkdir:
            os.mkdir(self.session_dir)

        self.name: Optional[str] = None
        self.file_name: Optional[str] = None
        self.thumbnail: Optional[str] = None
        self.user: Optional[str] = None
        self.event_loop: EventLoop = EventLoop()
        self.link_colors: Dict[int, str] = {}

        # dict of nodes: all nodes and nets
        self.nodes: Dict[int, NodeBase] = {}
        self._nodes_lock = threading.Lock()

        self.state: EventTypes = EventTypes.DEFINITION_STATE
        self._state_time: float = time.monotonic()
        self._state_file: str = os.path.join(self.session_dir, "state")

        # hooks handlers
        self._hooks: Dict[EventTypes, Tuple[str, str]] = {}
        self._state_hooks: Dict[EventTypes, Callable[[int], None]] = {}
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
        self.shutdown_handlers: List[Callable[[Session], None]] = []

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

        # initialize default node services
        self.services.default_services = {
            "mdr": ("zebra", "OSPFv3MDR", "IPForward"),
            "PC": ("DefaultRoute",),
            "prouter": (),
            "router": ("zebra", "OSPFv2", "OSPFv3", "IPForward"),
            "host": ("DefaultRoute", "SSH"),
        }

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

    def _link_nodes(
        self, node_one_id: int, node_two_id: int
    ) -> Tuple[
        Optional[CoreNode],
        Optional[CoreNode],
        Optional[CoreNetworkBase],
        Optional[CoreNetworkBase],
    ]:
        """
        Convenience method for retrieving nodes within link data.

        :param node_one_id: node one id
        :param node_two_id: node two id
        :return: nodes, network nodes if present, and tunnel if present
        """
        logging.debug(
            "link message between node1(%s) and node2(%s)", node_one_id, node_two_id
        )

        # values to fill
        net_one = None
        net_two = None

        # retrieve node one
        node_one = self.get_node(node_one_id, NodeBase)
        node_two = self.get_node(node_two_id, NodeBase)

        if isinstance(node_one, CoreNetworkBase):
            if not net_one:
                net_one = node_one
            else:
                net_two = node_one
            node_one = None

        if isinstance(node_two, CoreNetworkBase):
            if not net_one:
                net_one = node_two
            else:
                net_two = node_two
            node_two = None

        logging.debug(
            "link node types n1(%s) n2(%s) net1(%s) net2(%s)",
            node_one,
            node_two,
            net_one,
            net_two,
        )
        return node_one, node_two, net_one, net_two

    def _link_wireless(self, objects: Iterable[CoreNodeBase], connect: bool) -> None:
        """
        Objects to deal with when connecting/disconnecting wireless links.

        :param objects: possible objects to deal with
        :param connect: link interfaces if True, unlink otherwise
        :return: nothing
        :raises core.CoreError: when objects to link is less than 2, or no common
            networks are found
        """
        objects = [x for x in objects if x]
        if len(objects) < 2:
            raise CoreError(f"wireless link failure: {objects}")
        logging.debug(
            "handling wireless linking objects(%s) connect(%s)", objects, connect
        )
        common_networks = objects[0].commonnets(objects[1])
        if not common_networks:
            raise CoreError("no common network found for wireless link/unlink")

        for common_network, interface_one, interface_two in common_networks:
            if not isinstance(common_network, (WlanNode, EmaneNet)):
                logging.info(
                    "skipping common network that is not wireless/emane: %s",
                    common_network,
                )
                continue

            logging.info(
                "wireless linking connect(%s): %s - %s",
                connect,
                interface_one,
                interface_two,
            )
            if connect:
                common_network.link(interface_one, interface_two)
            else:
                common_network.unlink(interface_one, interface_two)

    def add_link(
        self,
        node_one_id: int,
        node_two_id: int,
        interface_one: InterfaceData = None,
        interface_two: InterfaceData = None,
        options: LinkOptions = None,
    ) -> Tuple[CoreInterface, CoreInterface]:
        """
        Add a link between nodes.

        :param node_one_id: node one id
        :param node_two_id: node two id
        :param interface_one: node one interface
            data, defaults to none
        :param interface_two: node two interface
            data, defaults to none
        :param options: data for creating link,
            defaults to no options
        :return: tuple of created core interfaces, depending on link
        """
        if not options:
            options = LinkOptions()

        # get node objects identified by link data
        node_one, node_two, net_one, net_two = self._link_nodes(
            node_one_id, node_two_id
        )

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        node_one_interface = None
        node_two_interface = None

        try:
            # wireless link
            if options.type == LinkTypes.WIRELESS:
                objects = [node_one, node_two, net_one, net_two]
                self._link_wireless(objects, connect=True)
            # wired link
            else:
                # 2 nodes being linked, ptp network
                if all([node_one, node_two]) and not net_one:
                    logging.info(
                        "adding link for peer to peer nodes: %s - %s",
                        node_one.name,
                        node_two.name,
                    )
                    start = self.state.should_start()
                    net_one = self.create_node(PtpNet, start=start)

                # node to network
                if node_one and net_one:
                    logging.info(
                        "adding link from node to network: %s - %s",
                        node_one.name,
                        net_one.name,
                    )
                    ifindex = node_one.newnetif(net_one, interface_one)
                    node_one_interface = node_one.netif(ifindex)
                    wireless_net = isinstance(net_one, (EmaneNet, WlanNode))
                    if not wireless_net:
                        net_one.linkconfig(node_one_interface, options)

                # network to node
                if node_two and net_one:
                    logging.info(
                        "adding link from network to node: %s - %s",
                        node_two.name,
                        net_one.name,
                    )
                    ifindex = node_two.newnetif(net_one, interface_two)
                    node_two_interface = node_two.netif(ifindex)
                    wireless_net = isinstance(net_one, (EmaneNet, WlanNode))
                    if not options.unidirectional and not wireless_net:
                        net_one.linkconfig(node_two_interface, options)

                # network to network
                if net_one and net_two:
                    logging.info(
                        "adding link from network to network: %s - %s",
                        net_one.name,
                        net_two.name,
                    )
                    interface = net_one.linknet(net_two)
                    node_one_interface = interface
                    net_one.linkconfig(interface, options)
                    if not options.unidirectional:
                        interface.swapparams("_params_up")
                        net_two.linkconfig(interface, options)
                        interface.swapparams("_params_up")

                # a tunnel node was found for the nodes
                addresses = []
                if not node_one and all([net_one, interface_one]):
                    addresses.extend(interface_one.get_addresses())
                if not node_two and all([net_two, interface_two]):
                    addresses.extend(interface_two.get_addresses())

                # tunnel node logic
                key = options.key
                if key and isinstance(net_one, TunnelNode):
                    logging.info("setting tunnel key for: %s", net_one.name)
                    net_one.setkey(key)
                    if addresses:
                        net_one.addrconfig(addresses)
                if key and isinstance(net_two, TunnelNode):
                    logging.info("setting tunnel key for: %s", net_two.name)
                    net_two.setkey(key)
                    if addresses:
                        net_two.addrconfig(addresses)
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

        self.sdt.add_link(node_one_id, node_two_id)
        return node_one_interface, node_two_interface

    def delete_link(
        self,
        node_one_id: int,
        node_two_id: int,
        interface_one_id: int,
        interface_two_id: int,
        link_type: LinkTypes = LinkTypes.WIRED,
    ) -> None:
        """
        Delete a link between nodes.

        :param node_one_id: node one id
        :param node_two_id: node two id
        :param interface_one_id: interface id for node one
        :param interface_two_id: interface id for node two
        :param link_type: link type to delete
        :return: nothing
        :raises core.CoreError: when no common network is found for link being deleted
        """
        # get node objects identified by link data
        node_one, node_two, net_one, net_two = self._link_nodes(
            node_one_id, node_two_id
        )

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if link_type == LinkTypes.WIRELESS:
                objects = [node_one, node_two, net_one, net_two]
                self._link_wireless(objects, connect=False)
            # wired link
            else:
                if all([node_one, node_two]):
                    # TODO: fix this for the case where ifindex[1,2] are not specified
                    # a wired unlink event, delete the connecting bridge
                    interface_one = node_one.netif(interface_one_id)
                    interface_two = node_two.netif(interface_two_id)

                    # get interfaces from common network, if no network node
                    # otherwise get interfaces between a node and network
                    if not interface_one and not interface_two:
                        common_networks = node_one.commonnets(node_two)
                        for (
                            network,
                            common_interface_one,
                            common_interface_two,
                        ) in common_networks:
                            if (net_one and network == net_one) or not net_one:
                                interface_one = common_interface_one
                                interface_two = common_interface_two
                                break

                    if all([interface_one, interface_two]) and any(
                        [interface_one.net, interface_two.net]
                    ):
                        if interface_one.net != interface_two.net and all(
                            [interface_one.up, interface_two.up]
                        ):
                            raise CoreError("no common network found")

                        logging.info(
                            "deleting link node(%s):interface(%s) node(%s):interface(%s)",
                            node_one.name,
                            interface_one.name,
                            node_two.name,
                            interface_two.name,
                        )
                        net_one = interface_one.net
                        interface_one.detachnet()
                        interface_two.detachnet()
                        if net_one.numnetif() == 0:
                            self.delete_node(net_one.id)
                        node_one.delnetif(interface_one.netindex)
                        node_two.delnetif(interface_two.netindex)
                elif node_one and net_one:
                    interface = node_one.netif(interface_one_id)
                    if interface:
                        logging.info(
                            "deleting link node(%s):interface(%s) node(%s)",
                            node_one.name,
                            interface.name,
                            net_one.name,
                        )
                        interface.detachnet()
                        node_one.delnetif(interface.netindex)
                elif node_two and net_one:
                    interface = node_two.netif(interface_two_id)
                    if interface:
                        logging.info(
                            "deleting link node(%s):interface(%s) node(%s)",
                            node_two.name,
                            interface.name,
                            net_one.name,
                        )
                        interface.detachnet()
                        node_two.delnetif(interface.netindex)
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

        self.sdt.delete_link(node_one_id, node_two_id)

    def update_link(
        self,
        node_one_id: int,
        node_two_id: int,
        interface_one_id: int = None,
        interface_two_id: int = None,
        options: LinkOptions = None,
    ) -> None:
        """
        Update link information between nodes.

        :param node_one_id: node one id
        :param node_two_id: node two id
        :param interface_one_id: interface id for node one
        :param interface_two_id: interface id for node two
        :param options: data to update link with
        :return: nothing
        :raises core.CoreError: when updating a wireless type link, when there is a unknown
            link between networks
        """
        if not options:
            options = LinkOptions()

        # get node objects identified by link data
        node_one, node_two, net_one, net_two = self._link_nodes(
            node_one_id, node_two_id
        )

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if options.type == LinkTypes.WIRELESS:
                raise CoreError("cannot update wireless link")
            else:
                if not node_one and not node_two:
                    if net_one and net_two:
                        # modify link between nets
                        interface = net_one.getlinknetif(net_two)
                        upstream = False

                        if not interface:
                            upstream = True
                            interface = net_two.getlinknetif(net_one)

                        if not interface:
                            raise CoreError("modify unknown link between nets")

                        if upstream:
                            interface.swapparams("_params_up")
                            net_one.linkconfig(interface, options)
                            interface.swapparams("_params_up")
                        else:
                            net_one.linkconfig(interface, options)

                        if not options.unidirectional:
                            if upstream:
                                net_two.linkconfig(interface, options)
                            else:
                                interface.swapparams("_params_up")
                                net_two.linkconfig(interface, options)
                                interface.swapparams("_params_up")
                    else:
                        raise CoreError("modify link for unknown nodes")
                elif not node_one:
                    # node1 = layer 2node, node2 = layer3 node
                    interface = node_two.netif(interface_two_id)
                    net_one.linkconfig(interface, options)
                elif not node_two:
                    # node2 = layer 2node, node1 = layer3 node
                    interface = node_one.netif(interface_one_id)
                    net_one.linkconfig(interface, options)
                else:
                    common_networks = node_one.commonnets(node_two)
                    if not common_networks:
                        raise CoreError("no common network found")

                    for net_one, interface_one, interface_two in common_networks:
                        if (
                            interface_one_id is not None
                            and interface_one_id != node_one.getifindex(interface_one)
                        ):
                            continue

                        net_one.linkconfig(interface_one, options, interface_two)
                        if not options.unidirectional:
                            net_one.linkconfig(interface_two, options, interface_one)
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

    def _next_node_id(self) -> int:
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
            _id = self._next_node_id()

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
        logging.info(
            "creating node(%s) id(%s) name(%s) start(%s)",
            _class.__name__,
            _id,
            name,
            start,
        )
        kwargs = dict(_id=_id, name=name, start=start, server=server)
        if _class in CONTAINER_NODES:
            kwargs["image"] = options.image
        node = self.create_node(_class, **kwargs)

        # set node attributes
        node.icon = options.icon
        node.canvas = options.canvas
        node.opaque = options.opaque

        # set node position and broadcast it
        self.set_node_position(node, options)

        # add services to needed nodes
        if isinstance(node, (CoreNode, PhysicalNode, DockerNode, LxcNode)):
            node.type = options.model
            logging.debug("set node type: %s", node.type)
            self.services.add_services(node, node.type, options.services)

            # add config services
            logging.info("setting node config services: %s", options.config_services)
            for name in options.config_services:
                service_class = self.service_manager.get_service(name)
                node.add_config_service(service_class)

        # ensure default emane configuration
        if isinstance(node, EmaneNet) and options.emane:
            self.emane.set_model_config(_id, options.emane)
        # set default wlan config if needed
        if isinstance(node, WlanNode):
            self.mobility.set_model_config(_id, BasicRangeModel.name)

        # boot nodes after runtime, CoreNodes, Physical, and RJ45 are all nodes
        is_boot_node = isinstance(node, CoreNodeBase) and not isinstance(node, Rj45Node)
        if self.state == EventTypes.RUNTIME_STATE and is_boot_node:
            self.write_nodes()
            self.add_remove_control_interface(node=node, remove=False)
            self.services.boot_services(node)

        self.sdt.add_node(node)
        return node

    def edit_node(self, node_id: int, options: NodeOptions) -> None:
        """
        Edit node information.

        :param node_id: id of node to update
        :param options: data to update node with
        :return: nothing
        :raises core.CoreError: when node to update does not exist
        """
        # get node to update
        node = self.get_node(node_id, NodeBase)

        # set node position and broadcast it
        self.set_node_position(node, options)

        # update attributes
        node.canvas = options.canvas
        node.icon = options.icon

        # provide edits to sdt
        self.sdt.edit_node(node, options.lon, options.lat, options.alt)

    def set_node_position(self, node: NodeBase, options: NodeOptions) -> None:
        """
        Set position for a node, use lat/lon/alt if needed.

        :param node: node to set position for
        :param options: data for node
        :return: nothing
        """
        # extract location values
        x = options.x
        y = options.y
        lat = options.lat
        lon = options.lon
        alt = options.alt

        # check if we need to generate position from lat/lon/alt
        has_empty_position = all(i is None for i in [x, y])
        has_lat_lon_alt = all(i is not None for i in [lat, lon, alt])
        using_lat_lon_alt = has_empty_position and has_lat_lon_alt
        if using_lat_lon_alt:
            x, y, _ = self.location.getxyz(lat, lon, alt)
            node.setposition(x, y, None)
            node.position.set_geo(lon, lat, alt)
            self.broadcast_node(node)
        elif not has_empty_position:
            node.setposition(x, y, None)

    def start_mobility(self, node_ids: List[int] = None) -> None:
        """
        Start mobility for the provided node ids.

        :param node_ids: nodes to start mobility for
        :return: nothing
        """
        self.mobility.startup(node_ids)

    def is_active(self) -> bool:
        """
        Determine if this session is considered to be active. (Runtime or Data collect states)

        :return: True if active, False otherwise
        """
        result = self.state in {EventTypes.RUNTIME_STATE, EventTypes.DATACOLLECT_STATE}
        logging.info("session(%s) checking if active: %s", self.id, result)
        return result

    def open_xml(self, file_name: str, start: bool = False) -> None:
        """
        Import a session from the EmulationScript XML format.

        :param file_name: xml file to load session from
        :param start: instantiate session if true, false otherwise
        :return: nothing
        """
        logging.info("opening xml: %s", file_name)

        # clear out existing session
        self.clear()

        if start:
            state = EventTypes.CONFIGURATION_STATE
        else:
            state = EventTypes.DEFINITION_STATE
        self.set_state(state)
        self.name = os.path.basename(file_name)
        self.file_name = file_name

        # write out xml file
        CoreXmlReader(self).read(file_name)

        # start session if needed
        if start:
            self.instantiate()

    def save_xml(self, file_name: str) -> None:
        """
        Export a session to the EmulationScript XML format.

        :param file_name: file name to write session xml to
        :return: nothing
        """
        CoreXmlWriter(self).write(file_name)

    def add_hook(
        self, state: EventTypes, file_name: str, data: str, source_name: str = None
    ) -> None:
        """
        Store a hook from a received file message.

        :param state: when to run hook
        :param file_name: file name for hook
        :param data: hook data
        :param source_name: source name
        :return: nothing
        """
        logging.info(
            "setting state hook: %s - %s source(%s)", state, file_name, source_name
        )
        hook = file_name, data
        state_hooks = self._hooks.setdefault(state, [])
        state_hooks.append(hook)

        # immediately run a hook if it is in the current state
        if self.state == state:
            logging.info("immediately running new state hook")
            self.run_hook(hook)

    def add_node_file(
        self, node_id: int, source_name: str, file_name: str, data: str
    ) -> None:
        """
        Add a file to a node.

        :param node_id: node to add file to
        :param source_name: source file name
        :param file_name: file name to add
        :param data: file data
        :return: nothing
        """
        node = self.get_node(node_id, CoreNodeBase)
        if source_name is not None:
            node.addfile(source_name, file_name)
        elif data is not None:
            node.nodefile(file_name, data)

    def clear(self) -> None:
        """
        Clear all CORE session data. (nodes, hooks, etc)

        :return: nothing
        """
        self.emane.shutdown()
        self.delete_nodes()
        self.distributed.shutdown()
        self.del_hooks()
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
        logging.info("session(%s) shutting down", self.id)
        self.set_state(EventTypes.DATACOLLECT_STATE, send_event=True)
        self.set_state(EventTypes.SHUTDOWN_STATE, send_event=True)

        # clear out current core session
        self.clear()

        # shutdown sdt
        self.sdt.shutdown()

        # remove this sessions working directory
        preserve = self.options.get_config("preservedir") == "1"
        if not preserve:
            shutil.rmtree(self.session_dir, ignore_errors=True)

        # call session shutdown handlers
        for handler in self.shutdown_handlers:
            handler(self)

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
        node_data = node.data(message_type, source)
        if not node_data:
            return
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
        state_name = state.name
        if self.state == state:
            logging.info(
                "session(%s) is already in state: %s, skipping change",
                self.id,
                state_name,
            )
            return

        self.state = state
        self._state_time = time.monotonic()
        logging.info("changing session(%s) to state %s", self.id, state_name)
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
        try:
            state_file = open(self._state_file, "w")
            state_file.write(f"{state.value} {state.name}\n")
            state_file.close()
        except IOError:
            logging.exception("error writing state file: %s", state.name)

    def run_hooks(self, state: EventTypes) -> None:
        """
        Run hook scripts upon changing states. If hooks is not specified, run all hooks
        in the given state.

        :param state: state to run hooks for
        :return: nothing
        """

        # check that state change hooks exist
        if state not in self._hooks:
            return

        # retrieve all state hooks
        hooks = self._hooks.get(state, [])

        # execute all state hooks
        if hooks:
            for hook in hooks:
                self.run_hook(hook)
        else:
            logging.info("no state hooks for %s", state)

    def set_hook(
        self, hook_type: str, file_name: str, source_name: str, data: str
    ) -> None:
        """
        Store a hook from a received file message.

        :param hook_type: hook type
        :param file_name: file name for hook
        :param source_name: source name
        :param data: hook data
        :return: nothing
        """
        logging.info(
            "setting state hook: %s - %s from %s", hook_type, file_name, source_name
        )

        _hook_id, state = hook_type.split(":")[:2]
        if not state.isdigit():
            logging.error("error setting hook having state '%s'", state)
            return

        state = int(state)
        hook = file_name, data

        # append hook to current state hooks
        state_hooks = self._hooks.setdefault(state, [])
        state_hooks.append(hook)

        # immediately run a hook if it is in the current state
        # (this allows hooks in the definition and configuration states)
        if self.state == state:
            logging.info("immediately running new state hook")
            self.run_hook(hook)

    def del_hooks(self) -> None:
        """
        Clear the hook scripts dict.
        """
        self._hooks.clear()

    def run_hook(self, hook: Tuple[str, str]) -> None:
        """
        Run a hook.

        :param hook: hook to run
        :return: nothing
        """
        file_name, data = hook
        logging.info("running hook %s", file_name)

        # write data to hook file
        try:
            hook_file = open(os.path.join(self.session_dir, file_name), "w")
            hook_file.write(data)
            hook_file.close()
        except IOError:
            logging.exception("error writing hook '%s'", file_name)

        # setup hook stdout and stderr
        try:
            stdout = open(os.path.join(self.session_dir, file_name + ".log"), "w")
            stderr = subprocess.STDOUT
        except IOError:
            logging.exception("error setting up hook stderr and stdout")
            stdout = None
            stderr = None

        # execute hook file
        try:
            args = ["/bin/sh", file_name]
            subprocess.check_call(
                args,
                stdout=stdout,
                stderr=stderr,
                close_fds=True,
                cwd=self.session_dir,
                env=self.get_environment(),
            )
        except (OSError, subprocess.CalledProcessError):
            logging.exception("error running hook: %s", file_name)

    def run_state_hooks(self, state: EventTypes) -> None:
        """
        Run state hooks.

        :param state: state to run hooks for
        :return: nothing
        """
        for hook in self._state_hooks.get(state, []):
            try:
                hook(state)
            except Exception:
                message = (
                    f"exception occured when running {state.name} state hook: {hook}"
                )
                logging.exception(message)
                self.exception(
                    ExceptionLevels.ERROR, "Session.run_state_hooks", message
                )

    def add_state_hook(
        self, state: EventTypes, hook: Callable[[EventTypes], None]
    ) -> None:
        """
        Add a state hook.

        :param state: state to add hook for
        :param hook: hook callback for the state
        :return: nothing
        """
        hooks = self._state_hooks.setdefault(state, [])
        if hook in hooks:
            raise CoreError("attempting to add duplicate state hook")
        hooks.append(hook)

        if self.state == state:
            hook(state)

    def del_state_hook(self, state: int, hook: Callable[[int], None]) -> None:
        """
        Delete a state hook.

        :param state: state to delete hook for
        :param hook: hook to delete
        :return: nothing
        """
        hooks = self._state_hooks.setdefault(state, [])
        hooks.remove(hook)

    def runtime_state_hook(self, state: EventTypes) -> None:
        """
        Runtime state hook check.

        :param state: state to check
        :return: nothing
        """
        if state == EventTypes.RUNTIME_STATE:
            self.emane.poststartup()

            # create session deployed xml
            xml_file_name = os.path.join(self.session_dir, "session-deployed.xml")
            xml_writer = corexml.CoreXmlWriter(self)
            corexmldeployment.CoreXmlDeployment(self, xml_writer.scenario)
            xml_writer.write(xml_file_name)

    def get_environment(self, state: bool = True) -> Dict[str, str]:
        """
        Get an environment suitable for a subprocess.Popen call.
        This is the current process environment with some session-specific
        variables.

        :param state: flag to determine if session state should be included
        :return: environment variables
        """
        env = os.environ.copy()
        env["SESSION"] = str(self.id)
        env["SESSION_SHORT"] = self.short_session_id()
        env["SESSION_DIR"] = self.session_dir
        env["SESSION_NAME"] = str(self.name)
        env["SESSION_FILENAME"] = str(self.file_name)
        env["SESSION_USER"] = str(self.user)
        env["SESSION_NODE_COUNT"] = str(self.get_node_count())

        if state:
            env["SESSION_STATE"] = str(self.state)

        # attempt to read and add environment config file
        environment_config_file = os.path.join(constants.CORE_CONF_DIR, "environment")
        try:
            if os.path.isfile(environment_config_file):
                utils.load_config(environment_config_file, env)
        except IOError:
            logging.warning(
                "environment configuration file does not exist: %s",
                environment_config_file,
            )

        # attempt to read and add user environment file
        if self.user:
            environment_user_file = os.path.join(
                "/home", self.user, ".core", "environment"
            )
            try:
                utils.load_config(environment_user_file, env)
            except IOError:
                logging.debug(
                    "user core environment settings file not present: %s",
                    environment_user_file,
                )

        return env

    def set_thumbnail(self, thumb_file: str) -> None:
        """
        Set the thumbnail filename. Move files from /tmp to session dir.

        :param thumb_file: tumbnail file to set for session
        :return: nothing
        """
        if not os.path.exists(thumb_file):
            logging.error("thumbnail file to set does not exist: %s", thumb_file)
            self.thumbnail = None
            return

        destination_file = os.path.join(self.session_dir, os.path.basename(thumb_file))
        shutil.copy(thumb_file, destination_file)
        self.thumbnail = destination_file

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
                gid = os.stat(self.session_dir).st_gid
                os.chown(self.session_dir, uid, gid)
            except IOError:
                logging.exception("failed to set permission on %s", self.session_dir)

        self.user = user

    def get_node_id(self) -> int:
        """
        Return a unique, new node id.
        """
        with self._nodes_lock:
            while True:
                node_id = random.randint(1, 0xFFFF)
                if node_id not in self.nodes:
                    break
        return node_id

    def create_node(self, _class: Type[NT], *args: Any, **kwargs: Any) -> NT:
        """
        Create an emulation node.

        :param _class: node class to create
        :param args: list of arguments for the class to create
        :param kwargs: dictionary of arguments for the class to create
        :return: the created node instance
        :raises core.CoreError: when id of the node to create already exists
        """
        node = _class(self, *args, **kwargs)
        with self._nodes_lock:
            if node.id in self.nodes:
                node.shutdown()
                raise CoreError(f"duplicate node id {node.id} for {node.name}")
            self.nodes[node.id] = node
        return node

    def get_node(self, _id: int, _class: Type[NT]) -> NT:
        """
        Get a session node.

        :param _id: node id to retrieve
        :param _class: expected node class
        :return: node for the given id
        :raises core.CoreError: when node does not exist
        """
        if _id not in self.nodes:
            raise CoreError(f"unknown node id {_id}")
        node = self.nodes[_id]
        if not isinstance(node, _class):
            actual = node.__class__.__name__
            expected = _class.__name__
            raise CoreError(f"node class({actual}) is not expected({expected})")
        return node

    def delete_node(self, _id: int) -> bool:
        """
        Delete a node from the session and check if session should shutdown, if no nodes are left.

        :param _id: id of node to delete
        :return: True if node deleted, False otherwise
        """
        # delete node and check for session shutdown if a node was removed
        logging.info("deleting node(%s)", _id)
        node = None
        with self._nodes_lock:
            if _id in self.nodes:
                node = self.nodes.pop(_id)

        if node:
            node.shutdown()
            self.sdt.delete_node(_id)
            self.check_shutdown()

        return node is not None

    def delete_nodes(self) -> None:
        """
        Clear the nodes dictionary, and call shutdown for each node.
        """
        with self._nodes_lock:
            funcs = []
            while self.nodes:
                _, node = self.nodes.popitem()
                self.sdt.delete_node(node.id)
                funcs.append((node.shutdown, [], {}))
            utils.threadpool(funcs)

    def write_nodes(self) -> None:
        """
        Write nodes to a 'nodes' file in the session dir.
        The 'nodes' file lists: number, name, api-type, class-type
        """
        try:
            with self._nodes_lock:
                file_path = os.path.join(self.session_dir, "nodes")
                with open(file_path, "w") as f:
                    for _id in self.nodes.keys():
                        node = self.nodes[_id]
                        f.write(f"{_id} {node.name} {node.apitype} {type(node)}\n")
        except IOError:
            logging.exception("error writing nodes file")

    def dump_session(self) -> None:
        """
        Log information about the session in its current state.
        """
        logging.info("session id=%s name=%s state=%s", self.id, self.name, self.state)
        logging.info(
            "file=%s thumbnail=%s node_count=%s/%s",
            self.file_name,
            self.thumbnail,
            self.get_node_count(),
            len(self.nodes),
        )

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
        # write current nodes out to session directory file
        self.write_nodes()

        # create control net interfaces and network tunnels
        # which need to exist for emane to sync on location events
        # in distributed scenarios
        self.add_remove_control_net(0, remove=False)

        # initialize distributed tunnels
        self.distributed.start()

        # instantiate will be invoked again upon emane configure
        if self.emane.startup() == self.emane.NOT_READY:
            return []

        # boot node services and then start mobility
        exceptions = self.boot_nodes()
        if not exceptions:
            self.mobility.startup()

            # notify listeners that instantiation is complete
            event = EventData(event_type=EventTypes.INSTANTIATION_COMPLETE)
            self.broadcast_event(event)

            # assume either all nodes have booted already, or there are some
            # nodes on slave servers that will be booted and those servers will
            # send a node status response message
            self.check_runtime()
        return exceptions

    def get_node_count(self) -> int:
        """
        Returns the number of CoreNodes and CoreNets, except for those
        that are not considered in the GUI's node count.

        :return: created node count
        """
        with self._nodes_lock:
            count = 0
            for node_id in self.nodes:
                node = self.nodes[node_id]
                is_p2p_ctrlnet = isinstance(node, (PtpNet, CtrlNet))
                is_tap = isinstance(node, GreTapBridge) and not isinstance(
                    node, TunnelNode
                )
                if is_p2p_ctrlnet or is_tap:
                    continue

                count += 1
        return count

    def check_runtime(self) -> None:
        """
        Check if we have entered the runtime state, that all nodes have been
        started and the emulation is running. Start the event loop once we
        have entered runtime (time=0).

        :return: nothing
        """
        # this is called from instantiate() after receiving an event message
        # for the instantiation state
        logging.debug(
            "session(%s) checking if not in runtime state, current state: %s",
            self.id,
            self.state.name,
        )
        if self.state == EventTypes.RUNTIME_STATE:
            logging.info("valid runtime state found, returning")
            return

        # start event loop and set to runtime
        self.event_loop.run()
        self.set_state(EventTypes.RUNTIME_STATE, send_event=True)

    def data_collect(self) -> None:
        """
        Tear down a running session. Stop the event loop and any running
        nodes, and perform clean-up.

        :return: nothing
        """
        # stop event loop
        self.event_loop.stop()

        # stop node services
        with self._nodes_lock:
            funcs = []
            for node_id in self.nodes:
                node = self.nodes[node_id]
                if not isinstance(node, CoreNodeBase) or not node.up:
                    continue
                args = (node,)
                funcs.append((self.services.stop_services, args, {}))
            utils.threadpool(funcs)

        # shutdown emane
        self.emane.shutdown()

        # update control interface hosts
        self.update_control_interface_hosts(remove=True)

        # remove all four possible control networks
        self.add_remove_control_net(0, remove=True)
        self.add_remove_control_net(1, remove=True)
        self.add_remove_control_net(2, remove=True)
        self.add_remove_control_net(3, remove=True)

    def check_shutdown(self) -> bool:
        """
        Check if we have entered the shutdown state, when no running nodes
        and links remain.

        :return: True if should shutdown, False otherwise
        """
        node_count = self.get_node_count()
        logging.debug(
            "session(%s) checking shutdown: %s nodes remaining", self.id, node_count
        )
        shutdown = False
        if node_count == 0:
            shutdown = True
            self.set_state(EventTypes.SHUTDOWN_STATE)
            # clearing sdt saved data here for legacy gui
            self.sdt.shutdown()
        return shutdown

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
        logging.info("booting node(%s): %s", node.name, [x.name for x in node.services])
        self.add_remove_control_interface(node=node, remove=False)
        self.services.boot_services(node)
        node.start_config_services()

    def boot_nodes(self) -> List[Exception]:
        """
        Invoke the boot() procedure for all nodes and send back node
        messages to the GUI for node messages that had the status
        request flag.

        :return: service boot exceptions
        """
        with self._nodes_lock:
            funcs = []
            start = time.monotonic()
            for _id in self.nodes:
                node = self.nodes[_id]
                if isinstance(node, CoreNodeBase) and not isinstance(node, Rj45Node):
                    args = (node,)
                    funcs.append((self.boot_node, args, {}))
            results, exceptions = utils.threadpool(funcs)
            total = time.monotonic() - start
            logging.debug("boot run time: %s", total)
        if not exceptions:
            self.update_control_interface_hosts()
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

    def get_control_net_server_interfaces(self) -> List[str]:
        """
        Retrieve control net server interfaces.

        :return: list of control net server interfaces
        """
        d0 = self.options.get_config("controlnetif0")
        if d0:
            logging.error("controlnet0 cannot be assigned with a host interface")
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
        logging.debug(
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
        logging.debug("prefix spec: %s", prefix_spec)

        server_interface = self.get_control_net_server_interfaces()[net_index]

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
                logging.debug("controlnet updown script not configured")

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

        logging.info(
            "controlnet(%s) prefix(%s) updown(%s) serverintf(%s)",
            _id,
            prefix,
            updown_script,
            server_interface,
        )
        control_net = self.create_node(
            CtrlNet,
            prefix,
            _id=_id,
            updown_script=updown_script,
            serverintf=server_interface,
        )
        return control_net

    def add_remove_control_interface(
        self,
        node: CoreNode,
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
        if node.netif(control_net.CTRLIF_IDX_BASE + net_index):
            return
        try:
            ip4 = control_net.prefix[node.id]
            ip4_mask = control_net.prefix.prefixlen
            interface = InterfaceData(
                id=control_net.CTRLIF_IDX_BASE + net_index,
                name=f"ctrl{net_index}",
                mac=utils.random_mac(),
                ip4=ip4,
                ip4_mask=ip4_mask,
            )
            ifindex = node.newnetif(control_net, interface)
            node.netif(ifindex).control = True
        except ValueError:
            msg = f"Control interface not added to node {node.id}. "
            msg += f"Invalid control network prefix ({control_net.prefix}). "
            msg += "A longer prefix length may be required for this many nodes."
            logging.exception(msg)

    def update_control_interface_hosts(
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
            logging.exception("error retrieving control net node")
            return

        header = f"CORE session {self.id} host entries"
        if remove:
            logging.info("Removing /etc/hosts file entries.")
            utils.file_demunge("/etc/hosts", header)
            return

        entries = []
        for interface in control_net.netifs():
            name = interface.node.name
            for address in interface.addrlist:
                address = address.split("/")[0]
                entries.append(f"{address} {name}")

        logging.info("Adding %d /etc/hosts file entries.", len(entries))
        utils.file_munge("/etc/hosts", header, "\n".join(entries) + "\n")

    def runtime(self) -> float:
        """
        Return the current time we have been in the runtime state, or zero
        if not in runtime.
        """
        if self.state == EventTypes.RUNTIME_STATE:
            return time.monotonic() - self._state_time
        else:
            return 0.0

    def add_event(
        self,
        event_time: float,
        node: CoreNode = None,
        name: str = None,
        data: str = None,
    ) -> None:
        """
        Add an event to the event queue, with a start time relative to the
        start of the runtime state.

        :param event_time: event time
        :param node: node to add event for
        :param name: name of event
        :param data: data for event
        :return: nothing
        """
        event_time = float(event_time)
        current_time = self.runtime()

        if current_time > 0:
            if event_time <= current_time:
                logging.warning(
                    "could not schedule past event for time %s (run time is now %s)",
                    event_time,
                    current_time,
                )
                return
            event_time = event_time - current_time

        self.event_loop.add_event(
            event_time, self.run_event, node=node, name=name, data=data
        )

        if not name:
            name = ""
        logging.info(
            "scheduled event %s at time %s data=%s",
            name,
            event_time + current_time,
            data,
        )

    # TODO: if data is None, this blows up, but this ties into how event functions
    #  are ran, need to clean that up
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
        now = self.runtime()
        if not name:
            name = ""

        logging.info("running event %s at time %s cmd=%s", name, now, data)
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
