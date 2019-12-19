"""
marker dialog
"""

import logging
import tkinter as tk
from tkinter import ttk

from core.gui.dialogs.colorpicker import ColorPickerDialog
from core.gui.dialogs.dialog import Dialog

MARKER_THICKNESS = [3, 5, 8, 10]


class MarkerDialog(Dialog):
    def __init__(self, master, app, initcolor="#000000"):
        super().__init__(master, app, "marker tool", modal=False)
        self.app = app
        self.color = initcolor
        self.radius = MARKER_THICKNESS[0]
        self.marker_thickness = tk.IntVar(value=MARKER_THICKNESS[0])
        self.draw()
        self.top.bind("<Destroy>", self.close_marker)

    def draw(self):
        button = ttk.Button(self.top, text="clear", command=self.clear_marker)
        button.grid(row=0, column=0, sticky="nsew")

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=1, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Thickness: ")
        label.grid(row=0, column=0, sticky="nsew")
        combobox = ttk.Combobox(
            frame,
            textvariable=self.marker_thickness,
            values=MARKER_THICKNESS,
            state="readonly",
        )
        combobox.grid(row=0, column=1, sticky="nsew")
        combobox.bind("<<ComboboxSelected>>", self.change_thickness)
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=2, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Color: ")
        label.grid(row=0, column=0, sticky="nsew")
        label = ttk.Label(frame, background=self.color)
        label.grid(row=0, column=1, sticky="nsew")
        label.bind("<Button-1>", self.change_color)

    def clear_marker(self):
        canvas = self.app.canvas
        for i in canvas.find_withtag("marker"):
            canvas.delete(i)

    def change_color(self, event):
        color_picker = ColorPickerDialog(self, self.app, self.color)
        color = color_picker.askcolor()
        event.widget.configure(background=color)
        self.color = color

    def change_thickness(self, event):
        self.radius = self.marker_thickness.get()

    def close_marker(self, event):
        logging.debug("destroy marker dialog")
        self.app.toolbar.marker_tool = None

    def position(self):
        print(self.winfo_width(), self.winfo_height())
        self.geometry("+{}+{}".format(self.app.master.winfo_x, self.app.master.winfo_y))
