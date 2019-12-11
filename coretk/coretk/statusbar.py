"status bar"
import tkinter as tk
from tkinter import ttk

from coretk.dialogs.cel import CheckLight


class StatusBar(ttk.Frame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.status = None
        self.statusvar = tk.StringVar()
        self.progress_bar = None
        self.zoom = None
        self.cpu_usage = None
        self.memory = None
        self.emulation_light = None
        self.running = False
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=7)
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
            self, text="ZOOM TBD", anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE
        )
        self.zoom.grid(row=0, column=2, sticky="ew")

        self.cpu_usage = ttk.Label(
            self, text="CPU TBD", anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE
        )
        self.cpu_usage.grid(row=0, column=3, sticky="ew")

        self.emulation_light = ttk.Label(
            self, text="CEL TBD", anchor=tk.CENTER, borderwidth=1, relief=tk.RIDGE
        )
        self.emulation_light.bind("<Button-1>", self.cel_callback)
        self.emulation_light.grid(row=0, column=4, sticky="ew")

    def cel_callback(self, event):
        dialog = CheckLight(self.app, self.app)
        dialog.show()

    def start_session_callback(self, process_time):
        self.progress_bar.stop()
        self.statusvar.set(f"Session started in {process_time:.3f} seconds")

    def stop_session_callback(self, cleanup_time):
        self.progress_bar.stop()
        self.statusvar.set(f"Stopped session in {cleanup_time:.3f} seconds")
