"""
throughput dialog
"""
import logging
import tkinter as tk
from tkinter import ttk

from core.gui.dialogs.colorpicker import ColorPickerDialog
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADY


class ThroughputDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Throughput Config", modal=False)
        self.app = app
        self.show_throughput = tk.IntVar(value=1)
        self.exponential_weight = tk.IntVar(value=1)
        self.transmission = tk.IntVar(value=1)
        self.reception = tk.IntVar(value=1)
        self.threshold = tk.DoubleVar(value=250.0)
        self.width = tk.IntVar(value=10)
        self.color = "#FF0000"
        self.color_button = None
        self.top.columnconfigure(0, weight=1)
        self.draw()

    def draw(self):
        button = ttk.Checkbutton(
            self.top,
            variable=self.show_throughput,
            text="Show Throughput Level On Every Link",
        )
        button.grid(row=0, column=0, sticky="ew")
        button = ttk.Checkbutton(
            self.top,
            variable=self.exponential_weight,
            text="Use Exponential Weighted Moving Average",
        )
        button.grid(row=1, column=0, sticky="ew")
        button = ttk.Checkbutton(
            self.top, variable=self.transmission, text="Include Transmissions"
        )
        button.grid(row=2, column=0, sticky="ew")
        button = ttk.Checkbutton(
            self.top, variable=self.reception, text="Include Receptions"
        )
        button.grid(row=3, column=0, sticky="ew")

        label_frame = ttk.LabelFrame(self.top, text="Link Highlight", padding=FRAME_PAD)
        label_frame.columnconfigure(0, weight=1)
        label_frame.grid(row=4, column=0, sticky="ew")
        label = ttk.Label(label_frame, text="Highlight Link Throughput")
        label.grid(row=0, column=0, sticky="ew")

        frame = ttk.Frame(label_frame)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.grid(row=1, column=0, sticky="ew")
        label = ttk.Label(frame, text="Threshold (0 for disabled)")
        label.grid(row=0, column=0, sticky="ew")
        entry = ttk.Entry(frame, textvariable=self.threshold)
        entry.grid(row=0, column=1, sticky="ew")
        label = ttk.Label(frame, text="kbps")
        label.grid(row=0, column=2, sticky="ew")

        scale = ttk.Scale(
            label_frame,
            from_=0,
            to=1000,
            value=0,
            orient=tk.HORIZONTAL,
            variable=self.threshold,
        )
        scale.grid(row=2, column=0, sticky="ew", pady=PADY)

        frame = ttk.Frame(label_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=3, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Highlight Link Width")
        label.grid(row=0, column=0, sticky="ew")
        entry = ttk.Entry(frame, textvariable=self.width)
        entry.grid(row=0, column=1, sticky="ew")

        frame = ttk.Frame(label_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=4, column=0, sticky="ew")
        label = ttk.Label(frame, text="Color")
        label.grid(row=0, column=0, sticky="ew")
        self.color_button = tk.Button(
            frame,
            text=self.color,
            command=self.click_color,
            bg=self.color,
            highlightthickness=0,
        )
        self.color_button.grid(row=0, column=1, sticky="ew")

        button = ttk.Button(self.top, text="OK", command=self.ok)
        button.grid(row=5, column=0, sticky="ew")

    def click_color(self):
        color_picker = ColorPickerDialog(self, self.app, self.color)
        self.color = color_picker.askcolor()
        self.color_button.config(bg=self.color, text=self.color, bd=0)

    def ok(self):
        logging.debug("click ok")
        self.destroy()
