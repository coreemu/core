import logging
import tkinter as tk
from enum import Enum
from functools import partial
from tkinter import ttk
from typing import TYPE_CHECKING, Callable, List, Optional

from PIL.ImageTk import PhotoImage

from core.gui import nodeutils as nutils
from core.gui.dialogs.colorpicker import ColorPickerDialog
from core.gui.dialogs.runtool import RunToolDialog
from core.gui.graph import tags
from core.gui.graph.enums import GraphMode
from core.gui.graph.shapeutils import ShapeType, is_marker
from core.gui.images import ImageEnum
from core.gui.nodeutils import NodeDraw
from core.gui.observers import ObserversMenu
from core.gui.task import ProgressTask
from core.gui.themes import Styles
from core.gui.tooltip import Tooltip

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application

TOOLBAR_SIZE: int = 32
PICKER_SIZE: int = 24


class NodeTypeEnum(Enum):
    NODE = 0
    NETWORK = 1
    OTHER = 2


def enable_buttons(frame: ttk.Frame, enabled: bool) -> None:
    state = tk.NORMAL if enabled else tk.DISABLED
    for child in frame.winfo_children():
        child.configure(state=state)


class PickerFrame(ttk.Frame):
    def __init__(self, app: "Application", button: ttk.Button) -> None:
        super().__init__(app)
        self.app: "Application" = app
        self.button: ttk.Button = button

    def create_node_button(self, node_draw: NodeDraw, func: Callable) -> None:
        self.create_button(
            node_draw.label, func, node_draw.image_enum, node_draw.image_file
        )

    def create_button(
        self,
        label: str,
        func: Callable,
        image_enum: ImageEnum = None,
        image_file: str = None,
    ) -> None:
        if image_enum:
            bar_image = self.app.get_enum_icon(image_enum, width=TOOLBAR_SIZE)
            image = self.app.get_enum_icon(image_enum, width=PICKER_SIZE)
        else:
            bar_image = self.app.get_file_icon(image_file, width=TOOLBAR_SIZE)
            image = self.app.get_file_icon(image_file, width=PICKER_SIZE)
        button = ttk.Button(
            self, image=image, text=label, compound=tk.TOP, style=Styles.picker_button
        )
        button.image = image
        button.bind("<ButtonRelease-1>", lambda e: func(bar_image))
        button.grid(pady=1)

    def show(self) -> None:
        self.button.after(0, self._show)

    def _show(self) -> None:
        x = self.button.winfo_width() + 1
        y = self.button.winfo_rooty() - self.app.winfo_rooty() - 1
        self.place(x=x, y=y)
        self.app.bind_all("<ButtonRelease-1>", lambda e: self.destroy())
        self.wait_visibility()
        self.grab_set()
        self.wait_window()
        self.app.unbind_all("<ButtonRelease-1>")


class ButtonBar(ttk.Frame):
    def __init__(self, master: tk.Widget, app: "Application") -> None:
        super().__init__(master)
        self.app: "Application" = app
        self.radio_buttons: List[ttk.Button] = []

    def create_button(
        self, image_enum: ImageEnum, func: Callable, tooltip: str, radio: bool = False
    ) -> ttk.Button:
        image = self.app.get_enum_icon(image_enum, width=TOOLBAR_SIZE)
        button = ttk.Button(self, image=image, command=func)
        button.image = image
        button.grid(sticky=tk.EW)
        Tooltip(button, tooltip)
        if radio:
            self.radio_buttons.append(button)
        return button

    def select_radio(self, selected: ttk.Button) -> None:
        for button in self.radio_buttons:
            button.state(["!pressed"])
        selected.state(["pressed"])


