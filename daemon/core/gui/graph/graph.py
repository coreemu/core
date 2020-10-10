import logging
import tkinter as tk
from copy import deepcopy
from tkinter import BooleanVar
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from PIL import Image
from PIL.ImageTk import PhotoImage

from core.api.grpc.wrappers import (
    Interface,
    Link,
    LinkType,
    Node,
    Session,
    ThroughputsEvent,
)
from core.gui.dialogs.shapemod import ShapeDialog
from core.gui.graph import tags
from core.gui.graph.edges import (
    EDGE_WIDTH,
    CanvasEdge,
    CanvasWirelessEdge,
    arc_edges,
    create_edge_token,
)
from core.gui.graph.enums import GraphMode, ScaleOption
from core.gui.graph.node import CanvasNode
from core.gui.graph.shape import Shape
from core.gui.graph.shapeutils import ShapeType, is_draw_shape, is_marker
from core.gui.images import ImageEnum, TypeToImage
from core.gui.nodeutils import NodeDraw, NodeUtils

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.coreclient import CoreClient

ZOOM_IN = 1.1
ZOOM_OUT = 0.9
ICON_SIZE = 48
MOVE_NODE_MODES = {GraphMode.NODE, GraphMode.SELECT}
MOVE_SHAPE_MODES = {GraphMode.ANNOTATION, GraphMode.SELECT}


class ShowVar(BooleanVar):
    def __init__(self, canvas: "CanvasGraph", tag: str, value: bool) -> None:
        super().__init__(value=value)
        self.canvas = canvas
        self.tag = tag

    def state(self) -> str:
        return tk.NORMAL if self.get() else tk.HIDDEN

    def click_handler(self) -> None:
        self.canvas.itemconfigure(self.tag, state=self.state())


