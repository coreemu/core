import logging
import tkinter as tk

from PIL import Image, ImageTk

from core.api.grpc import core_pb2
from core.api.grpc.core_pb2 import NodeType
from coretk.dialogs.shapemod import ShapeDialog
from coretk.graph.edges import CanvasEdge, CanvasWirelessEdge
from coretk.graph.enums import GraphMode, ScaleOption
from coretk.graph.graph_helper import GraphHelper
from coretk.graph.linkinfo import LinkInfo, Throughput
from coretk.graph.node import CanvasNode
from coretk.graph.shape import Shape
from coretk.images import ImageEnum, Images
from coretk.nodeutils import NodeUtils

ABOVE_WALLPAPER = ["edge", "linkinfo", "wireless", "antenna", "nodename", "node"]


class CanvasGraph(tk.Canvas):
    def __init__(self, master, core, width, height, cnf=None, **kwargs):
        if cnf is None:
            cnf = {}
        kwargs["highlightthickness"] = 0
        super().__init__(master, cnf, **kwargs)
        self.app = master
        self.mode = GraphMode.SELECT
        self.annotation_type = None
        self.selection = {}
        self.selected = None
        self.node_draw = None
        self.context = None
        self.nodes = {}
        self.edges = {}
        self.shapes = {}
        self.texts = {}
        self.wireless_edges = {}
        self.drawing_edge = None
        self.grid = None
        self.setup_bindings()
        self.draw_grid(width, height)
        self.core = core
        self.helper = GraphHelper(self, core)
        self.throughput_draw = Throughput(self, core)
        self.shape_drawing = False

        # background related
        self.wallpaper_id = None
        self.wallpaper = None
        self.wallpaper_drawn = None
        self.wallpaper_file = ""
        self.scale_option = tk.IntVar(value=1)
        self.show_grid = tk.BooleanVar(value=True)
        self.adjust_to_dim = tk.BooleanVar(value=False)

    def create_node_context(self, canvas_node):
        node = canvas_node.core_node
        context = tk.Menu(self.master)
        context.add_command(label="Configure", command=canvas_node.show_config)
        if node.type == NodeType.WIRELESS_LAN:
            context.add_command(
                label="WLAN Config", command=canvas_node.show_wlan_config
            )
            if self.master.core.is_runtime():
                if canvas_node.core_node.id in self.master.core.mobility_players:
                    context.add_command(
                        label="Mobility Player",
                        command=canvas_node.show_mobility_player,
                    )
            else:
                context.add_command(
                    label="Mobility Config", command=canvas_node.show_mobility_config
                )
        if node.type == NodeType.EMANE:
            context.add_command(
                label="EMANE Config", command=canvas_node.show_emane_config
            )
        context.add_command(label="Select adjacent", state=tk.DISABLED)
        context.add_command(label="Create link to", state=tk.DISABLED)
        context.add_command(label="Assign to", state=tk.DISABLED)
        context.add_command(label="Move to", state=tk.DISABLED)
        context.add_command(label="Cut", state=tk.DISABLED)
        context.add_command(label="Copy", state=tk.DISABLED)
        context.add_command(label="Paste", state=tk.DISABLED)
        context.add_command(label="Delete", state=tk.DISABLED)
        context.add_command(label="Hide", state=tk.DISABLED)
        context.add_command(label="Services", state=tk.DISABLED)
        return context

    def reset_and_redraw(self, session):
        """
        Reset the private variables CanvasGraph object, redraw nodes given the new grpc
        client.

        :param core.api.grpc.core_pb2.Session session: session to draw
        :return: nothing
        """
        # delete any existing drawn items
        self.helper.delete_canvas_components()

        # set the private variables to default value
        self.mode = GraphMode.SELECT
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
        self.bind("<Button-3>", self.click_context)
        self.bind("<Delete>", self.press_delete)
        self.bind("<Control-1>", self.ctrl_click)
        self.bind("<Double-Button-1>", self.double_click)

    def draw_grid(self, width=1000, height=800):
        """
        Create grid

        :param int width: the width
        :param int height: the height

        :return: nothing
        """
        self.grid = self.create_rectangle(
            0,
            0,
            width,
            height,
            outline="#000000",
            fill="#ffffff",
            width=1,
            tags="rectangle",
        )
        for i in range(0, width, 27):
            self.create_line(i, 0, i, height, dash=(2, 4), tags="gridline")
        for i in range(0, height, 27):
            self.create_line(0, i, width, i, dash=(2, 4), tags="gridline")
        self.tag_lower("gridline")
        self.tag_lower(self.grid)

    def add_wireless_edge(self, src, dst):
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
            # peer to peer node is not drawn on the GUI
            if NodeUtils.is_ignore_node(core_node.type):
                continue

            # draw nodes on the canvas
            image = NodeUtils.node_icon(core_node.type, core_node.model)
            node = CanvasNode(self.master, core_node, image)
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
                is_node_one_wireless = NodeUtils.is_wireless_node(node_one.type)
                is_node_two_wireless = NodeUtils.is_wireless_node(node_two.type)
                has_no_wireless = not (is_node_one_wireless or is_node_two_wireless)
                edge = CanvasEdge(
                    node_one.position.x,
                    node_one.position.y,
                    node_two.position.x,
                    node_two.position.y,
                    canvas_node_one.id,
                    self,
                    is_wired=has_no_wireless,
                )
                edge.token = tuple(sorted((canvas_node_one.id, canvas_node_two.id)))
                edge.dst = canvas_node_two.id
                canvas_node_one.edges.add(edge)
                canvas_node_two.edges.add(edge)
                self.edges[edge.token] = edge
                self.core.links[edge.token] = link
                self.helper.redraw_antenna(canvas_node_one, canvas_node_two)
                edge.link_info = LinkInfo(self, edge, link)
                if link.HasField("interface_one"):
                    canvas_node_one.interfaces.append(link.interface_one)
                if link.HasField("interface_two"):
                    canvas_node_two.interfaces.append(link.interface_two)

        # raise the nodes so they on top of the links
        self.tag_raise("node")

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
        overlapping = self.find_overlapping(event.x, event.y, event.x, event.y)
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
        if self.context:
            self.context.unpost()
            self.context = None
        else:
            if self.mode == GraphMode.ANNOTATION:
                if self.annotation_type in [ImageEnum.OVAL, ImageEnum.RECTANGLE]:
                    self.focus_set()
                    x, y = self.canvas_xy(event)
                    if self.shape_drawing:
                        self.shapes[self.selected].shape_complete(x, y)
                        self.shape_drawing = False
                elif self.annotation_type == ImageEnum.TEXT:
                    self.text.shape_complete(self.text.cursor_x, self.text.cursor_y)
            else:
                self.focus_set()
                self.selected = self.get_selected(event)
                logging.debug(
                    f"click release selected({self.selected}) mode({self.mode})"
                )
                if self.mode == GraphMode.EDGE:
                    self.handle_edge_release(event)
                elif self.mode == GraphMode.NODE:
                    x, y = self.canvas_xy(event)
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

        # set dst node and snap edge to center
        x, y = self.coords(self.selected)
        edge.complete(self.selected, x, y)
        logging.debug(f"drawing edge token: {edge.token}")
        if edge.token in self.edges:
            edge.delete()
        else:
            self.edges[edge.token] = edge
            node_src = self.nodes[edge.src]
            node_src.edges.add(edge)
            node_dst = self.nodes[edge.dst]
            node_dst.edges.add(edge)
            link = self.core.create_link(edge, node_src, node_dst)
            edge.link_info = LinkInfo(self, edge, link)
        logging.debug(f"edges: {self.find_withtag('edge')}")

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
                tags="selectednodes",
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

    def object_drag(self, object_id, offset_x, offset_y):
        select_id = self.selection.get(object_id)
        if select_id is not None:
            self.move(select_id, offset_x, offset_y)

    def delete_selection_objects(self):
        edges = set()
        nodes = []
        for object_id in self.selection:
            if object_id in self.nodes:
                selection_id = self.selection[object_id]
                canvas_node = self.nodes.pop(object_id)
                nodes.append(canvas_node)
                self.delete(object_id)
                self.delete(selection_id)
                self.delete(canvas_node.text_id)

                # delete antennas
                is_wireless = NodeUtils.is_wireless_node(canvas_node.core_node.type)
                if is_wireless:
                    canvas_node.antenna_draw.delete_antennas()

                # delete related edges
                for edge in canvas_node.edges:
                    if edge in edges:
                        continue
                    edges.add(edge)
                    self.edges.pop(edge.token)
                    self.delete(edge.id)
                    self.delete(edge.link_info.id1)
                    self.delete(edge.link_info.id2)
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
                        other_node.antenna_draw.delete_antenna()
            if object_id in self.shapes:
                selection_id = self.selection[object_id]
                self.shapes[object_id].delete()
                self.delete(selection_id)
                self.shapes.pop(object_id)

        self.selection.clear()
        return nodes

    def click_press(self, event):
        """
        Start drawing an edge if mouse click is on a node

        :param event: mouse event
        :return: nothing
        """
        logging.debug(f"click press: {event}")
        selected = self.get_selected(event)
        is_node = selected in self.nodes
        if self.mode == GraphMode.EDGE and is_node:
            x, y = self.coords(selected)
            self.drawing_edge = CanvasEdge(x, y, x, y, selected, self)

        if self.mode == GraphMode.ANNOTATION and selected is None:
            if self.annotation_type in [ImageEnum.OVAL, ImageEnum.RECTANGLE]:
                x, y = self.canvas_xy(event)
                shape = Shape(self.app, self, x, y)
                self.selected = shape.id
                self.shapes[shape.id] = shape
                self.shape_drawing = True
            elif self.annotation_type == ImageEnum.TEXT:
                x, y = self.canvas_xy(event)
                self.text = Shape(self.app, self, x, y)
                # self.shapes[shape.id] = shape

        if self.mode == GraphMode.SELECT:
            if selected is not None:
                if selected in self.shapes:
                    x, y = self.canvas_xy(event)
                    shape = self.shapes[selected]
                    shape.cursor_x = x
                    shape.cursor_y = y
                    if selected not in self.selection:
                        self.select_object(shape.id)
                    self.selected = selected
            else:
                self.clear_selection()

    def ctrl_click(self, event):
        logging.debug("control left click: %s", event)
        selected = self.get_selected(event)
        if (
            self.mode == GraphMode.SELECT
            and selected is not None
            and selected in self.shapes
        ):
            self.select_object(selected, choose_multiple=True)

    def click_motion(self, event):
        """
        Redraw drawing edge according to the current position of the mouse

        :param event: mouse event
        :return: nothing
        """
        if self.mode == GraphMode.EDGE and self.drawing_edge is not None:
            x2, y2 = self.canvas_xy(event)
            x1, y1, _, _ = self.coords(self.drawing_edge.id)
            self.coords(self.drawing_edge.id, x1, y1, x2, y2)
        if self.mode == GraphMode.ANNOTATION:
            if (
                self.annotation_type in [ImageEnum.OVAL, ImageEnum.RECTANGLE]
                and self.shape_drawing
            ):
                x, y = self.canvas_xy(event)
                self.shapes[self.selected].shape_motion(x, y)
        if (
            self.mode == GraphMode.SELECT
            and self.selected is not None
            and self.selected in self.shapes
        ):
            x, y = self.canvas_xy(event)
            shape = self.shapes[self.selected]
            delta_x = x - shape.cursor_x
            delta_y = y - shape.cursor_y
            shape.motion(event)

            # move other selected components
            for _id in self.selection:
                if _id != self.selected and _id in self.shapes:
                    shape = self.shapes[_id]
                    shape.motion(None, delta_x, delta_y)
                if _id != self.selected and _id in self.nodes:
                    node = self.nodes[_id]
                    node_x = node.core_node.position.x
                    node_y = node.core_node.position.y
                    node.move(node_x + delta_x, node_y + delta_y)

    def click_context(self, event):
        logging.info("context event: %s", self.context)
        if not self.context:
            selected = self.get_selected(event)
            canvas_node = self.nodes.get(selected)
            if canvas_node:
                logging.debug(f"node context: {selected}")
                self.context = self.create_node_context(canvas_node)
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
            core_node = self.core.create_node(
                int(x), int(y), self.node_draw.node_type, self.node_draw.model
            )
            node = CanvasNode(self.master, core_node, self.node_draw.image)
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

    def wallpaper_upper_left(self):
        tk_img = ImageTk.PhotoImage(self.wallpaper)
        # crop image if it is bigger than canvas
        canvas_w, canvas_h = self.width_and_height()
        cropx = img_w = tk_img.width()
        cropy = img_h = tk_img.height()
        if img_w > canvas_w:
            cropx -= img_w - canvas_w
        if img_h > canvas_h:
            cropy -= img_h - canvas_h
        cropped = self.wallpaper.crop((0, 0, cropx, cropy))
        cropped_tk = ImageTk.PhotoImage(cropped)
        self.delete(self.wallpaper_id)
        # place left corner of image to the left corner of the canvas
        self.wallpaper_id = self.create_image(
            (cropx / 2, cropy / 2), image=cropped_tk, tags="wallpaper"
        )
        self.wallpaper_drawn = cropped_tk

    def wallpaper_center(self):
        """
        place the image at the center of canvas

        :return: nothing
        """
        tk_img = ImageTk.PhotoImage(self.wallpaper)
        canvas_w, canvas_h = self.width_and_height()
        cropx = img_w = tk_img.width()
        cropy = img_h = tk_img.height()
        # dimension of the cropped image
        if img_w > canvas_w:
            cropx -= img_w - canvas_w
        if img_h > canvas_h:
            cropy -= img_h - canvas_h
        x0 = (img_w - cropx) / 2
        y0 = (img_h - cropy) / 2
        x1 = x0 + cropx
        y1 = y0 + cropy
        cropped = self.wallpaper.crop((x0, y0, x1, y1))
        cropped_tk = ImageTk.PhotoImage(cropped)
        # place the center of the image at the center of the canvas
        self.delete(self.wallpaper_id)
        self.wallpaper_id = self.create_image(
            (canvas_w / 2, canvas_h / 2), image=cropped_tk, tags="wallpaper"
        )
        self.wallpaper_drawn = cropped_tk

    def wallpaper_scaled(self):
        """
        scale image based on canvas dimension

        :return: nothing
        """
        canvas_w, canvas_h = self.width_and_height()
        image = Images.create(self.wallpaper_file, int(canvas_w), int(canvas_h))
        self.delete(self.wallpaper_id)
        self.wallpaper_id = self.create_image(
            (canvas_w / 2, canvas_h / 2), image=image, tags="wallpaper"
        )
        self.wallpaper_drawn = image

    def resize_to_wallpaper(self):
        image_tk = ImageTk.PhotoImage(self.wallpaper)
        img_w = image_tk.width()
        img_h = image_tk.height()
        self.delete(self.wallpaper_id)
        self.delete("rectangle")
        self.delete("gridline")
        self.draw_grid(img_w, img_h)
        self.wallpaper_id = self.create_image((img_w / 2, img_h / 2), image=image_tk)
        self.wallpaper_drawn = image_tk

    def redraw_grid(self, width, height):
        """
        redraw grid with new dimension

        :return: nothing
        """
        self.config(scrollregion=(0, 0, width + 200, height + 200))

        # delete previous grid
        self.delete("rectangle")
        self.delete("gridline")

        # redraw
        self.draw_grid(width=width, height=height)

        # hide/show grid
        self.update_grid()

    def redraw(self):
        if self.adjust_to_dim.get():
            self.resize_to_wallpaper()
        else:
            print(self.scale_option.get())
            option = ScaleOption(self.scale_option.get())
            if option == ScaleOption.UPPER_LEFT:
                self.wallpaper_upper_left()
            elif option == ScaleOption.CENTERED:
                self.wallpaper_center()
            elif option == ScaleOption.SCALED:
                self.wallpaper_scaled()
            elif option == ScaleOption.TILED:
                logging.warning("tiled background not implemented yet")

    def update_grid(self):
        logging.info("updating grid show: %s", self.show_grid.get())
        if self.show_grid.get():
            self.itemconfig("gridline", state=tk.NORMAL)
            self.tag_raise("gridline")
        else:
            self.itemconfig("gridline", state=tk.HIDDEN)

    def set_wallpaper(self, filename):
        logging.info("setting wallpaper: %s", filename)
        if filename is not None:
            img = Image.open(filename)
            self.wallpaper = img
            self.wallpaper_file = filename
            self.redraw()
            for component in ABOVE_WALLPAPER:
                self.tag_raise(component)
        else:
            if self.wallpaper_id is not None:
                self.delete(self.wallpaper_id)
            self.wallpaper = None
            self.wallpaper_file = None

    def is_selection_mode(self):
        return self.mode == GraphMode.SELECT
