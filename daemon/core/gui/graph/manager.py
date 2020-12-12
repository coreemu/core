import logging
import tkinter as tk
from tkinter import BooleanVar, messagebox, ttk
from typing import TYPE_CHECKING, Dict, Optional, Set, Tuple, ValuesView

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
        self.unique_ids: Dict[str, int] = {}
        self.draw()

    def draw(self) -> None:
        self.notebook = ttk.Notebook(self.master)
        self.notebook.grid(sticky=tk.NSEW, pady=1)

    def _next_id(self) -> int:
        _id = 1
        tab_ids = set(self.unique_ids.values())
        while _id in tab_ids:
            _id += 1
        return _id

    def current(self) -> CanvasGraph:
        unique_id = self.notebook.select()
        tab_id = self.unique_ids[unique_id]
        return self.canvases[tab_id]

    def all(self) -> ValuesView[CanvasGraph]:
        return self.canvases.values()

    def add_canvas(self) -> CanvasGraph:
        # create tab frame
        tab = ttk.Frame(self.notebook, padding=0)
        tab.grid(sticky=tk.NSEW)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        tab_id = self._next_id()
        self.notebook.add(tab, text=f"Canvas {tab_id}")
        unique_id = self.notebook.tabs()[-1]
        logging.info("tab(%s) is %s", unique_id, tab_id)
        self.unique_ids[unique_id] = tab_id

        # create canvas
        canvas = CanvasGraph(tab, self.app, self, self.core, tab_id)
        canvas.grid(sticky=tk.NSEW)
        self.canvases[tab_id] = canvas

        # add scrollbars
        scroll_y = ttk.Scrollbar(tab, command=canvas.yview)
        scroll_y.grid(row=0, column=1, sticky=tk.NS)
        scroll_x = ttk.Scrollbar(tab, orient=tk.HORIZONTAL, command=canvas.xview)
        scroll_x.grid(row=1, column=0, sticky=tk.EW)
        canvas.configure(xscrollcommand=scroll_x.set)
        canvas.configure(yscrollcommand=scroll_y.set)
        return canvas

    def delete_canvas(self) -> None:
        if len(self.notebook.tabs()) == 1:
            messagebox.showinfo("Canvas", "Cannot delete last canvas", parent=self.app)
            return
        unique_id = self.notebook.select()
        self.notebook.forget(unique_id)
        tab_id = self.unique_ids.pop(unique_id)
        self.canvases.pop(tab_id)
        # TODO: handle clearing out canvas related nodes and links

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

        # TODO: create and add nodes to all associated canvases
        # draw initial tab(s) and session
        canvas = self.add_canvas()

        # draw session on canvas
        canvas.reset_and_redraw(session)
        self.core.parse_metadata(canvas)
        canvas.organize()
