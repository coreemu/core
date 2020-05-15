import logging
import tkinter as tk
from enum import Enum
from functools import partial
from tkinter import ttk
from typing import TYPE_CHECKING, Callable

from PIL.ImageTk import PhotoImage

from core.api.grpc import core_pb2
from core.gui.dialogs.marker import MarkerDialog
from core.gui.dialogs.runtool import RunToolDialog
from core.gui.graph.enums import GraphMode
from core.gui.graph.shapeutils import ShapeType, is_marker
from core.gui.images import ImageEnum, Images
from core.gui.nodeutils import NodeDraw, NodeUtils
from core.gui.task import ProgressTask
from core.gui.themes import Styles
from core.gui.tooltip import Tooltip

if TYPE_CHECKING:
    from core.gui.app import Application

TOOLBAR_SIZE = 32
PICKER_SIZE = 24


class NodeTypeEnum(Enum):
    NODE = 0
    NETWORK = 1
    OTHER = 2


def enable_buttons(frame: ttk.Frame, enabled: bool) -> None:
    state = tk.NORMAL if enabled else tk.DISABLED
    for child in frame.winfo_children():
        child.configure(state=state)


class Toolbar(ttk.Frame):
    """
    Core toolbar class
    """

    def __init__(self, master: tk.Widget, app: "Application", **kwargs) -> None:
        """
        Create a CoreToolbar instance
        """
        super().__init__(master, **kwargs)
        self.app = app

        # design buttons
        self.play_button = None
        self.select_button = None
        self.link_button = None
        self.node_button = None
        self.network_button = None
        self.annotation_button = None

        # runtime buttons
        self.runtime_select_button = None
        self.stop_button = None
        self.runtime_marker_button = None
        self.run_command_button = None

        # frames
        self.design_frame = None
        self.runtime_frame = None
        self.node_picker = None
        self.network_picker = None
        self.annotation_picker = None

        # dialog
        self.marker_tool = None

        # these variables help keep track of what images being drawn so that scaling
        # is possible since PhotoImage does not have resize method
        self.node_enum = None
        self.network_enum = None
        self.annotation_enum = None

        # draw components
        self.draw()

    def get_icon(self, image_enum: ImageEnum, width: int) -> PhotoImage:
        return Images.get(image_enum, int(width * self.app.app_scale))

    def draw(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.draw_design_frame()
        self.draw_runtime_frame()
        self.design_frame.tkraise()

    def draw_design_frame(self) -> None:
        self.design_frame = ttk.Frame(self)
        self.design_frame.grid(row=0, column=0, sticky="nsew")
        self.design_frame.columnconfigure(0, weight=1)
        self.play_button = self.create_button(
            self.design_frame,
            self.get_icon(ImageEnum.START, TOOLBAR_SIZE),
            self.click_start,
            "start the session",
        )
        self.select_button = self.create_button(
            self.design_frame,
            self.get_icon(ImageEnum.SELECT, TOOLBAR_SIZE),
            self.click_selection,
            "selection tool",
        )
        self.link_button = self.create_button(
            self.design_frame,
            self.get_icon(ImageEnum.LINK, TOOLBAR_SIZE),
            self.click_link,
            "link tool",
        )
        self.create_node_button()
        self.create_network_button()
        self.create_annotation_button()

    def design_select(self, button: ttk.Button) -> None:
        logging.debug("selecting design button: %s", button)
        self.select_button.state(["!pressed"])
        self.link_button.state(["!pressed"])
        self.node_button.state(["!pressed"])
        self.network_button.state(["!pressed"])
        self.annotation_button.state(["!pressed"])
        button.state(["pressed"])

    def runtime_select(self, button: ttk.Button) -> None:
        logging.debug("selecting runtime button: %s", button)
        self.runtime_select_button.state(["!pressed"])
        self.stop_button.state(["!pressed"])
        self.runtime_marker_button.state(["!pressed"])
        self.run_command_button.state(["!pressed"])
        button.state(["pressed"])

    def draw_runtime_frame(self) -> None:
        self.runtime_frame = ttk.Frame(self)
        self.runtime_frame.grid(row=0, column=0, sticky="nsew")
        self.runtime_frame.columnconfigure(0, weight=1)
        self.stop_button = self.create_button(
            self.runtime_frame,
            self.get_icon(ImageEnum.STOP, TOOLBAR_SIZE),
            self.click_stop,
            "stop the session",
        )
        self.runtime_select_button = self.create_button(
            self.runtime_frame,
            self.get_icon(ImageEnum.SELECT, TOOLBAR_SIZE),
            self.click_runtime_selection,
            "selection tool",
        )
        self.runtime_marker_button = self.create_button(
            self.runtime_frame,
            self.get_icon(ImageEnum.MARKER, TOOLBAR_SIZE),
            self.click_marker_button,
            "marker",
        )
        self.run_command_button = self.create_button(
            self.runtime_frame,
            self.get_icon(ImageEnum.RUN, TOOLBAR_SIZE),
            self.click_run_button,
            "run",
        )

    def draw_node_picker(self) -> None:
        self.hide_pickers()
        self.node_picker = ttk.Frame(self.master)
        # draw default nodes
        for node_draw in NodeUtils.NODES:
            toolbar_image = self.get_icon(node_draw.image_enum, TOOLBAR_SIZE)
            image = self.get_icon(node_draw.image_enum, PICKER_SIZE)
            func = partial(
                self.update_button,
                self.node_button,
                toolbar_image,
                node_draw,
                NodeTypeEnum.NODE,
                node_draw.image_enum,
            )
            self.create_picker_button(image, func, self.node_picker, node_draw.label)
        # draw custom nodes
        for name in sorted(self.app.core.custom_nodes):
            node_draw = self.app.core.custom_nodes[name]
            toolbar_image = Images.get_custom(
                node_draw.image_file, int(TOOLBAR_SIZE * self.app.app_scale)
            )
            image = Images.get_custom(
                node_draw.image_file, int(PICKER_SIZE * self.app.app_scale)
            )
            func = partial(
                self.update_button,
                self.node_button,
                toolbar_image,
                node_draw,
                NodeTypeEnum,
                node_draw.image_file,
            )
            self.create_picker_button(image, func, self.node_picker, name)
        self.design_select(self.node_button)
        self.node_button.after(
            0, lambda: self.show_picker(self.node_button, self.node_picker)
        )

    def show_picker(self, button: ttk.Button, picker: ttk.Frame) -> None:
        x = self.winfo_width() + 1
        y = button.winfo_rooty() - picker.master.winfo_rooty() - 1
        picker.place(x=x, y=y)
        self.app.bind_all("<ButtonRelease-1>", lambda e: self.hide_pickers())
        picker.wait_visibility()
        picker.grab_set()
        self.wait_window(picker)
        self.app.unbind_all("<ButtonRelease-1>")

    def create_picker_button(
        self, image: PhotoImage, func: Callable, frame: ttk.Frame, label: str
    ) -> None:
        """
        Create button and put it on the frame

        :param image: button image
        :param func: the command that is executed when button is clicked
        :param frame: frame that contains the button
        :param label: button label
        """
        button = ttk.Button(
            frame, image=image, text=label, compound=tk.TOP, style=Styles.picker_button
        )
        button.image = image
        button.bind("<ButtonRelease-1>", lambda e: func())
        button.grid(pady=1)

    def create_button(
        self, frame: ttk.Frame, image: PhotoImage, func: Callable, tooltip: str
    ) -> ttk.Button:
        button = ttk.Button(frame, image=image, command=func)
        button.image = image
        button.grid(sticky="ew")
        Tooltip(button, tooltip)
        return button

    def click_selection(self) -> None:
        logging.debug("clicked selection tool")
        self.design_select(self.select_button)
        self.app.canvas.mode = GraphMode.SELECT

    def click_runtime_selection(self) -> None:
        logging.debug("clicked selection tool")
        self.runtime_select(self.runtime_select_button)
        self.app.canvas.mode = GraphMode.SELECT

    def click_start(self) -> None:
        """
        Start session handler redraw buttons, send node and link messages to grpc
        server.
        """
        self.app.menubar.change_menubar_item_state(is_runtime=True)
        self.app.canvas.mode = GraphMode.SELECT
        enable_buttons(self.design_frame, enabled=False)
        task = ProgressTask(
            self.app, "Start", self.app.core.start_session, self.start_callback
        )
        task.start()

    def start_callback(self, response: core_pb2.StartSessionResponse) -> None:
        if response.result:
            self.set_runtime()
            self.app.core.set_metadata()
            self.app.core.show_mobility_players()
        else:
            enable_buttons(self.design_frame, enabled=True)
            message = "\n".join(response.exceptions)
            self.app.show_error("Start Session Error", message)

    def set_runtime(self) -> None:
        enable_buttons(self.runtime_frame, enabled=True)
        self.runtime_frame.tkraise()
        self.click_runtime_selection()

    def set_design(self) -> None:
        enable_buttons(self.design_frame, enabled=True)
        self.design_frame.tkraise()
        self.click_selection()

    def click_link(self) -> None:
        logging.debug("Click LINK button")
        self.design_select(self.link_button)
        self.app.canvas.mode = GraphMode.EDGE

    def update_button(
        self,
        button: ttk.Button,
        image: PhotoImage,
        node_draw: NodeDraw,
        type_enum,
        image_enum,
    ) -> None:
        logging.debug("update button(%s): %s", button, node_draw)
        self.hide_pickers()
        button.configure(image=image)
        button.image = image
        self.app.canvas.mode = GraphMode.NODE
        self.app.canvas.node_draw = node_draw
        if type_enum == NodeTypeEnum.NODE:
            self.node_enum = image_enum
        elif type_enum == NodeTypeEnum.NETWORK:
            self.network_enum = image_enum

    def hide_pickers(self) -> None:
        logging.debug("hiding pickers")
        if self.node_picker:
            self.node_picker.destroy()
            self.node_picker = None
        if self.network_picker:
            self.network_picker.destroy()
            self.network_picker = None
        if self.annotation_picker:
            self.annotation_picker.destroy()
            self.annotation_picker = None

    def create_node_button(self) -> None:
        """
        Create network layer button
        """
        image = self.get_icon(ImageEnum.ROUTER, TOOLBAR_SIZE)
        self.node_button = ttk.Button(
            self.design_frame, image=image, command=self.draw_node_picker
        )
        self.node_button.image = image
        self.node_button.grid(sticky="ew")
        Tooltip(self.node_button, "Network-layer virtual nodes")
        self.node_enum = ImageEnum.ROUTER

    def draw_network_picker(self) -> None:
        """
        Draw the options for link-layer button.
        """
        self.hide_pickers()
        self.network_picker = ttk.Frame(self.master)
        for node_draw in NodeUtils.NETWORK_NODES:
            toolbar_image = self.get_icon(node_draw.image_enum, TOOLBAR_SIZE)
            image = self.get_icon(node_draw.image_enum, PICKER_SIZE)
            self.create_picker_button(
                image,
                partial(
                    self.update_button,
                    self.network_button,
                    toolbar_image,
                    node_draw,
                    NodeTypeEnum.NETWORK,
                    node_draw.image_enum,
                ),
                self.network_picker,
                node_draw.label,
            )
        self.design_select(self.network_button)
        self.network_button.after(
            0, lambda: self.show_picker(self.network_button, self.network_picker)
        )

    def create_network_button(self) -> None:
        """
        Create link-layer node button and the options that represent different
        link-layer node types.
        """
        image = self.get_icon(ImageEnum.HUB, TOOLBAR_SIZE)
        self.network_button = ttk.Button(
            self.design_frame, image=image, command=self.draw_network_picker
        )
        self.network_button.image = image
        self.network_button.grid(sticky="ew")
        Tooltip(self.network_button, "link-layer nodes")
        self.network_enum = ImageEnum.HUB

    def draw_annotation_picker(self) -> None:
        """
        Draw the options for marker button.
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
            toolbar_image = self.get_icon(image_enum, TOOLBAR_SIZE)
            image = self.get_icon(image_enum, PICKER_SIZE)
            self.create_picker_button(
                image,
                partial(self.update_annotation, toolbar_image, shape_type, image_enum),
                self.annotation_picker,
                shape_type.value,
            )
        self.design_select(self.annotation_button)
        self.annotation_button.after(
            0, lambda: self.show_picker(self.annotation_button, self.annotation_picker)
        )

    def create_annotation_button(self) -> None:
        """
        Create marker button and options that represent different marker types
        """
        image = self.get_icon(ImageEnum.MARKER, TOOLBAR_SIZE)
        self.annotation_button = ttk.Button(
            self.design_frame, image=image, command=self.draw_annotation_picker
        )
        self.annotation_button.image = image
        self.annotation_button.grid(sticky="ew")
        Tooltip(self.annotation_button, "background annotation tools")
        self.annotation_enum = ImageEnum.MARKER

    def create_observe_button(self) -> None:
        image = self.get_icon(ImageEnum.OBSERVE, TOOLBAR_SIZE)
        menu_button = ttk.Menubutton(
            self.runtime_frame, image=image, direction=tk.RIGHT
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

    def click_stop(self) -> None:
        """
        redraw buttons on the toolbar, send node and link messages to grpc server
        """
        logging.info("clicked stop button")
        self.app.menubar.change_menubar_item_state(is_runtime=False)
        self.app.core.close_mobility_players()
        enable_buttons(self.runtime_frame, enabled=False)
        task = ProgressTask(
            self.app, "Stop", self.app.core.stop_session, self.stop_callback
        )
        task.start()

    def stop_callback(self, response: core_pb2.StopSessionResponse) -> None:
        self.set_design()
        self.app.canvas.stopped_session()

    def update_annotation(
        self, image: PhotoImage, shape_type: ShapeType, image_enum
    ) -> None:
        logging.debug("clicked annotation: ")
        self.hide_pickers()
        self.annotation_button.configure(image=image)
        self.annotation_button.image = image
        self.app.canvas.mode = GraphMode.ANNOTATION
        self.app.canvas.annotation_type = shape_type
        self.annotation_enum = image_enum
        if is_marker(shape_type):
            if self.marker_tool:
                self.marker_tool.destroy()
            self.marker_tool = MarkerDialog(self.app)
            self.marker_tool.show()

    def click_run_button(self) -> None:
        logging.debug("Click on RUN button")
        dialog = RunToolDialog(self.app)
        dialog.show()

    def click_marker_button(self) -> None:
        logging.debug("Click on marker button")
        self.runtime_select(self.runtime_marker_button)
        self.app.canvas.mode = GraphMode.ANNOTATION
        self.app.canvas.annotation_type = ShapeType.MARKER
        if self.marker_tool:
            self.marker_tool.destroy()
        self.marker_tool = MarkerDialog(self.app)
        self.marker_tool.show()

    def scale_button(self, button, image_enum) -> None:
        image = self.get_icon(image_enum, TOOLBAR_SIZE)
        button.config(image=image)
        button.image = image

    def scale(self) -> None:
        self.scale_button(self.play_button, ImageEnum.START)
        self.scale_button(self.select_button, ImageEnum.SELECT)
        self.scale_button(self.link_button, ImageEnum.LINK)
        self.scale_button(self.node_button, self.node_enum)
        self.scale_button(self.network_button, self.network_enum)
        self.scale_button(self.annotation_button, self.annotation_enum)
        self.scale_button(self.runtime_select_button, ImageEnum.SELECT)
        self.scale_button(self.stop_button, ImageEnum.STOP)
        self.scale_button(self.runtime_marker_button, ImageEnum.MARKER)
        self.scale_button(self.run_command_button, ImageEnum.RUN)
