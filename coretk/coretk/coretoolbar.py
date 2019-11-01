import logging
import tkinter as tk

# from core.api.grpc import core_pb2
from coretk.coretoolbarhelp import CoreToolbarHelp
from coretk.graph import GraphMode
from coretk.images import ImageEnum, Images
from coretk.tooltip import CreateToolTip

# from enum import Enum


# class SessionStateEnum(Enum):
#     NONE = "none"
#     DEFINITION = "definition"
#     CONFIGURATION = "configuration"
#     RUNTIME = "runtime"
#     DATACOLLECT = "datacollect"
#     SHUTDOWN = "shutdown"
#     INSTANTIATION = "instantiation"


class CoreToolbar(object):
    """
    Core toolbar class
    """

    def __init__(self, app, edit_frame, menubar):
        """
        Create a CoreToolbar instance

        :param tkinter.Frame edit_frame: edit frame
        """
        self.app = app
        self.master = app.master
        self.edit_frame = edit_frame
        self.menubar = menubar
        self.radio_value = tk.IntVar()
        self.exec_radio_value = tk.IntVar()

        # button dimension
        self.width = 32
        self.height = 32

        self.selection_tool_button = None

        # Reference to the option menus
        self.link_layer_option_menu = None
        self.marker_option_menu = None
        self.network_layer_option_menu = None

        self.canvas = None

    def destroy_previous_frame(self):
        """
        Destroy any extra frame from previous before drawing a new one

        :return: nothing
        """
        if (
            self.network_layer_option_menu
            and self.network_layer_option_menu.winfo_exists()
        ):
            self.network_layer_option_menu.destroy()
        if self.link_layer_option_menu and self.link_layer_option_menu.winfo_exists():
            self.link_layer_option_menu.destroy()
        if self.marker_option_menu and self.marker_option_menu.winfo_exists():
            self.marker_option_menu.destroy()

    def destroy_children_widgets(self):
        """
        Destroy all children of a parent widget

        :param tkinter.Frame parent: parent frame
        :return: nothing
        """

        for i in self.edit_frame.winfo_children():
            if i.winfo_name() != "!frame":
                i.destroy()

    def create_button(self, img, func, frame, main_button, btt_message):
        """
        Create button and put it on the frame

        :param PIL.Image img: button image
        :param func: the command that is executed when button is clicked
        :param tkinter.Frame frame: frame that contains the button
        :param tkinter.Radiobutton main_button: main button
        :return: nothing
        """
        button = tk.Button(frame, width=self.width, height=self.height, image=img)
        button.pack(side=tk.LEFT, pady=1)
        CreateToolTip(button, btt_message)
        button.bind("<Button-1>", lambda mb: func(main_button))

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
        button.pack(side=tk.TOP, pady=1)
        CreateToolTip(button, tooltip_msg)

    def create_regular_button(self, frame, image, func, btt_message):
        button = tk.Button(
            frame, width=self.width, height=self.height, image=image, command=func
        )
        button.pack(side=tk.TOP, pady=1)
        CreateToolTip(button, btt_message)

    def draw_button_menu_frame(self, edit_frame, option_frame, main_button):
        """
        Draw option menu frame right next to the main button

        :param tkinter.Frame edit_frame: parent frame of the main button
        :param tkinter.Frame option_frame: option frame to draw
        :param tkinter.Radiobutton main_button: the main button
        :return: nothing
        """

        first_button = edit_frame.winfo_children()[0]
        _x = main_button.winfo_rootx() - first_button.winfo_rootx() + 40
        _y = main_button.winfo_rooty() - first_button.winfo_rooty() - 1
        option_frame.place(x=_x, y=_y)

    def bind_widgets_before_frame_hide(self, frame):
        """
        Bind the widgets to a left click, when any of the widgets is clicked, the menu option frame is destroyed before
        any further action is performed

        :param tkinter.Frame frame: the frame to be destroyed
        :return: nothing
        """
        self.menubar.bind("<Button-1>", lambda e: frame.destroy())
        self.master.bind("<Button-1>", lambda e: frame.destroy())

    def unbind_widgets_after_frame_hide(self):
        """
        Unbind the widgets to make sure everything works normally again after the menu option frame is destroyed

        :return: nothing
        """
        self.master.unbind("<Button-1>")
        self.menubar.unbind("Button-1>")

    def click_selection_tool(self):
        logging.debug("Click SELECTION TOOL")
        self.canvas.mode = GraphMode.SELECT

    def click_start_session_tool(self):
        """
        Start session handler: redraw buttons, send node and link messages to grpc server

        :return: nothing
        """
        logging.debug("Click START STOP SESSION button")
        helper = CoreToolbarHelp(self.app)
        self.destroy_children_widgets()
        self.canvas.mode = GraphMode.SELECT

        # set configuration state
        # state = self.canvas.core_grpc.get_session_state()
        # if state == core_pb2.SessionState.SHUTDOWN or self.application.is_open_xml:
        #     self.canvas.core_grpc.set_session_state(SessionStateEnum.DEFINITION.value)
        #     self.application.is_open_xml = False
        #
        # self.canvas.core_grpc.set_session_state(SessionStateEnum.CONFIGURATION.value)
        # helper.add_nodes()
        # helper.add_edges()
        # self.canvas.core_grpc.set_session_state(SessionStateEnum.INSTANTIATION.value)
        helper.gui_start_session()
        self.create_runtime_toolbar()

        # for node in self.canvas.grpc_manager.nodes.values():
        #     print(node.type, node.model, int(node.x), int(node.y), node.name, node.node_id)
        #     self.canvas.core_grpc.add_node(
        #         node.type, node.model, int(node.x), int(node.y), node.name, node.node_id
        #     )

        # print(len(self.canvas.grpc_manager.edges))
        # for edge in self.canvas.grpc_manager.edges.values():
        #     print(edge.id1, edge.id2, edge.type1, edge.type2)
        #     self.canvas.core_grpc.add_link(
        #         edge.id1, edge.id2, edge.type1, edge.type2, edge
        #     )
        # self.canvas.core_grpc.get_session()
        # self.application.is_open_xml = False

    def click_link_tool(self):
        logging.debug("Click LINK button")
        self.canvas.mode = GraphMode.EDGE

    def pick_router(self, main_button):
        logging.debug("Pick router option")
        self.network_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.ROUTER))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.ROUTER)
        self.canvas.draw_node_name = "router"

    def pick_host(self, main_button):
        logging.debug("Pick host option")
        self.network_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.HOST))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.HOST)
        self.canvas.draw_node_name = "host"

    def pick_pc(self, main_button):
        logging.debug("Pick PC option")
        self.network_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.PC))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.PC)
        self.canvas.draw_node_name = "PC"

    def pick_mdr(self, main_button):
        logging.debug("Pick MDR option")
        self.network_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.MDR))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.MDR)
        self.canvas.draw_node_name = "mdr"

    def pick_prouter(self, main_button):
        logging.debug("Pick prouter option")
        self.network_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.PROUTER))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.PROUTER)
        self.canvas.draw_node_name = "prouter"

    def pick_ovs(self, main_button):
        logging.debug("Pick OVS option")
        self.network_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.OVS))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.OVS)
        self.canvas.draw_node_name = "OVS"

    # TODO what graph node is this
    def pick_editnode(self, main_button):
        self.network_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.EDITNODE))
        logging.debug("Pick editnode option")

    def draw_network_layer_options(self, network_layer_button):
        """
        Draw the options for network-layer button

        :param tkinter.Radiobutton network_layer_button: network-layer button
        :return: nothing
        """
        # create a frame and add buttons to it
        self.destroy_previous_frame()
        option_frame = tk.Frame(self.master, padx=1, pady=1)
        img_list = [
            Images.get(ImageEnum.ROUTER),
            Images.get(ImageEnum.HOST),
            Images.get(ImageEnum.PC),
            Images.get(ImageEnum.MDR),
            Images.get(ImageEnum.PROUTER),
            Images.get(ImageEnum.OVS),
            Images.get(ImageEnum.EDITNODE),
        ]
        func_list = [
            self.pick_router,
            self.pick_host,
            self.pick_pc,
            self.pick_mdr,
            self.pick_prouter,
            self.pick_ovs,
            self.pick_editnode,
        ]
        tooltip_list = [
            "router",
            "host",
            "PC",
            "mdr",
            "prouter",
            "OVS",
            "edit node types",
        ]
        for i in range(len(img_list)):
            self.create_button(
                img_list[i],
                func_list[i],
                option_frame,
                network_layer_button,
                tooltip_list[i],
            )

        # place frame at a calculated position as well as keep a reference of that frame
        self.draw_button_menu_frame(self.edit_frame, option_frame, network_layer_button)
        self.network_layer_option_menu = option_frame

        # destroy the frame before any further actions on other widgets
        self.bind_widgets_before_frame_hide(option_frame)
        option_frame.wait_window(option_frame)
        self.unbind_widgets_after_frame_hide()

    def create_network_layer_button(self):
        """
        Create network layer button

        :return: nothing
        """
        router_image = Images.get(ImageEnum.ROUTER)
        network_layer_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=3,
            width=self.width,
            height=self.height,
            image=router_image,
            command=lambda: self.draw_network_layer_options(network_layer_button),
        )
        network_layer_button.pack(side=tk.TOP, pady=1)
        CreateToolTip(network_layer_button, "Network-layer virtual nodes")

    def pick_hub(self, main_button):
        logging.debug("Pick link-layer node HUB")
        self.link_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.HUB))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.HUB)
        self.canvas.draw_node_name = "hub"

    def pick_switch(self, main_button):
        logging.debug("Pick link-layer node SWITCH")
        self.link_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.SWITCH))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.SWITCH)
        self.canvas.draw_node_name = "switch"

    def pick_wlan(self, main_button):
        logging.debug("Pick link-layer node WLAN")
        self.link_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.WLAN))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.WLAN)
        self.canvas.draw_node_name = "wlan"

    def pick_rj45(self, main_button):
        logging.debug("Pick link-layer node RJ45")
        self.link_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.RJ45))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.RJ45)
        self.canvas.draw_node_name = "rj45"

    def pick_tunnel(self, main_button):
        logging.debug("Pick link-layer node TUNNEL")
        self.link_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.TUNNEL))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.TUNNEL)
        self.canvas.draw_node_name = "tunnel"

    def pick_emane(self, main_button):
        self.link_layer_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.EMANE.value))
        self.canvas.mode = GraphMode.PICKNODE
        self.canvas.draw_node_image = Images.get(ImageEnum.EMANE.value)
        self.canvas.draw_node_name = "emane"

    def draw_link_layer_options(self, link_layer_button):
        """
        Draw the options for link-layer button

        :param tkinter.RadioButton link_layer_button: link-layer button
        :return: nothing
        """
        # create a frame and add buttons to it
        self.destroy_previous_frame()
        option_frame = tk.Frame(self.master, padx=1, pady=1)
        img_list = [
            Images.get(ImageEnum.HUB),
            Images.get(ImageEnum.SWITCH),
            Images.get(ImageEnum.WLAN),
            Images.get(ImageEnum.EMANE),
            Images.get(ImageEnum.RJ45),
            Images.get(ImageEnum.TUNNEL),
        ]
        func_list = [
            self.pick_hub,
            self.pick_switch,
            self.pick_wlan,
            self.pick_emane,
            self.pick_rj45,
            self.pick_tunnel,
        ]
        tooltip_list = [
            "ethernet hub",
            "ethernet switch",
            "wireless LAN",
            "emane",
            "rj45 physical interface tool",
            "tunnel tool",
        ]
        for i in range(len(img_list)):
            self.create_button(
                img_list[i],
                func_list[i],
                option_frame,
                link_layer_button,
                tooltip_list[i],
            )

        # place frame at a calculated position as well as keep a reference of the frame
        self.draw_button_menu_frame(self.edit_frame, option_frame, link_layer_button)
        self.link_layer_option_menu = option_frame

        # destroy the frame before any further actions on other widgets
        self.bind_widgets_before_frame_hide(option_frame)
        option_frame.wait_window(option_frame)
        self.unbind_widgets_after_frame_hide()

    def create_link_layer_button(self):
        """
        Create link-layer node button and the options that represent different link-layer node types

        :return: nothing
        """
        hub_image = Images.get(ImageEnum.HUB)
        link_layer_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=4,
            width=self.width,
            height=self.height,
            image=hub_image,
            command=lambda: self.draw_link_layer_options(link_layer_button),
        )
        link_layer_button.pack(side=tk.TOP, pady=1)
        CreateToolTip(link_layer_button, "link-layer nodes")

    def pick_marker(self, main_button):
        self.marker_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.MARKER))
        logging.debug("Pick MARKER")

    def pick_oval(self, main_button):
        self.marker_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.OVAL))
        logging.debug("Pick OVAL")

    def pick_rectangle(self, main_button):
        self.marker_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.RECTANGLE))
        logging.debug("Pick RECTANGLE")

    def pick_text(self, main_button):
        self.marker_option_menu.destroy()
        main_button.configure(image=Images.get(ImageEnum.TEXT))
        logging.debug("Pick TEXT")

    def draw_marker_options(self, main_button):
        """
        Draw the options for marker button

        :param tkinter.Radiobutton main_button: the main button
        :return: nothing
        """
        # create a frame and add buttons to it
        self.destroy_previous_frame()
        option_frame = tk.Frame(self.master, padx=1, pady=1)
        img_list = [
            Images.get(ImageEnum.MARKER),
            Images.get(ImageEnum.OVAL),
            Images.get(ImageEnum.RECTANGLE),
            Images.get(ImageEnum.TEXT),
        ]
        func_list = [
            self.pick_marker,
            self.pick_oval,
            self.pick_rectangle,
            self.pick_text,
        ]
        tooltip_list = ["marker", "oval", "rectangle", "text"]
        for i in range(len(img_list)):
            self.create_button(
                img_list[i], func_list[i], option_frame, main_button, tooltip_list[i]
            )

        # place the frame at a calculated position as well as keep a reference of that frame
        self.draw_button_menu_frame(self.edit_frame, option_frame, main_button)
        self.marker_option_menu = option_frame

        # destroy the frame before any further actions on other widgets
        self.bind_widgets_before_frame_hide(option_frame)
        option_frame.wait_window(option_frame)
        self.unbind_widgets_after_frame_hide()

    def create_marker_button(self):
        """
        Create marker button and options that represent different marker types

        :return: nothing
        """
        marker_image = Images.get(ImageEnum.MARKER)
        marker_main_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=5,
            width=self.width,
            height=self.height,
            image=marker_image,
            command=lambda: self.draw_marker_options(marker_main_button),
        )
        marker_main_button.pack(side=tk.TOP, pady=1)
        CreateToolTip(marker_main_button, "background annotation tools")

    def create_toolbar(self):
        """
        Create buttons for toolbar in edit mode

        :return: nothing
        """
        self.create_regular_button(
            self.edit_frame,
            Images.get(ImageEnum.START),
            self.click_start_session_tool,
            "start the session",
        )
        self.create_radio_button(
            self.edit_frame,
            Images.get(ImageEnum.SELECT),
            self.click_selection_tool,
            self.radio_value,
            1,
            "selection tool",
        )
        self.create_radio_button(
            self.edit_frame,
            Images.get(ImageEnum.LINK),
            self.click_link_tool,
            self.radio_value,
            2,
            "link tool",
        )
        self.create_network_layer_button()
        self.create_link_layer_button()
        self.create_marker_button()
        self.radio_value.set(1)

    def create_observe_button(self):
        menu_button = tk.Menubutton(
            self.edit_frame,
            image=Images.get(ImageEnum.OBSERVE),
            width=self.width,
            height=self.height,
            direction=tk.RIGHT,
            relief=tk.RAISED,
        )
        menu_button.menu = tk.Menu(menu_button, tearoff=0)
        menu_button["menu"] = menu_button.menu
        menu_button.pack(side=tk.TOP, pady=1)

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
        self.destroy_children_widgets()
        self.app.core.stop_session()
        self.create_toolbar()

    def click_run_button(self):
        logging.debug("Click on RUN button")

    def click_plot_button(self):
        logging.debug("Click on plot button")

    def click_marker_button(self):
        logging.debug("Click on marker button")

    def click_two_node_button(self):
        logging.debug("Click TWONODE button")

    def create_runtime_toolbar(self):
        self.create_regular_button(
            self.edit_frame,
            Images.get(ImageEnum.STOP),
            self.click_stop_button,
            "stop the session",
        )
        self.create_radio_button(
            self.edit_frame,
            Images.get(ImageEnum.SELECT),
            self.click_selection_tool,
            self.exec_radio_value,
            1,
            "selection tool",
        )
        self.create_observe_button()
        self.create_radio_button(
            self.edit_frame,
            Images.get(ImageEnum.PLOT),
            self.click_plot_button,
            self.exec_radio_value,
            2,
            "plot",
        )
        self.create_radio_button(
            self.edit_frame,
            Images.get(ImageEnum.MARKER),
            self.click_marker_button,
            self.exec_radio_value,
            3,
            "marker",
        )
        self.create_radio_button(
            self.edit_frame,
            Images.get(ImageEnum.TWONODE),
            self.click_two_node_button,
            self.exec_radio_value,
            4,
            "run command from one node to another",
        )
        self.create_regular_button(
            self.edit_frame, Images.get(ImageEnum.RUN), self.click_run_button, "run"
        )
        self.exec_radio_value.set(1)