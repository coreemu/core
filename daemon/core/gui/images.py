from enum import Enum
from typing import Optional

from PIL import Image
from PIL.ImageTk import PhotoImage

from core.api.grpc.wrappers import Node, NodeType
from core.gui.appconfig import LOCAL_ICONS_PATH

NODE_SIZE: int = 48
ANTENNA_SIZE: int = 32
BUTTON_SIZE: int = 16
ERROR_SIZE: int = 24
DIALOG_SIZE: int = 16
IMAGES: dict[str, str] = {}


def load_all() -> None:
    for image in LOCAL_ICONS_PATH.glob("*"):
        try:
            ImageEnum(image.stem)
            IMAGES[image.stem] = str(image)
        except ValueError:
            pass


def from_file(
    file_path: str, *, width: int, height: int = None, scale: float = 1.0
) -> PhotoImage:
    if height is None:
        height = width
    width = int(width * scale)
    height = int(height * scale)
    image = Image.open(file_path)
    image = image.resize((width, height), Image.ANTIALIAS)
    return PhotoImage(image)


def from_enum(
    image_enum: "ImageEnum", *, width: int, height: int = None, scale: float = 1.0
) -> PhotoImage:
    file_path = IMAGES[image_enum.value]
    return from_file(file_path, width=width, height=height, scale=scale)


class ImageEnum(Enum):
    SWITCH = "lanswitch"
    CORE = "core-icon"
    START = "start"
    MARKER = "marker"
    ROUTER = "router"
    SELECT = "select"
    LINK = "link"
    HUB = "hub"
    WLAN = "wlan"
    WIRELESS = "wireless"
    EMANE = "emane"
    RJ45 = "rj45"
    TUNNEL = "tunnel"
    OVAL = "oval"
    RECTANGLE = "rectangle"
    TEXT = "text"
    HOST = "host"
    PC = "pc"
    MDR = "mdr"
    PROUTER = "prouter"
    OVS = "OVS"
    EDITNODE = "edit-node"
    PLOT = "plot"
    TWONODE = "twonode"
    PAUSE = "pause"
    STOP = "stop"
    OBSERVE = "observe"
    RUN = "run"
    DOCUMENTNEW = "document-new"
    DOCUMENTSAVE = "document-save"
    FILEOPEN = "fileopen"
    EDITDELETE = "edit-delete"
    ANTENNA = "antenna"
    DOCKER = "docker"
    PODMAN = "podman"
    LXC = "lxc"
    ALERT = "alert"
    DELETE = "delete"
    SHUTDOWN = "shutdown"
    CANCEL = "cancel"
    ERROR = "error"
    SHADOW = "shadow"


TYPE_MAP: dict[tuple[NodeType, str], ImageEnum] = {
    (NodeType.DEFAULT, "router"): ImageEnum.ROUTER,
    (NodeType.DEFAULT, "PC"): ImageEnum.PC,
    (NodeType.DEFAULT, "host"): ImageEnum.HOST,
    (NodeType.DEFAULT, "mdr"): ImageEnum.MDR,
    (NodeType.DEFAULT, "prouter"): ImageEnum.PROUTER,
    (NodeType.HUB, None): ImageEnum.HUB,
    (NodeType.SWITCH, None): ImageEnum.SWITCH,
    (NodeType.WIRELESS_LAN, None): ImageEnum.WLAN,
    (NodeType.WIRELESS, None): ImageEnum.WIRELESS,
    (NodeType.EMANE, None): ImageEnum.EMANE,
    (NodeType.RJ45, None): ImageEnum.RJ45,
    (NodeType.TUNNEL, None): ImageEnum.TUNNEL,
    (NodeType.DOCKER, None): ImageEnum.DOCKER,
    (NodeType.PODMAN, None): ImageEnum.PODMAN,
    (NodeType.LXC, None): ImageEnum.LXC,
}


def from_node(node: Node, *, scale: float) -> Optional[PhotoImage]:
    image = None
    image_enum = TYPE_MAP.get((node.type, node.model))
    if image_enum:
        image = from_enum(image_enum, width=NODE_SIZE, scale=scale)
    return image
