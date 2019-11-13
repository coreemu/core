import logging
from enum import Enum

from PIL import Image, ImageTk

from core.api.grpc import core_pb2
from coretk.appconfig import LOCAL_ICONS_PATH

NODE_WIDTH = 32


class Images:
    images = {}

    @classmethod
    def create(cls, file_path, width, height=None):
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
    def get(cls, image_enum, width, height=None):
        file_path = cls.images[image_enum.value]
        return cls.create(file_path, width, height)

    @classmethod
    def get_custom(cls, name, width, height):
        file_path = cls.images[name]
        return cls.create(file_path, width, height)

    @classmethod
    def node_icon(cls, node_type, node_model):
        """
        Retrieve image based on type and model
        :param core_pb2.NodeType node_type: core node type
        :param string node_model: the node model

        :rtype: tuple(PhotoImage, str)
        :return: the matching image and its name
        """
        image_enum = ImageEnum.ROUTER
        name = "unknown"
        if node_type == core_pb2.NodeType.SWITCH:
            image_enum = ImageEnum.SWITCH
            name = "switch"
        elif node_type == core_pb2.NodeType.HUB:
            image_enum = ImageEnum.HUB
            name = "hub"
        elif node_type == core_pb2.NodeType.WIRELESS_LAN:
            image_enum = ImageEnum.WLAN
            name = "wlan"
        elif node_type == core_pb2.NodeType.EMANE:
            image_enum = ImageEnum.EMANE
            name = "emane"
        elif node_type == core_pb2.NodeType.RJ45:
            image_enum = ImageEnum.RJ45
            name = "rj45"
        elif node_type == core_pb2.NodeType.TUNNEL:
            image_enum = ImageEnum.TUNNEL
            name = "tunnel"
        elif node_type == core_pb2.NodeType.DEFAULT:
            if node_model == "router":
                image_enum = ImageEnum.ROUTER
                name = "router"
            elif node_model == "host":
                image_enum = ImageEnum.HOST
                name = "host"
            elif node_model == "PC":
                image_enum = ImageEnum.PC
                name = "PC"
            elif node_model == "mdr":
                image_enum = ImageEnum.MDR
                name = "mdr"
            elif node_model == "prouter":
                image_enum = ImageEnum.PROUTER
                name = "prouter"
            else:
                logging.error("invalid node model: %s", node_model)
        else:
            logging.error("invalid node type: %s", node_type)

        return Images.get(image_enum, NODE_WIDTH), name


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
    PROUTER = "router_green"
    OVS = "OVS"
    EDITNODE = "document-properties"
    PLOT = "plot"
    TWONODE = "twonode"
    STOP = "stop"
    OBSERVE = "observe"
    RUN = "run"
    DOCUMENTNEW = "document-new"
    FILEOPEN = "fileopen"
    EDITDELETE = "edit-delete"
    ANTENNA = "antenna"
