import enum
import logging
import tkinter as tk
from tkinter import font

from PIL import ImageTk

from core.api.grpc import core_pb2
from core.api.grpc.core_pb2 import NodeType
from coretk.canvastooltip import CanvasTooltip
from coretk.dialogs.emaneconfig import EmaneConfigDialog
from coretk.dialogs.mobilityconfig import MobilityConfigDialog
from coretk.dialogs.nodeconfig import NodeConfigDialog
from coretk.dialogs.wlanconfig import WlanConfigDialog
from coretk.graph_helper import GraphHelper, WlanAntennaManager
from coretk.images import Images
from coretk.linkinfo import LinkInfo, Throughput
from coretk.nodedelete import CanvasComponentManagement
from coretk.nodeutils import NodeUtils
from coretk.wirelessconnection import WirelessConnection

NODE_TEXT_OFFSET = 5


class GraphMode(enum.Enum):
    SELECT = 0
    EDGE = 1
    PICKNODE = 2
    NODE = 3
    OTHER = 4


class ScaleOption(enum.Enum):
    NONE = 0
    UPPER_LEFT = 1
    CENTERED = 2
    SCALED = 3
    TILED = 4


class CanvasGraph(tk.Canvas):
    def __init__(self, master, core, cnf=None, **kwargs):
        if cnf is None:
            cnf = {}
        kwargs["highlightthickness"] = 0
        super().__init__(master, cnf, **kwargs)
        self.mode = GraphMode.SELECT
        self.selected = None
        self.node_draw = None
        self.context = None
        self.nodes = {}
        self.edges = {}
        self.drawing_edge = None
        self.grid = None
        self.canvas_management = CanvasComponentManagement(self, core)
        self.setup_bindings()
        self.draw_grid()
        self.core = core
        self.helper = GraphHelper(self, core)
        self.throughput_draw = Throughput(self, core)
        self.wireless_draw = WirelessConnection(self, core)

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

    def draw_session(self, session):
        """
        Draw existing session.

        :return: nothing
        """
        # draw existing nodes
        for core_node in session.nodes:
            # peer to peer node is not drawn on the GUI
            if core_node.type == core_pb2.NodeType.PEER_TO_PEER:
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
                self.wireless_draw.add_connection(link.node_one_id, link.node_two_id)
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

                # TODO add back the link info to grpc manager also redraw
                # TODO will include throughput and ipv6 in the future
                interface_one = link.interface_one
                interface_two = link.interface_two
                ip4_src = None
                ip4_dst = None
                ip6_src = None
                ip6_dst = None
                if interface_one is not None:
                    ip4_src = interface_one.ip4
                    ip6_src = interface_one.ip6
                if interface_two is not None:
                    ip4_dst = interface_two.ip4
                    ip6_dst = interface_two.ip6
                edge.link_info = LinkInfo(
                    canvas=self,
                    edge=edge,
                    ip4_src=ip4_src,
                    ip6_src=ip6_src,
                    ip4_dst=ip4_dst,
                    ip6_dst=ip6_dst,
                )
                canvas_node_one.interfaces.append(interface_one)
                canvas_node_two.interfaces.append(interface_two)

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
        nodes = set(self.find_withtag("node"))
        selected = None
        for _id in overlapping:
            if self.drawing_edge and self.drawing_edge.id == _id:
                continue

            if _id in nodes:
                selected = _id
                break

            if selected is None:
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
            self.focus_set()
            self.selected = self.get_selected(event)
            logging.debug(f"click release selected({self.selected}) mode({self.mode})")
            if self.mode == GraphMode.EDGE:
                self.handle_edge_release(event)
            elif self.mode == GraphMode.NODE:
                x, y = self.canvas_xy(event)
                self.add_node(x, y)
            elif self.mode == GraphMode.PICKNODE:
                self.mode = GraphMode.NODE

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

            # draw link info on the edge
            ip4_and_prefix_1 = None
            ip4_and_prefix_2 = None
            if link.HasField("interface_one"):
                if1 = link.interface_one
                ip4_and_prefix_1 = f"{if1.ip4}/{if1.ip4mask}"
            if link.HasField("interface_two"):
                if2 = link.interface_two
                ip4_and_prefix_2 = f"{if2.ip4}/{if2.ip4mask}"
            edge.link_info = LinkInfo(
                self,
                edge,
                ip4_src=ip4_and_prefix_1,
                ip6_src=None,
                ip4_dst=ip4_and_prefix_2,
                ip6_dst=None,
            )

        logging.debug(f"edges: {self.find_withtag('edge')}")

    def click_press(self, event):
        """
        Start drawing an edge if mouse click is on a node

        :param event: mouse event
        :return: nothing
        """
        logging.debug(f"click press: {event}")
        selected = self.get_selected(event)
        is_node = selected in self.find_withtag("node")
        if self.mode == GraphMode.EDGE and is_node:
            x, y = self.coords(selected)
            self.drawing_edge = CanvasEdge(x, y, x, y, selected, self)

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

    # TODO rather than delete, might move the data to somewhere else in order to reuse
    # TODO when the user undo
    def press_delete(self, event):
        """
        delete selected nodes and any data that relates to it
        :param event:
        :return:
        """
        # hide nodes, links, link information that shows on the GUI
        to_delete_nodes, to_delete_edge_tokens = (
            self.canvas_management.delete_selected_nodes()
        )

        # delete nodes and link info stored in CanvasGraph object
        node_ids = []
        for nid in to_delete_nodes:
            canvas_node = self.nodes.pop(nid)
            node_ids.append(canvas_node.core_node.id)
        for token in to_delete_edge_tokens:
            self.edges.pop(token)

        # delete the edge data inside of canvas node
        canvas_node_link_to_delete = []
        for canvas_id, node in self.nodes.items():
            for e in node.edges:
                if e.token in to_delete_edge_tokens:
                    canvas_node_link_to_delete.append(tuple([canvas_id, e]))
        for nid, edge in canvas_node_link_to_delete:
            self.nodes[nid].edges.remove(edge)

        # delete the related data from core
        self.core.delete_wanted_graph_nodes(node_ids, to_delete_edge_tokens)

    def add_node(self, x, y):
        plot_id = self.find_all()[0]
        logging.info("add node event: %s - %s", plot_id, self.selected)
        if self.selected == plot_id:
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
        grid = self.find_withtag("rectangle")[0]
        x0, y0, x1, y1 = self.coords(grid)
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


