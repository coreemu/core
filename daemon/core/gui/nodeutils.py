import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Union

from core.api.grpc.core_pb2 import Node, NodeType
from core.gui.images import ImageEnum, Images, TypeToImage

if TYPE_CHECKING:
    from core.api.grpc import core_pb2
    from PIL import ImageTk

ICON_SIZE = 48
ANTENNA_SIZE = 32


class NodeDraw:
    def __init__(self):
        self.custom: bool = False
        self.image = None
        self.image_enum: Optional[ImageEnum] = None
        self.image_file = None
        self.node_type: core_pb2.NodeType = None
        self.model: Optional[str] = None
        self.services: Set[str] = set()

    @classmethod
    def from_setup(
        cls,
        image_enum: ImageEnum,
        node_type: "core_pb2.NodeType",
        label: str,
        model: str = None,
        tooltip=None,
    ):
        node_draw = NodeDraw()
        node_draw.image_enum = image_enum
        node_draw.image = Images.get(image_enum, ICON_SIZE)
        node_draw.node_type = node_type
        node_draw.label = label
        node_draw.model = model
        node_draw.tooltip = tooltip
        return node_draw

    @classmethod
    def from_custom(cls, name: str, image_file: str, services: Set[str]):
        node_draw = NodeDraw()
        node_draw.custom = True
        node_draw.image_file = image_file
        node_draw.image = Images.get_custom(image_file, ICON_SIZE)
        node_draw.node_type = NodeType.DEFAULT
        node_draw.services = services
        node_draw.label = name
        node_draw.model = name
        node_draw.tooltip = name
        return node_draw


class NodeUtils:
    NODES = []
    NETWORK_NODES = []
    NODE_ICONS = {}
    CONTAINER_NODES = {NodeType.DEFAULT, NodeType.DOCKER, NodeType.LXC}
    IMAGE_NODES = {NodeType.DOCKER, NodeType.LXC}
    WIRELESS_NODES = {NodeType.WIRELESS_LAN, NodeType.EMANE}
    RJ45_NODES = {NodeType.RJ45}
    IGNORE_NODES = {NodeType.CONTROL_NET, NodeType.PEER_TO_PEER}
    NODE_MODELS = {"router", "host", "PC", "mdr", "prouter"}
    ROUTER_NODES = {"router", "mdr"}
    ANTENNA_ICON = None

    @classmethod
    def is_router_node(cls, node: Node) -> bool:
        return cls.is_model_node(node.type) and node.model in cls.ROUTER_NODES

    @classmethod
    def is_ignore_node(cls, node_type: NodeType) -> bool:
        return node_type in cls.IGNORE_NODES

    @classmethod
    def is_container_node(cls, node_type: NodeType) -> bool:
        return node_type in cls.CONTAINER_NODES

    @classmethod
    def is_model_node(cls, node_type: NodeType) -> bool:
        return node_type == NodeType.DEFAULT

    @classmethod
    def is_image_node(cls, node_type: NodeType) -> bool:
        return node_type in cls.IMAGE_NODES

    @classmethod
    def is_wireless_node(cls, node_type: NodeType) -> bool:
        return node_type in cls.WIRELESS_NODES

    @classmethod
    def is_rj45_node(cls, node_type: NodeType) -> bool:
        return node_type in cls.RJ45_NODES

    @classmethod
    def node_icon(
        cls,
        node_type: NodeType,
        model: str,
        gui_config: Dict[str, List[Dict[str, str]]],
        scale=1.0,
    ) -> "ImageTk.PhotoImage":

        image_enum = TypeToImage.get(node_type, model)
        if image_enum:
            return Images.get(image_enum, int(ICON_SIZE * scale))
        else:
            image_stem = cls.get_image_file(gui_config, model)
            if image_stem:
                return Images.get_with_image_file(image_stem, int(ICON_SIZE * scale))

    @classmethod
    def node_image(
        cls,
        core_node: "core_pb2.Node",
        gui_config: Dict[str, List[Dict[str, str]]],
        scale=1.0,
    ) -> "ImageTk.PhotoImage":
        image = cls.node_icon(core_node.type, core_node.model, gui_config, scale)
        if core_node.icon:
            try:
                image = Images.create(core_node.icon, int(ICON_SIZE * scale))
            except OSError:
                logging.error("invalid icon: %s", core_node.icon)
        return image

    @classmethod
    def is_custom(cls, node_type: NodeType, model: str) -> bool:
        return node_type == NodeType.DEFAULT and model not in cls.NODE_MODELS

    @classmethod
    def get_custom_node_services(
        cls, gui_config: Dict[str, List[Dict[str, str]]], name: str
    ) -> List[str]:
        for m in gui_config["nodes"]:
            if m["name"] == name:
                return m["services"]
        return []

    @classmethod
    def get_image_file(cls, gui_config, name: str) -> Union[str, None]:
        if "nodes" in gui_config:
            for m in gui_config["nodes"]:
                if m["name"] == name:
                    return m["image"]
        return None

    @classmethod
    def setup(cls):
        nodes = [
            (ImageEnum.ROUTER, NodeType.DEFAULT, "Router", "router"),
            (ImageEnum.HOST, NodeType.DEFAULT, "Host", "host"),
            (ImageEnum.PC, NodeType.DEFAULT, "PC", "PC"),
            (ImageEnum.MDR, NodeType.DEFAULT, "MDR", "mdr"),
            (ImageEnum.PROUTER, NodeType.DEFAULT, "PRouter", "prouter"),
            (ImageEnum.DOCKER, NodeType.DOCKER, "Docker", None),
            (ImageEnum.LXC, NodeType.LXC, "LXC", None),
        ]
        for image_enum, node_type, label, model in nodes:
            node_draw = NodeDraw.from_setup(image_enum, node_type, label, model)
            cls.NODES.append(node_draw)
            cls.NODE_ICONS[(node_type, model)] = node_draw.image

        network_nodes = [
            (ImageEnum.HUB, NodeType.HUB, "Hub"),
            (ImageEnum.SWITCH, NodeType.SWITCH, "Switch"),
            (ImageEnum.WLAN, NodeType.WIRELESS_LAN, "WLAN"),
            (ImageEnum.EMANE, NodeType.EMANE, "EMANE"),
            (ImageEnum.RJ45, NodeType.RJ45, "RJ45"),
            (ImageEnum.TUNNEL, NodeType.TUNNEL, "Tunnel"),
        ]
        for image_enum, node_type, label in network_nodes:
            node_draw = NodeDraw.from_setup(image_enum, node_type, label)
            cls.NETWORK_NODES.append(node_draw)
            cls.NODE_ICONS[(node_type, None)] = node_draw.image
        cls.ANTENNA_ICON = Images.get(ImageEnum.ANTENNA, ANTENNA_SIZE)