class MarkerFrame(ttk.Frame):
    PAD: int = 3

    def __init__(self, master: tk.BaseWidget, app: "Application") -> None:
        super().__init__(master, padding=self.PAD)
        self.app: "Application" = app
        self.color: str = "#000000"
        self.size: tk.DoubleVar = tk.DoubleVar()
        self.color_frame: Optional[tk.Frame] = None
        self.draw()

    def draw(self) -> None:
        self.columnconfigure(0, weight=1)

        image = self.app.get_enum_icon(ImageEnum.DELETE, width=16)
        button = ttk.Button(self, image=image, width=2, command=self.click_clear)
        button.image = image
        button.grid(sticky=tk.EW, pady=self.PAD)
        Tooltip(button, "Delete Marker")

        sizes = [1, 3, 8, 10]
        self.size.set(sizes[0])
        sizes = ttk.Combobox(
            self, state="readonly", textvariable=self.size, value=sizes, width=2
        )
        sizes.grid(sticky=tk.EW, pady=self.PAD)
        Tooltip(sizes, "Marker Size")

        frame_size = TOOLBAR_SIZE
        self.color_frame = tk.Frame(
            self, background=self.color, height=frame_size, width=frame_size
        )
        self.color_frame.grid(sticky=tk.EW)
        self.color_frame.bind("<Button-1>", self.click_color)
        Tooltip(self.color_frame, "Marker Color")

    def click_clear(self) -> None:
        canvas = self.app.manager.current()
        canvas.delete(tags.MARKER)

    def click_color(self, _event: tk.Event) -> None:
        dialog = ColorPickerDialog(self.app, self.app, self.color)
        self.color = dialog.askcolor()
        self.color_frame.config(background=self.color)


