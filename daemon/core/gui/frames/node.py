import tkinter as tk
from typing import TYPE_CHECKING

from core.api.grpc.wrappers import NodeType
from core.gui import nodeutils as nutils
from core.gui.frames.base import DetailsFrame, InfoFrameBase

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode


class NodeInfoFrame(InfoFrameBase):
    def __init__(self, master, app: "Application", canvas_node: "CanvasNode") -> None:
        super().__init__(master, app)
        self.canvas_node: "CanvasNode" = canvas_node

    def draw(self) -> None:
        self.columnconfigure(0, weight=1)
        node = self.canvas_node.core_node
        frame = DetailsFrame(self)
        frame.grid(sticky=tk.EW)
        frame.add_detail("ID", str(node.id))
        frame.add_detail("Name", node.name)
        if nutils.is_model(node):
            frame.add_detail("Type", node.model)
        if nutils.is_container(node):
            for index, service in enumerate(sorted(node.services)):
                if index == 0:
                    frame.add_detail("Services", service)
                else:
                    frame.add_detail("", service)
        if node.type == NodeType.EMANE:
            emane = "".join(node.emane.split("_")[1:])
            frame.add_detail("EMANE", emane)
        if nutils.has_image(node.type):
            frame.add_detail("Image", node.image)
        if nutils.is_container(node):
            server = node.server if node.server else "localhost"
            frame.add_detail("Server", server)
