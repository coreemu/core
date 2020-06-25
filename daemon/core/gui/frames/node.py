from typing import TYPE_CHECKING

from core.api.grpc.core_pb2 import NodeType
from core.gui.frames.base import DetailsFrame, InfoFrameBase
from core.gui.nodeutils import NodeUtils

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
        frame.grid(sticky="ew")
        frame.add_detail("ID", node.id)
        frame.add_detail("Name", node.name)
        if NodeUtils.is_model_node(node.type):
            frame.add_detail("Type", node.model)
        if node.type == NodeType.EMANE:
            emane = node.emane.split("_")[1:]
            frame.add_detail("EMANE", emane)
        if NodeUtils.is_image_node(node.type):
            frame.add_detail("Image", node.image)
        if NodeUtils.is_container_node(node.type):
            server = node.server if node.server else "localhost"
            frame.add_detail("Server", server)