class CanvasEdge:
    """
    Canvas edge class
    """

    width = 1.4

    def __init__(self, x1, y1, x2, y2, src, canvas, is_wired=None):
        """
        Create an instance of canvas edge object
        :param int x1: source x-coord
        :param int y1: source y-coord
        :param int x2: destination x-coord
        :param int y2: destination y-coord
        :param int src: source id
        :param tkinter.Canvas canvas: canvas object
        """
        self.src = src
        self.dst = None
        self.src_interface = None
        self.dst_interface = None
        self.canvas = canvas
        if is_wired is None or is_wired is True:
            self.id = self.canvas.create_line(
                x1, y1, x2, y2, tags="edge", width=self.width, fill="#ff0000"
            )
        else:
            self.id = self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                tags="edge",
                width=self.width,
                fill="#ff0000",
                state=tk.HIDDEN,
            )
        self.token = None
        self.link_info = None
        self.throughput = None
        self.wired = is_wired

    def complete(self, dst, x, y):
        self.dst = dst
        self.token = tuple(sorted((self.src, self.dst)))
        x1, y1, _, _ = self.canvas.coords(self.id)
        self.canvas.coords(self.id, x1, y1, x, y)
        self.canvas.helper.draw_wireless_case(self.src, self.dst, self)
        self.canvas.tag_raise(self.src)
        self.canvas.tag_raise(self.dst)

    def delete(self):
        self.canvas.delete(self.id)


