"""
wlan configuration
"""

from tkinter import ttk

import grpc

from coretk.dialogs.dialog import Dialog
from coretk.errors import show_grpc_error
from coretk.themes import PADX, PADY
from coretk.widgets import ConfigFrame


class WlanConfigDialog(Dialog):
    def __init__(self, master, app, canvas_node):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Wlan Configuration", modal=True
        )
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.config_frame = None
        try:
            self.config = self.app.core.get_wlan_config(self.node.id)
        except grpc.RpcError as e:
            show_grpc_error(e)
            self.destroy()
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PADY)
        self.draw_apply_buttons()

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
        button.grid(row=0, column=0, padx=PADX, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        """
        retrieve user's wlan configuration and store the new configuration values

        :return: nothing
        """
        self.config_frame.parse_config()
        self.app.core.wlan_configs[self.node.id] = self.config
        self.destroy()
