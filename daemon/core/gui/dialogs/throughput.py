"""
throughput dialog
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.gui.dialogs.colorpicker import ColorPickerDialog
from core.gui.dialogs.dialog import Dialog
from core.gui.graph.manager import CanvasManager
from core.gui.themes import FRAME_PAD, PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application


class ThroughputDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Throughput Config")
        self.manager: CanvasManager = app.manager
        self.show_throughput: tk.IntVar = tk.IntVar(value=1)
        self.exponential_weight: tk.IntVar = tk.IntVar(value=1)
        self.transmission: tk.IntVar = tk.IntVar(value=1)
        self.reception: tk.IntVar = tk.IntVar(value=1)
        self.threshold: tk.DoubleVar = tk.DoubleVar(
            value=self.manager.throughput_threshold
        )
        self.width: tk.IntVar = tk.IntVar(value=self.manager.throughput_width)
        self.color: str = self.manager.throughput_color
        self.color_button: Optional[tk.Button] = None
        self.top.columnconfigure(0, weight=1)
        self.draw()

    def draw(self) -> None:
        button = ttk.Checkbutton(
            self.top,
            variable=self.show_throughput,
            text="Show Throughput Level On Every Link",
        )
        button.grid(sticky=tk.EW)
        button = ttk.Checkbutton(
            self.top,
            variable=self.exponential_weight,
            text="Use Exponential Weighted Moving Average",
        )
        button.grid(sticky=tk.EW)
        button = ttk.Checkbutton(
            self.top, variable=self.transmission, text="Include Transmissions"
        )
        button.grid(sticky=tk.EW)
        button = ttk.Checkbutton(
            self.top, variable=self.reception, text="Include Receptions"
        )
        button.grid(sticky=tk.EW)

        label_frame = ttk.LabelFrame(self.top, text="Link Highlight", padding=FRAME_PAD)
        label_frame.columnconfigure(0, weight=1)
        label_frame.grid(sticky=tk.EW)

        scale = ttk.Scale(
            label_frame,
            from_=0,
            to=1000,
            value=0,
            orient=tk.HORIZONTAL,
            variable=self.threshold,
        )
        scale.grid(sticky=tk.EW, pady=PADY)

        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Threshold Kbps (0 disabled)")
        label.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.threshold)
        entry.grid(row=0, column=1, sticky=tk.EW, pady=PADY)
        label = ttk.Label(frame, text="Width")
        label.grid(row=1, column=0, sticky=tk.EW, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.width)
        entry.grid(row=1, column=1, sticky=tk.EW, pady=PADY)
        label = ttk.Label(frame, text="Color")
        label.grid(row=2, column=0, sticky=tk.EW, padx=PADX)
        self.color_button = tk.Button(
            frame,
            text=self.color,
            command=self.click_color,
            bg=self.color,
            highlightthickness=0,
        )
        self.color_button.grid(row=2, column=1, sticky=tk.EW)

        self.draw_spacer()

        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_color(self) -> None:
        color_picker = ColorPickerDialog(self, self.app, self.color)
        self.color = color_picker.askcolor()
        self.color_button.config(bg=self.color, text=self.color, bd=0)

    def click_save(self) -> None:
        self.manager.throughput_threshold = self.threshold.get()
        self.manager.throughput_width = self.width.get()
        self.manager.throughput_color = self.color
        self.destroy()
