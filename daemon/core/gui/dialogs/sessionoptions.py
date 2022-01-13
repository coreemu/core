import logging
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import ConfigFrame

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application


class SessionOptionsDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Session Options")
        self.config_frame: Optional[ConfigFrame] = None
        self.has_error: bool = False
        self.enabled: bool = not self.app.core.is_runtime()
        if not self.has_error:
            self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        options = self.app.core.session.options
        self.config_frame = ConfigFrame(self.top, self.app, options, self.enabled)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky=tk.NSEW, pady=PADY)

        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        state = tk.NORMAL if self.enabled else tk.DISABLED
        button = ttk.Button(frame, text="Save", command=self.save, state=state)
        button.grid(row=0, column=0, padx=PADX, sticky=tk.EW)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def save(self) -> None:
        config = self.config_frame.parse_config()
        for key, value in config.items():
            self.app.core.session.options[key].value = value
        self.destroy()
