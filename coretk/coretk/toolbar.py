import logging
import tkinter as tk
from functools import partial

from coretk.dialogs.customnodes import CustomNodesDialog
from coretk.graph import GraphMode
from coretk.images import ImageEnum, Images
from coretk.tooltip import CreateToolTip


class Toolbar(tk.Frame):
    """
    Core toolbar class
    """

    def __init__(self, master, app, cnf={}, **kwargs):
        """
        Create a CoreToolbar instance

        :param tkinter.Frame edit_frame: edit frame
        """
        super().__init__(master, cnf, **kwargs)
        self.app = app
        self.master = app.master
        self.radio_value = tk.IntVar()
        self.exec_radio_value = tk.IntVar()

        # button dimension
        self.width = 32
        self.height = 32

        # Reference to the option menus
        self.selection_tool_button = None
        self.link_layer_option_menu = None
        self.marker_option_menu = None
        self.network_layer_option_menu = None
        self.node_button = None
        self.network_button = None
        self.annotation_button = None

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
        self.design_frame = tk.Frame(self)
        self.design_frame.grid(row=0, column=0, sticky="nsew")
        self.design_frame.columnconfigure(0, weight=1)

        self.create_regular_button(
            self.design_frame,
            Images.get(ImageEnum.START),
            self.click_start_session_tool,
            "start the session",
        )
        self.create_radio_button(
            self.design_frame,
            Images.get(ImageEnum.SELECT),
            self.click_selection_tool,
            self.radio_value,
            1,
            "selection tool",
        )
        self.create_radio_button(
            self.design_frame,
            Images.get(ImageEnum.LINK),
            self.click_link_tool,
            self.radio_value,
            2,
            "link tool",
        )
        self.create_node_button()
        self.create_link_layer_button()
        self.create_marker_button()
        self.radio_value.set(1)

    def draw_runtime_frame(self):
        self.runtime_frame = tk.Frame(self)
        self.runtime_frame.grid(row=0, column=0, sticky="nsew")
        self.runtime_frame.columnconfigure(0, weight=1)

        self.create_regular_button(
            self.runtime_frame,
            Images.get(ImageEnum.STOP),
            self.click_stop_button,
            "stop the session",
        )
        self.create_radio_button(
            self.runtime_frame,
            Images.get(ImageEnum.SELECT),
            self.click_selection_tool,
            self.exec_radio_value,
            1,
            "selection tool",
        )
        self.create_observe_button()
        self.create_radio_button(
            self.runtime_frame,
            Images.get(ImageEnum.PLOT),
            self.click_plot_button,
            self.exec_radio_value,
            2,
            "plot",
        )
        self.create_radio_button(
            self.runtime_frame,
            Images.get(ImageEnum.MARKER),
            self.click_marker_button,
            self.exec_radio_value,
            3,
            "marker",
        )
        self.create_radio_button(
            self.runtime_frame,
            Images.get(ImageEnum.TWONODE),
            self.click_two_node_button,
            self.exec_radio_value,
            4,
            "run command from one node to another",
        )
        self.create_regular_button(
            self.runtime_frame, Images.get(ImageEnum.RUN), self.click_run_button, "run"
        )
        self.exec_radio_value.set(1)

    def draw_node_picker(self):
        self.hide_pickers()
        self.node_picker = tk.Frame(self.master, padx=1, pady=1)
        nodes = [
            (ImageEnum.ROUTER, "router"),
            (ImageEnum.HOST, "host"),
            (ImageEnum.PC, "PC"),
            (ImageEnum.MDR, "mdr"),
            (ImageEnum.PROUTER, "prouter"),
            (ImageEnum.EDITNODE, "custom node types"),
        ]
        for image_enum, tooltip in nodes:
            self.create_button(
                Images.get(image_enum),
                partial(self.update_button, self.node_button, image_enum, tooltip),
                self.node_picker,
                tooltip,
            )
        self.show_picker(self.node_button, self.node_picker)

    def show_picker(self, button, picker):
        first_button = self.winfo_children()[0]
        x = button.winfo_rootx() - first_button.winfo_rootx() + 40
        y = button.winfo_rooty() - first_button.winfo_rooty() - 1
        picker.place(x=x, y=y)
        self.app.bind_all("<Button-1>", lambda e: self.hide_pickers())
        self.wait_window(picker)
        self.app.unbind_all("<Button-1>")

    def create_button(self, img, func, frame, tooltip):
        """
        Create button and put it on the frame

        :param PIL.Image img: button image
        :param func: the command that is executed when button is clicked
        :param tkinter.Frame frame: frame that contains the button
        :param str tooltip: tooltip text
        :return: nothing
        """
        button = tk.Button(frame, width=self.width, height=self.height, image=img)
        button.bind("<Button-1>", lambda e: func())
        button.grid(pady=1)
        CreateToolTip(button, tooltip)

    def create_radio_button(self, frame, image, func, variable, value, tooltip_msg):
        button = tk.Radiobutton(
            frame,
            indicatoron=False,
            width=self.width,
            height=self.height,
            image=image,
            value=value,
            variable=variable,
            command=func,
        )
        button.grid()
        CreateToolTip(button, tooltip_msg)

    def create_regular_button(self, frame, image, func, tooltip):
        button = tk.Button(
            frame, width=self.width, height=self.height, image=image, command=func
        )
        button.grid()
        CreateToolTip(button, tooltip)

    def click_selection_tool(self):
        logging.debug("clicked selection tool")
        self.app.canvas.mode = GraphMode.SELECT

    def click_start_session_tool(self):
        """
        Start session handler redraw buttons, send node and link messages to grpc
        server.

        :return: nothing
        """
        logging.debug("clicked start button")
        self.app.canvas.mode = GraphMode.SELECT
        self.app.core.start_session()
        self.runtime_frame.tkraise()

    def click_link_tool(self):
        logging.debug("Click LINK button")
        self.app.canvas.mode = GraphMode.EDGE

    def update_button(self, button, image_enum, name):
        logging.info("update button(%s): %s, %s", button, image_enum, name)
        self.hide_pickers()
        if image_enum == ImageEnum.EDITNODE:
            dialog = CustomNodesDialog(self.app, self.app)
            dialog.show()
        else:
            image = Images.get(image_enum)
            logging.info("updating button(%s): %s", button, name)
            button.configure(image=image)
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
        router_image = Images.get(ImageEnum.ROUTER)
        self.node_button = tk.Radiobutton(
            self.design_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=3,
            width=self.width,
            height=self.height,
            image=router_image,
            command=self.draw_node_picker,
        )
        self.node_button.grid()
        CreateToolTip(self.node_button, "Network-layer virtual nodes")

    def draw_network_picker(self):
        """
        Draw the options for link-layer button

        :param tkinter.RadioButton link_layer_button: link-layer button
        :return: nothing
        """
        self.hide_pickers()
        self.network_picker = tk.Frame(self.master, padx=1, pady=1)
        nodes = [
            (ImageEnum.HUB, "hub", "ethernet hub"),
            (ImageEnum.SWITCH, "switch", "ethernet switch"),
            (ImageEnum.WLAN, "wlan", "wireless LAN"),
            (ImageEnum.EMANE, "emane", "EMANE"),
            (ImageEnum.RJ45, "rj45", "rj45 physical interface tool"),
            (ImageEnum.TUNNEL, "tunnel", "tunnel tool"),
        ]
        for image_enum, name, tooltip in nodes:
            self.create_button(
                Images.get(image_enum),
                partial(self.update_button, self.network_button, image_enum, name),
                self.network_picker,
                tooltip,
            )
        self.show_picker(self.network_button, self.network_picker)

    def create_link_layer_button(self):
        """
        Create link-layer node button and the options that represent different link-layer node types

        :return: nothing
        """
        hub_image = Images.get(ImageEnum.HUB)
        self.network_button = tk.Radiobutton(
            self.design_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=4,
            width=self.width,
            height=self.height,
            image=hub_image,
            command=self.draw_network_picker,
        )
        self.network_button.grid()
        CreateToolTip(self.network_button, "link-layer nodes")

    def draw_annotation_picker(self):
        """
        Draw the options for marker button

        :param tkinter.Radiobutton main_button: the main button
        :return: nothing
        """
        self.hide_pickers()
        self.annotation_picker = tk.Frame(self.master, padx=1, pady=1)
        nodes = [
            (ImageEnum.MARKER, "marker"),
            (ImageEnum.OVAL, "oval"),
            (ImageEnum.RECTANGLE, "rectangle"),
            (ImageEnum.TEXT, "text"),
        ]
        for image_enum, tooltip in nodes:
            self.create_button(
                Images.get(image_enum),
                partial(self.update_annotation, image_enum),
                self.annotation_picker,
                tooltip,
            )
        self.show_picker(self.annotation_button, self.annotation_picker)

    def create_marker_button(self):
        """
        Create marker button and options that represent different marker types

        :return: nothing
        """
        marker_image = Images.get(ImageEnum.MARKER)
        self.annotation_button = tk.Radiobutton(
            self.design_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=5,
            width=self.width,
            height=self.height,
            image=marker_image,
            command=self.draw_annotation_picker,
        )
        self.annotation_button.grid()
        CreateToolTip(self.annotation_button, "background annotation tools")

    def create_observe_button(self):
        menu_button = tk.Menubutton(
            self.runtime_frame,
            image=Images.get(ImageEnum.OBSERVE),
            width=self.width,
            height=self.height,
            direction=tk.RIGHT,
            relief=tk.RAISED,
        )
        menu_button.menu = tk.Menu(menu_button, tearoff=0)
        menu_button["menu"] = menu_button.menu
        menu_button.grid()

        menu_button.menu.add_command(label="None")
        menu_button.menu.add_command(label="processes")
        menu_button.menu.add_command(label="ifconfig")
        menu_button.menu.add_command(label="IPv4 routes")
        menu_button.menu.add_command(label="IPv6 routes")
        menu_button.menu.add_command(label="OSPFv2 neighbors")
        menu_button.menu.add_command(label="OSPFv3 neighbors")
        menu_button.menu.add_command(label="Listening sockets")
        menu_button.menu.add_command(label="IPv4 MFC entries")
        menu_button.menu.add_command(label="IPv6 MFC entries")
        menu_button.menu.add_command(label="firewall rules")
        menu_button.menu.add_command(label="IPSec policies")
        menu_button.menu.add_command(label="docker logs")
        menu_button.menu.add_command(label="OSPFv3 MDR level")
        menu_button.menu.add_command(label="PIM neighbors")
        menu_button.menu.add_command(label="Edit...")

    def click_stop_button(self):
        """
        redraw buttons on the toolbar, send node and link messages to grpc server

        :return: nothing
        """
        logging.debug("Click on STOP button ")
        self.app.core.stop_session()
        self.design_frame.tkraise()

    def update_annotation(self, image_enum):
        logging.info("clicked annotation: ")
        self.hide_pickers()
        self.annotation_button.configure(image=Images.get(image_enum))

    def click_run_button(self):
        logging.debug("Click on RUN button")

    def click_plot_button(self):
        logging.debug("Click on plot button")

    def click_marker_button(self):
        logging.debug("Click on marker button")

    def click_two_node_button(self):
        logging.debug("Click TWONODE button")
