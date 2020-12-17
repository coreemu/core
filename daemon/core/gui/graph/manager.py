import logging
import tkinter as tk
from tkinter import BooleanVar, messagebox, ttk
from typing import TYPE_CHECKING, Any, Dict, Optional, Set, Tuple, ValuesView

from core.api.grpc.wrappers import LinkType, Session, ThroughputsEvent
from core.gui.graph import tags
from core.gui.graph.enums import GraphMode
from core.gui.graph.graph import CanvasGraph
from core.gui.graph.shapeutils import ShapeType
from core.gui.nodeutils import NodeDraw, NodeUtils

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
        for canvas in self.manager.all():
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
        self.current_dimensions: Tuple[int, int] = self.default_dimensions
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

        self.setup_bindings()
        # start with a single tab by default
        self.add_canvas()

    def setup_bindings(self) -> None:
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_change)

    def tab_change(self, _event: tk.Event) -> None:
        canvas = self.current()
        self.app.statusbar.set_zoom(canvas.ratio)

    def draw(self) -> None:
        self.notebook = ttk.Notebook(self.master)
        self.notebook.grid(sticky=tk.NSEW, pady=1)

    def _next_id(self) -> int:
        _id = 1
        canvas_ids = set(self.unique_ids.values())
        while _id in canvas_ids:
            _id += 1
        return _id

    def current(self) -> CanvasGraph:
        unique_id = self.notebook.select()
        canvas_id = self.unique_ids[unique_id]
        return self.canvases[canvas_id]

    def all(self) -> ValuesView[CanvasGraph]:
        return self.canvases.values()

    def get(self, canvas_id: int) -> CanvasGraph:
        canvas = self.canvases.get(canvas_id)
        if not canvas:
            canvas = self.add_canvas(canvas_id)
        return canvas

    def add_canvas(self, canvas_id: int = None) -> CanvasGraph:
        # create tab frame
        tab = ttk.Frame(self.notebook, padding=0)
        tab.grid(sticky=tk.NSEW)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        if canvas_id is None:
            canvas_id = self._next_id()
        self.notebook.add(tab, text=f"Canvas {canvas_id}")
        unique_id = self.notebook.tabs()[-1]
        self.unique_ids[unique_id] = canvas_id

        # create canvas
        canvas = CanvasGraph(
            tab, self.app, self, self.core, canvas_id, self.default_dimensions
        )
        canvas.grid(sticky=tk.NSEW)
        self.canvases[canvas_id] = canvas

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
        canvas_id = self.unique_ids.pop(unique_id)
        self.canvases.pop(canvas_id)
        # TODO: handle clearing out canvas related nodes and links from core client

    def join(self, session: Session) -> None:
        # clear out all canvas
        for canvas_id in self.notebook.tabs():
            self.notebook.forget(canvas_id)
        self.canvases.clear()
        self.unique_ids.clear()

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

        # draw session
        self.draw_session(session)

    def draw_session(self, session: Session) -> None:
        # create session nodes
        for core_node in session.nodes.values():
            # get tab id for node
            canvas_id = core_node.canvas if core_node.canvas > 0 else 1
            canvas = self.get(canvas_id)
            # add node, avoiding ignored nodes
            if NodeUtils.is_ignore_node(core_node.type):
                continue
            logging.debug("drawing node: %s", core_node)
            canvas.add_core_node(core_node)

        # draw existing links
        for link in session.links:
            logging.debug("drawing link: %s", link)
            node1 = self.core.get_canvas_node(link.node1_id)
            node2 = self.core.get_canvas_node(link.node2_id)
            # TODO: handle edges for nodes on different canvases
            if node1.canvas == node2.canvas:
                canvas = node1.canvas
                if link.type == LinkType.WIRELESS:
                    canvas.add_wireless_edge(node1, node2, link)
                else:
                    canvas.add_wired_edge(node1, node2, link)
            else:
                logging.error("cant handle nodes linked between canvases")

        # parse metadata and organize canvases
        self.core.parse_metadata()
        for canvas in self.canvases.values():
            canvas.organize()

        # create a default canvas if none were created prior
        if not self.canvases:
            self.add_canvas()

    def redraw_canvases(self, dimensions: Tuple[int, int]) -> None:
        for canvas in self.canvases.values():
            canvas.redraw_canvas(dimensions)
            if canvas.wallpaper:
                canvas.redraw_wallpaper()

    def get_metadata(self) -> Dict[str, Any]:
        canvases = [x.get_metadata() for x in self.all()]
        return dict(
            gridlines=self.app.manager.show_grid.get(),
            dimensions=self.app.manager.current_dimensions,
            canvases=canvases,
        )

    def parse_metadata(self, config: Dict[str, Any]) -> None:
        # get configured dimensions and gridlines option
        dimensions = self.default_dimensions
        dimensions = config.get("dimensions", dimensions)
        gridlines = config.get("gridlines", True)
        self.show_grid.set(gridlines)
        self.redraw_canvases(dimensions)

        # get background configurations
        for canvas_config in config.get("canvases", []):
            canvas_id = canvas_config.get("id")
            if canvas_id is None:
                logging.error("canvas config id not provided")
                continue
            canvas = self.get(canvas_id)
            canvas.parse_metadata(canvas_config)

    def set_throughputs(self, throughputs_event: ThroughputsEvent):
        for iface_throughput in throughputs_event.iface_throughputs:
            node_id = iface_throughput.node_id
            iface_id = iface_throughput.iface_id
            throughput = iface_throughput.throughput
            iface_to_edge_id = (node_id, iface_id)
            edge = self.core.iface_to_edge.get(iface_to_edge_id)
            if edge:
                edge.set_throughput(throughput)

    def clear_throughputs(self) -> None:
        for canvas in self.all():
            for edge in canvas.edges.values():
                edge.clear_throughput()
