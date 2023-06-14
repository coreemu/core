import logging
from typing import TYPE_CHECKING, Optional

from PIL.ImageTk import PhotoImage

from core.api.grpc.wrappers import Node, NodeType
from core.gui import images
from core.gui.appconfig import CustomNode, GuiConfig
from core.gui.images import ImageEnum

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application

NODES: list["NodeDraw"] = []
NETWORK_NODES: list["NodeDraw"] = []
NODE_ICONS = {}
CONTAINER_NODES: set[NodeType] = {
    NodeType.DEFAULT,
    NodeType.DOCKER,
    NodeType.LXC,
    NodeType.PODMAN,
}
IMAGE_NODES: set[NodeType] = {NodeType.DOCKER, NodeType.LXC, NodeType.PODMAN}
WIRELESS_NODES: set[NodeType] = {
    NodeType.WIRELESS_LAN,
    NodeType.EMANE,
    NodeType.WIRELESS,
}
RJ45_NODES: set[NodeType] = {NodeType.RJ45}
BRIDGE_NODES: set[NodeType] = {NodeType.HUB, NodeType.SWITCH}
IGNORE_NODES: set[NodeType] = {NodeType.CONTROL_NET}
MOBILITY_NODES: set[NodeType] = {NodeType.WIRELESS_LAN, NodeType.EMANE}
NODE_MODELS: set[str] = {"router", "PC", "mdr", "prouter"}
ROUTER_NODES: set[str] = {"router", "mdr"}
ANTENNA_ICON: Optional[PhotoImage] = None


def setup() -> None:
    global ANTENNA_ICON
    nodes = [
        (ImageEnum.PC, NodeType.DEFAULT, "PC", "PC"),
        (ImageEnum.MDR, NodeType.DEFAULT, "MDR", "mdr"),
        (ImageEnum.ROUTER, NodeType.DEFAULT, "Router", "router"),
        (ImageEnum.PROUTER, NodeType.DEFAULT, "PRouter", "prouter"),
        (ImageEnum.DOCKER, NodeType.DOCKER, "Docker", None),
        (ImageEnum.LXC, NodeType.LXC, "LXC", None),
        (ImageEnum.PODMAN, NodeType.PODMAN, "Podman", None),
    ]
    for image_enum, node_type, label, model in nodes:
        node_draw = NodeDraw.from_setup(image_enum, node_type, label, model)
        NODES.append(node_draw)
        NODE_ICONS[(node_type, model)] = node_draw.image
    network_nodes = [
        (ImageEnum.HUB, NodeType.HUB, "Hub"),
        (ImageEnum.SWITCH, NodeType.SWITCH, "Switch"),
        (ImageEnum.WLAN, NodeType.WIRELESS_LAN, "WLAN"),
        (ImageEnum.WIRELESS, NodeType.WIRELESS, "Wireless"),
        (ImageEnum.EMANE, NodeType.EMANE, "EMANE"),
        (ImageEnum.RJ45, NodeType.RJ45, "RJ45"),
        (ImageEnum.TUNNEL, NodeType.TUNNEL, "Tunnel"),
    ]
    for image_enum, node_type, label in network_nodes:
        node_draw = NodeDraw.from_setup(image_enum, node_type, label)
        NETWORK_NODES.append(node_draw)
        NODE_ICONS[(node_type, None)] = node_draw.image
    ANTENNA_ICON = images.from_enum(ImageEnum.ANTENNA, width=images.ANTENNA_SIZE)


def is_bridge(node: Node) -> bool:
    return node.type in BRIDGE_NODES


def is_mobility(node: Node) -> bool:
    return node.type in MOBILITY_NODES


def is_router(node: Node) -> bool:
    return is_model(node) and node.model in ROUTER_NODES


def should_ignore(node: Node) -> bool:
    return node.type in IGNORE_NODES


def is_container(node: Node) -> bool:
    return node.type in CONTAINER_NODES


def is_model(node: Node) -> bool:
    return node.type == NodeType.DEFAULT


def has_image(node_type: NodeType) -> bool:
    return node_type in IMAGE_NODES


def is_wireless(node: Node) -> bool:
    return node.type in WIRELESS_NODES


def is_rj45(node: Node) -> bool:
    return node.type in RJ45_NODES


def is_custom(node: Node) -> bool:
    return is_model(node) and node.model not in NODE_MODELS


def is_iface_node(node: Node) -> bool:
    return is_container(node) or is_bridge(node)


def get_custom_services(gui_config: GuiConfig, name: str) -> list[str]:
    for custom_node in gui_config.nodes:
        if custom_node.name == name:
            return custom_node.services
    return []


def _get_custom_file(config: GuiConfig, name: str) -> Optional[str]:
    for custom_node in config.nodes:
        if custom_node.name == name:
            return custom_node.image
    return None


def get_icon(node: Node, app: "Application") -> PhotoImage:
    scale = app.app_scale
    image = None
    # node icon was overridden with a specific value
    if node.icon:
        try:
            image = images.from_file(node.icon, width=images.NODE_SIZE, scale=scale)
        except OSError:
            logger.error("invalid icon: %s", node.icon)
    # custom node
    elif is_custom(node):
        image_file = _get_custom_file(app.guiconfig, node.model)
        logger.info("custom node file: %s", image_file)
        if image_file:
            image = images.from_file(image_file, width=images.NODE_SIZE, scale=scale)
    # built in node
    else:
        image = images.from_node(node, scale=scale)
    # default image, if everything above fails
    if not image:
        image = images.from_enum(
            ImageEnum.EDITNODE, width=images.NODE_SIZE, scale=scale
        )
    return image


class NodeDraw:
    def __init__(self) -> None:
        self.custom: bool = False
        self.image: Optional[PhotoImage] = None
        self.image_enum: Optional[ImageEnum] = None
        self.image_file: Optional[str] = None
        self.node_type: Optional[NodeType] = None
        self.model: Optional[str] = None
        self.services: set[str] = set()
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
        node_draw.image = images.from_enum(image_enum, width=images.NODE_SIZE)
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
        node_draw.image = images.from_file(custom_node.image, width=images.NODE_SIZE)
        node_draw.node_type = NodeType.DEFAULT
        node_draw.services = set(custom_node.services)
        node_draw.label = custom_node.name
        node_draw.model = custom_node.name
        node_draw.tooltip = custom_node.name
        return node_draw
