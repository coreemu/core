import logging
from typing import List, Optional, Set

from PIL.ImageTk import PhotoImage

from core.api.grpc.wrappers import Node, NodeType
from core.gui.appconfig import CustomNode, GuiConfig
from core.gui.images import ImageEnum, Images, TypeToImage

ICON_SIZE: int = 48
ANTENNA_SIZE: int = 32


class NodeDraw:
    def __init__(self) -> None:
        self.custom: bool = False
        self.image: Optional[PhotoImage] = None
        self.image_enum: Optional[ImageEnum] = None
        self.image_file: Optional[str] = None
        self.node_type: Optional[NodeType] = None
        self.model: Optional[str] = None
        self.services: Set[str] = set()
        self.label: Optional[str] = None

    @classmethod
    def from_setup(
        cls,
        image_enum: ImageEnum,
        node_type: NodeType,
        label: str,
        model: str = None,
        tooltip: str = None,
    ) -> "NodeDraw":
        node_draw = NodeDraw()
        node_draw.image_enum = image_enum
        node_draw.image = Images.get(image_enum, ICON_SIZE)
        node_draw.node_type = node_type
        node_draw.label = label
        node_draw.model = model
        node_draw.tooltip = tooltip
        return node_draw

    @classmethod
    def from_custom(cls, custom_node: CustomNode) -> "NodeDraw":
        node_draw = NodeDraw()
        node_draw.custom = True
        node_draw.image_file = custom_node.image
        node_draw.image = Images.get_custom(custom_node.image, ICON_SIZE)
        node_draw.node_type = NodeType.DEFAULT
        node_draw.services = custom_node.services
        node_draw.label = custom_node.name
        node_draw.model = custom_node.name
        node_draw.tooltip = custom_node.name
        return node_draw


class NodeUtils:
    NODES: List[NodeDraw] = []
    NETWORK_NODES: List[NodeDraw] = []
    NODE_ICONS = {}
    CONTAINER_NODES: Set[NodeType] = {NodeType.DEFAULT, NodeType.DOCKER, NodeType.LXC}
    IMAGE_NODES: Set[NodeType] = {NodeType.DOCKER, NodeType.LXC}
    WIRELESS_NODES: Set[NodeType] = {NodeType.WIRELESS_LAN, NodeType.EMANE}
    RJ45_NODES: Set[NodeType] = {NodeType.RJ45}
    IGNORE_NODES: Set[NodeType] = {NodeType.CONTROL_NET}
    MOBILITY_NODES: Set[NodeType] = {NodeType.WIRELESS_LAN, NodeType.EMANE}
    NODE_MODELS: Set[str] = {"router", "host", "PC", "mdr", "prouter"}
    ROUTER_NODES: Set[str] = {"router", "mdr"}
    ANTENNA_ICON: PhotoImage = None

    @classmethod
    def is_mobility(cls, node: Node) -> bool:
        return node.type in cls.MOBILITY_NODES

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
        cls, node_type: NodeType, model: str, gui_config: GuiConfig, scale: float = 1.0
    ) -> PhotoImage:

        image_enum = TypeToImage.get(node_type, model)
        if image_enum:
            return Images.get(image_enum, int(ICON_SIZE * scale))
        else:
            image_stem = cls.get_image_file(gui_config, model)
            if image_stem:
                return Images.get_with_image_file(image_stem, int(ICON_SIZE * scale))

    @classmethod
    def node_image(
        cls, core_node: Node, gui_config: GuiConfig, scale: float = 1.0
    ) -> PhotoImage:
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
    def get_custom_node_services(cls, gui_config: GuiConfig, name: str) -> List[str]:
        for custom_node in gui_config.nodes:
            if custom_node.name == name:
                return custom_node.services
        return []

    @classmethod
    def get_image_file(cls, gui_config: GuiConfig, name: str) -> Optional[str]:
        for custom_node in gui_config.nodes:
            if custom_node.name == name:
                return custom_node.image
        return None

    @classmethod
    def setup(cls) -> None:
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
