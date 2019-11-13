import logging
import tkinter as tk
from functools import partial
from tkinter import ttk

from coretk.dialogs.customnodes import CustomNodesDialog
from coretk.graph import GraphMode
from coretk.images import ImageEnum, Images
from coretk.tooltip import Tooltip

WIDTH = 32


def icon(image_enum):
    return Images.get(image_enum, WIDTH)


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

        # design buttons
        self.select_button = None
        self.link_button = None
        self.node_button = None
        self.network_button = None
        self.annotation_button = None

        # runtime buttons

        # frames
        self.design_frame = None
        self.runtime_frame = None
        self.node_picker = None
        self.network_picker = None
        self.annotation_picker = None

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
        self.create_button(
            self.runtime_frame,
            icon(ImageEnum.SELECT),
            self.click_selection,
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
        nodes = [
            (ImageEnum.ROUTER, "router"),
            (ImageEnum.HOST, "host"),
            (ImageEnum.PC, "PC"),
            (ImageEnum.MDR, "mdr"),
            (ImageEnum.PROUTER, "prouter"),
        ]
        # draw default nodes
        for image_enum, tooltip in nodes:
            image = icon(image_enum)
            func = partial(self.update_button, self.node_button, image, tooltip)
            self.create_picker_button(image, func, self.node_picker, tooltip)
        # draw custom nodes
        for name in sorted(self.app.core.custom_nodes):
            custom_node = self.app.core.custom_nodes[name]
            image = custom_node.image
            func = partial(self.update_button, self.node_button, image, name)
            self.create_picker_button(image, func, self.node_picker, name)
        # draw edit node
        image = icon(ImageEnum.EDITNODE)
        self.create_picker_button(
            image, self.click_edit_node, self.node_picker, "custom nodes"
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

    def create_picker_button(self, image, func, frame, tooltip):
        """
        Create button and put it on the frame

        :param PIL.Image image: button image
        :param func: the command that is executed when button is clicked
        :param tkinter.Frame frame: frame that contains the button
        :param str tooltip: tooltip text
        :return: nothing
        """
        button = ttk.Button(frame, image=image)
        button.image = image
        button.bind("<ButtonRelease-1>", lambda e: func())
        button.grid(pady=1)
        Tooltip(button, tooltip)

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

    def click_start(self):
        """
        Start session handler redraw buttons, send node and link messages to grpc
        server.

        :return: nothing
        """
        logging.debug("clicked start button")
        self.app.canvas.mode = GraphMode.SELECT
        self.app.core.start_session()
        self.runtime_frame.tkraise()

    def click_link(self):
        logging.debug("Click LINK button")
        self.design_select(self.link_button)
        self.app.canvas.mode = GraphMode.EDGE

    def click_edit_node(self):
        self.hide_pickers()
        dialog = CustomNodesDialog(self.app, self.app)
        dialog.show()

    def update_button(self, button, image, name):
        logging.info("update button(%s): %s", button, name)
        self.hide_pickers()
        button.configure(image=image)
        button.image = image
        self.app.canvas.mode = GraphMode.NODE
        self.app.canvas.draw_node_image = image
        self.app.canvas.draw_node_name = name

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
        nodes = [
            (ImageEnum.HUB, "hub", "ethernet hub"),
            (ImageEnum.SWITCH, "switch", "ethernet switch"),
            (ImageEnum.WLAN, "wlan", "wireless LAN"),
            (ImageEnum.EMANE, "emane", "EMANE"),
            (ImageEnum.RJ45, "rj45", "rj45 physical interface tool"),
            (ImageEnum.TUNNEL, "tunnel", "tunnel tool"),
        ]
        for image_enum, name, tooltip in nodes:
            image = icon(image_enum)
            self.create_picker_button(
                image,
                partial(self.update_button, self.network_button, image, name),
                self.network_picker,
                tooltip,
            )
        self.design_select(self.network_button)
        self.network_button.after(
            0, lambda: self.show_picker(self.network_button, self.network_picker)
        )

    def create_network_button(self):
        """
        Create link-layer node button and the options that represent different link-layer node types

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
            (ImageEnum.MARKER, "marker"),
            (ImageEnum.OVAL, "oval"),
            (ImageEnum.RECTANGLE, "rectangle"),
            (ImageEnum.TEXT, "text"),
        ]
        for image_enum, tooltip in nodes:
            image = icon(image_enum)
            self.create_picker_button(
                image,
                partial(self.update_annotation, image),
                self.annotation_picker,
                tooltip,
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
        logging.debug("Click on STOP button ")
        self.app.core.stop_session()
        self.design_frame.tkraise()

    def update_annotation(self, image):
        logging.info("clicked annotation: ")
        self.hide_pickers()
        self.annotation_button.configure(image=image)
        self.annotation_button.image = image

    def click_run_button(self):
        logging.debug("Click on RUN button")

    def click_plot_button(self):
        logging.debug("Click on plot button")

    def click_marker_button(self):
        logging.debug("Click on marker button")

    def click_two_node_button(self):
        logging.debug("Click TWONODE button")
