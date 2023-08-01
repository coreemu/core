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
    from core.gui.graph.graph import CanvasGraph

RANGE_COLOR: str = "#009933"
RANGE_WIDTH: int = 3


class WlanConfigDialog(Dialog):
    def __init__(self, app: "Application", canvas_node: "CanvasNode") -> None:
        super().__init__(app, f"{canvas_node.core_node.name} WLAN Configuration")
        self.canvas: "CanvasGraph" = app.manager.current()
        self.canvas_node: "CanvasNode" = canvas_node
        self.node: Node = canvas_node.core_node
        self.config_frame: Optional[ConfigFrame] = None
        self.range_entry: Optional[ttk.Entry] = None
        self.has_error: bool = False
        self.ranges: dict[int, int] = {}
        self.positive_int: int = self.app.master.register(self.validate_and_update)
        try:
            config = self.node.wlan_config
            if not config:
                config = self.app.core.get_wlan_config(self.node.id)
            self.config: dict[str, ConfigOption] = config
            self.init_draw_range()
            self.draw()
        except grpc.RpcError as e:
            self.app.show_grpc_exception("WLAN Config Error", e)
            self.has_error: bool = True
            self.destroy()

    def init_draw_range(self) -> None:
        if self.canvas_node.id in self.canvas.wireless_network:
            for cid in self.canvas.wireless_network[self.canvas_node.id]:
                x, y = self.canvas.coords(cid)
                range_id = self.canvas.create_oval(
                    x, y, x, y, width=RANGE_WIDTH, outline=RANGE_COLOR, tags="range"
                )
                self.ranges[cid] = range_id

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky=tk.NSEW, pady=PADY)
        self.draw_apply_buttons()
        self.top.bind("<Destroy>", self.remove_ranges)

    def draw_apply_buttons(self) -> None:
        """
        create node configuration options
        """
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        self.range_entry = self.config_frame.winfo_children()[0].frame.winfo_children()[
            -1
        ]
        self.range_entry.config(validatecommand=(self.positive_int, "%P"))

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, padx=PADX, sticky=tk.EW)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_apply(self) -> None:
        """
        retrieve user's wlan configuration and store the new configuration values
        """
        config = self.config_frame.parse_config()
        self.node.wlan_config = self.config
        if self.app.core.is_runtime():
            session_id = self.app.core.session.id
            self.app.core.client.set_wlan_config(session_id, self.node.id, config)
        self.remove_ranges()
        self.destroy()

    def remove_ranges(self, event=None) -> None:
        for cid in self.canvas.find_withtag("range"):
            self.canvas.delete(cid)
        self.ranges.clear()

    def validate_and_update(self, s: str) -> bool:
        """
        custom validation to also redraw the mdr ranges when the range value changes
        """
        if len(s) == 0:
            return True
        try:
            int_value = int(s) / 2
            if int_value >= 0:
                net_range = int_value * self.canvas.ratio
                if self.canvas_node.id in self.canvas.wireless_network:
                    for cid in self.canvas.wireless_network[self.canvas_node.id]:
                        x, y = self.canvas.coords(cid)
                        self.canvas.coords(
                            self.ranges[cid],
                            x - net_range,
                            y - net_range,
                            x + net_range,
                            y + net_range,
                        )
                return True
            return False
        except ValueError:
            return False
