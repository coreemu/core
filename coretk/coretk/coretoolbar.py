import logging
import tkinter as tk

from coretk.images import Images


class CoreToolbar(object):
    """
    Core toolbar class
    """

    # TODO Temporarily have a radio_value instance here, might have to include the run frame
    def __init__(self, master, edit_frame):
        """
        Create a CoreToolbar instance

        :param tkinter.Frame edit_frame: edit frame
        """
        self.master = master
        self.edit_frame = edit_frame
        self.radio_value = tk.IntVar()

        # Used for drawing the horizontally displayed menu items for network-layer nodes and link-layer node
        self.selection_tool_button = None
        # Reference to the option menus
        self.link_layer_option_menu = None
        self.marker_option_menu = None
        self.network_layer_option_menu = None

    def load_toolbar_images(self):
        """
        Load the images that appear in core toolbar

        :return: nothing
        """
        Images.load("core", "core-icon.png")
        Images.load("start", "start.gif")
        Images.load("switch", "lanswitch.gif")
        Images.load("marker", "marker.gif")
        Images.load("router", "router.gif")
        Images.load("select", "select.gif")
        Images.load("link", "link.gif")
        Images.load("hub", "hub.gif")
        Images.load("wlan", "wlan.gif")
        Images.load("rj45", "rj45.gif")
        Images.load("tunnel", "tunnel.gif")
        Images.load("oval", "oval.gif")
        Images.load("rectangle", "rectangle.gif")
        Images.load("text", "text.gif")

    def hide_all_option_menu_frames(self):
        """
        Hide any option menu frame that is displayed on screen so that when a new option menu frame is drawn, only
        one frame is displayed

        :return: nothing
        """
        if self.marker_option_menu:
            self.marker_option_menu.place_forget()
        if self.link_layer_option_menu:
            self.link_layer_option_menu.place_forget()
        if self.network_layer_option_menu:
            self.network_layer_option_menu.place_forget()

    def click_selection_tool(self):
        logging.debug("Click selection tool")

    def create_selection_tool_button(self):
        """
        Create selection tool button

        :return: nothing
        """
        selection_tool_image = Images.get("select")
        self.selection_tool_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=1,
            width=32,
            height=32,
            image=selection_tool_image,
            command=self.click_selection_tool,
        )
        self.selection_tool_button.pack(side=tk.TOP, pady=1)

    def create_start_stop_session_button(self):
        """
        Create start stop session button

        :return: nothing
        """
        start_image = Images.get("start")
        start_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=2,
            width=32,
            height=32,
            image=start_image,
        )
        start_button.pack(side=tk.TOP, pady=1)

    def create_link_tool_button(self):
        """
        Create link tool button

        :return: nothing
        """
        link_image = Images.get("link")
        link_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=3,
            width=32,
            height=32,
            image=link_image,
        )
        link_button.pack(side=tk.TOP, pady=1)

    def create_network_layer_button(self):
        """
        Create network layer button

        :return: nothing
        """
        router_image = Images.get("router")
        network_layer_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=4,
            width=32,
            height=32,
            image=router_image,
        )
        network_layer_button.pack(side=tk.TOP, pady=1)

    def pick_hub(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("hub"))
        if self.radio_value.get() != 5:
            self.radio_value.set(5)
        logging.debug("Pick link-layer node HUB")

    def pick_switch(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("switch"))
        if self.radio_value.get() != 5:
            self.radio_value.set(5)
        logging.debug("Pick link-layer node SWITCH")

    def pick_wlan(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("wlan"))
        if self.radio_value.get() != 5:
            self.radio_value.set(5)
        logging.debug("Pick link-layer node WLAN")

    def pick_rj45(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("rj45"))
        if self.radio_value.get() != 5:
            self.radio_value.set(5)
        logging.debug("Pick link-layer node RJ45")

    def pick_tunnel(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("tunnel"))
        if self.radio_value.get() != 5:
            self.radio_value.set(5)
        logging.debug("Pick link-layer node TUNNEL")

    def draw_link_layer_options(self, link_layer_button):
        # TODO if other buttons are press or nothing is pressed or the button is pressed but frame is forgotten/hidden
        option_frame = tk.Frame(self.master)
        current_choice = self.radio_value.get()
        self.hide_all_option_menu_frames()
        if (
            current_choice == 0
            or current_choice != 5
            or (current_choice == 5 and not option_frame.winfo_manager())
        ):
            hub_image = Images.get("hub")
            switch_image = Images.get("switch")
            wlan_image = Images.get("wlan")
            rj45_image = Images.get("rj45")
            tunnel_image = Images.get("tunnel")

            hub_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=7,
                width=32,
                height=32,
                image=hub_image,
                command=lambda: self.pick_hub(
                    frame=option_frame, main_button=link_layer_button
                ),
            )
            hub_button.pack(side=tk.LEFT, pady=1)
            switch_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=8,
                width=32,
                height=32,
                image=switch_image,
                command=lambda: self.pick_switch(
                    frame=option_frame, main_button=link_layer_button
                ),
            )
            switch_button.pack(side=tk.LEFT, pady=1)
            wlan_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=9,
                width=32,
                height=32,
                image=wlan_image,
                command=lambda: self.pick_wlan(
                    frame=option_frame, main_button=link_layer_button
                ),
            )
            wlan_button.pack(side=tk.LEFT, pady=1)
            rj45_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=10,
                width=32,
                height=32,
                image=rj45_image,
                command=lambda: self.pick_rj45(
                    frame=option_frame, main_button=link_layer_button
                ),
            )
            rj45_button.pack(side=tk.LEFT, pady=1)
            tunnel_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=11,
                width=32,
                height=32,
                image=tunnel_image,
                command=lambda: self.pick_tunnel(
                    frame=option_frame, main_button=link_layer_button
                ),
            )
            tunnel_button.pack(side=tk.LEFT, pady=1)

            _x = (
                link_layer_button.winfo_rootx()
                - self.selection_tool_button.winfo_rootx()
                + 33
            )
            _y = (
                link_layer_button.winfo_rooty()
                - self.selection_tool_button.winfo_rooty()
            )
            option_frame.place(x=_x, y=_y)
            self.link_layer_option_menu = option_frame

    def create_link_layer_button(self):
        """
        Create link-layer node button and the options that represent different link-layer node types

        :return: nothing
        """
        hub_image = Images.get("hub")
        link_layer_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=5,
            width=32,
            height=32,
            image=hub_image,
            command=lambda: self.draw_link_layer_options(link_layer_button),
        )
        link_layer_button.pack(side=tk.TOP, pady=1)

    def pick_marker(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("marker"))
        if self.radio_value.get() != 6:
            self.radio_value.set(6)
        logging.debug("Pick marker")

    def pick_oval(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("oval"))
        if self.radio_value.get() != 6:
            self.radio_value.set(6)
        logging.debug("Pick frame")

    def pick_rectangle(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("rectangle"))
        if self.radio_value.get() != 6:
            self.radio_value.set(6)
        logging.debug("Pick rectangle")

    def pick_text(self, frame, main_button):
        frame.place_forget()
        main_button.configure(image=Images.get("text"))
        if self.radio_value.get() != 6:
            self.radio_value.set(6)
        logging.debug("Pick text")

    def draw_marker_options(self, main_button):
        # TODO if no button pressed, or other buttons being pressed, or marker button is being pressed but no frame is drawn
        option_frame = tk.Frame(self.master)
        current_choice = self.radio_value.get()
        self.hide_all_option_menu_frames()
        # TODO might need to find better way to write this, or might not
        if (
            current_choice == 0
            or current_choice != 6
            or (current_choice == 6 and not option_frame.winfo_manager())
        ):
            marker_image = Images.get("marker")
            oval_image = Images.get("oval")
            rectangle_image = Images.get("rectangle")
            text_image = Images.get("text")

            marker_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=12,
                width=32,
                height=32,
                image=marker_image,
                command=lambda: self.pick_marker(
                    frame=option_frame, main_button=main_button
                ),
            )
            marker_button.pack(side=tk.LEFT, pady=1)
            oval_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=13,
                width=32,
                height=32,
                image=oval_image,
                command=lambda: self.pick_oval(
                    frame=option_frame, main_button=main_button
                ),
            )
            oval_button.pack(side=tk.LEFT, pady=1)
            rectangle_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=14,
                width=32,
                height=32,
                image=rectangle_image,
                command=lambda: self.pick_rectangle(
                    frame=option_frame, main_button=main_button
                ),
            )
            rectangle_button.pack(side=tk.LEFT, pady=1)
            text_button = tk.Radiobutton(
                option_frame,
                indicatoron=False,
                variable=self.radio_value,
                value=15,
                width=32,
                height=32,
                image=text_image,
                command=lambda: self.pick_text(
                    frame=option_frame, main_button=main_button
                ),
            )
            text_button.pack(side=tk.LEFT, pady=1)
            self.master.update()
            _x = (
                main_button.winfo_rootx()
                - self.selection_tool_button.winfo_rootx()
                + 33
            )
            _y = main_button.winfo_rooty() - self.selection_tool_button.winfo_rooty()
            option_frame.place(x=_x, y=_y)
            self.marker_option_menu = option_frame

    def create_marker_button(self):
        """
        Create marker button and options that represent different marker types

        :return: nothing
        """
        marker_image = Images.get("marker")
        marker_main_button = tk.Radiobutton(
            self.edit_frame,
            indicatoron=False,
            variable=self.radio_value,
            value=6,
            width=32,
            height=32,
            image=marker_image,
            command=lambda: self.draw_marker_options(marker_main_button),
        )
        marker_main_button.pack(side=tk.TOP, pady=1)

    def create_toolbar(self):
        self.load_toolbar_images()
        self.create_selection_tool_button()
        self.create_start_stop_session_button()
        self.create_link_tool_button()
        self.create_network_layer_button()
        self.create_link_layer_button()
        self.create_marker_button()
