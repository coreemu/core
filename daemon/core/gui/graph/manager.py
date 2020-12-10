import tkinter as tk
from tkinter import BooleanVar
from typing import Dict, Optional, Set, Tuple

from core.gui.app import Application
from core.gui.coreclient import CoreClient
from core.gui.graph import tags
from core.gui.graph.edges import CanvasEdge
from core.gui.graph.enums import GraphMode
from core.gui.graph.graph import CanvasGraph
from core.gui.graph.node import CanvasNode
from core.gui.graph.shape import Shape
from core.gui.graph.shapeutils import ShapeType


class ShowVar(BooleanVar):
    def __init__(self, manager: "CanvasManager", tag: str, value: bool) -> None:
        super().__init__(value=value)
        self.manager: "CanvasManager" = manager
        self.tag: str = tag

    def state(self) -> str:
        return tk.NORMAL if self.get() else tk.HIDDEN

    def click_handler(self) -> None:
        for canvas in self.manager.canvases.values():
            canvas.itemconfigure(self.tag, state=self.state())


class CanvasManager:
    def __init__(
        self, master: tk.BaseWidget, app: "Application", core: "CoreClient"
    ) -> None:
        self.master: tk.BaseWidget = master
        self.app: "Application" = app
        self.core: "CoreClient" = core

        # canvas interactions
        self.mode: GraphMode = GraphMode.SELECT
        self.annotation_type: Optional[ShapeType] = None
        self.canvases: Dict[int, CanvasGraph] = {}

        # canvas object storage
        self.nodes: Dict[int, CanvasNode] = {}
        self.edges: Dict[str, CanvasEdge] = {}
        self.shapes: Dict[int, Shape] = {}
        self.wireless_network: Dict[int, Set[int]] = {}

        # global canvas settings
        width = self.app.guiconfig.preferences.width
        height = self.app.guiconfig.preferences.height
        self.default_dimensions: Tuple[int, int] = (width, height)
        self.show_node_labels: ShowVar = ShowVar(self, tags.NODE_LABEL, value=True)
        self.show_link_labels: ShowVar = ShowVar(self, tags.LINK_LABEL, value=True)
        self.show_links: ShowVar = ShowVar(self, tags.EDGE, value=True)
        self.show_wireless: ShowVar = ShowVar(self, tags.WIRELESS_EDGE, value=True)
        self.show_grid: ShowVar = ShowVar(self, tags.GRIDLINE, value=True)
        self.show_annotations: ShowVar = ShowVar(self, tags.ANNOTATION, value=True)
        self.show_loss_links: ShowVar = ShowVar(self, tags.LOSS_EDGES, value=True)
        self.show_iface_names: BooleanVar = BooleanVar(value=False)
        self.show_ip4s: BooleanVar = BooleanVar(value=True)
        self.show_ip6s: BooleanVar = BooleanVar(value=True)

        # throughput settings
        self.throughput_threshold: float = 250.0
        self.throughput_width: int = 10
        self.throughput_color: str = "#FF0000"
