import logging
import threading
import tkinter as tk
from functools import partial
from tkinter import ttk
from tkinter.font import Font

from coretk.dialogs.customnodes import CustomNodesDialog
from coretk.dialogs.marker import Marker
from coretk.graph import tags
from coretk.graph.enums import GraphMode
from coretk.graph.shapeutils import ShapeType, is_marker
from coretk.images import ImageEnum, Images
from coretk.nodeutils import NodeUtils
from coretk.themes import Styles
from coretk.tooltip import Tooltip

TOOLBAR_SIZE = 32
PICKER_SIZE = 24


def icon(image_enum, width=TOOLBAR_SIZE):
    return Images.get(image_enum, width)


class Toolbar(ttk.Frame):
    """
    Core toolbar class
    """

    def __init__(self, master, app, **kwargs):
        """
        Create a CoreToolbar instance

        :param tkinter.Frame edit_frame: edit frame
        """
        super().__init__(master, **kwargs)
        self.app = app
        self.master = app.master

        # picker data
        self.picker_font = Font(size=8)

        # design buttons
        self.select_button = None
        self.link_button = None
        self.node_button = None
        self.network_button = None
        self.annotation_button = None

        # runtime buttons
        self.runtime_select_button = None

        # frames
        self.design_frame = None
        self.runtime_frame = None
        self.node_picker = None
        self.network_picker = None
        self.annotation_picker = None

        # dialog
        self.marker_tool = None

        # draw components
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.draw_design_frame()
        self.draw_runtime_frame()
        self.design_frame.tkraise()

    def draw_design_frame(self):
        self.design_frame = ttk.Frame(self)
        self.design_frame.grid(row=0, column=0, sticky="nsew")
        self.design_frame.columnconfigure(0, weight=1)
        self.create_button(
            self.design_frame,
            icon(ImageEnum.START),
            self.click_start,
            "start the session",
        )
        self.select_button = self.create_button(
            self.design_frame,
            icon(ImageEnum.SELECT),
            self.click_selection,
            "selection tool",
        )
        self.link_button = self.create_button(
            self.design_frame, icon(ImageEnum.LINK), self.click_link, "link tool"
        )
        self.create_node_button()
        self.create_network_button()
        self.create_annotation_button()

    def design_select(self, button):
        logging.info("selecting design button: %s", button)
        self.select_button.state(["!pressed"])
        self.link_button.state(["!pressed"])
        self.node_button.state(["!pressed"])
        self.network_button.state(["!pressed"])
        self.annotation_button.state(["!pressed"])
        button.state(["pressed"])

    def runtime_select(self, button):
        logging.info("selecting runtime button: %s", button)
        self.runtime_select_button.state(["!pressed"])
        button.state(["pressed"])

    def draw_runtime_frame(self):
        self.runtime_frame = ttk.Frame(self)
        self.runtime_frame.grid(row=0, column=0, sticky="nsew")
        self.runtime_frame.columnconfigure(0, weight=1)

        self.create_button(
            self.runtime_frame,
            icon(ImageEnum.STOP),
            self.click_stop,
            "stop the session",
        )
        self.runtime_select_button = self.create_button(
            self.runtime_frame,
            icon(ImageEnum.SELECT),
            self.click_runtime_selection,
            "selection tool",
        )
        # self.create_observe_button()
        self.create_button(
            self.runtime_frame, icon(ImageEnum.PLOT), self.click_plot_button, "plot"
        )
        self.create_button(
            self.runtime_frame,
            icon(ImageEnum.MARKER),
            self.click_marker_button,
            "marker",
        )
        self.create_button(
            self.runtime_frame,
            icon(ImageEnum.TWONODE),
            self.click_two_node_button,
            "run command from one node to another",
        )
        self.create_button(
            self.runtime_frame, icon(ImageEnum.RUN), self.click_run_button, "run"
        )

    def draw_node_picker(self):
        self.hide_pickers()
        self.node_picker = ttk.Frame(self.master)
        # draw default nodes
        for node_draw in NodeUtils.NODES:
            toolbar_image = icon(node_draw.image_enum)
            image = icon(node_draw.image_enum, PICKER_SIZE)
            func = partial(
                self.update_button, self.node_button, toolbar_image, node_draw
            )
            self.create_picker_button(image, func, self.node_picker, node_draw.label)
        # draw custom nodes
        for name in sorted(self.app.core.custom_nodes):
            node_draw = self.app.core.custom_nodes[name]
            toolbar_image = Images.get_custom(node_draw.image_file, TOOLBAR_SIZE)
            image = Images.get_custom(node_draw.image_file, PICKER_SIZE)
            func = partial(
                self.update_button, self.node_button, toolbar_image, node_draw
            )
            self.create_picker_button(image, func, self.node_picker, name)
        # draw edit node
        image = icon(ImageEnum.EDITNODE, PICKER_SIZE)
        self.create_picker_button(
            image, self.click_edit_node, self.node_picker, "Custom"
        )
        self.design_select(self.node_button)
        self.node_button.after(
            0, lambda: self.show_picker(self.node_button, self.node_picker)
        )

    def show_picker(self, button, picker):
        x = self.winfo_width() + 1
        y = button.winfo_rooty() - picker.master.winfo_rooty() - 1
        picker.place(x=x, y=y)
        self.app.bind_all("<ButtonRelease-1>", lambda e: self.hide_pickers())
        picker.wait_visibility()
        picker.grab_set()
        self.wait_window(picker)
        self.app.unbind_all("<ButtonRelease-1>")

    def create_picker_button(self, image, func, frame, label):
        """
        Create button and put it on the frame

        :param PIL.Image image: button image
        :param func: the command that is executed when button is clicked
        :param tkinter.Frame frame: frame that contains the button
        :param str label: button label
        :return: nothing
        """
        button = ttk.Button(
            frame, image=image, text=label, compound=tk.TOP, style=Styles.picker_button
        )
        button.image = image
        button.bind("<ButtonRelease-1>", lambda e: func())
        button.grid(pady=1)

    def create_button(self, frame, image, func, tooltip):
        button = ttk.Button(frame, image=image, command=func)
        button.image = image
        button.grid(sticky="ew")
        Tooltip(button, tooltip)
        return button

    def click_selection(self):
        logging.debug("clicked selection tool")
        self.design_select(self.select_button)
        self.app.canvas.mode = GraphMode.SELECT

    def click_runtime_selection(self):
        logging.debug("clicked selection tool")
        self.runtime_select(self.runtime_select_button)
        self.app.canvas.mode = GraphMode.SELECT

    def click_start(self):
        """
        Start session handler redraw buttons, send node and link messages to grpc
        server.

        :return: nothing
        """
        self.app.canvas.hide_context()
        self.app.statusbar.core_alarms.clear()
        self.app.statusbar.progress_bar.start(5)
        self.app.canvas.mode = GraphMode.SELECT
        thread = threading.Thread(target=self.app.core.start_session)
        thread.start()
        self.runtime_frame.tkraise()
        self.click_runtime_selection()

    def click_link(self):
        logging.debug("Click LINK button")
        self.design_select(self.link_button)
        self.app.canvas.mode = GraphMode.EDGE

    def click_edit_node(self):
        self.hide_pickers()
        dialog = CustomNodesDialog(self.app, self.app)
        dialog.show()

    def update_button(self, button, image, node_draw):
        logging.info("update button(%s): %s", button, node_draw)
        self.hide_pickers()
        button.configure(image=image)
        button.image = image
        self.app.canvas.mode = GraphMode.NODE
        self.app.canvas.node_draw = node_draw

    def hide_pickers(self):
        logging.info("hiding pickers")
        if self.node_picker:
            self.node_picker.destroy()
            self.node_picker = None
        if self.network_picker:
            self.network_picker.destroy()
            self.network_picker = None
        if self.annotation_picker:
            self.annotation_picker.destroy()
            self.annotation_picker = None

    def create_node_button(self):
        """
        Create network layer button

        :return: nothing
        """
        image = icon(ImageEnum.ROUTER)
        self.node_button = ttk.Button(
            self.design_frame, image=image, command=self.draw_node_picker
        )
        self.node_button.image = image
        self.node_button.grid(sticky="ew")
        Tooltip(self.node_button, "Network-layer virtual nodes")

    def draw_network_picker(self):
        """
        Draw the options for link-layer button.

        :return: nothing
        """
        self.hide_pickers()
        self.network_picker = ttk.Frame(self.master)
        for node_draw in NodeUtils.NETWORK_NODES:
            toolbar_image = icon(node_draw.image_enum)
            image = icon(node_draw.image_enum, PICKER_SIZE)
            self.create_picker_button(
                image,
                partial(
                    self.update_button, self.network_button, toolbar_image, node_draw
                ),
                self.network_picker,
                node_draw.label,
            )
        self.design_select(self.network_button)
        self.network_button.after(
            0, lambda: self.show_picker(self.network_button, self.network_picker)
        )

    def create_network_button(self):
        """
        Create link-layer node button and the options that represent different
        link-layer node types.

        :return: nothing
        """
        image = icon(ImageEnum.HUB)
        self.network_button = ttk.Button(
            self.design_frame, image=image, command=self.draw_network_picker
        )
        self.network_button.image = image
        self.network_button.grid(sticky="ew")
        Tooltip(self.network_button, "link-layer nodes")

    def draw_annotation_picker(self):
        """
        Draw the options for marker button.

        :return: nothing
        """
        self.hide_pickers()
        self.annotation_picker = ttk.Frame(self.master)
        nodes = [
            (ImageEnum.MARKER, ShapeType.MARKER),
            (ImageEnum.OVAL, ShapeType.OVAL),
            (ImageEnum.RECTANGLE, ShapeType.RECTANGLE),
            (ImageEnum.TEXT, ShapeType.TEXT),
        ]
        for image_enum, shape_type in nodes:
            toolbar_image = icon(image_enum)
            image = icon(image_enum, PICKER_SIZE)
            self.create_picker_button(
                image,
                partial(self.update_annotation, toolbar_image, shape_type),
                self.annotation_picker,
                shape_type.value,
            )
        self.design_select(self.annotation_button)
        self.annotation_button.after(
            0, lambda: self.show_picker(self.annotation_button, self.annotation_picker)
        )

    def create_annotation_button(self):
        """
        Create marker button and options that represent different marker types

        :return: nothing
        """
        image = icon(ImageEnum.MARKER)
        self.annotation_button = ttk.Button(
            self.design_frame, image=image, command=self.draw_annotation_picker
        )
        self.annotation_button.image = image
        self.annotation_button.grid(sticky="ew")
        Tooltip(self.annotation_button, "background annotation tools")

    def create_observe_button(self):
        menu_button = ttk.Menubutton(
            self.runtime_frame, image=icon(ImageEnum.OBSERVE), direction=tk.RIGHT
        )
        menu_button.grid(sticky="ew")
        menu = tk.Menu(menu_button, tearoff=0)
        menu_button["menu"] = menu
        menu.add_command(label="None")
        menu.add_command(label="processes")
        menu.add_command(label="ifconfig")
        menu.add_command(label="IPv4 routes")
        menu.add_command(label="IPv6 routes")
        menu.add_command(label="OSPFv2 neighbors")
        menu.add_command(label="OSPFv3 neighbors")
        menu.add_command(label="Listening sockets")
        menu.add_command(label="IPv4 MFC entries")
        menu.add_command(label="IPv6 MFC entries")
        menu.add_command(label="firewall rules")
        menu.add_command(label="IPSec policies")
        menu.add_command(label="docker logs")
        menu.add_command(label="OSPFv3 MDR level")
        menu.add_command(label="PIM neighbors")
        menu.add_command(label="Edit...")

    def click_stop(self):
        """
        redraw buttons on the toolbar, send node and link messages to grpc server

        :return: nothing
        """
        self.app.canvas.hide_context()
        self.app.statusbar.progress_bar.start(5)
        thread = threading.Thread(target=self.app.core.stop_session)
        thread.start()
        self.app.canvas.delete(tags.WIRELESS_EDGE)
        self.design_frame.tkraise()
        self.click_selection()

    def update_annotation(self, image, shape_type):
        logging.info("clicked annotation: ")
        self.hide_pickers()
        self.annotation_button.configure(image=image)
        self.annotation_button.image = image
        self.app.canvas.mode = GraphMode.ANNOTATION
        self.app.canvas.annotation_type = shape_type
        if is_marker(shape_type):
            if not self.marker_tool:
                self.marker_tool = Marker(self.master, self.app)
                self.marker_tool.show()

    def click_run_button(self):
        logging.debug("Click on RUN button")

    def click_plot_button(self):
        logging.debug("Click on plot button")

    def click_marker_button(self):
        logging.debug("Click on marker button")
        dialog = Marker(self.master, self.app)
        dialog.show()

    def click_two_node_button(self):
        logging.debug("Click TWONODE button")
