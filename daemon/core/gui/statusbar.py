"""
status bar
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, List, Optional

from core.api.grpc.core_pb2 import ExceptionEvent
from core.gui.dialogs.alerts import AlertsDialog
from core.gui.themes import Styles

if TYPE_CHECKING:
    from core.gui.app import Application


class StatusBar(ttk.Frame):
    def __init__(self, master: tk.Widget, app: "Application") -> None:
        super().__init__(master)
        self.app: "Application" = app
        self.status: Optional[ttk.Label] = None
        self.statusvar: tk.StringVar = tk.StringVar()
        self.zoom: Optional[ttk.Label] = None
        self.cpu_usage: Optional[ttk.Label] = None
        self.alerts_button: Optional[ttk.Button] = None
        self.running: bool = False
        self.core_alarms: List[ExceptionEvent] = []
        self.draw()

    def draw(self) -> None:
        self.columnconfigure(0, weight=7)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)

        frame = ttk.Frame(self, borderwidth=1, relief=tk.RIDGE)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        self.status = ttk.Label(
            self,
            textvariable=self.statusvar,
            anchor=tk.CENTER,
            borderwidth=1,
            relief=tk.RIDGE,
        )
        self.status.grid(row=0, column=0, sticky="ew")

        self.zoom = ttk.Label(
            self,
            text="%s" % (int(self.app.canvas.ratio * 100)) + "%",
            anchor=tk.CENTER,
            borderwidth=1,
            relief=tk.RIDGE,
        )
        self.zoom.grid(row=0, column=1, sticky="ew")

        self.cpu_usage = ttk.Label(
            self, text="CPU TBD", anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE
        )
        self.cpu_usage.grid(row=0, column=2, sticky="ew")

        self.alerts_button = ttk.Button(
            self, text="Alerts", command=self.click_alerts, style=Styles.green_alert
        )
        self.alerts_button.grid(row=0, column=3, sticky="ew")

    def click_alerts(self) -> None:
        dialog = AlertsDialog(self.app)
        dialog.show()

    def set_status(self, message: str) -> None:
        self.statusvar.set(message)
