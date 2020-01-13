"""
mobility configuration
"""
from tkinter import ttk
from typing import TYPE_CHECKING

import grpc

from core.gui.dialogs.dialog import Dialog
from core.gui.errors import show_grpc_error
from core.gui.themes import PADX, PADY
from core.gui.widgets import ConfigFrame

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode


class MobilityConfigDialog(Dialog):
    def __init__(self, master, app: "Application", canvas_node: "CanvasNode"):
        super().__init__(
            master,
            app,
            f"{canvas_node.core_node.name} Mobility Configuration",
            modal=True,
        )
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.config_frame = None
        try:
            self.config = self.app.core.get_mobility_config(self.node.id)
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
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, padx=PADX, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        self.config_frame.parse_config()
        self.app.core.mobility_configs[self.node.id] = self.config
        self.destroy()
