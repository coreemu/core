from enum import Enum
from tkinter import messagebox

from PIL import Image, ImageTk

from core.api.grpc import core_pb2
from core.gui.appconfig import LOCAL_ICONS_PATH


class Images:
    images = {}

    @classmethod
    def create(cls, file_path: str, width: int, height: int = None):
        if height is None:
            height = width
        image = Image.open(file_path)
        image = image.resize((width, height), Image.ANTIALIAS)
        return ImageTk.PhotoImage(image)

    @classmethod
    def load_all(cls):
        for image in LOCAL_ICONS_PATH.glob("*"):
            cls.images[image.stem] = str(image)

    @classmethod
    def get(
        cls, image_enum: Enum, width: int, height: int = None
    ) -> ImageTk.PhotoImage:
        file_path = cls.images[image_enum.value]
        return cls.create(file_path, width, height)

    @classmethod
    def get_with_image_file(
        cls, stem: str, width: int, height: int = None
    ) -> ImageTk.PhotoImage:
        file_path = cls.images[stem]
        return cls.create(file_path, width, height)

    @classmethod
    def get_custom(
        cls, name: str, width: int, height: int = None
    ) -> ImageTk.PhotoImage:
        try:
            file_path = cls.images[name]
            return cls.create(file_path, width, height)
        except KeyError:
            messagebox.showwarning(
                "Missing image file",
                f"{name}.png is missing at daemon/core/gui/data/icons, drop image file at daemon/core/gui/data/icons and restart the gui",
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


class TypeToImage:
    type_to_image = {
        (core_pb2.NodeType.DEFAULT, "router"): ImageEnum.ROUTER,
        (core_pb2.NodeType.DEFAULT, "PC"): ImageEnum.PC,
        (core_pb2.NodeType.DEFAULT, "host"): ImageEnum.HOST,
        (core_pb2.NodeType.DEFAULT, "mdr"): ImageEnum.MDR,
        (core_pb2.NodeType.DEFAULT, "prouter"): ImageEnum.PROUTER,
        (core_pb2.NodeType.HUB, ""): ImageEnum.HUB,
        (core_pb2.NodeType.SWITCH, ""): ImageEnum.SWITCH,
        (core_pb2.NodeType.WIRELESS_LAN, ""): ImageEnum.WLAN,
        (core_pb2.NodeType.EMANE, ""): ImageEnum.EMANE,
        (core_pb2.NodeType.RJ45, ""): ImageEnum.RJ45,
        (core_pb2.NodeType.TUNNEL, ""): ImageEnum.TUNNEL,
        (core_pb2.NodeType.DOCKER, ""): ImageEnum.DOCKER,
        (core_pb2.NodeType.LXC, ""): ImageEnum.LXC,
    }

    @classmethod
    def get(cls, node_type, model):
        return cls.type_to_image.get((node_type, model), None)
