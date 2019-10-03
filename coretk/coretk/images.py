import logging
import os

from PIL import Image, ImageTk

from core.api.grpc import core_pb2

PATH = os.path.abspath(os.path.dirname(__file__))


class Images:
    images = {}

    @classmethod
    def load(cls, name, file_path):
        file_path = os.path.join(PATH, file_path)
        image = Image.open(file_path)
        tk_image = ImageTk.PhotoImage(image)
        cls.images[name] = tk_image

    @classmethod
    def get(cls, name):
        return cls.images[name]

    @classmethod
    def convert_type_and_model_to_image(cls, node_type, node_model):
        """
                Retrieve image based on type and model
                :param core_pb2.NodeType node_type: core node type
                :param string node_model: the node model

                :return: the matching image
                """
        if node_type == core_pb2.NodeType.SWITCH:
            return Images.get("switch")
        if node_type == core_pb2.NodeType.HUB:
            return Images.get("hub")
        if node_type == core_pb2.NodeType.WIRELESS_LAN:
            return Images.get("wlan")
        if node_type == core_pb2.NodeType.RJ45:
            return Images.get("rj45")
        if node_type == core_pb2.NodeType.TUNNEL:
            return Images.get("tunnel")
        if node_type == core_pb2.NodeType.DEFAULT:
            if node_model == "router":
                return Images.get("router")
            if node_model == "host":
                return Images.get(("host"))
            if node_model == "PC":
                return Images.get("pc")
            if node_model == "mdr":
                return Images.get("mdr")
            if node_model == "prouter":
                return Images.get("prouter")
            if node_model == "OVS":
                return Images.get("ovs")
        else:
            logging.debug("INVALID INPUT OR NOT CONSIDERED YET")


def load_core_images(images):
    images.load("core", "core-icon.png")
    images.load("start", "start.gif")
    images.load("switch", "lanswitch.gif")
    images.load("marker", "marker.gif")
    images.load("router", "router.gif")
    images.load("select", "select.gif")
    images.load("link", "link.gif")
    images.load("hub", "hub.gif")
    images.load("wlan", "wlan.gif")
    images.load("rj45", "rj45.gif")
    images.load("tunnel", "tunnel.gif")
    images.load("oval", "oval.gif")
    images.load("rectangle", "rectangle.gif")
    images.load("text", "text.gif")
    images.load("host", "host.gif")
    images.load("pc", "pc.gif")
    images.load("mdr", "mdr.gif")
    images.load("prouter", "router_green.gif")
    images.load("ovs", "OVS.gif")
    images.load("editnode", "document-properties.gif")
    images.load("run", "run.gif")
    images.load("plot", "plot.gif")
    images.load("twonode", "twonode.gif")
    images.load("stop", "stop.gif")
    images.load("observe", "observe.gif")
