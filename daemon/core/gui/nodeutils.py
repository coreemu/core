from core.api.grpc.core_pb2 import NodeType
from core.gui.images import ImageEnum, Images

ICON_SIZE = 48
ANTENNA_SIZE = 32


class NodeDraw:
    def __init__(self):
        self.custom = False
        self.image = None
        self.image_enum = None
        self.image_file = None
        self.node_type = None
        self.model = None
        self.services = set()

    @classmethod
    def from_setup(cls, image_enum, node_type, label, model=None, tooltip=None):
        node_draw = NodeDraw()
        node_draw.image_enum = image_enum
        node_draw.image = Images.get(image_enum, ICON_SIZE)
        node_draw.node_type = node_type
        node_draw.label = label
        node_draw.model = model
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
    IGNORE_NODES = {NodeType.CONTROL_NET, NodeType.PEER_TO_PEER}
    NODE_MODELS = {"router", "host", "PC", "mdr", "prouter"}
    ANTENNA_ICON = None

    @classmethod
    def is_ignore_node(cls, node_type):
        return node_type in cls.IGNORE_NODES

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
