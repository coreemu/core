"""
throughput dialog
"""
import tkinter as tk
from tkinter import ttk

from core.gui.dialogs.colorpicker import ColorPickerDialog
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY


class ThroughputDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Throughput Config", modal=False)
        self.app = app
        self.canvas = app.canvas
        self.show_throughput = tk.IntVar(value=1)
        self.exponential_weight = tk.IntVar(value=1)
        self.transmission = tk.IntVar(value=1)
        self.reception = tk.IntVar(value=1)
        self.threshold = tk.DoubleVar(value=self.canvas.throughput_threshold)
        self.width = tk.IntVar(value=self.canvas.throughput_width)
        self.color = self.canvas.throughput_color
        self.color_button = None
        self.top.columnconfigure(0, weight=1)
        self.draw()

    def draw(self):
        button = ttk.Checkbutton(
            self.top,
            variable=self.show_throughput,
            text="Show Throughput Level On Every Link",
        )
        button.grid(sticky="ew")
        button = ttk.Checkbutton(
            self.top,
            variable=self.exponential_weight,
            text="Use Exponential Weighted Moving Average",
        )
        button.grid(sticky="ew")
        button = ttk.Checkbutton(
            self.top, variable=self.transmission, text="Include Transmissions"
        )
        button.grid(sticky="ew")
        button = ttk.Checkbutton(
            self.top, variable=self.reception, text="Include Receptions"
        )
        button.grid(sticky="ew")

        label_frame = ttk.LabelFrame(self.top, text="Link Highlight", padding=FRAME_PAD)
        label_frame.columnconfigure(0, weight=1)
        label_frame.grid(sticky="ew")

        scale = ttk.Scale(
            label_frame,
            from_=0,
            to=1000,
            value=0,
            orient=tk.HORIZONTAL,
            variable=self.threshold,
        )
        scale.grid(sticky="ew", pady=PADY)

        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew")
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Threshold Kbps (0 disabled)")
        label.grid(row=0, column=0, sticky="ew", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.threshold)
        entry.grid(row=0, column=1, sticky="ew", pady=PADY)
        label = ttk.Label(frame, text="Width")
        label.grid(row=1, column=0, sticky="ew", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.width)
        entry.grid(row=1, column=1, sticky="ew", pady=PADY)
        label = ttk.Label(frame, text="Color")
        label.grid(row=2, column=0, sticky="ew", padx=PADX)
        self.color_button = tk.Button(
            frame,
            text=self.color,
            command=self.click_color,
            bg=self.color,
            highlightthickness=0,
        )
        self.color_button.grid(row=2, column=1, sticky="ew")

        self.draw_spacer()

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_color(self):
        color_picker = ColorPickerDialog(self, self.app, self.color)
        self.color = color_picker.askcolor()
        self.color_button.config(bg=self.color, text=self.color, bd=0)

    def click_save(self):
        self.canvas.throughput_threshold = self.threshold.get()
        self.canvas.throughput_width = self.width.get()
        self.canvas.throughput_color = self.color
        self.destroy()