class Toolbar(ttk.Frame):
    """
    Core toolbar class
    """

    def __init__(self, app: "Application") -> None:
        """
        Create a CoreToolbar instance
        """
        super().__init__(app)
        self.app: "Application" = app

        # design buttons
        self.play_button: Optional[ttk.Button] = None
        self.select_button: Optional[ttk.Button] = None
        self.link_button: Optional[ttk.Button] = None
        self.node_button: Optional[ttk.Button] = None
        self.network_button: Optional[ttk.Button] = None
        self.annotation_button: Optional[ttk.Button] = None

        # runtime buttons
        self.runtime_select_button: Optional[ttk.Button] = None
        self.stop_button: Optional[ttk.Button] = None
        self.runtime_marker_button: Optional[ttk.Button] = None
        self.run_command_button: Optional[ttk.Button] = None

        # frames
        self.design_frame: Optional[ButtonBar] = None
        self.runtime_frame: Optional[ButtonBar] = None
        self.marker_frame: Optional[MarkerFrame] = None
        self.picker: Optional[PickerFrame] = None

        # observers
        self.observers_menu: Optional[ObserversMenu] = None

        # these variables help keep track of what images being drawn so that scaling
        # is possible since PhotoImage does not have resize method
        self.current_node: NodeDraw = nutils.NODES[0]
        self.current_network: NodeDraw = nutils.NETWORK_NODES[0]
        self.current_annotation: ShapeType = ShapeType.MARKER
        self.annotation_enum: ImageEnum = ImageEnum.MARKER

        # draw components
        self.draw()

    def draw(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.draw_design_frame()
        self.draw_runtime_frame()
        self.design_frame.tkraise()
        self.marker_frame = MarkerFrame(self, self.app)

    def draw_design_frame(self) -> None:
        self.design_frame = ButtonBar(self, self.app)
        self.design_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self.design_frame.columnconfigure(0, weight=1)
        self.play_button = self.design_frame.create_button(
            ImageEnum.START, self.click_start, "Start Session"
        )
        self.select_button = self.design_frame.create_button(
            ImageEnum.SELECT, self.click_selection, "Selection Tool", radio=True
        )
        self.link_button = self.design_frame.create_button(
            ImageEnum.LINK, self.click_link, "Link Tool", radio=True
        )
        self.node_button = self.design_frame.create_button(
            self.current_node.image_enum,
            self.draw_node_picker,
            "Container Nodes",
            radio=True,
        )
        self.network_button = self.design_frame.create_button(
            self.current_network.image_enum,
            self.draw_network_picker,
            "Link Layer Nodes",
            radio=True,
        )
        self.annotation_button = self.design_frame.create_button(
            self.annotation_enum,
            self.draw_annotation_picker,
            "Annotation Tools",
            radio=True,
        )

    def draw_runtime_frame(self) -> None:
        self.runtime_frame = ButtonBar(self, self.app)
        self.runtime_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self.runtime_frame.columnconfigure(0, weight=1)
        self.stop_button = self.runtime_frame.create_button(
            ImageEnum.STOP, self.click_stop, "Stop Session"
        )
        self.runtime_select_button = self.runtime_frame.create_button(
            ImageEnum.SELECT, self.click_runtime_selection, "Selection Tool", radio=True
        )
        self.create_observe_button()
        self.runtime_marker_button = self.runtime_frame.create_button(
            ImageEnum.MARKER, self.click_marker_button, "Marker Tool", radio=True
        )
        self.run_command_button = self.runtime_frame.create_button(
            ImageEnum.RUN, self.click_run_button, "Run Tool"
        )

    def draw_node_picker(self) -> None:
        self.hide_marker()
        self.app.manager.mode = GraphMode.NODE
        self.app.manager.node_draw = self.current_node
        self.design_frame.select_radio(self.node_button)
        self.picker = PickerFrame(self.app, self.node_button)
        # draw default nodes
        for node_draw in nutils.NODES:
            func = partial(
                self.update_button, self.node_button, node_draw, NodeTypeEnum.NODE
            )
            self.picker.create_node_button(node_draw, func)
        # draw custom nodes
        for name in sorted(self.app.core.custom_nodes):
            node_draw = self.app.core.custom_nodes[name]
            func = partial(
                self.update_button, self.node_button, node_draw, NodeTypeEnum.NODE
            )
            self.picker.create_node_button(node_draw, func)
        self.picker.show()

    def click_selection(self) -> None:
        self.design_frame.select_radio(self.select_button)
        self.app.manager.mode = GraphMode.SELECT
        self.hide_marker()

    def click_runtime_selection(self) -> None:
        self.runtime_frame.select_radio(self.runtime_select_button)
        self.app.manager.mode = GraphMode.SELECT
        self.hide_marker()

    def click_start(self) -> None:
        """
        Start session handler redraw buttons, send node and link messages to grpc
        server.
        """
        self.app.menubar.set_state(is_runtime=True)
        self.app.manager.mode = GraphMode.SELECT
        enable_buttons(self.design_frame, enabled=False)
        task = ProgressTask(
            self.app, "Start", self.app.core.start_session, self.start_callback
        )
        task.start()

    def start_callback(self, result: bool, exceptions: List[str]) -> None:
        self.set_runtime()
        self.app.core.show_mobility_players()
        if not result and exceptions:
            message = "\n".join(exceptions)
            self.app.show_exception_data(
                "Start Exception", "Session failed to start", message
            )

    def set_runtime(self) -> None:
        enable_buttons(self.runtime_frame, enabled=True)
        self.runtime_frame.tkraise()
        self.click_runtime_selection()
        self.hide_marker()

    def set_design(self) -> None:
        enable_buttons(self.design_frame, enabled=True)
        self.design_frame.tkraise()
        self.click_selection()
        self.hide_marker()

    def click_link(self) -> None:
        self.design_frame.select_radio(self.link_button)
        self.app.manager.mode = GraphMode.EDGE
        self.hide_marker()

    def update_button(
        self,
        button: ttk.Button,
        node_draw: NodeDraw,
        type_enum: NodeTypeEnum,
        image: PhotoImage,
    ) -> None:
        logger.debug("update button(%s): %s", button, node_draw)
        button.configure(image=image)
        button.image = image
        self.app.manager.node_draw = node_draw
        if type_enum == NodeTypeEnum.NODE:
            self.current_node = node_draw
        elif type_enum == NodeTypeEnum.NETWORK:
            self.current_network = node_draw

    def draw_network_picker(self) -> None:
        """
        Draw the options for link-layer button.
        """
        self.hide_marker()
        self.app.manager.mode = GraphMode.NODE
        self.app.manager.node_draw = self.current_network
        self.design_frame.select_radio(self.network_button)
        self.picker = PickerFrame(self.app, self.network_button)
        for node_draw in nutils.NETWORK_NODES:
            func = partial(
                self.update_button, self.network_button, node_draw, NodeTypeEnum.NETWORK
            )
            self.picker.create_node_button(node_draw, func)
        self.picker.show()

    def draw_annotation_picker(self) -> None:
        """
        Draw the options for marker button.
        """
        self.design_frame.select_radio(self.annotation_button)
        self.app.manager.mode = GraphMode.ANNOTATION
        self.app.manager.annotation_type = self.current_annotation
        if is_marker(self.current_annotation):
            self.show_marker()
        self.picker = PickerFrame(self.app, self.annotation_button)
        nodes = [
            (ImageEnum.MARKER, ShapeType.MARKER),
            (ImageEnum.OVAL, ShapeType.OVAL),
            (ImageEnum.RECTANGLE, ShapeType.RECTANGLE),
            (ImageEnum.TEXT, ShapeType.TEXT),
        ]
        for image_enum, shape_type in nodes:
            label = shape_type.value
            func = partial(self.update_annotation, shape_type, image_enum)
            self.picker.create_button(label, func, image_enum)
        self.picker.show()

    def create_observe_button(self) -> None:
        image = self.app.get_enum_icon(ImageEnum.OBSERVE, width=TOOLBAR_SIZE)
        menu_button = ttk.Menubutton(
            self.runtime_frame, image=image, direction=tk.RIGHT
        )
        menu_button.image = image
        menu_button.grid(sticky=tk.EW)
        self.observers_menu = ObserversMenu(menu_button, self.app)
        menu_button["menu"] = self.observers_menu

    def click_stop(self) -> None:
        """
        redraw buttons on the toolbar, send node and link messages to grpc server
        """
        logger.info("clicked stop button")
        self.app.menubar.set_state(is_runtime=False)
        self.app.core.close_mobility_players()
        enable_buttons(self.runtime_frame, enabled=False)
        task = ProgressTask(
            self.app, "Stop", self.app.core.stop_session, self.stop_callback
        )
        task.start()

    def stop_callback(self, result: bool) -> None:
        self.set_design()
        self.app.manager.stopped_session()

    def update_annotation(
        self, shape_type: ShapeType, image_enum: ImageEnum, image: PhotoImage
    ) -> None:
        logger.debug("clicked annotation")
        self.annotation_button.configure(image=image)
        self.annotation_button.image = image
        self.app.manager.annotation_type = shape_type
        self.current_annotation = shape_type
        self.annotation_enum = image_enum
        if is_marker(shape_type):
            self.show_marker()
        else:
            self.hide_marker()

    def hide_marker(self) -> None:
        self.marker_frame.grid_forget()

    def show_marker(self) -> None:
        self.marker_frame.grid()

    def click_run_button(self) -> None:
        logger.debug("Click on RUN button")
        dialog = RunToolDialog(self.app)
        dialog.show()

    def click_marker_button(self) -> None:
        self.runtime_frame.select_radio(self.runtime_marker_button)
        self.app.manager.mode = GraphMode.ANNOTATION
        self.app.manager.annotation_type = ShapeType.MARKER
        self.show_marker()

    def scale_button(
        self, button: ttk.Button, image_enum: ImageEnum = None, image_file: str = None
    ) -> None:
        image = None
        if image_enum:
            image = self.app.get_enum_icon(image_enum, width=TOOLBAR_SIZE)
        elif image_file:
            image = self.app.get_file_icon(image_file, width=TOOLBAR_SIZE)
        if image:
            button.config(image=image)
            button.image = image

    def scale(self) -> None:
        self.scale_button(self.play_button, ImageEnum.START)
        self.scale_button(self.select_button, ImageEnum.SELECT)
        self.scale_button(self.link_button, ImageEnum.LINK)
        if self.current_node.image_enum:
            self.scale_button(self.node_button, self.current_node.image_enum)
        else:
            self.scale_button(self.node_button, image_file=self.current_node.image_file)
        self.scale_button(self.network_button, self.current_network.image_enum)
        self.scale_button(self.annotation_button, self.annotation_enum)
        self.scale_button(self.runtime_select_button, ImageEnum.SELECT)
        self.scale_button(self.stop_button, ImageEnum.STOP)
        self.scale_button(self.runtime_marker_button, ImageEnum.MARKER)
        self.scale_button(self.run_command_button, ImageEnum.RUN)
