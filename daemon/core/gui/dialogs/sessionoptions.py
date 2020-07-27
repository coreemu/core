import logging
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict, Optional

import grpc

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import ConfigFrame
from core.gui.wrappers import ConfigOption

if TYPE_CHECKING:
    from core.gui.app import Application


class SessionOptionsDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Session Options")
        self.config_frame: Optional[ConfigFrame] = None
        self.has_error: bool = False
        self.config: Dict[str, ConfigOption] = self.get_config()
        self.enabled: bool = not self.app.core.is_runtime()
        if not self.has_error:
            self.draw()

    def get_config(self) -> Dict[str, ConfigOption]:
        try:
            session_id = self.app.core.session_id
            response = self.app.core.client.get_session_options(session_id)
            return ConfigOption.from_dict(response.config)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Get Session Options Error", e)
            self.has_error = True
            self.destroy()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config, self.enabled)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PADY)

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        state = tk.NORMAL if self.enabled else tk.DISABLED
        button = ttk.Button(frame, text="Save", command=self.save, state=state)
        button.grid(row=0, column=0, padx=PADX, sticky="ew")
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def save(self) -> None:
        config = self.config_frame.parse_config()
        try:
            session_id = self.app.core.session_id
            response = self.app.core.client.set_session_options(session_id, config)
            logging.info("saved session config: %s", response)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Set Session Options Error", e)
        self.destroy()