class CanvasNode:
    def __init__(self, app, core_node, image):
        self.app = app
        self.canvas = app.canvas
        self.image = image
        self.core_node = core_node
        x = self.core_node.position.x
        y = self.core_node.position.y
        self.id = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags="node"
        )
        image_box = self.canvas.bbox(self.id)
        y = image_box[3] + NODE_TEXT_OFFSET
        text_font = font.Font(family="TkIconFont", size=12)
        self.text_id = self.canvas.create_text(
            x,
            y,
            text=self.core_node.name,
            tags="nodename",
            font=text_font,
            fill="#0000CD",
        )
        self.antenna_draw = WlanAntennaManager(self.canvas, self.id)
        self.tooltip = CanvasTooltip(self.canvas)
        self.canvas.tag_bind(self.id, "<ButtonPress-1>", self.click_press)
        self.canvas.tag_bind(self.id, "<ButtonRelease-1>", self.click_release)
        self.canvas.tag_bind(self.id, "<B1-Motion>", self.motion)
        self.canvas.tag_bind(self.id, "<Double-Button-1>", self.double_click)
        self.canvas.tag_bind(self.id, "<Control-1>", self.select_multiple)
        self.canvas.tag_bind(self.id, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.id, "<Leave>", self.on_leave)
        self.edges = set()
        self.interfaces = []
        self.wlans = []
        self.moving = None

    def redraw(self):
        self.canvas.itemconfig(self.id, image=self.image)
        self.canvas.itemconfig(self.text_id, text=self.core_node.name)

    def on_enter(self, event):
        if self.app.core.is_runtime() and self.app.core.observer:
            self.tooltip.text.set("waiting...")
            self.tooltip.on_enter(event)
            output = self.app.core.run(self.core_node.id)
            self.tooltip.text.set(output)

    def on_leave(self, event):
        self.tooltip.on_leave(event)

    def click(self, event):
        print("click")

    def double_click(self, event):
        if self.app.core.is_runtime():
            self.canvas.core.launch_terminal(self.core_node.id)
        else:
            self.show_config()

    def update_coords(self):
        x, y = self.canvas.coords(self.id)
        self.core_node.position.x = int(x)
        self.core_node.position.y = int(y)

    def click_press(self, event):
        logging.debug(f"node click press {self.core_node.name}: {event}")
        self.moving = self.canvas.canvas_xy(event)

        self.canvas.canvas_management.node_select(self)

    def click_release(self, event):
        logging.debug(f"node click release {self.core_node.name}: {event}")
        self.update_coords()
        self.moving = None

    def motion(self, event):
        if self.canvas.mode == GraphMode.EDGE or self.canvas.mode == GraphMode.NODE:
            return
        x, y = self.canvas.canvas_xy(event)
        moving_x, moving_y = self.moving
        offset_x, offset_y = x - moving_x, y - moving_y
        self.moving = x, y

        old_x, old_y = self.canvas.coords(self.id)
        self.canvas.move(self.id, offset_x, offset_y)
        self.canvas.move(self.text_id, offset_x, offset_y)
        self.antenna_draw.update_antennas_position(offset_x, offset_y)
        self.canvas.canvas_management.node_drag(self, offset_x, offset_y)

        new_x, new_y = self.canvas.coords(self.id)

        if self.canvas.core.get_session_state() == core_pb2.SessionState.RUNTIME:
            self.canvas.core.edit_node(self.core_node.id, int(new_x), int(new_y))

        for edge in self.edges:
            x1, y1, x2, y2 = self.canvas.coords(edge.id)
            if x1 == old_x and y1 == old_y:
                self.canvas.coords(edge.id, new_x, new_y, x2, y2)
            else:
                self.canvas.coords(edge.id, x1, y1, new_x, new_y)
            edge.link_info.recalculate_info()

        self.canvas.helper.update_wlan_connection(
            old_x, old_y, new_x, new_y, self.wlans
        )

    def select_multiple(self, event):
        self.canvas.canvas_management.node_select(self, True)

    def show_config(self):
        self.canvas.context = None
        dialog = NodeConfigDialog(self.app, self.app, self)
        dialog.show()

    def show_wlan_config(self):
        self.canvas.context = None
        dialog = WlanConfigDialog(self.app, self.app, self)
        dialog.show()

    def show_mobility_config(self):
        self.canvas.context = None
        dialog = MobilityConfigDialog(self.app, self.app, self)
        dialog.show()

    def show_emane_config(self):
        self.canvas.context = None
        dialog = EmaneConfigDialog(self.app, self.app, self)
        dialog.show()
