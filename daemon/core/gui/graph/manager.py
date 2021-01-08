import logging
import tkinter as tk
from copy import deepcopy
from tkinter import BooleanVar, messagebox, ttk
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, ValuesView

from core.api.grpc.wrappers import Link, LinkType, Node, Session, ThroughputsEvent
from core.gui.graph import tags
from core.gui.graph.edges import (
    CanvasEdge,
    CanvasWirelessEdge,
    create_edge_token,
    create_wireless_token,
)
from core.gui.graph.enums import GraphMode
from core.gui.graph.graph import CanvasGraph
from core.gui.graph.node import CanvasNode
from core.gui.graph.shapeutils import ShapeType
from core.gui.images import ImageEnum
from core.gui.nodeutils import ICON_SIZE, NodeDraw, NodeUtils

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

        # global edge management
        self.edges: Dict[str, CanvasEdge] = {}
        self.wireless_edges: Dict[str, CanvasWirelessEdge] = {}

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
        self.canvas_ids: Dict[str, int] = {}
        self.unique_ids: Dict[int, str] = {}
        self.draw()

        self.setup_bindings()
        # start with a single tab by default
        self.add_canvas()

    def setup_bindings(self) -> None:
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_change)

    def tab_change(self, _event: tk.Event) -> None:
        # ignore tab change events before tab data has been setup
        unique_id = self.notebook.select()
        if not unique_id or unique_id not in self.canvas_ids:
            return
        canvas = self.current()
        self.app.statusbar.set_zoom(canvas.ratio)

    def select(self, tab_id: int):
        unique_id = self.unique_ids.get(tab_id)
        self.notebook.select(unique_id)

    def draw(self) -> None:
        self.notebook = ttk.Notebook(self.master)
        self.notebook.grid(sticky=tk.NSEW, pady=1)

    def _next_id(self) -> int:
        _id = 1
        canvas_ids = set(self.canvas_ids.values())
        while _id in canvas_ids:
            _id += 1
        return _id

    def current(self) -> CanvasGraph:
        unique_id = self.notebook.select()
        canvas_id = self.canvas_ids[unique_id]
        return self.get(canvas_id)

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
        logging.info("creating canvas(%s) unique(%s)", canvas_id, unique_id)
        self.canvas_ids[unique_id] = canvas_id
        self.unique_ids[canvas_id] = unique_id

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
        canvas_id = self.canvas_ids.pop(unique_id)
        canvas = self.canvases.pop(canvas_id)
        edges = set()
        for node in canvas.nodes.values():
            node.delete()
            while node.edges:
                edge = node.edges.pop()
                if edge in edges:
                    continue
                edges.add(edge)
                edge.delete()

    def join(self, session: Session) -> None:
        # clear out all canvas
        for canvas_id in self.notebook.tabs():
            self.notebook.forget(canvas_id)
        self.canvases.clear()
        self.canvas_ids.clear()
        self.unique_ids.clear()
        self.edges.clear()
        self.wireless_edges.clear()
        logging.info("cleared canvases")

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
            # add node, avoiding ignored nodes
            if NodeUtils.is_ignore_node(core_node.type):
                continue
            self.add_core_node(core_node)

        # draw existing links
        for link in session.links:
            node1 = self.core.get_canvas_node(link.node1_id)
            node2 = self.core.get_canvas_node(link.node2_id)
            if link.type == LinkType.WIRELESS:
                self.add_wireless_edge(node1, node2, link)
            else:
                self.add_wired_edge(node1, node2, link)

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

    def add_core_node(self, core_node: Node) -> None:
        # get canvas tab for node
        canvas_id = core_node.canvas if core_node.canvas > 0 else 1
        logging.info("adding core node canvas(%s): %s", core_node.name, canvas_id)
        canvas = self.get(canvas_id)
        # if the gui can't find node's image, default to the "edit-node" image
        image = NodeUtils.node_image(core_node, self.app.guiconfig, self.app.app_scale)
        if not image:
            image = self.app.get_icon(ImageEnum.EDITNODE, ICON_SIZE)
        x = core_node.position.x
        y = core_node.position.y
        node = CanvasNode(self.app, canvas, x, y, core_node, image)
        canvas.nodes[node.id] = node
        self.core.set_canvas_node(core_node, node)

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
        for edge in self.edges.values():
            edge.clear_throughput()

    def stopped_session(self) -> None:
        # clear wireless edges
        for edge in self.wireless_edges.values():
            edge.delete()
        self.wireless_edges.clear()
        self.clear_throughputs()

    def update_wired_edge(self, link: Link) -> None:
        token = create_edge_token(link)
        edge = self.edges.get(token)
        if edge:
            edge.link.options = deepcopy(link.options)
            edge.draw_link_options()
            edge.check_options()

    def delete_wired_edge(self, link: Link) -> None:
        token = create_edge_token(link)
        edge = self.edges.get(token)
        if edge:
            edge.delete()

    def add_wired_edge(self, src: CanvasNode, dst: CanvasNode, link: Link) -> None:
        token = create_edge_token(link)
        if token in self.edges and link.options.unidirectional:
            edge = self.edges[token]
            edge.asymmetric_link = link
        elif token not in self.edges:
            edge = CanvasEdge(self.app, src, dst)
            self.complete_edge(edge, dst, link)

    def add_wireless_edge(self, src: CanvasNode, dst: CanvasNode, link: Link) -> None:
        network_id = link.network_id if link.network_id else None
        token = create_wireless_token(src.id, dst.id, network_id)
        if token in self.wireless_edges:
            logging.warning("ignoring link that already exists: %s", link)
            return
        edge = CanvasWirelessEdge(self.app, src, dst, network_id, token, link)
        self.wireless_edges[token] = edge
        src.wireless_edges.add(edge)
        dst.wireless_edges.add(edge)
        src.canvas.tag_raise(src.id)
        dst.canvas.tag_raise(dst.id)

    def delete_wireless_edge(
        self, src: CanvasNode, dst: CanvasNode, link: Link
    ) -> None:
        network_id = link.network_id if link.network_id else None
        token = create_wireless_token(src.id, dst.id, network_id)
        if token not in self.wireless_edges:
            return
        edge = self.wireless_edges.pop(token)
        edge.delete()

    def update_wireless_edge(
        self, src: CanvasNode, dst: CanvasNode, link: Link
    ) -> None:
        if not link.label:
            return
        network_id = link.network_id if link.network_id else None
        token = create_wireless_token(src.id, dst.id, network_id)
        if token not in self.wireless_edges:
            self.add_wireless_edge(src, dst, link)
        else:
            edge = self.wireless_edges[token]
            edge.middle_label_text(link.label)

    # TODO: look into properly moving this into the edge itself and complete when
    #       the destination is already provided
    def complete_edge(
        self, edge: CanvasEdge, dst: CanvasNode, link: Optional[Link] = None
    ) -> None:
        src = edge.src
        edge.complete(dst)
        if link is None:
            link = self.core.create_link(edge, src, dst)
        edge.link = link
        if link.iface1:
            iface1 = link.iface1
            src.ifaces[iface1.id] = iface1
        if link.iface2:
            iface2 = link.iface2
            dst.ifaces[iface2.id] = iface2
        src.edges.add(edge)
        dst.edges.add(edge)
        edge.token = create_edge_token(edge.link)
        if not edge.linked_wireless:
            edge.arc_common_edges()
        edge.draw_labels()
        edge.check_options()
        self.edges[edge.token] = edge
        self.core.save_edge(edge, src, dst)
        edge.src.canvas.organize()
        if edge.has_shadows():
            edge.dst.canvas.organize()
