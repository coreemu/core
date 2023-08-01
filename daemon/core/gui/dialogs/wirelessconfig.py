import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

import grpc

from core.api.grpc.wrappers import ConfigOption, Node
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import ConfigFrame

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode


class WirelessConfigDialog(Dialog):
    def __init__(self, app: "Application", canvas_node: "CanvasNode"):
        super().__init__(app, f"Wireless Configuration - {canvas_node.core_node.name}")
        self.node: Node = canvas_node.core_node
        self.config_frame: Optional[ConfigFrame] = None
        self.config: dict[str, ConfigOption] = {}
        try:
            config = self.node.wireless_config
            if not config:
                config = self.app.core.get_wireless_config(self.node.id)
            self.config: dict[str, ConfigOption] = config
            self.draw()
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Wireless Config Error", e)
            self.has_error: bool = True
            self.destroy()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky=tk.NSEW, pady=PADY)
        self.draw_buttons()

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, padx=PADX, sticky=tk.EW)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_apply(self) -> None:
        self.config_frame.parse_config()
        self.node.wireless_config = self.config
        self.destroy()
