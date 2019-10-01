import os

from PIL import Image, ImageTk

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
