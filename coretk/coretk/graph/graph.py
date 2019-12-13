import logging
import tkinter as tk

from PIL import Image, ImageTk

from core.api.grpc import core_pb2
from coretk import nodeutils
from coretk.dialogs.shapemod import ShapeDialog
from coretk.graph import tags
from coretk.graph.edges import CanvasEdge, CanvasWirelessEdge
from coretk.graph.enums import GraphMode, ScaleOption
from coretk.graph.linkinfo import LinkInfo, Throughput
from coretk.graph.node import CanvasNode
from coretk.graph.shape import Shape
from coretk.graph.shapeutils import ShapeType, is_draw_shape
from coretk.images import Images
from coretk.nodeutils import NodeUtils

ZOOM_IN = 1.1
ZOOM_OUT = 0.9


class CanvasGraph(tk.Canvas):
    def __init__(self, master, core, width, height):
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
        self.drawing_edge = None
        self.grid = None
        self.throughput_draw = Throughput(self, core)
        self.shape_drawing = False
        self.default_dimensions = (width, height)
        self.current_dimensions = self.default_dimensions
        self.ratio = 1.0
        self.offset = (0, 0)
        self.cursor = (0, 0)

        # background related
        self.wallpaper_id = None
        self.wallpaper = None
        self.wallpaper_drawn = None
        self.wallpaper_file = ""
        self.scale_option = tk.IntVar(value=1)
        self.show_grid = tk.BooleanVar(value=True)
        self.adjust_to_dim = tk.BooleanVar(value=False)

        # bindings
        self.setup_bindings()

        # draw base canvas
        self.draw_canvas()
        self.draw_grid()

    def draw_canvas(self, dimensions=None):
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

    def reset_and_redraw(self, session):
        """
        Reset the private variables CanvasGraph object, redraw nodes given the new grpc
        client.

        :param core.api.grpc.core_pb2.Session session: session to draw
        :return: nothing
        """
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
        self.drawing_edge = None
        self.draw_session(session)

    def setup_bindings(self):
        """
        Bind any mouse events or hot keys to the matching action

        :return: nothing
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

    def get_actual_coords(self, x, y):
        actual_x = (x - self.offset[0]) / self.ratio
        actual_y = (y - self.offset[1]) / self.ratio
        return actual_x, actual_y

    def get_scaled_coords(self, x, y):
        scaled_x = (x * self.ratio) + self.offset[0]
        scaled_y = (y * self.ratio) + self.offset[1]
        return scaled_x, scaled_y

    def inside_canvas(self, x, y):
        x1, y1, x2, y2 = self.bbox(self.grid)
        valid_x = x1 <= x <= x2
        valid_y = y1 <= y <= y2
        return valid_x and valid_y

    def valid_position(self, x1, y1, x2, y2):
        valid_topleft = self.inside_canvas(x1, y1)
        valid_bottomright = self.inside_canvas(x2, y2)
        return valid_topleft and valid_bottomright

    def draw_grid(self):
        """
        Create grid.

        :return: nothing
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

    def add_wireless_edge(self, src, dst):
        """
        add a wireless edge between 2 canvas nodes

        :param CanvasNode src: source node
        :param CanvasNode dst: destination node
        :return: nothing
        """
        token = tuple(sorted((src.id, dst.id)))
        x1, y1 = self.coords(src.id)
        x2, y2 = self.coords(dst.id)
        position = (x1, y1, x2, y2)
        edge = CanvasWirelessEdge(token, position, src.id, dst.id, self)
        self.wireless_edges[token] = edge
        src.wireless_edges.add(edge)
        dst.wireless_edges.add(edge)
        self.tag_raise(src.id)
        self.tag_raise(dst.id)

    def delete_wireless_edge(self, src, dst):
        token = tuple(sorted((src.id, dst.id)))
        edge = self.wireless_edges.pop(token)
        edge.delete()
        src.wireless_edges.remove(edge)
        dst.wireless_edges.remove(edge)

    def draw_session(self, session):
        """
        Draw existing session.

        :return: nothing
        """
        # draw existing nodes
        for core_node in session.nodes:
            logging.info("drawing core node: %s", core_node)
            # peer to peer node is not drawn on the GUI
            if NodeUtils.is_ignore_node(core_node.type):
                continue

            # draw nodes on the canvas
            image = NodeUtils.node_icon(core_node.type, core_node.model)
            if core_node.icon:
                try:
                    image = Images.create(core_node.icon, nodeutils.ICON_SIZE)
                except OSError:
                    logging.error("invalid icon: %s", core_node.icon)

            x = core_node.position.x
            y = core_node.position.y
            node = CanvasNode(self.master, x, y, core_node, image)
            self.nodes[node.id] = node
            self.core.canvas_nodes[core_node.id] = node

        # draw existing links
        for link in session.links:
            canvas_node_one = self.core.canvas_nodes[link.node_one_id]
            node_one = canvas_node_one.core_node
            canvas_node_two = self.core.canvas_nodes[link.node_two_id]
            node_two = canvas_node_two.core_node
            if link.type == core_pb2.LinkType.WIRELESS:
                self.add_wireless_edge(canvas_node_one, canvas_node_two)
            else:
                edge = CanvasEdge(
                    node_one.position.x,
                    node_one.position.y,
                    node_two.position.x,
                    node_two.position.y,
                    canvas_node_one.id,
                    self,
                )
                edge.token = tuple(sorted((canvas_node_one.id, canvas_node_two.id)))
                edge.dst = canvas_node_two.id
                edge.check_wireless()
                canvas_node_one.edges.add(edge)
                canvas_node_two.edges.add(edge)
                self.edges[edge.token] = edge
                self.core.links[edge.token] = link
                edge.link_info = LinkInfo(self, edge, link)
                if link.HasField("interface_one"):
                    canvas_node_one.interfaces.append(link.interface_one)
                if link.HasField("interface_two"):
                    canvas_node_two.interfaces.append(link.interface_two)

        # raise the nodes so they on top of the links
        self.tag_raise(tags.NODE)

    def canvas_xy(self, event):
        """
        Convert window coordinate to canvas coordinate

        :param event:
        :rtype: (int, int)
        :return: x, y canvas coordinate
        """
        x = self.canvasx(event.x)
        y = self.canvasy(event.y)
        return x, y

    def get_selected(self, event):
        """
        Retrieve the item id that is on the mouse position

        :param event: mouse event
        :rtype: int
        :return: the item that the mouse point to
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

    def click_release(self, event):
        """
        Draw a node or finish drawing an edge according to the current graph mode

        :param event: mouse event
        :return: nothing
        """
        logging.debug("click release")
        x, y = self.canvas_xy(event)
        if not self.inside_canvas(x, y):
            return

        if self.context:
            self.context.unpost()
            self.context = None
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

    def handle_edge_release(self, event):
        edge = self.drawing_edge
        self.drawing_edge = None

        # not drawing edge return
        if edge is None:
            return

        # edge dst must be a node
        logging.debug(f"current selected: {self.selected}")
        dst_node = self.nodes.get(self.selected)
        if not dst_node:
            edge.delete()
            return

        # edge dst is same as src, delete edge
        if edge.src == self.selected:
            edge.delete()
            return

        # ignore repeated edges
        token = tuple(sorted((edge.src, self.selected)))
        if token in self.edges:
            edge.delete()
            return

        # set dst node and snap edge to center
        edge.complete(self.selected)
        logging.debug("drawing edge token: %s", edge.token)

        self.edges[edge.token] = edge
        node_src = self.nodes[edge.src]
        node_src.edges.add(edge)
        node_dst = self.nodes[edge.dst]
        node_dst.edges.add(edge)
        link = self.core.create_link(edge, node_src, node_dst)
        edge.link_info = LinkInfo(self, edge, link)

    def select_object(self, object_id, choose_multiple=False):
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

        :return: nothing
        """
        for _id in self.selection.values():
            self.delete(_id)
        self.selection.clear()

    def move_selection(self, object_id, x_offset, y_offset):
        select_id = self.selection.get(object_id)
        if select_id is not None:
            self.move(select_id, x_offset, y_offset)

    def delete_selection_objects(self):
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
                    self.throughput_draw.delete(edge)
                    del self.edges[edge.token]
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
        return nodes

    def zoom(self, event, factor=None):
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
        if self.wallpaper:
            self.redraw_wallpaper()

    def click_press(self, event):
        """
        Start drawing an edge if mouse click is on a node

        :param event: mouse event
        :return: nothing
        """
        x, y = self.canvas_xy(event)
        if not self.inside_canvas(x, y):
            return

        self.cursor = x, y
        selected = self.get_selected(event)
        logging.debug("click press(%s): %s", self.cursor, selected)
        x_check = self.cursor[0] - self.offset[0]
        y_check = self.cursor[1] - self.offset[1]
        logging.debug("clock press ofset(%s, %s)", x_check, y_check)
        is_node = selected in self.nodes
        if self.mode == GraphMode.EDGE and is_node:
            x, y = self.coords(selected)
            self.drawing_edge = CanvasEdge(x, y, x, y, selected, self)

        if self.mode == GraphMode.ANNOTATION and selected is None:
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
                    logging.info(
                        "selected coords: (%s, %s)",
                        node.core_node.position.x,
                        node.core_node.position.y,
                    )
        else:
            logging.debug("create selection box")
            if self.mode == GraphMode.SELECT:
                shape = Shape(self.app, self, ShapeType.RECTANGLE, x, y)
                self.select_box = shape
            self.clear_selection()

    def ctrl_click(self, event):
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

    def click_motion(self, event):
        """
        Redraw drawing edge according to the current position of the mouse

        :param event: mouse event
        :return: nothing
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
            x1, y1, _, _ = self.coords(self.drawing_edge.id)
            self.coords(self.drawing_edge.id, x1, y1, x, y)
        if self.mode == GraphMode.ANNOTATION:
            if is_draw_shape(self.annotation_type) and self.shape_drawing:
                shape = self.shapes[self.selected]
                shape.shape_motion(x, y)

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

    def click_context(self, event):
        logging.info("context event: %s", self.context)
        if not self.context:
            selected = self.get_selected(event)
            canvas_node = self.nodes.get(selected)
            if canvas_node:
                logging.debug(f"node context: {selected}")
                self.context = canvas_node.create_context()
                self.context.post(event.x_root, event.y_root)
        else:
            self.context.unpost()
            self.context = None

    def press_delete(self, event):
        """
        delete selected nodes and any data that relates to it
        :param event:
        :return:
        """
        logging.debug("press delete key")
        nodes = self.delete_selection_objects()
        self.core.delete_graph_nodes(nodes)

    def double_click(self, event):
        selected = self.get_selected(event)
        if selected is not None and selected in self.shapes:
            shape = self.shapes[selected]
            dialog = ShapeDialog(self.app, self.app, shape)
            dialog.show()

    def add_node(self, x, y):
        if self.selected is None or self.selected in self.shapes:
            actual_x, actual_y = self.get_actual_coords(x, y)
            core_node = self.core.create_node(
                int(actual_x),
                int(actual_y),
                self.node_draw.node_type,
                self.node_draw.model,
            )
            node = CanvasNode(self.master, x, y, core_node, self.node_draw.image)
            self.core.canvas_nodes[core_node.id] = node
            self.nodes[node.id] = node
            return node

    def width_and_height(self):
        """
        retrieve canvas width and height in pixels

        :return: nothing
        """
        x0, y0, x1, y1 = self.coords(self.grid)
        canvas_w = abs(x0 - x1)
        canvas_h = abs(y0 - y1)
        return canvas_w, canvas_h

    def get_wallpaper_image(self):
        width = int(self.wallpaper.width * self.ratio)
        height = int(self.wallpaper.height * self.ratio)
        image = self.wallpaper.resize((width, height), Image.ANTIALIAS)
        return image

    def draw_wallpaper(self, image, x=None, y=None):
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

        :return: nothing
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

        :return: nothing
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

    def redraw_canvas(self, dimensions=None):
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
        self.update_grid()

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

    def update_grid(self):
        logging.info("updating grid show: %s", self.show_grid.get())
        if self.show_grid.get():
            self.itemconfig(tags.GRIDLINE, state=tk.NORMAL)
        else:
            self.itemconfig(tags.GRIDLINE, state=tk.HIDDEN)

    def set_wallpaper(self, filename):
        logging.info("setting wallpaper: %s", filename)
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

    def is_selection_mode(self):
        return self.mode == GraphMode.SELECT

    def create_edge(self, source, dest):
        """
        create an edge between source node and destination node

        :param CanvasNode source: source node
        :param CanvasNode dest: destination node
        :return: nothing
        """
        if tuple([source.id, dest.id]) not in self.edges:
            pos0 = source.core_node.position
            x0 = pos0.x
            y0 = pos0.y
            edge = CanvasEdge(x0, y0, x0, y0, source.id, self)
            edge.complete(dest.id)
            self.edges[edge.token] = edge
            self.nodes[source.id].edges.add(edge)
            self.nodes[dest.id].edges.add(edge)
            link = self.core.create_link(edge, source, dest)
            edge.link_info = LinkInfo(self, edge, link)
