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

RANGE_COLOR = "#009933"
RANGE_WIDTH = 3


class WlanConfigDialog(Dialog):
    def __init__(
        self, master: "Application", app: "Application", canvas_node: "CanvasNode"
    ):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Wlan Configuration"
        )
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.config_frame = None
        self.range_entry = None
        self.has_error = False
        self.canvas = app.canvas
        self.ranges = {}
        self.positive_int = self.app.master.register(self.validate_and_update)
        try:
            self.config = self.canvas_node.wlan_config
            if not self.config:
                self.config = self.app.core.get_wlan_config(self.node.id)
            self.init_draw_range()
            self.draw()
        except grpc.RpcError as e:
            show_grpc_error(e, self.app, self.app)
            self.has_error = True
            self.destroy()

    def init_draw_range(self):
        if self.canvas_node.id in self.canvas.wireless_network:
            for cid in self.canvas.wireless_network[self.canvas_node.id]:
                x, y = self.canvas.coords(cid)
                range_id = self.canvas.create_oval(
                    x, y, x, y, width=RANGE_WIDTH, outline=RANGE_COLOR, tags="range"
                )
                self.ranges[cid] = range_id

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PADY)
        self.draw_apply_buttons()
        self.top.bind("<Destroy>", self.remove_ranges)

    def draw_apply_buttons(self):
        """
        create node configuration options
        """
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        self.range_entry = self.config_frame.winfo_children()[0].frame.winfo_children()[
            -1
        ]
        self.range_entry.config(validatecommand=(self.positive_int, "%P"))

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, padx=PADX, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        """
        retrieve user's wlan configuration and store the new configuration values
        """
        config = self.config_frame.parse_config()
        self.canvas_node.wlan_config = self.config
        if self.app.core.is_runtime():
            session_id = self.app.core.session_id
            self.app.core.client.set_wlan_config(session_id, self.node.id, config)
        self.remove_ranges()
        self.destroy()

    def remove_ranges(self, event=None):
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
