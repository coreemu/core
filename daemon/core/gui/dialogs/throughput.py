"""
throughput dialog
"""
import logging
import tkinter as tk
from tkinter import ttk

from core.gui.dialogs.dialog import Dialog


class ThroughputDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "throughput config", modal=False)
        self.app = app
        self.show_throughput = tk.IntVar(value=1)
        self.exponential_weight = tk.IntVar(value=1)
        self.transmission = tk.IntVar(value=1)
        self.reception = tk.IntVar(value=1)
        self.threshold = tk.DoubleVar(value=250.0)
        self.width = tk.IntVar(value=10)
        self.top.columnconfigure(0, weight=1)
        self.draw()

    def draw(self):
        button = ttk.Checkbutton(
            self.top,
            variable=self.show_throughput,
            text="Show throughput level on every link",
        )
        button.grid(row=0, column=0, sticky="nsew")
        button = ttk.Checkbutton(
            self.top,
            variable=self.exponential_weight,
            text="Use exponential weighted moving average",
        )
        button.grid(row=1, column=0, sticky="nsew")
        button = ttk.Checkbutton(
            self.top, variable=self.transmission, text="Include transmissions"
        )
        button.grid(row=2, column=0, sticky="nsew")
        button = ttk.Checkbutton(
            self.top, variable=self.reception, text="Include receptions"
        )
        button.grid(row=3, column=0, sticky="nsew")

        label_frame = ttk.LabelFrame(self.top, text="Link highlight")
        label_frame.columnconfigure(0, weight=1)
        label_frame.grid(row=4, column=0, sticky="nsew")
        label = ttk.Label(label_frame, text="Highlight link if throughput exceeds this")
        label.grid(row=0, column=0, sticky="nsew")

        frame = ttk.Frame(label_frame)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.grid(row=1, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Threshold (0 for disabled)")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.threshold)
        entry.grid(row=0, column=1, sticky="nsew")
        label = ttk.Label(frame, text="kbps")
        label.grid(row=0, column=2, sticky="nsew")

        scale = ttk.Scale(
            label_frame,
            from_=0,
            to=1000,
            value=0,
            orient=tk.HORIZONTAL,
            variable=self.threshold,
        )
        scale.grid(row=2, column=0, sticky="nsew")

        frame = ttk.Frame(label_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=3, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Highlight link width: ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.width)
        entry.grid(row=0, column=1, sticky="nsew")

        frame = ttk.Frame(label_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=4, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Color: ")
        label.grid(row=0, column=0, sticky="nsew")
        button = ttk.Button(frame, text="not implemented")
        button.grid(row=0, column=1, sticky="nsew")

        button = ttk.Button(self.top, text="OK", command=self.ok)
        button.grid(row=5, column=0, sticky="nsew")

    def ok(self):
        logging.debug("click ok")
        self.destroy()
