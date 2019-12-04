"""
shape input dialog
"""
import tkinter as tk
from tkinter import colorchooser, font, ttk

from coretk.dialogs.dialog import Dialog

FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
BORDER_WIDTH = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class ShapeDialog(Dialog):
    def __init__(self, master, app, shape_id):
        super().__init__(master, app, "Add a new shape", modal=True)
        self.canvas = app.canvas
        self.id = shape_id
        self.shape_text = tk.StringVar(value="")
        self.font = tk.StringVar(value="Arial")
        self.font_size = tk.IntVar(value=12)
        self.text_color = "#000000"
        self.fill_color = "#CFCFFF"
        self.border_color = "black"
        self.border_width = tk.IntVar(value=0)
        self.bold = tk.IntVar(value=0)
        self.italic = tk.IntVar(value=0)
        self.underline = tk.IntVar(value=0)

        self.fill = None
        self.border = None

        self.top.columnconfigure(0, weight=1)
        self.draw()

    def draw(self):
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)
        label = ttk.Label(frame, text="Text for top of shape: ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.shape_text)
        entry.grid(row=0, column=1, sticky="nsew")
        frame.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        combobox = ttk.Combobox(
            frame,
            textvariable=self.font,
            values=sorted(font.families()),
            state="readonly",
        )
        combobox.grid(row=0, column=0, sticky="nsew")
        combobox = ttk.Combobox(
            frame, textvariable=self.font_size, values=FONT_SIZES, state="readonly"
        )
        combobox.grid(row=0, column=1, padx=3, sticky="nsew")
        button = ttk.Button(frame, text="Text color", command=self.choose_text_color)
        button.grid(row=0, column=2, sticky="nsew")
        frame.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        button = ttk.Checkbutton(frame, variable=self.bold, text="Bold")
        button.grid(row=0, column=0)
        button = ttk.Checkbutton(frame, variable=self.italic, text="Italic")
        button.grid(row=0, column=1, padx=3)
        button = ttk.Checkbutton(frame, variable=self.underline, text="Underline")
        button.grid(row=0, column=2)
        frame.grid(row=2, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        label = ttk.Label(frame, text="Fill color")
        label.grid(row=0, column=0, sticky="nsew")
        self.fill = ttk.Label(frame, text=self.fill_color, background="#CFCFFF")
        self.fill.grid(row=0, column=1, sticky="nsew", padx=3)
        button = ttk.Button(frame, text="Color", command=self.choose_fill_color)
        button.grid(row=0, column=2, sticky="nsew")
        frame.grid(row=3, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        label = ttk.Label(frame, text="Border color:")
        label.grid(row=0, column=0, sticky="nsew")
        self.border = ttk.Label(
            frame, text=self.border_color, background=self.fill_color
        )
        self.border.grid(row=0, column=1, sticky="nsew", padx=3)
        button = ttk.Button(frame, text="Color", command=self.choose_border_color)
        button.grid(row=0, column=2, sticky="nsew")
        frame.grid(row=4, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)
        label = ttk.Label(frame, text="Border width:")
        label.grid(row=0, column=0, sticky="nsew")
        combobox = ttk.Combobox(
            frame, textvariable=self.border_width, values=BORDER_WIDTH, state="readonly"
        )
        combobox.grid(row=0, column=1, sticky="nsew")
        frame.grid(row=5, column=0, sticky="nsew", padx=3, pady=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="Add shape", command=self.add_shape)
        button.grid(row=0, column=0, sticky="e", padx=3)
        button = ttk.Button(frame, text="Cancel", command=self.cancel)
        button.grid(row=0, column=1, sticky="w", pady=3)
        frame.grid(row=6, column=0, sticky="nsew", padx=3, pady=3)

    def choose_text_color(self):
        color = colorchooser.askcolor(color="black")
        self.text_color = color[1]

    def choose_fill_color(self):
        color = colorchooser.askcolor(color=self.fill_color)
        self.fill_color = color[1]
        self.fill.config(background=color[1], text=color[1])

    def choose_border_color(self):
        color = colorchooser.askcolor(color="black")
        self.border_color = color[1]
        self.border.config(background=color[1], text=color[1])

    def cancel(self):
        if not self.canvas.shapes[self.id].created:
            self.canvas.delete(self.id)
            self.canvas.shapes.pop(self.id)
        self.destroy()

    def add_shape(self):
        self.canvas.itemconfig(
            self.id,
            fill=self.fill_color,
            dash="",
            outline=self.border_color,
            width=int(self.border_width.get()),
        )
        shape = self.canvas.shapes[self.id]
        shape_text = self.shape_text.get()
        if shape.text is None:
            size = int(self.font_size.get())
            x0, y0, x1, y1 = self.canvas.bbox(self.id)
            text_y = y0 + 2 * size
            text_x = (x0 + x1) / 2
            f = [self.font.get(), size]
            if self.bold.get() == 1:
                f.append("bold")
            if self.italic.get() == 1:
                f.append("italic")
            if self.underline.get() == 1:
                f.append("underline")
            shape.text = self.canvas.create_text(
                text_x, text_y, text=shape_text, fill=self.text_color, font=f
            )
        self.canvas.shapes[self.id].created = True
        self.destroy()
