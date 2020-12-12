import logging
import tkinter as tk
from tkinter import BooleanVar, ttk
from typing import TYPE_CHECKING, Dict, Optional, Set, Tuple

from core.api.grpc.wrappers import Session
from core.gui.graph import tags
from core.gui.graph.enums import GraphMode
from core.gui.graph.graph import CanvasGraph
from core.gui.graph.shapeutils import ShapeType
from core.gui.nodeutils import NodeDraw

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.coreclient import CoreClient


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
        self.node_draw: Optional[NodeDraw] = None
        self.canvases: Dict[int, CanvasGraph] = {}

        # canvas object storage
        # TODO: validate this
        self.wireless_network: Dict[int, Set[int]] = {}

        # global canvas settings
        self.default_dimensions: Tuple[int, int] = (
            self.app.guiconfig.preferences.width,
            self.app.guiconfig.preferences.height,
        )
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

        # widget
        self.notebook: Optional[ttk.Notebook] = None
        self.draw()

    def draw(self) -> None:
        self.notebook = ttk.Notebook(self.master)
        self.notebook.grid(sticky=tk.NSEW)

    def join(self, session: Session) -> None:
        # clear out all canvas
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        self.canvases.clear()

        # reset settings
        self.show_node_labels.set(True)
        self.show_link_labels.set(True)
        self.show_grid.set(True)
        self.show_annotations.set(True)
        self.show_iface_names.set(False)
        self.show_ip4s.set(True)
        self.show_ip6s.set(True)
        self.show_loss_links.set(True)
        self.mode = GraphMode.SELECT
        self.annotation_type = None
        self.node_draw = None

        # draw initial tab(s) and session
        tab = ttk.Frame(self.notebook, padding=0)
        tab.grid(sticky=tk.NSEW)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        tab_id = len(self.notebook.tabs())
        self.notebook.add(tab, text=f"Canvas {tab_id}")
        logging.info("canvas tab id: %s", tab_id)
        canvas = CanvasGraph(tab, self.app, self, self.core, tab_id)
        canvas.grid(sticky=tk.NSEW)
        self.canvases[tab_id] = canvas

        canvas.reset_and_redraw(session)
        self.core.parse_metadata(canvas)
        canvas.organize()
