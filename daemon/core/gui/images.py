from enum import Enum
from tkinter import messagebox

from PIL import Image, ImageTk

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
