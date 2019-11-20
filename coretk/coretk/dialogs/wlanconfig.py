"""
wlan configuration
"""

import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog
from coretk.dialogs.icondialog import IconDialog
from coretk.dialogs.mobilityconfig import MobilityConfigDialog


class WlanConfigDialog(Dialog):
    def __init__(self, master, app, canvas_node, config):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Wlan Configuration", modal=True
        )
        self.image = canvas_node.image
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.config = config

        self.name = tk.StringVar(value=self.node.name)
        self.range_var = tk.StringVar(value=config["range"])
        self.bandwidth_var = tk.StringVar(value=config["bandwidth"])
        self.delay_var = tk.StringVar(value=config["delay"])
        self.loss_var = tk.StringVar(value=config["error"])
        self.jitter_var = tk.StringVar(value=config["jitter"])
        self.ip4_subnet = tk.StringVar()
        self.ip6_subnet = tk.StringVar()
        self.image_button = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.draw_name_config()
        self.draw_wlan_config()
        self.draw_subnet()
        self.draw_wlan_buttons()
        self.draw_apply_buttons()

    def draw_name_config(self):
        """
        draw image modification part

        :return: nothing
        """
        frame = ttk.Frame(self.top)
        frame.grid(pady=2, sticky="ew")
        frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=0, padx=2, sticky="ew")

        self.image_button = ttk.Button(frame, image=self.image, command=self.click_icon)
        self.image_button.grid(row=0, column=1, padx=3)

    def draw_wlan_config(self):
        """
        create wireless configuration table

        :return: nothing
        """
        label = ttk.Label(self.top, text="Wireless")
        label.grid(sticky="w", pady=2)

        frame = ttk.Frame(self.top)
        frame.grid(pady=2, sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        label = ttk.Label(
            frame,
            text=(
                "The basic range model calculates on/off "
                "connectivity based on pixel distance between nodes."
            ),
        )
        label.grid(row=0, columnspan=2, pady=2, sticky="ew")

        label = ttk.Label(frame, text="Range")
        label.grid(row=1, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.range_var)
        entry.grid(row=1, column=1, sticky="ew")

        label = ttk.Label(frame, text="Bandwidth (bps)")
        label.grid(row=2, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.bandwidth_var)
        entry.grid(row=2, column=1, sticky="ew")

        label = ttk.Label(frame, text="Delay (us)")
        label.grid(row=3, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.delay_var)
        entry.grid(row=3, column=1, sticky="ew")

        label = ttk.Label(frame, text="Loss (%)")
        label.grid(row=4, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.loss_var)
        entry.grid(row=4, column=1, sticky="ew")

        label = ttk.Label(frame, text="Jitter (us)")
        label.grid(row=5, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.jitter_var)
        entry.grid(row=5, column=1, sticky="ew")

    def draw_subnet(self):
        """
        create the entries for ipv4 subnet and ipv6 subnet

        :return: nothing
        """

        frame = ttk.Frame(self.top)
        frame.grid(pady=3, sticky="ew")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        label = ttk.Label(frame, text="IPv4 Subnet")
        label.grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.ip4_subnet)
        entry.grid(row=0, column=1, sticky="ew")

        label = ttk.Label(frame, text="IPv6 Subnet")
        label.grid(row=0, column=2, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.ip6_subnet)
        entry.grid(row=0, column=3, sticky="ew")

    def draw_wlan_buttons(self):
        """
        create wireless node options

        :return:
        """

        frame = ttk.Frame(self.top)
        frame.grid(pady=2, sticky="ew")
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(
            frame, text="ns-2 mobility script...", command=self.click_mobility
        )
        button.grid(row=0, column=0, padx=2, sticky="ew")

        button = ttk.Button(frame, text="Link to all routers")
        button.grid(row=0, column=1, padx=2, sticky="ew")

        button = ttk.Button(frame, text="Choose WLAN members")
        button.grid(row=0, column=2, padx=2, sticky="ew")

    def draw_apply_buttons(self):
        """
        create node configuration options

        :return: nothing
        """
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, padx=2, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, padx=2, sticky="ew")

    def click_mobility(self):
        dialog = MobilityConfigDialog(self, self.app, self.canvas_node)
        dialog.show()

    def click_icon(self):
        dialog = IconDialog(self, self.app, self.node.name, self.canvas_node.image)
        dialog.show()
        if dialog.image:
            self.image = dialog.image
            self.image_button.config(image=self.image)

    def click_apply(self):
        """
        retrieve user's wlan configuration and store the new configuration values

        :return: nothing
        """
        basic_range = self.range_var.get()
        bandwidth = self.bandwidth_var.get()
        delay = self.delay_var.get()
        loss = self.loss_var.get()
        jitter = self.jitter_var.get()

        # set wireless node configuration here
        wlanconfig_manager = self.app.core.wlanconfig_management
        wlanconfig_manager.set_custom_config(
            node_id=self.node.id,
            range=basic_range,
            bandwidth=bandwidth,
            jitter=jitter,
            delay=delay,
            error=loss,
        )
        self.destroy()
