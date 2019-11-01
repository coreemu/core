import logging
import os
from enum import Enum

from PIL import Image, ImageTk

from core.api.grpc import core_pb2

PATH = os.path.abspath(os.path.dirname(__file__))
ICONS_DIR = os.path.join(PATH, "icons")


class Images:
    images = {}

    @classmethod
    def load_all(cls):
        for file_name in os.listdir(ICONS_DIR):
            file_path = os.path.join(ICONS_DIR, file_name)
            name = file_name.split(".")[0]
            cls.load(name, file_path)

    @classmethod
    def load(cls, name, file_path):
        # file_path = os.path.join(PATH, file_path)
        image = Image.open(file_path)
        tk_image = ImageTk.PhotoImage(image)
        cls.images[name] = tk_image

    @classmethod
    def get(cls, image):
        return cls.images[image.value]

    @classmethod
    def convert_type_and_model_to_image(cls, node_type, node_model):
        """
        Retrieve image based on type and model
        :param core_pb2.NodeType node_type: core node type
        :param string node_model: the node model

        :rtype: tuple(PhotoImage, str)
        :return: the matching image and its name
        """
        if node_type == core_pb2.NodeType.SWITCH:
            return Images.get(ImageEnum.SWITCH), "switch"
        if node_type == core_pb2.NodeType.HUB:
            return Images.get(ImageEnum.HUB), "hub"
        if node_type == core_pb2.NodeType.WIRELESS_LAN:
            return Images.get(ImageEnum.WLAN), "wlan"
        if node_type == core_pb2.NodeType.EMANE:
            return Images.get(ImageEnum.EMANE), "emane"

        if node_type == core_pb2.NodeType.RJ45:
            return Images.get(ImageEnum.RJ45), "rj45"
        if node_type == core_pb2.NodeType.TUNNEL:
            return Images.get(ImageEnum.TUNNEL), "tunnel"
        if node_type == core_pb2.NodeType.DEFAULT:
            if node_model == "router":
                return Images.get(ImageEnum.ROUTER), "router"
            if node_model == "host":
                return Images.get(ImageEnum.HOST), "host"
            if node_model == "PC":
                return Images.get(ImageEnum.PC), "PC"
            if node_model == "mdr":
                return Images.get(ImageEnum.MDR), "mdr"
            if node_model == "prouter":
                return Images.get(ImageEnum.PROUTER), "prouter"
            if node_model == "OVS":
                return Images.get(ImageEnum.OVS), "ovs"
        else:
            logging.debug("INVALID INPUT OR NOT CONSIDERED YET")


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
