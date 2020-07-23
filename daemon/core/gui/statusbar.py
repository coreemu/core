"""
status bar
"""
import sched
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import ttk
from typing import TYPE_CHECKING, List, Optional

from core.api.grpc.core_pb2 import ExceptionEvent, ExceptionLevel
from core.gui.dialogs.alerts import AlertsDialog
from core.gui.themes import Styles

if TYPE_CHECKING:
    from core.gui.app import Application


class CpuUsage:
    def __init__(self, statusbar: "StatusBar") -> None:
        self.scheduler: sched.scheduler = sched.scheduler()
        self.running: bool = False
        self.thread: Optional[Thread] = None
        self.prev_idle: int = 0
        self.prev_total: int = 0
        self.stat_file: Path = Path("/proc/stat")
        self.statusbar: "StatusBar" = statusbar

    def start(self) -> None:
        self.running = True
        self.thread = Thread(target=self._start, daemon=True)
        self.thread.start()

    def _start(self):
        self.scheduler.enter(0, 0, self.run)
        self.scheduler.run()

    def run(self) -> None:
        lines = self.stat_file.read_text().splitlines()[0]
        values = [int(x) for x in lines.split()[1:]]
        idle = sum(values[3:5])
        non_idle = sum(values[:3] + values[5:8])
        total = idle + non_idle
        total_diff = total - self.prev_total
        idle_diff = idle - self.prev_idle
        cpu_percent = (total_diff - idle_diff) / total_diff
        self.statusbar.after(0, self.statusbar.set_cpu, cpu_percent)
        self.prev_idle = idle
        self.prev_total = total
        if self.running:
            self.scheduler.enter(3, 0, self.run)


class StatusBar(ttk.Frame):
    def __init__(self, master: tk.Widget, app: "Application") -> None:
        super().__init__(master)
        self.app: "Application" = app
        self.status: Optional[ttk.Label] = None
        self.statusvar: tk.StringVar = tk.StringVar()
        self.zoom: Optional[ttk.Label] = None
        self.cpu_label: Optional[ttk.Label] = None
        self.alerts_button: Optional[ttk.Button] = None
        self.alert_style = Styles.no_alert
        self.running: bool = False
        self.core_alarms: List[ExceptionEvent] = []
        self.draw()
        self.cpu_usage: CpuUsage = CpuUsage(self)
        self.cpu_usage.start()

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

        self.zoom = ttk.Label(self, anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE)
        self.zoom.grid(row=0, column=1, sticky="ew")
        self.set_zoom(self.app.canvas.ratio)

        self.cpu_label = ttk.Label(
            self, anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE
        )
        self.cpu_label.grid(row=0, column=2, sticky="ew")
        self.set_cpu(0.0)

        self.alerts_button = ttk.Button(
            self, text="Alerts", command=self.click_alerts, style=self.alert_style
        )
        self.alerts_button.grid(row=0, column=3, sticky="ew")

    def set_cpu(self, usage: float) -> None:
        self.cpu_label.config(text=f"CPU {usage * 100:.2f}%")

    def set_zoom(self, zoom: float) -> None:
        self.zoom.config(text=f"ZOOM {zoom * 100:.0f}%")

    def add_alert(self, event: ExceptionEvent) -> None:
        self.core_alarms.append(event)
        level = event.exception_event.level
        self._set_alert_style(level)
        label = f"Alerts ({len(self.core_alarms)})"
        self.alerts_button.config(text=label, style=self.alert_style)

    def _set_alert_style(self, level: ExceptionLevel) -> None:
        if level in [ExceptionLevel.FATAL, ExceptionLevel.ERROR]:
            self.alert_style = Styles.red_alert
        elif level == ExceptionLevel.WARNING and self.alert_style != Styles.red_alert:
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
