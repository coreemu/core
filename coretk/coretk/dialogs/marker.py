"""
marker dialog
"""

from tkinter import ttk

from coretk.dialogs.colorpicker import ColorPicker
from coretk.dialogs.dialog import Dialog

MARKER_THICKNESS = [3, 5, 8, 10]


class Marker(Dialog):
    def __init__(self, master, app, initcolor="#000000"):
        super().__init__(master, app, "marker tool", modal=False)
        self.app = app
        self.color = initcolor
        self.radius = MARKER_THICKNESS[0]
        self.draw()

    def draw(self):
        button = ttk.Button(self.top, text="clear", command=self.clear_marker)
        button.grid(row=0, column=0)

        frame = ttk.Frame(self.top)
        frame.grid(row=1, column=0)

        button = ttk.Button(frame, text="radius 1")
        button.grid(row=0, column=0)
        button = ttk.Button(frame, text="radius 2")
        button.grid(row=0, column=1)
        button = ttk.Button(frame, text="radius 3")
        button.grid(row=1, column=0)
        button = ttk.Button(frame, text="radius 4")
        button.grid(row=1, column=1)

        label = ttk.Label(self.top, background=self.color)
        label.grid(row=2, column=0, sticky="nsew")
        label.bind("<Button-1>", self.change_color)

        # button = ttk.Button(self.top, text="color", command=self.change_color)
        # button.grid(row=2, column=0)

    def clear_marker(self):
        canvas = self.app.canvas
        for i in canvas.find_withtag("marker"):
            canvas.delete(i)

    def change_color(self, event):
        color_picker = ColorPicker(self, self.app, self.color)
        color = color_picker.askcolor()
        event.widget.configure(background=color)
        self.color = color