class CanvasGraph(tk.Canvas):
    def __init__(
        self, master: tk.BaseWidget, app: "Application", core: "CoreClient"
    ) -> None:
        super().__init__(master, highlightthickness=0, background="#cccccc")
        self.app: "Application" = app
        self.core: "CoreClient" = core
        self.mode: GraphMode = GraphMode.SELECT
        self.annotation_type: Optional[ShapeType] = None
        self.selection: Dict[int, int] = {}
        self.select_box: Optional[Shape] = None
        self.selected: Optional[int] = None
        self.node_draw: Optional[NodeDraw] = None
        self.nodes: Dict[int, CanvasNode] = {}
        self.edges: Dict[int, CanvasEdge] = {}
        self.shapes: Dict[int, Shape] = {}
        self.wireless_edges: Dict[Tuple[int, ...], CanvasWirelessEdge] = {}

        # map wireless/EMANE node to the set of MDRs connected to that node
        self.wireless_network: Dict[int, Set[int]] = {}

        self.drawing_edge: Optional[CanvasEdge] = None
        self.rect: Optional[int] = None
        self.shape_drawing: bool = False
        width = self.app.guiconfig.preferences.width
        height = self.app.guiconfig.preferences.height
        self.default_dimensions: Tuple[int, int] = (width, height)
        self.current_dimensions: Tuple[int, int] = self.default_dimensions
        self.ratio: float = 1.0
        self.offset: Tuple[int, int] = (0, 0)
        self.cursor: Tuple[int, int] = (0, 0)
        self.to_copy: List[CanvasNode] = []

        # background related
        self.wallpaper_id: Optional[int] = None
        self.wallpaper: Optional[Image.Image] = None
        self.wallpaper_drawn: Optional[PhotoImage] = None
        self.wallpaper_file: str = ""
        self.scale_option: tk.IntVar = tk.IntVar(value=1)
        self.adjust_to_dim: tk.BooleanVar = tk.BooleanVar(value=False)

        # throughput related
        self.throughput_threshold: float = 250.0
        self.throughput_width: int = 10
        self.throughput_color: str = "#FF0000"

        # drawing related
        self.show_node_labels: ShowVar = ShowVar(self, tags.NODE_LABEL, value=True)
        self.show_link_labels: ShowVar = ShowVar(self, tags.LINK_LABEL, value=True)
        self.show_links: ShowVar = ShowVar(self, tags.EDGE, value=True)
        self.show_wireless: ShowVar = ShowVar(self, tags.WIRELESS_EDGE, value=True)
        self.show_grid: ShowVar = ShowVar(self, tags.GRIDLINE, value=True)
        self.show_annotations: ShowVar = ShowVar(self, tags.ANNOTATION, value=True)
        self.show_iface_names: BooleanVar = BooleanVar(value=False)
        self.show_ip4s: BooleanVar = BooleanVar(value=True)
        self.show_ip6s: BooleanVar = BooleanVar(value=True)

        # bindings
        self.setup_bindings()

        # draw base canvas
        self.draw_canvas()
        self.draw_grid()

    def draw_canvas(self, dimensions: Tuple[int, int] = None) -> None:
        if self.rect is not None:
            self.delete(self.rect)
        if not dimensions:
            dimensions = self.default_dimensions
        self.current_dimensions = dimensions
        self.rect = self.create_rectangle(
            0,
            0,
            *dimensions,
            outline="#000000",
            fill="#ffffff",
            width=1,
            tags="rectangle",
        )
        self.configure(scrollregion=self.bbox(tk.ALL))

    def reset_and_redraw(self, session: Session) -> None:
        # reset view options to default state
        self.show_node_labels.set(True)
        self.show_link_labels.set(True)
        self.show_grid.set(True)
        self.show_annotations.set(True)
        self.show_iface_names.set(False)
        self.show_ip4s.set(True)
        self.show_ip6s.set(True)

        # delete any existing drawn items
        for tag in tags.RESET_TAGS:
            self.delete(tag)

        # set the private variables to default value
        self.mode = GraphMode.SELECT
        self.annotation_type = None
        self.node_draw = None
        self.selected = None
        self.nodes.clear()
        self.edges.clear()
        self.shapes.clear()
        self.wireless_edges.clear()
        self.wireless_network.clear()
        self.drawing_edge = None
        self.draw_session(session)

    def setup_bindings(self) -> None:
        """
        Bind any mouse events or hot keys to the matching action
        """
        self.bind("<ButtonPress-1>", self.click_press)
        self.bind("<ButtonRelease-1>", self.click_release)
        self.bind("<B1-Motion>", self.click_motion)
        self.bind("<Delete>", self.press_delete)
        self.bind("<Control-1>", self.ctrl_click)
        self.bind("<Double-Button-1>", self.double_click)
        self.bind("<MouseWheel>", self.zoom)
        self.bind("<Button-4>", lambda e: self.zoom(e, ZOOM_IN))
        self.bind("<Button-5>", lambda e: self.zoom(e, ZOOM_OUT))
        self.bind("<ButtonPress-3>", lambda e: self.scan_mark(e.x, e.y))
        self.bind("<B3-Motion>", lambda e: self.scan_dragto(e.x, e.y, gain=1))

    def get_actual_coords(self, x: float, y: float) -> Tuple[float, float]:
        actual_x = (x - self.offset[0]) / self.ratio
        actual_y = (y - self.offset[1]) / self.ratio
        return actual_x, actual_y

    def get_scaled_coords(self, x: float, y: float) -> Tuple[float, float]:
        scaled_x = (x * self.ratio) + self.offset[0]
        scaled_y = (y * self.ratio) + self.offset[1]
        return scaled_x, scaled_y

    def inside_canvas(self, x: float, y: float) -> Tuple[bool, bool]:
        x1, y1, x2, y2 = self.bbox(self.rect)
        valid_x = x1 <= x <= x2
        valid_y = y1 <= y <= y2
        return valid_x and valid_y

    def valid_position(self, x1: int, y1: int, x2: int, y2: int) -> Tuple[bool, bool]:
        valid_topleft = self.inside_canvas(x1, y1)
        valid_bottomright = self.inside_canvas(x2, y2)
        return valid_topleft and valid_bottomright

    def set_throughputs(self, throughputs_event: ThroughputsEvent) -> None:
        for iface_throughput in throughputs_event.iface_throughputs:
            node_id = iface_throughput.node_id
            iface_id = iface_throughput.iface_id
            throughput = iface_throughput.throughput
            iface_to_edge_id = (node_id, iface_id)
            token = self.core.iface_to_edge.get(iface_to_edge_id)
            if not token:
                continue
            edge = self.edges.get(token)
            if edge:
                edge.set_throughput(throughput)
            else:
                del self.core.iface_to_edge[iface_to_edge_id]

    def draw_grid(self) -> None:
        """
        Create grid.
        """
        width, height = self.width_and_height()
        width = int(width)
        height = int(height)
        for i in range(0, width, 27):
            self.create_line(i, 0, i, height, dash=(2, 4), tags=tags.GRIDLINE)
        for i in range(0, height, 27):
            self.create_line(0, i, width, i, dash=(2, 4), tags=tags.GRIDLINE)
        self.tag_lower(tags.GRIDLINE)
        self.tag_lower(self.rect)

    def add_wired_edge(self, src: CanvasNode, dst: CanvasNode, link: Link) -> None:
        token = create_edge_token(src.id, dst.id)
        if token in self.edges and link.options.unidirectional:
            edge = self.edges[token]
            edge.asymmetric_link = link
        elif token not in self.edges:
            node1 = src.core_node
            node2 = dst.core_node
            src_pos = (node1.position.x, node1.position.y)
            dst_pos = (node2.position.x, node2.position.y)
            edge = CanvasEdge(self, src.id, src_pos, dst_pos)
            edge.linked_wireless = self.is_linked_wireless(src.id, dst.id)
            edge.token = token
            edge.dst = dst.id
            edge.set_link(link)
            edge.check_wireless()
            src.edges.add(edge)
            dst.edges.add(edge)
            self.edges[edge.token] = edge
            self.core.links[edge.token] = edge
            if link.iface1:
                iface1 = link.iface1
                self.core.iface_to_edge[(node1.id, iface1.id)] = token
                src.ifaces[iface1.id] = iface1
                edge.src_iface = iface1
            if link.iface2:
                iface2 = link.iface2
                self.core.iface_to_edge[(node2.id, iface2.id)] = edge.token
                dst.ifaces[iface2.id] = iface2
                edge.dst_iface = iface2

    def delete_wired_edge(self, src: CanvasNode, dst: CanvasNode) -> None:
        token = create_edge_token(src.id, dst.id)
        edge = self.edges.get(token)
        if not edge:
            return
        self.delete_edge(edge)

    def update_wired_edge(self, src: CanvasNode, dst: CanvasNode, link: Link) -> None:
        token = create_edge_token(src.id, dst.id)
        edge = self.edges.get(token)
        if not edge:
            return
        edge.link.options = deepcopy(link.options)

    def add_wireless_edge(self, src: CanvasNode, dst: CanvasNode, link: Link) -> None:
        network_id = link.network_id if link.network_id else None
        token = create_edge_token(src.id, dst.id, network_id)
        if token in self.wireless_edges:
            logging.warning("ignoring link that already exists: %s", link)
            return
        src_pos = self.coords(src.id)
        dst_pos = self.coords(dst.id)
        edge = CanvasWirelessEdge(self, src.id, dst.id, src_pos, dst_pos, token, link)
        self.wireless_edges[token] = edge
        src.wireless_edges.add(edge)
        dst.wireless_edges.add(edge)
        self.tag_raise(src.id)
        self.tag_raise(dst.id)
        # update arcs when there are multiple links
        common_edges = list(src.wireless_edges & dst.wireless_edges)
        arc_edges(common_edges)

    def delete_wireless_edge(
        self, src: CanvasNode, dst: CanvasNode, link: Link
    ) -> None:
        network_id = link.network_id if link.network_id else None
        token = create_edge_token(src.id, dst.id, network_id)
        if token not in self.wireless_edges:
            return
        edge = self.wireless_edges.pop(token)
        edge.delete()
        src.wireless_edges.remove(edge)
        dst.wireless_edges.remove(edge)
        # update arcs when there are multiple links
        common_edges = list(src.wireless_edges & dst.wireless_edges)
        arc_edges(common_edges)

    def update_wireless_edge(
        self, src: CanvasNode, dst: CanvasNode, link: Link
    ) -> None:
        if not link.label:
            return
        network_id = link.network_id if link.network_id else None
        token = create_edge_token(src.id, dst.id, network_id)
        if token not in self.wireless_edges:
            self.add_wireless_edge(src, dst, link)
        else:
            edge = self.wireless_edges[token]
            edge.middle_label_text(link.label)

    def add_core_node(self, core_node: Node) -> None:
        logging.debug("adding node: %s", core_node)
        # if the gui can't find node's image, default to the "edit-node" image
        image = NodeUtils.node_image(core_node, self.app.guiconfig, self.app.app_scale)
        if not image:
            image = self.app.get_icon(ImageEnum.EDITNODE, ICON_SIZE)
        x = core_node.position.x
        y = core_node.position.y
        node = CanvasNode(self.app, x, y, core_node, image)
        self.nodes[node.id] = node
        self.core.set_canvas_node(core_node, node)

    def draw_session(self, session: Session) -> None:
        """
        Draw existing session.
        """
        # draw existing nodes
        for core_node in session.nodes.values():
            logging.debug("drawing node: %s", core_node)
            # peer to peer node is not drawn on the GUI
            if NodeUtils.is_ignore_node(core_node.type):
                continue
            self.add_core_node(core_node)
        # draw existing links
        for link in session.links:
            logging.debug("drawing link: %s", link)
            canvas_node1 = self.core.get_canvas_node(link.node1_id)
            canvas_node2 = self.core.get_canvas_node(link.node2_id)
            if link.type == LinkType.WIRELESS:
                self.add_wireless_edge(canvas_node1, canvas_node2, link)
            else:
                self.add_wired_edge(canvas_node1, canvas_node2, link)

    def stopped_session(self) -> None:
        # clear wireless edges
        for edge in self.wireless_edges.values():
            edge.delete()
            src_node = self.nodes[edge.src]
            src_node.wireless_edges.remove(edge)
            dst_node = self.nodes[edge.dst]
            dst_node.wireless_edges.remove(edge)
        self.wireless_edges.clear()

        # clear throughputs
        self.clear_throughputs()

    def canvas_xy(self, event: tk.Event) -> Tuple[float, float]:
        """
        Convert window coordinate to canvas coordinate
        """
        x = self.canvasx(event.x)
        y = self.canvasy(event.y)
        return x, y

    def get_selected(self, event: tk.Event) -> int:
        """
        Retrieve the item id that is on the mouse position
        """
        x, y = self.canvas_xy(event)
        overlapping = self.find_overlapping(x, y, x, y)
        selected = None
        for _id in overlapping:
            if self.drawing_edge and self.drawing_edge.id == _id:
                continue

            if _id in self.nodes:
                selected = _id
                break

            if _id in self.shapes:
                selected = _id

        return selected

    def click_release(self, event: tk.Event) -> None:
        """
        Draw a node or finish drawing an edge according to the current graph mode
        """
        logging.debug("click release")
        x, y = self.canvas_xy(event)
        if not self.inside_canvas(x, y):
            return
        if self.mode == GraphMode.ANNOTATION:
            self.focus_set()
            if self.shape_drawing:
                shape = self.shapes[self.selected]
                shape.shape_complete(x, y)
                self.shape_drawing = False
        elif self.mode == GraphMode.SELECT:
            self.focus_set()
            if self.select_box:
                x0, y0, x1, y1 = self.coords(self.select_box.id)
                inside = [
                    x
                    for x in self.find_enclosed(x0, y0, x1, y1)
                    if "node" in self.gettags(x) or "shape" in self.gettags(x)
                ]
                for i in inside:
                    self.select_object(i, True)
                self.select_box.disappear()
                self.select_box = None
        else:
            self.focus_set()
            self.selected = self.get_selected(event)
            logging.debug(f"click release selected({self.selected}) mode({self.mode})")
            if self.mode == GraphMode.EDGE:
                self.handle_edge_release(event)
            elif self.mode == GraphMode.NODE:
                self.add_node(x, y)
            elif self.mode == GraphMode.PICKNODE:
                self.mode = GraphMode.NODE
        self.selected = None

    def handle_edge_release(self, _event: tk.Event) -> None:
        edge = self.drawing_edge
        self.drawing_edge = None

        # not drawing edge return
        if edge is None:
            return

        # edge dst must be a node
        logging.debug("current selected: %s", self.selected)
        src_node = self.nodes.get(edge.src)
        dst_node = self.nodes.get(self.selected)
        if not dst_node or not src_node:
            edge.delete()
            return

        # edge dst is same as src, delete edge
        if edge.src == self.selected:
            edge.delete()
            return

        # ignore repeated edges
        token = create_edge_token(edge.src, self.selected)
        if token in self.edges:
            edge.delete()
            return

        # rj45 nodes can only support one link
        if NodeUtils.is_rj45_node(src_node.core_node.type) and src_node.edges:
            edge.delete()
            return
        if NodeUtils.is_rj45_node(dst_node.core_node.type) and dst_node.edges:
            edge.delete()
            return

        # set dst node and snap edge to center
        linked_wireless = self.is_linked_wireless(src_node.id, self.selected)
        edge.complete(self.selected, linked_wireless)

        self.edges[edge.token] = edge
        src_node.edges.add(edge)
        dst_node.edges.add(edge)
        self.core.create_link(edge, src_node, dst_node)

    def select_object(self, object_id: int, choose_multiple: bool = False) -> None:
        """
        create a bounding box when a node is selected
        """
        if not choose_multiple:
            self.clear_selection()

        # draw a bounding box if node hasn't been selected yet
        if object_id not in self.selection:
            x0, y0, x1, y1 = self.bbox(object_id)
            selection_id = self.create_rectangle(
                (x0 - 6, y0 - 6, x1 + 6, y1 + 6),
                activedash=True,
                dash="-",
                tags=tags.SELECTION,
            )
            self.selection[object_id] = selection_id
        else:
            selection_id = self.selection.pop(object_id)
            self.delete(selection_id)

    def clear_selection(self) -> None:
        """
        Clear current selection boxes.
        """
        for _id in self.selection.values():
            self.delete(_id)
        self.selection.clear()

    def move_selection(self, object_id: int, x_offset: float, y_offset: float) -> None:
        select_id = self.selection.get(object_id)
        if select_id is not None:
            self.move(select_id, x_offset, y_offset)

    def delete_selected_objects(self) -> None:
        edges = set()
        nodes = []
        for object_id in self.selection:
            #  delete selection box
            selection_id = self.selection[object_id]
            self.delete(selection_id)

            # delete node and related edges
            if object_id in self.nodes:
                canvas_node = self.nodes.pop(object_id)
                canvas_node.delete()
                nodes.append(canvas_node)
                is_wireless = NodeUtils.is_wireless_node(canvas_node.core_node.type)
                # delete related edges
                for edge in canvas_node.edges:
                    if edge in edges:
                        continue
                    edges.add(edge)
                    del self.edges[edge.token]
                    edge.delete()
                    # update node connected to edge being deleted
                    other_id = edge.src
                    other_iface = edge.src_iface
                    if edge.src == object_id:
                        other_id = edge.dst
                        other_iface = edge.dst_iface
                    other_node = self.nodes[other_id]
                    other_node.edges.remove(edge)
                    if other_iface:
                        del other_node.ifaces[other_iface.id]
                    if is_wireless:
                        other_node.delete_antenna()

            # delete shape
            if object_id in self.shapes:
                shape = self.shapes.pop(object_id)
                shape.delete()

        self.selection.clear()
        self.core.deleted_canvas_nodes(nodes)
        self.core.deleted_canvas_edges(edges)

    def delete_edge(self, edge: CanvasEdge) -> None:
        edge.delete()
        del self.edges[edge.token]
        src_node = self.nodes[edge.src]
        src_node.edges.discard(edge)
        if edge.src_iface:
            del src_node.ifaces[edge.src_iface.id]
        dst_node = self.nodes[edge.dst]
        dst_node.edges.discard(edge)
        if edge.dst_iface:
            del dst_node.ifaces[edge.dst_iface.id]
        src_wireless = NodeUtils.is_wireless_node(src_node.core_node.type)
        if src_wireless:
            dst_node.delete_antenna()
        dst_wireless = NodeUtils.is_wireless_node(dst_node.core_node.type)
        if dst_wireless:
            src_node.delete_antenna()
        self.core.deleted_canvas_edges([edge])

    def zoom(self, event: tk.Event, factor: float = None) -> None:
        if not factor:
            factor = ZOOM_IN if event.delta > 0 else ZOOM_OUT
        event.x, event.y = self.canvasx(event.x), self.canvasy(event.y)
        self.scale(tk.ALL, event.x, event.y, factor, factor)
        self.configure(scrollregion=self.bbox(tk.ALL))
        self.ratio *= float(factor)
        self.offset = (
            self.offset[0] * factor + event.x * (1 - factor),
            self.offset[1] * factor + event.y * (1 - factor),
        )
        logging.debug("ratio: %s", self.ratio)
        logging.debug("offset: %s", self.offset)
        self.app.statusbar.set_zoom(self.ratio)
        if self.wallpaper:
            self.redraw_wallpaper()

    def click_press(self, event: tk.Event) -> None:
        """
        Start drawing an edge if mouse click is on a node
        """
        x, y = self.canvas_xy(event)
        if not self.inside_canvas(x, y):
            return

        self.cursor = x, y
        selected = self.get_selected(event)
        logging.debug("click press(%s): %s", self.cursor, selected)
        x_check = self.cursor[0] - self.offset[0]
        y_check = self.cursor[1] - self.offset[1]
        logging.debug("click press offset(%s, %s)", x_check, y_check)
        is_node = selected in self.nodes
        if self.mode == GraphMode.EDGE and is_node:
            pos = self.coords(selected)
            self.drawing_edge = CanvasEdge(self, selected, pos, pos)
            self.organize()

        if self.mode == GraphMode.ANNOTATION:
            if is_marker(self.annotation_type):
                r = self.app.toolbar.marker_frame.size.get()
                self.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    fill=self.app.toolbar.marker_frame.color,
                    outline="",
                    tags=(tags.MARKER, tags.ANNOTATION),
                    state=self.show_annotations.state(),
                )
                return
            if selected is None:
                shape = Shape(self.app, self, self.annotation_type, x, y)
                self.selected = shape.id
                self.shape_drawing = True
                self.shapes[shape.id] = shape

        if selected is not None:
            if selected not in self.selection:
                if selected in self.shapes:
                    shape = self.shapes[selected]
                    self.select_object(shape.id)
                    self.selected = selected
                elif selected in self.nodes:
                    node = self.nodes[selected]
                    self.select_object(node.id)
                    self.selected = selected
                    logging.debug(
                        "selected node(%s), coords: (%s, %s)",
                        node.core_node.name,
                        node.core_node.position.x,
                        node.core_node.position.y,
                    )
        else:
            if self.mode == GraphMode.SELECT:
                shape = Shape(self.app, self, ShapeType.RECTANGLE, x, y)
                self.select_box = shape
            self.clear_selection()

    def ctrl_click(self, event: tk.Event) -> None:
        # update cursor location
        x, y = self.canvas_xy(event)
        if not self.inside_canvas(x, y):
            return

        self.cursor = x, y

        # handle multiple selections
        logging.debug("control left click: %s", event)
        selected = self.get_selected(event)
        if (
            selected not in self.selection
            and selected in self.shapes
            or selected in self.nodes
        ):
            self.select_object(selected, choose_multiple=True)

    def click_motion(self, event: tk.Event) -> None:
        x, y = self.canvas_xy(event)
        if not self.inside_canvas(x, y):
            if self.select_box:
                self.select_box.delete()
                self.select_box = None
            if is_draw_shape(self.annotation_type) and self.shape_drawing:
                shape = self.shapes.pop(self.selected)
                shape.delete()
                self.shape_drawing = False
            return

        x_offset = x - self.cursor[0]
        y_offset = y - self.cursor[1]
        self.cursor = x, y

        if self.mode == GraphMode.EDGE and self.drawing_edge is not None:
            self.drawing_edge.move_dst(self.cursor)
        if self.mode == GraphMode.ANNOTATION:
            if is_draw_shape(self.annotation_type) and self.shape_drawing:
                shape = self.shapes[self.selected]
                shape.shape_motion(x, y)
                return
            elif is_marker(self.annotation_type):
                r = self.app.toolbar.marker_frame.size.get()
                self.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    fill=self.app.toolbar.marker_frame.color,
                    outline="",
                    tags=(tags.MARKER, tags.ANNOTATION),
                )
                return

        if self.mode == GraphMode.EDGE:
            return

        # move selected objects
        if self.selection:
            for selected_id in self.selection:
                if self.mode in MOVE_SHAPE_MODES and selected_id in self.shapes:
                    shape = self.shapes[selected_id]
                    shape.motion(x_offset, y_offset)

                if self.mode in MOVE_NODE_MODES and selected_id in self.nodes:
                    node = self.nodes[selected_id]
                    node.motion(x_offset, y_offset, update=self.core.is_runtime())
        else:
            if self.select_box and self.mode == GraphMode.SELECT:
                self.select_box.shape_motion(x, y)

    def press_delete(self, _event: tk.Event) -> None:
        """
        delete selected nodes and any data that relates to it
        """
        logging.debug("press delete key")
        if not self.app.core.is_runtime():
            self.delete_selected_objects()
            self.app.default_info()
        else:
            logging.debug("node deletion is disabled during runtime state")

    def double_click(self, event: tk.Event) -> None:
        selected = self.get_selected(event)
        if selected is not None and selected in self.shapes:
            shape = self.shapes[selected]
            dialog = ShapeDialog(self.app, shape)
            dialog.show()

    def add_node(self, x: float, y: float) -> None:
        if self.selected is not None and self.selected not in self.shapes:
            return
        actual_x, actual_y = self.get_actual_coords(x, y)
        core_node = self.core.create_node(
            actual_x, actual_y, self.node_draw.node_type, self.node_draw.model
        )
        if not core_node:
            return
        try:
            image_enum = self.node_draw.image_enum
            self.node_draw.image = self.app.get_icon(image_enum, ICON_SIZE)
        except AttributeError:
            image_file = self.node_draw.image_file
            self.node_draw.image = self.app.get_custom_icon(image_file, ICON_SIZE)
        node = CanvasNode(self.app, x, y, core_node, self.node_draw.image)
        self.nodes[node.id] = node
        self.core.set_canvas_node(core_node, node)

    def width_and_height(self) -> Tuple[int, int]:
        """
        retrieve canvas width and height in pixels
        """
        x0, y0, x1, y1 = self.coords(self.rect)
        canvas_w = abs(x0 - x1)
        canvas_h = abs(y0 - y1)
        return canvas_w, canvas_h

    def get_wallpaper_image(self) -> Image.Image:
        width = int(self.wallpaper.width * self.ratio)
        height = int(self.wallpaper.height * self.ratio)
        image = self.wallpaper.resize((width, height), Image.ANTIALIAS)
        return image

    def draw_wallpaper(
        self, image: PhotoImage, x: float = None, y: float = None
    ) -> None:
        if x is None and y is None:
            x1, y1, x2, y2 = self.bbox(self.rect)
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2
        self.wallpaper_id = self.create_image((x, y), image=image, tags=tags.WALLPAPER)
        self.wallpaper_drawn = image

    def wallpaper_upper_left(self) -> None:
        self.delete(self.wallpaper_id)

        # create new scaled image, cropped if needed
        width, height = self.width_and_height()
        image = self.get_wallpaper_image()
        cropx = image.width
        cropy = image.height
        if image.width > width:
            cropx = image.width
        if image.height > height:
            cropy = image.height
        cropped = image.crop((0, 0, cropx, cropy))
        image = PhotoImage(cropped)

        # draw on canvas
        x1, y1, _, _ = self.bbox(self.rect)
        x = (cropx / 2) + x1
        y = (cropy / 2) + y1
        self.draw_wallpaper(image, x, y)

    def wallpaper_center(self) -> None:
        """
        place the image at the center of canvas
        """
        self.delete(self.wallpaper_id)

        # dimension of the cropped image
        width, height = self.width_and_height()
        image = self.get_wallpaper_image()
        cropx = 0
        if image.width > width:
            cropx = (image.width - width) / 2
        cropy = 0
        if image.height > height:
            cropy = (image.height - height) / 2
        x1 = 0 + cropx
        y1 = 0 + cropy
        x2 = image.width - cropx
        y2 = image.height - cropy
        cropped = image.crop((x1, y1, x2, y2))
        image = PhotoImage(cropped)
        self.draw_wallpaper(image)

    def wallpaper_scaled(self) -> None:
        """
        scale image based on canvas dimension
        """
        self.delete(self.wallpaper_id)
        canvas_w, canvas_h = self.width_and_height()
        image = self.wallpaper.resize((int(canvas_w), int(canvas_h)), Image.ANTIALIAS)
        image = PhotoImage(image)
        self.draw_wallpaper(image)

    def resize_to_wallpaper(self) -> None:
        self.delete(self.wallpaper_id)
        image = PhotoImage(self.wallpaper)
        self.redraw_canvas((image.width(), image.height()))
        self.draw_wallpaper(image)

    def redraw_canvas(self, dimensions: Tuple[int, int] = None) -> None:
        logging.debug("redrawing canvas to dimensions: %s", dimensions)

        # reset scale and move back to original position
        logging.debug("resetting scaling: %s %s", self.ratio, self.offset)
        factor = 1 / self.ratio
        self.scale(tk.ALL, self.offset[0], self.offset[1], factor, factor)
        self.move(tk.ALL, -self.offset[0], -self.offset[1])

        # reset ratio and offset
        self.ratio = 1.0
        self.offset = (0, 0)

        # redraw canvas rectangle
        self.draw_canvas(dimensions)

        # redraw gridlines to new canvas size
        self.delete(tags.GRIDLINE)
        self.draw_grid()
        self.app.canvas.show_grid.click_handler()

    def redraw_wallpaper(self) -> None:
        if self.adjust_to_dim.get():
            logging.debug("drawing wallpaper to canvas dimensions")
            self.resize_to_wallpaper()
        else:
            option = ScaleOption(self.scale_option.get())
            logging.debug("drawing canvas using scaling option: %s", option)
            if option == ScaleOption.UPPER_LEFT:
                self.wallpaper_upper_left()
            elif option == ScaleOption.CENTERED:
                self.wallpaper_center()
            elif option == ScaleOption.SCALED:
                self.wallpaper_scaled()
            elif option == ScaleOption.TILED:
                logging.warning("tiled background not implemented yet")
        self.organize()

    def organize(self) -> None:
        for tag in tags.ORGANIZE_TAGS:
            self.tag_raise(tag)

    def set_wallpaper(self, filename: Optional[str]) -> None:
        logging.debug("setting wallpaper: %s", filename)
        if filename:
            img = Image.open(filename)
            self.wallpaper = img
            self.wallpaper_file = filename
            self.redraw_wallpaper()
        else:
            if self.wallpaper_id is not None:
                self.delete(self.wallpaper_id)
            self.wallpaper = None
            self.wallpaper_file = None

    def is_selection_mode(self) -> bool:
        return self.mode == GraphMode.SELECT

    def create_edge(self, source: CanvasNode, dest: CanvasNode) -> None:
        """
        create an edge between source node and destination node
        """
        token = create_edge_token(source.id, dest.id)
        if token not in self.edges:
            pos = (source.core_node.position.x, source.core_node.position.y)
            edge = CanvasEdge(self, source.id, pos, pos)
            linked_wireless = self.is_linked_wireless(source.id, dest.id)
            edge.complete(dest.id, linked_wireless)
            self.edges[edge.token] = edge
            self.nodes[source.id].edges.add(edge)
            self.nodes[dest.id].edges.add(edge)
            self.core.create_link(edge, source, dest)

    def copy(self) -> None:
        if self.core.is_runtime():
            logging.debug("copy is disabled during runtime state")
            return
        if self.selection:
            logging.debug("to copy nodes: %s", self.selection)
            self.to_copy.clear()
            for node_id in self.selection.keys():
                canvas_node = self.nodes[node_id]
                self.to_copy.append(canvas_node)

    def paste(self) -> None:
        if self.core.is_runtime():
            logging.debug("paste is disabled during runtime state")
            return
        # maps original node canvas id to copy node canvas id
        copy_map = {}
        # the edges that will be copy over
        to_copy_edges = set()
        to_copy_ids = {x.id for x in self.to_copy}
        for canvas_node in self.to_copy:
            core_node = canvas_node.core_node
            actual_x = core_node.position.x + 50
            actual_y = core_node.position.y + 50
            scaled_x, scaled_y = self.get_scaled_coords(actual_x, actual_y)
            copy = self.core.create_node(
                actual_x, actual_y, core_node.type, core_node.model
            )
            if not copy:
                continue
            node = CanvasNode(self.app, scaled_x, scaled_y, copy, canvas_node.image)
            # copy configurations and services
            node.core_node.services = core_node.services.copy()
            node.core_node.config_services = core_node.config_services.copy()
            node.core_node.emane_model_configs = deepcopy(core_node.emane_model_configs)
            node.core_node.wlan_config = deepcopy(core_node.wlan_config)
            node.core_node.mobility_config = deepcopy(core_node.mobility_config)
            node.core_node.service_configs = deepcopy(core_node.service_configs)
            node.core_node.service_file_configs = deepcopy(
                core_node.service_file_configs
            )
            node.core_node.config_service_configs = deepcopy(
                core_node.config_service_configs
            )

            copy_map[canvas_node.id] = node.id
            self.nodes[node.id] = node
            self.core.set_canvas_node(copy, node)
            for edge in canvas_node.edges:
                if edge.src not in to_copy_ids or edge.dst not in to_copy_ids:
                    if canvas_node.id == edge.src:
                        dst_node = self.nodes[edge.dst]
                        self.create_edge(node, dst_node)
                        token = create_edge_token(node.id, dst_node.id)
                    elif canvas_node.id == edge.dst:
                        src_node = self.nodes[edge.src]
                        self.create_edge(src_node, node)
                        token = create_edge_token(src_node.id, node.id)
                    copy_edge = self.edges[token]
                    copy_link = copy_edge.link
                    iface1_id = copy_link.iface1.id if copy_link.iface1 else None
                    iface2_id = copy_link.iface2.id if copy_link.iface2 else None
                    options = edge.link.options
                    if options:
                        copy_edge.link.options = deepcopy(options)
                    if options and options.unidirectional:
                        asym_iface1 = None
                        if iface1_id is not None:
                            asym_iface1 = Interface(id=iface1_id)
                        asym_iface2 = None
                        if iface2_id is not None:
                            asym_iface2 = Interface(id=iface2_id)
                        copy_edge.asymmetric_link = Link(
                            node1_id=copy_link.node2_id,
                            node2_id=copy_link.node1_id,
                            iface1=asym_iface2,
                            iface2=asym_iface1,
                            options=deepcopy(edge.asymmetric_link.options),
                        )
                    copy_edge.redraw()
                else:
                    to_copy_edges.add(edge)

        # copy link and link config
        for edge in to_copy_edges:
            src_node_id = copy_map[edge.token[0]]
            dst_node_id = copy_map[edge.token[1]]
            src_node_copy = self.nodes[src_node_id]
            dst_node_copy = self.nodes[dst_node_id]
            self.create_edge(src_node_copy, dst_node_copy)
            token = create_edge_token(src_node_copy.id, dst_node_copy.id)
            copy_edge = self.edges[token]
            copy_link = copy_edge.link
            iface1_id = copy_link.iface1.id if copy_link.iface1 else None
            iface2_id = copy_link.iface2.id if copy_link.iface2 else None
            options = edge.link.options
            if options:
                copy_link.options = deepcopy(options)
            if options and options.unidirectional:
                asym_iface1 = None
                if iface1_id is not None:
                    asym_iface1 = Interface(id=iface1_id)
                asym_iface2 = None
                if iface2_id is not None:
                    asym_iface2 = Interface(id=iface2_id)
                copy_edge.asymmetric_link = Link(
                    node1_id=copy_link.node2_id,
                    node2_id=copy_link.node1_id,
                    iface1=asym_iface2,
                    iface2=asym_iface1,
                    options=deepcopy(edge.asymmetric_link.options),
                )
            copy_edge.redraw()
            self.itemconfig(
                copy_edge.id,
                width=self.itemcget(edge.id, "width"),
                fill=self.itemcget(edge.id, "fill"),
            )
        self.tag_raise(tags.NODE)

    def is_linked_wireless(self, src: int, dst: int) -> bool:
        src_node = self.nodes[src]
        dst_node = self.nodes[dst]
        src_node_type = src_node.core_node.type
        dst_node_type = dst_node.core_node.type
        is_src_wireless = NodeUtils.is_wireless_node(src_node_type)
        is_dst_wireless = NodeUtils.is_wireless_node(dst_node_type)

        # update the wlan/EMANE network
        wlan_network = self.wireless_network
        if is_src_wireless and not is_dst_wireless:
            if src not in wlan_network:
                wlan_network[src] = set()
            wlan_network[src].add(dst)
        elif not is_src_wireless and is_dst_wireless:
            if dst not in wlan_network:
                wlan_network[dst] = set()
            wlan_network[dst].add(src)
        return is_src_wireless or is_dst_wireless

    def clear_throughputs(self) -> None:
        for edge in self.edges.values():
            edge.clear_throughput()

    def scale_graph(self) -> None:
        for nid, canvas_node in self.nodes.items():
            img = None
            if NodeUtils.is_custom(
                canvas_node.core_node.type, canvas_node.core_node.model
            ):
                for custom_node in self.app.guiconfig.nodes:
                    if custom_node.name == canvas_node.core_node.model:
                        img = self.app.get_custom_icon(custom_node.image, ICON_SIZE)
            else:
                image_enum = TypeToImage.get(
                    canvas_node.core_node.type, canvas_node.core_node.model
                )
                img = self.app.get_icon(image_enum, ICON_SIZE)

            self.itemconfig(nid, image=img)
            canvas_node.image = img
            canvas_node.scale_text()
            canvas_node.scale_antennas()

            for edge_id in self.find_withtag(tags.EDGE):
                self.itemconfig(edge_id, width=int(EDGE_WIDTH * self.app.app_scale))
