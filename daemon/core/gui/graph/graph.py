import logging
import tkinter as tk
from tkinter import BooleanVar
from typing import TYPE_CHECKING, Tuple

from PIL import Image, ImageTk

from core.api.grpc import core_pb2
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
from core.gui.images import ImageEnum, Images, TypeToImage
from core.gui.nodeutils import NodeUtils

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.coreclient import CoreClient

ZOOM_IN = 1.1
ZOOM_OUT = 0.9
ICON_SIZE = 48


class ShowVar(BooleanVar):
    def __init__(self, canvas: "CanvasGraph", tag: str, value: bool) -> None:
        super().__init__(value=value)
        self.canvas = canvas
        self.tag = tag

    def state(self) -> str:
        return tk.NORMAL if self.get() else tk.HIDDEN

    def click_handler(self):
        self.canvas.itemconfigure(self.tag, state=self.state())


class CanvasGraph(tk.Canvas):
    def __init__(
        self, master: "Application", core: "CoreClient", width: int, height: int
    ):
        super().__init__(master, highlightthickness=0, background="#cccccc")
        self.app = master
        self.core = core
        self.mode = GraphMode.SELECT
        self.annotation_type = None
        self.selection = {}
        self.select_box = None
        self.selected = None
        self.node_draw = None
        self.context = None
        self.nodes = {}
        self.edges = {}
        self.shapes = {}
        self.wireless_edges = {}

        # map wireless/EMANE node to the set of MDRs connected to that node
        self.wireless_network = {}

        self.drawing_edge = None
        self.grid = None
        self.shape_drawing = False
        self.default_dimensions = (width, height)
        self.current_dimensions = self.default_dimensions
        self.ratio = 1.0
        self.offset = (0, 0)
        self.cursor = (0, 0)
        self.marker_tool = None
        self.to_copy = []

        # background related
        self.wallpaper_id = None
        self.wallpaper = None
        self.wallpaper_drawn = None
        self.wallpaper_file = ""
        self.scale_option = tk.IntVar(value=1)
        self.adjust_to_dim = tk.BooleanVar(value=False)

        # throughput related
        self.throughput_threshold = 250.0
        self.throughput_width = 10
        self.throughput_color = "#FF0000"

        # drawing related
        self.show_node_labels = ShowVar(self, tags.NODE_LABEL, value=True)
        self.show_link_labels = ShowVar(self, tags.LINK_LABEL, value=True)
        self.show_grid = ShowVar(self, tags.GRIDLINE, value=True)
        self.show_annotations = ShowVar(self, tags.ANNOTATION, value=True)
        self.show_interface_names = BooleanVar(value=False)
        self.show_ip4s = BooleanVar(value=True)
        self.show_ip6s = BooleanVar(value=True)

        # bindings
        self.setup_bindings()

        # draw base canvas
        self.draw_canvas()
        self.draw_grid()

    def draw_canvas(self, dimensions: Tuple[int, int] = None):
        if self.grid is not None:
            self.delete(self.grid)
        if not dimensions:
            dimensions = self.default_dimensions
        self.current_dimensions = dimensions
        self.grid = self.create_rectangle(
            0,
            0,
            *dimensions,
            outline="#000000",
            fill="#ffffff",
            width=1,
            tags="rectangle",
        )
        self.configure(scrollregion=self.bbox(tk.ALL))

    def reset_and_redraw(self, session: core_pb2.Session):
        """
        Reset the private variables CanvasGraph object, redraw nodes given the new grpc
        client.
        :param session: session to draw
        """
        # hide context
        self.hide_context()

        # delete any existing drawn items
        for tag in tags.COMPONENT_TAGS:
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

    def setup_bindings(self):
        """
        Bind any mouse events or hot keys to the matching action
        """
        self.bind("<ButtonPress-1>", self.click_press)
        self.bind("<ButtonRelease-1>", self.click_release)
        self.bind("<B1-Motion>", self.click_motion)
        self.bind("<ButtonRelease-3>", self.click_context)
        self.bind("<Delete>", self.press_delete)
        self.bind("<Control-1>", self.ctrl_click)
        self.bind("<Double-Button-1>", self.double_click)
        self.bind("<MouseWheel>", self.zoom)
        self.bind("<Button-4>", lambda e: self.zoom(e, ZOOM_IN))
        self.bind("<Button-5>", lambda e: self.zoom(e, ZOOM_OUT))
        self.bind("<ButtonPress-3>", lambda e: self.scan_mark(e.x, e.y))
        self.bind("<B3-Motion>", lambda e: self.scan_dragto(e.x, e.y, gain=1))

    def hide_context(self, event=None):
        if self.context:
            self.context.unpost()
            self.context = None

    def get_actual_coords(self, x: float, y: float) -> [float, float]:
        actual_x = (x - self.offset[0]) / self.ratio
        actual_y = (y - self.offset[1]) / self.ratio
        return actual_x, actual_y

    def get_scaled_coords(self, x: float, y: float) -> [float, float]:
        scaled_x = (x * self.ratio) + self.offset[0]
        scaled_y = (y * self.ratio) + self.offset[1]
        return scaled_x, scaled_y

    def inside_canvas(self, x: float, y: float) -> [bool, bool]:
        x1, y1, x2, y2 = self.bbox(self.grid)
        valid_x = x1 <= x <= x2
        valid_y = y1 <= y <= y2
        return valid_x and valid_y

    def valid_position(self, x1: int, y1: int, x2: int, y2: int) -> [bool, bool]:
        valid_topleft = self.inside_canvas(x1, y1)
        valid_bottomright = self.inside_canvas(x2, y2)
        return valid_topleft and valid_bottomright

    def set_throughputs(self, throughputs_event: core_pb2.ThroughputsEvent):
        for interface_throughput in throughputs_event.interface_throughputs:
            node_id = interface_throughput.node_id
            interface_id = interface_throughput.interface_id
            throughput = interface_throughput.throughput
            interface_to_edge_id = (node_id, interface_id)
            token = self.core.interface_to_edge.get(interface_to_edge_id)
            if not token:
                continue
            edge = self.edges.get(token)
            if edge:
                edge.set_throughput(throughput)
            else:
                del self.core.interface_to_edge[interface_to_edge_id]

    def draw_grid(self):
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
        self.tag_lower(self.grid)

    def add_wireless_edge(
        self, src: CanvasNode, dst: CanvasNode, link: core_pb2.Link
    ) -> None:
        network_id = link.network_id if link.network_id else None
        token = create_edge_token(src.id, dst.id, network_id)
        if token in self.wireless_edges:
            logging.warning("ignoring link that already exists: %s", link)
            return
        src_pos = self.coords(src.id)
        dst_pos = self.coords(dst.id)
        edge = CanvasWirelessEdge(self, src.id, dst.id, src_pos, dst_pos, token)
        if link.label:
            edge.middle_label_text(link.label)
        if link.color:
            edge.color = link.color
        self.wireless_edges[token] = edge
        src.wireless_edges.add(edge)
        dst.wireless_edges.add(edge)
        self.tag_raise(src.id)
        self.tag_raise(dst.id)
        # update arcs when there are multiple links
        common_edges = list(src.wireless_edges & dst.wireless_edges)
        arc_edges(common_edges)

    def delete_wireless_edge(
        self, src: CanvasNode, dst: CanvasNode, link: core_pb2.Link
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
        self, src: CanvasNode, dst: CanvasNode, link: core_pb2.Link
    ) -> None:
        if not link.label:
            return
        network_id = link.network_id if link.network_id else None
        token = create_edge_token(src.id, dst.id, network_id)
        edge = self.wireless_edges[token]
        edge.middle_label_text(link.label)

    def draw_session(self, session: core_pb2.Session):
        """
        Draw existing session.
        """
        # draw existing nodes
        for core_node in session.nodes:
            logging.debug("drawing node %s", core_node)
            # peer to peer node is not drawn on the GUI
            if NodeUtils.is_ignore_node(core_node.type):
                continue
            image = NodeUtils.node_image(
                core_node, self.app.guiconfig, self.app.app_scale
            )
            # if the gui can't find node's image, default to the "edit-node" image
            if not image:
                image = Images.get(
                    ImageEnum.EDITNODE, int(ICON_SIZE * self.app.app_scale)
                )
            x = core_node.position.x
            y = core_node.position.y
            node = CanvasNode(self.master, x, y, core_node, image)
            self.nodes[node.id] = node
            self.core.canvas_nodes[core_node.id] = node

        # draw existing links
        for link in session.links:
            logging.debug("drawing link: %s", link)
            canvas_node_one = self.core.canvas_nodes[link.node_one_id]
            node_one = canvas_node_one.core_node
            canvas_node_two = self.core.canvas_nodes[link.node_two_id]
            node_two = canvas_node_two.core_node
            token = create_edge_token(canvas_node_one.id, canvas_node_two.id)

            if link.type == core_pb2.LinkType.WIRELESS:
                self.add_wireless_edge(canvas_node_one, canvas_node_two)
            else:
                if token not in self.edges:
                    src_pos = (node_one.position.x, node_one.position.y)
                    dst_pos = (node_two.position.x, node_two.position.y)
                    edge = CanvasEdge(self, canvas_node_one.id, src_pos, dst_pos)
                    edge.token = token
                    edge.dst = canvas_node_two.id
                    edge.set_link(link)
                    edge.check_wireless()
                    canvas_node_one.edges.add(edge)
                    canvas_node_two.edges.add(edge)
                    self.edges[edge.token] = edge
                    self.core.links[edge.token] = edge
                    if link.HasField("interface_one"):
                        canvas_node_one.interfaces.append(link.interface_one)
                        edge.src_interface = link.interface_one
                    if link.HasField("interface_two"):
                        canvas_node_two.interfaces.append(link.interface_two)
                        edge.dst_interface = link.interface_two
                elif link.options.unidirectional:
                    edge = self.edges[token]
                    edge.asymmetric_link = link
                else:
                    logging.error("duplicate link received: %s", link)

        # raise the nodes so they on top of the links
        self.tag_raise(tags.NODE)

    def stopped_session(self):
        # clear wireless edges
        for edge in self.wireless_edges.values():
            edge.delete()
            src_node = self.nodes[edge.src]
            src_node.wireless_edges.remove(edge)
            dst_node = self.nodes[edge.dst]
            dst_node.wireless_edges.remove(edge)
        self.wireless_edges.clear()

        # clear all middle edge labels
        for edge in self.edges.values():
            edge.reset()

    def canvas_xy(self, event: tk.Event) -> [float, float]:
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

    def click_release(self, event: tk.Event):
        """
        Draw a node or finish drawing an edge according to the current graph mode
        """
        logging.debug("click release")
        x, y = self.canvas_xy(event)
        if not self.inside_canvas(x, y):
            return

        if self.context:
            self.hide_context()
        else:
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
                logging.debug(
                    f"click release selected({self.selected}) mode({self.mode})"
                )
                if self.mode == GraphMode.EDGE:
                    self.handle_edge_release(event)
                elif self.mode == GraphMode.NODE:
                    self.add_node(x, y)
                elif self.mode == GraphMode.PICKNODE:
                    self.mode = GraphMode.NODE
        self.selected = None

    def handle_edge_release(self, event: tk.Event):
        edge = self.drawing_edge
        self.drawing_edge = None

        # not drawing edge return
        if edge is None:
            return

        # edge dst must be a node
        logging.debug("current selected: %s", self.selected)
        dst_node = self.nodes.get(self.selected)
        if not dst_node:
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

        # set dst node and snap edge to center
        edge.complete(self.selected)

        self.edges[edge.token] = edge
        node_src = self.nodes[edge.src]
        node_src.edges.add(edge)
        node_dst = self.nodes[edge.dst]
        node_dst.edges.add(edge)
        self.core.create_link(edge, node_src, node_dst)

    def select_object(self, object_id: int, choose_multiple: bool = False):
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

    def clear_selection(self):
        """
        Clear current selection boxes.
        """
        for _id in self.selection.values():
            self.delete(_id)
        self.selection.clear()

    def move_selection(self, object_id: int, x_offset: float, y_offset: float):
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
                    self.edges.pop(edge.token, None)
                    edge.delete()

                    # update node connected to edge being deleted
                    other_id = edge.src
                    other_interface = edge.src_interface
                    if edge.src == object_id:
                        other_id = edge.dst
                        other_interface = edge.dst_interface
                    other_node = self.nodes[other_id]
                    other_node.edges.remove(edge)
                    try:
                        other_node.interfaces.remove(other_interface)
                    except ValueError:
                        pass
                    if is_wireless:
                        other_node.delete_antenna()

            # delete shape
            if object_id in self.shapes:
                shape = self.shapes.pop(object_id)
                shape.delete()

        self.selection.clear()
        self.core.delete_graph_nodes(nodes)

    def zoom(self, event: tk.Event, factor: float = None):
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
        logging.info("ratio: %s", self.ratio)
        logging.info("offset: %s", self.offset)
        self.app.statusbar.zoom.config(text="%s" % (int(self.ratio * 100)) + "%")

        if self.wallpaper:
            self.redraw_wallpaper()

    def click_press(self, event: tk.Event):
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

        if self.mode == GraphMode.ANNOTATION:
            if is_marker(self.annotation_type):
                r = self.app.toolbar.marker_tool.radius
                self.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    fill=self.app.toolbar.marker_tool.color,
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

    def ctrl_click(self, event: tk.Event):
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

    def click_motion(self, event: tk.Event):
        """
        Redraw drawing edge according to the current position of the mouse
        """
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
            elif is_marker(self.annotation_type):
                r = self.app.toolbar.marker_tool.radius
                self.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    fill=self.app.toolbar.marker_tool.color,
                    outline="",
                    tags=(tags.MARKER, tags.ANNOTATION),
                )
            return

        if self.mode == GraphMode.EDGE:
            return

        # move selected objects
        if self.selection:
            for selected_id in self.selection:
                if selected_id in self.shapes:
                    shape = self.shapes[selected_id]
                    shape.motion(x_offset, y_offset)

                if selected_id in self.nodes:
                    node = self.nodes[selected_id]
                    node.motion(x_offset, y_offset, update=self.core.is_runtime())
        else:
            if self.select_box and self.mode == GraphMode.SELECT:
                self.select_box.shape_motion(x, y)

    def click_context(self, event: tk.Event):
        logging.info("context: %s", self.context)
        if not self.context:
            selected = self.get_selected(event)
            canvas_node = self.nodes.get(selected)
            if canvas_node:
                logging.debug("node context: %s", selected)
                self.context = canvas_node.create_context()
                self.context.bind("<Unmap>", self.hide_context)
                self.context.post(event.x_root, event.y_root)
        else:
            self.hide_context()

    def press_delete(self, event: tk.Event):
        """
        delete selected nodes and any data that relates to it
        """
        logging.debug("press delete key")
        if not self.app.core.is_runtime():
            self.delete_selected_objects()
        else:
            logging.info("node deletion is disabled during runtime state")

    def double_click(self, event: tk.Event):
        selected = self.get_selected(event)
        if selected is not None and selected in self.shapes:
            shape = self.shapes[selected]
            dialog = ShapeDialog(self.app, self.app, shape)
            dialog.show()

    def add_node(self, x: float, y: float) -> CanvasNode:
        if self.selected is None or self.selected in self.shapes:
            actual_x, actual_y = self.get_actual_coords(x, y)
            core_node = self.core.create_node(
                actual_x, actual_y, self.node_draw.node_type, self.node_draw.model
            )
            try:
                self.node_draw.image = Images.get(
                    self.node_draw.image_enum, int(ICON_SIZE * self.app.app_scale)
                )
            except AttributeError:
                self.node_draw.image = Images.get_custom(
                    self.node_draw.image_file, int(ICON_SIZE * self.app.app_scale)
                )
            node = CanvasNode(self.master, x, y, core_node, self.node_draw.image)
            self.core.canvas_nodes[core_node.id] = node
            self.nodes[node.id] = node
            return node

    def width_and_height(self):
        """
        retrieve canvas width and height in pixels
        """
        x0, y0, x1, y1 = self.coords(self.grid)
        canvas_w = abs(x0 - x1)
        canvas_h = abs(y0 - y1)
        return canvas_w, canvas_h

    def get_wallpaper_image(self) -> Image.Image:
        width = int(self.wallpaper.width * self.ratio)
        height = int(self.wallpaper.height * self.ratio)
        image = self.wallpaper.resize((width, height), Image.ANTIALIAS)
        return image

    def draw_wallpaper(
        self, image: ImageTk.PhotoImage, x: float = None, y: float = None
    ):
        if x is None and y is None:
            x1, y1, x2, y2 = self.bbox(self.grid)
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2
        self.wallpaper_id = self.create_image((x, y), image=image, tags=tags.WALLPAPER)
        self.wallpaper_drawn = image

    def wallpaper_upper_left(self):
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
        image = ImageTk.PhotoImage(cropped)

        # draw on canvas
        x1, y1, _, _ = self.bbox(self.grid)
        x = (cropx / 2) + x1
        y = (cropy / 2) + y1
        self.draw_wallpaper(image, x, y)

    def wallpaper_center(self):
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
        image = ImageTk.PhotoImage(cropped)
        self.draw_wallpaper(image)

    def wallpaper_scaled(self):
        """
        scale image based on canvas dimension
        """
        self.delete(self.wallpaper_id)
        canvas_w, canvas_h = self.width_and_height()
        image = self.wallpaper.resize((int(canvas_w), int(canvas_h)), Image.ANTIALIAS)
        image = ImageTk.PhotoImage(image)
        self.draw_wallpaper(image)

    def resize_to_wallpaper(self):
        self.delete(self.wallpaper_id)
        image = ImageTk.PhotoImage(self.wallpaper)
        self.redraw_canvas((image.width(), image.height()))
        self.draw_wallpaper(image)

    def redraw_canvas(self, dimensions: Tuple[int, int] = None):
        logging.info("redrawing canvas to dimensions: %s", dimensions)

        # reset scale and move back to original position
        logging.info("resetting scaling: %s %s", self.ratio, self.offset)
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

    def redraw_wallpaper(self):
        if self.adjust_to_dim.get():
            logging.info("drawing wallpaper to canvas dimensions")
            self.resize_to_wallpaper()
        else:
            option = ScaleOption(self.scale_option.get())
            logging.info("drawing canvas using scaling option: %s", option)
            if option == ScaleOption.UPPER_LEFT:
                self.wallpaper_upper_left()
            elif option == ScaleOption.CENTERED:
                self.wallpaper_center()
            elif option == ScaleOption.SCALED:
                self.wallpaper_scaled()
            elif option == ScaleOption.TILED:
                logging.warning("tiled background not implemented yet")

        # raise items above wallpaper
        for component in tags.ABOVE_WALLPAPER_TAGS:
            self.tag_raise(component)

    def set_wallpaper(self, filename: str):
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

    def create_edge(self, source: CanvasNode, dest: CanvasNode):
        """
        create an edge between source node and destination node
        """
        token = create_edge_token(source.id, dest.id)
        if token not in self.edges:
            pos = (source.core_node.position.x, source.core_node.position.y)
            edge = CanvasEdge(self, source.id, pos, pos)
            edge.complete(dest.id)
            self.edges[edge.token] = edge
            self.nodes[source.id].edges.add(edge)
            self.nodes[dest.id].edges.add(edge)
            self.core.create_link(edge, source, dest)

    def copy(self):
        if self.app.core.is_runtime():
            logging.info("copy is disabled during runtime state")
            return
        if self.selection:
            logging.debug("to copy %s nodes", len(self.selection))
            self.to_copy = self.selection.keys()

    def paste(self):
        if self.app.core.is_runtime():
            logging.info("paste is disabled during runtime state")
            return
        # maps original node canvas id to copy node canvas id
        copy_map = {}
        # the edges that will be copy over
        to_copy_edges = []
        for canvas_nid in self.to_copy:
            core_node = self.nodes[canvas_nid].core_node
            actual_x = core_node.position.x + 50
            actual_y = core_node.position.y + 50
            scaled_x, scaled_y = self.get_scaled_coords(actual_x, actual_y)

            copy = self.core.create_node(
                actual_x, actual_y, core_node.type, core_node.model
            )
            node = CanvasNode(
                self.master, scaled_x, scaled_y, copy, self.nodes[canvas_nid].image
            )

            # add new node to modified_service_nodes set if that set contains the
            # to_copy node
            if self.app.core.service_been_modified(core_node.id):
                self.app.core.modified_service_nodes.add(copy.id)

            copy_map[canvas_nid] = node.id
            self.core.canvas_nodes[copy.id] = node
            self.nodes[node.id] = node
            self.core.copy_node_config(core_node.id, copy.id)

            edges = self.nodes[canvas_nid].edges
            for edge in edges:
                if edge.src not in self.to_copy or edge.dst not in self.to_copy:
                    if canvas_nid == edge.src:
                        self.create_edge(node, self.nodes[edge.dst])
                    elif canvas_nid == edge.dst:
                        self.create_edge(self.nodes[edge.src], node)
                else:
                    to_copy_edges.append(edge)
        # copy link and link config
        for edge in to_copy_edges:
            source_node_copy = self.nodes[copy_map[edge.token[0]]]
            dest_node_copy = self.nodes[copy_map[edge.token[1]]]
            self.create_edge(source_node_copy, dest_node_copy)
            copy_edge = self.edges[
                create_edge_token(source_node_copy.id, dest_node_copy.id)
            ]
            copy_link = copy_edge.link
            options = edge.link.options
            copy_link.options.CopyFrom(options)
            interface_one = None
            if copy_link.HasField("interface_one"):
                interface_one = copy_link.interface_one.id
            interface_two = None
            if copy_link.HasField("interface_two"):
                interface_two = copy_link.interface_two.id
            if not options.unidirectional:
                copy_edge.asymmetric_link = None
            else:
                asym_interface_one = None
                if interface_one:
                    asym_interface_one = core_pb2.Interface(id=interface_one)
                asym_interface_two = None
                if interface_two:
                    asym_interface_two = core_pb2.Interface(id=interface_two)
                copy_edge.asymmetric_link = core_pb2.Link(
                    node_one_id=copy_link.node_two_id,
                    node_two_id=copy_link.node_one_id,
                    interface_one=asym_interface_one,
                    interface_two=asym_interface_two,
                    options=edge.asymmetric_link.options,
                )
            self.itemconfig(
                copy_edge.id,
                width=self.itemcget(edge.id, "width"),
                fill=self.itemcget(edge.id, "fill"),
            )

    def scale_graph(self):
        for nid, canvas_node in self.nodes.items():
            img = None
            if NodeUtils.is_custom(
                canvas_node.core_node.type, canvas_node.core_node.model
            ):
                for custom_node in self.app.guiconfig["nodes"]:
                    if custom_node["name"] == canvas_node.core_node.model:
                        img = Images.get_custom(
                            custom_node["image"], int(ICON_SIZE * self.app.app_scale)
                        )
            else:
                image_enum = TypeToImage.get(
                    canvas_node.core_node.type, canvas_node.core_node.model
                )
                img = Images.get(image_enum, int(ICON_SIZE * self.app.app_scale))

            self.itemconfig(nid, image=img)
            canvas_node.image = img
            canvas_node.scale_text()
            canvas_node.scale_antennas()

            for edge_id in self.find_withtag(tags.EDGE):
                self.itemconfig(edge_id, width=int(EDGE_WIDTH * self.app.app_scale))
