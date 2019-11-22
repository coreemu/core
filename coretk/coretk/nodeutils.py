from core.api.grpc.core_pb2 import NodeType
from coretk.images import ImageEnum, Images

ICON_SIZE = 48


class NodeDraw:
    def __init__(self):
        self.custom = False
        self.image = None
        self.image_enum = None
        self.image_file = None
        self.node_type = None
        self.model = None
        self.tooltip = None
        self.services = set()

    @classmethod
    def from_setup(cls, image_enum, node_type, model=None, tooltip=None):
        node_draw = NodeDraw()
        node_draw.image_enum = image_enum
        node_draw.image = Images.get(image_enum, ICON_SIZE)
        node_draw.node_type = node_type
        node_draw.model = model
        if tooltip is None:
            tooltip = model
        node_draw.tooltip = tooltip
        return node_draw

    @classmethod
    def from_custom(cls, name, image_file, services):
        node_draw = NodeDraw()
        node_draw.custom = True
        node_draw.image_file = image_file
        node_draw.image = Images.get_custom(image_file, ICON_SIZE)
        node_draw.node_type = NodeType.DEFAULT
        node_draw.services = services
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
    NODE_MODELS = {"router", "host", "PC", "mdr", "prouter"}

    @classmethod
    def is_container_node(cls, node_type):
        return node_type in cls.CONTAINER_NODES

    @classmethod
    def is_model_node(cls, node_type):
        return node_type == NodeType.DEFAULT

    @classmethod
    def is_image_node(cls, node_type):
        return node_type in cls.IMAGE_NODES

    @classmethod
    def is_wireless_node(cls, node_type):
        return node_type in cls.WIRELESS_NODES

    @classmethod
    def node_icon(cls, node_type, model):
        if model == "":
            model = None
        return cls.NODE_ICONS[(node_type, model)]

    @classmethod
    def setup(cls):
        nodes = [
            (ImageEnum.ROUTER, NodeType.DEFAULT, "router"),
            (ImageEnum.HOST, NodeType.DEFAULT, "host"),
            (ImageEnum.PC, NodeType.DEFAULT, "PC"),
            (ImageEnum.MDR, NodeType.DEFAULT, "mdr"),
            (ImageEnum.PROUTER, NodeType.DEFAULT, "prouter"),
            (ImageEnum.DOCKER, NodeType.DOCKER, "Docker"),
            (ImageEnum.LXC, NodeType.LXC, "LXC"),
        ]
        for image_enum, node_type, model in nodes:
            node_draw = NodeDraw.from_setup(image_enum, node_type, model)
            cls.NODES.append(node_draw)
            cls.NODE_ICONS[(node_type, model)] = node_draw.image

        network_nodes = [
            (ImageEnum.HUB, NodeType.HUB, "ethernet hub"),
            (ImageEnum.SWITCH, NodeType.SWITCH, "ethernet switch"),
            (ImageEnum.WLAN, NodeType.WIRELESS_LAN, "wireless LAN"),
            (ImageEnum.EMANE, NodeType.EMANE, "EMANE"),
            (ImageEnum.RJ45, NodeType.RJ45, "rj45 physical interface tool"),
            (ImageEnum.TUNNEL, NodeType.TUNNEL, "tunnel tool"),
        ]
        for image_enum, node_type, tooltip in network_nodes:
            node_draw = NodeDraw.from_setup(image_enum, node_type, tooltip=tooltip)
            cls.NETWORK_NODES.append(node_draw)
            cls.NODE_ICONS[(node_type, None)] = node_draw.image
