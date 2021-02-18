from enum import Enum
from tkinter import messagebox
from typing import Dict, Optional, Tuple

from PIL import Image
from PIL.ImageTk import PhotoImage

from core.api.grpc.wrappers import NodeType
from core.gui.appconfig import LOCAL_ICONS_PATH

ICON_SIZE: int = 48


class Images:
    images: Dict[str, str] = {}

    @classmethod
    def create(
        cls, file_path: str, width: int = None, height: int = None
    ) -> PhotoImage:
        if width is None:
            width = ICON_SIZE
        if height is None:
            height = width
        image = Image.open(file_path)
        image = image.resize((width, height), Image.ANTIALIAS)
        return PhotoImage(image)

    @classmethod
    def load_all(cls) -> None:
        for image in LOCAL_ICONS_PATH.glob("*"):
            cls.images[image.stem] = str(image)

    @classmethod
    def get(cls, image_enum: Enum, width: int, height: int = None) -> PhotoImage:
        file_path = cls.images[image_enum.value]
        return cls.create(file_path, width, height)

    @classmethod
    def get_with_image_file(
        cls, stem: str, width: int, height: int = None
    ) -> PhotoImage:
        file_path = cls.images[stem]
        return cls.create(file_path, width, height)

    @classmethod
    def get_custom(cls, name: str, width: int, height: int = None) -> PhotoImage:
        try:
            file_path = cls.images[name]
            return cls.create(file_path, width, height)
        except KeyError:
            messagebox.showwarning(
                "Missing image file",
                f"{name}.png is missing at daemon/core/gui/data/icons, drop image "
                f"file at daemon/core/gui/data/icons and restart the gui",
            )


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
    LXC = "lxc"
    ALERT = "alert"
    DELETE = "delete"
    SHUTDOWN = "shutdown"
    CANCEL = "cancel"
    ERROR = "error"
    SHADOW = "shadow"


class TypeToImage:
    type_to_image: Dict[Tuple[NodeType, str], ImageEnum] = {
        (NodeType.DEFAULT, "router"): ImageEnum.ROUTER,
        (NodeType.DEFAULT, "PC"): ImageEnum.PC,
        (NodeType.DEFAULT, "host"): ImageEnum.HOST,
        (NodeType.DEFAULT, "mdr"): ImageEnum.MDR,
        (NodeType.DEFAULT, "prouter"): ImageEnum.PROUTER,
        (NodeType.HUB, ""): ImageEnum.HUB,
        (NodeType.SWITCH, ""): ImageEnum.SWITCH,
        (NodeType.WIRELESS_LAN, ""): ImageEnum.WLAN,
        (NodeType.EMANE, ""): ImageEnum.EMANE,
        (NodeType.RJ45, ""): ImageEnum.RJ45,
        (NodeType.TUNNEL, ""): ImageEnum.TUNNEL,
        (NodeType.DOCKER, ""): ImageEnum.DOCKER,
        (NodeType.LXC, ""): ImageEnum.LXC,
    }

    @classmethod
    def get(cls, node_type, model) -> Optional[ImageEnum]:
        return cls.type_to_image.get((node_type, model))
