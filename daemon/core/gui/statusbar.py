"""
status bar
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.api.grpc.wrappers import AlertEvent, AlertLevel
from core.gui.dialogs.alerts import AlertsDialog
from core.gui.themes import Styles

if TYPE_CHECKING:
    from core.gui.app import Application


class StatusBar(ttk.Frame):
    def __init__(self, master: tk.Widget, app: "Application") -> None:
        super().__init__(master)
        self.app: "Application" = app
        self.status: ttk.Label | None = None
        self.statusvar: tk.StringVar = tk.StringVar()
        self.zoom: ttk.Label | None = None
        self.cpu_label: ttk.Label | None = None
        self.alerts_button: ttk.Button | None = None
        self.alert_style = Styles.no_alert
        self.running: bool = False
        self.core_alarms: list[AlertEvent] = []
        self.draw()

    def draw(self) -> None:
        self.columnconfigure(0, weight=7)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)

        frame = ttk.Frame(self, borderwidth=1, relief=tk.RIDGE)
        frame.grid(row=0, column=0, sticky=tk.EW)
        frame.columnconfigure(0, weight=1)

        self.status = ttk.Label(
            self,
            textvariable=self.statusvar,
            anchor=tk.CENTER,
            borderwidth=1,
            relief=tk.RIDGE,
        )
        self.status.grid(row=0, column=0, sticky=tk.EW)

        self.zoom = ttk.Label(self, anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE)
        self.zoom.grid(row=0, column=1, sticky=tk.EW)

        self.cpu_label = ttk.Label(
            self, anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE
        )
        self.cpu_label.grid(row=0, column=2, sticky=tk.EW)
        self.set_cpu(0.0)

        self.alerts_button = ttk.Button(
            self, text="Alerts", command=self.click_alerts, style=self.alert_style
        )
        self.alerts_button.grid(row=0, column=3, sticky=tk.EW)

    def set_cpu(self, usage: float) -> None:
        self.cpu_label.config(text=f"CPU {usage * 100:.2f}%")

    def set_zoom(self, zoom: float) -> None:
        self.zoom.config(text=f"ZOOM {zoom * 100:.0f}%")

    def add_alert(self, event: AlertEvent) -> None:
        self.core_alarms.append(event)
        level = event.level
        self._set_alert_style(level)
        label = f"Alerts ({len(self.core_alarms)})"
        self.alerts_button.config(text=label, style=self.alert_style)

    def _set_alert_style(self, level: AlertLevel) -> None:
        if level in [AlertLevel.FATAL, AlertLevel.ERROR]:
            self.alert_style = Styles.red_alert
        elif level == AlertLevel.WARNING and self.alert_style != Styles.red_alert:
            self.alert_style = Styles.yellow_alert
        elif self.alert_style == Styles.no_alert:
            self.alert_style = Styles.green_alert

    def clear_alerts(self):
        self.core_alarms.clear()
        self.alert_style = Styles.no_alert
        self.alerts_button.config(text="Alerts", style=self.alert_style)

    def click_alerts(self) -> None:
        dialog = AlertsDialog(self.app)
        dialog.show()

    def set_status(self, message: str) -> None:
        self.statusvar.set(message)
