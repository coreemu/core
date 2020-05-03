"""
status bar
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.dialogs.alerts import AlertsDialog
from core.gui.themes import Styles

if TYPE_CHECKING:
    from core.gui.app import Application


class StatusBar(ttk.Frame):
    def __init__(self, master: tk.Widget, app: "Application", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.status = None
        self.statusvar = tk.StringVar()
        self.progress_bar = None
        self.zoom = None
        self.cpu_usage = None
        self.memory = None
        self.alerts_button = None
        self.running = False
        self.core_alarms = []
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=5)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)
        self.columnconfigure(4, weight=1)

        frame = ttk.Frame(self, borderwidth=1, relief=tk.RIDGE)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(
            frame, orient="horizontal", mode="indeterminate"
        )
        self.progress_bar.grid(sticky="ew")

        self.status = ttk.Label(
            self,
            textvariable=self.statusvar,
            anchor=tk.CENTER,
            borderwidth=1,
            relief=tk.RIDGE,
        )
        self.status.grid(row=0, column=1, sticky="ew")

        self.zoom = ttk.Label(
            self,
            text="%s" % (int(self.app.canvas.ratio * 100)) + "%",
            anchor=tk.CENTER,
            borderwidth=1,
            relief=tk.RIDGE,
        )
        self.zoom.grid(row=0, column=2, sticky="ew")

        self.cpu_usage = ttk.Label(
            self, text="CPU TBD", anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE
        )
        self.cpu_usage.grid(row=0, column=3, sticky="ew")

        self.alerts_button = ttk.Button(
            self, text="Alerts", command=self.click_alerts, style=Styles.green_alert
        )
        self.alerts_button.grid(row=0, column=4, sticky="ew")

    def click_alerts(self):
        dialog = AlertsDialog(self.app, self.app)
        dialog.show()

    def set_status(self, message: str):
        self.statusvar.set(message)
