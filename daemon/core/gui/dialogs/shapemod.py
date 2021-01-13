"""
shape input dialog
"""
import tkinter as tk
from tkinter import font, ttk
from typing import TYPE_CHECKING, List, Optional, Union

from core.gui.dialogs.colorpicker import ColorPickerDialog
from core.gui.dialogs.dialog import Dialog
from core.gui.graph import tags
from core.gui.graph.shapeutils import is_draw_shape, is_shape_text
from core.gui.themes import FRAME_PAD, PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.graph import CanvasGraph
    from core.gui.graph.shape import Shape

FONT_SIZES: List[int] = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
BORDER_WIDTH: List[int] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class ShapeDialog(Dialog):
    def __init__(self, app: "Application", shape: "Shape") -> None:
        if is_draw_shape(shape.shape_type):
            title = "Add Shape"
        else:
            title = "Add Text"
        super().__init__(app, title)
        self.canvas: "CanvasGraph" = app.manager.current()
        self.fill: Optional[ttk.Label] = None
        self.border: Optional[ttk.Label] = None
        self.shape: "Shape" = shape
        data = shape.shape_data
        self.shape_text: tk.StringVar = tk.StringVar(value=data.text)
        self.font: tk.StringVar = tk.StringVar(value=data.font)
        self.font_size: tk.IntVar = tk.IntVar(value=data.font_size)
        self.text_color: str = data.text_color
        fill_color = data.fill_color
        if not fill_color:
            fill_color = "#CFCFFF"
        self.fill_color: str = fill_color
        self.border_color: str = data.border_color
        self.border_width: tk.IntVar = tk.IntVar(value=0)
        self.bold: tk.BooleanVar = tk.BooleanVar(value=data.bold)
        self.italic: tk.BooleanVar = tk.BooleanVar(value=data.italic)
        self.underline: tk.BooleanVar = tk.BooleanVar(value=data.underline)
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.draw_label_options()
        if is_draw_shape(self.shape.shape_type):
            self.draw_shape_options()
        self.draw_spacer()
        self.draw_buttons()

    def draw_label_options(self) -> None:
        label_frame = ttk.LabelFrame(self.top, text="Label", padding=FRAME_PAD)
        label_frame.grid(sticky=tk.EW)
        label_frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(label_frame, textvariable=self.shape_text)
        entry.grid(sticky=tk.EW, pady=PADY)

        # font options
        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.NSEW, pady=PADY)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        combobox = ttk.Combobox(
            frame,
            textvariable=self.font,
            values=sorted(font.families()),
            state="readonly",
        )
        combobox.grid(row=0, column=0, sticky=tk.NSEW)
        combobox = ttk.Combobox(
            frame, textvariable=self.font_size, values=FONT_SIZES, state="readonly"
        )
        combobox.grid(row=0, column=1, padx=PADX, sticky=tk.NSEW)
        button = ttk.Button(frame, text="Color", command=self.choose_text_color)
        button.grid(row=0, column=2, sticky=tk.NSEW)

        # style options
        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        button = ttk.Checkbutton(frame, variable=self.bold, text="Bold")
        button.grid(row=0, column=0, sticky=tk.EW)
        button = ttk.Checkbutton(frame, variable=self.italic, text="Italic")
        button.grid(row=0, column=1, padx=PADX, sticky=tk.EW)
        button = ttk.Checkbutton(frame, variable=self.underline, text="Underline")
        button.grid(row=0, column=2, sticky=tk.EW)

    def draw_shape_options(self) -> None:
        label_frame = ttk.LabelFrame(self.top, text="Shape", padding=FRAME_PAD)
        label_frame.grid(sticky=tk.EW, pady=PADY)
        label_frame.columnconfigure(0, weight=1)

        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW)
        for i in range(1, 3):
            frame.columnconfigure(i, weight=1)
        label = ttk.Label(frame, text="Fill Color")
        label.grid(row=0, column=0, padx=PADX, sticky=tk.W)
        self.fill = ttk.Label(frame, text=self.fill_color, background=self.fill_color)
        self.fill.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Color", command=self.choose_fill_color)
        button.grid(row=0, column=2, sticky=tk.EW)

        label = ttk.Label(frame, text="Border Color")
        label.grid(row=1, column=0, sticky=tk.W, padx=PADX)
        self.border = ttk.Label(
            frame, text=self.border_color, background=self.border_color
        )
        self.border.grid(row=1, column=1, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Color", command=self.choose_border_color)
        button.grid(row=1, column=2, sticky=tk.EW)

        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Border Width")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        combobox = ttk.Combobox(
            frame, textvariable=self.border_width, values=BORDER_WIDTH, state="readonly"
        )
        combobox.grid(row=0, column=1, sticky=tk.NSEW)

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="Add shape", command=self.click_add)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.cancel)
        button.grid(row=0, column=1, sticky=tk.EW)

    def choose_text_color(self) -> None:
        color_picker = ColorPickerDialog(self, self.app, self.text_color)
        self.text_color = color_picker.askcolor()

    def choose_fill_color(self) -> None:
        color_picker = ColorPickerDialog(self, self.app, self.fill_color)
        color = color_picker.askcolor()
        self.fill_color = color
        self.fill.config(background=color, text=color)

    def choose_border_color(self) -> None:
        color_picker = ColorPickerDialog(self, self.app, self.border_color)
        color = color_picker.askcolor()
        self.border_color = color
        self.border.config(background=color, text=color)

    def cancel(self) -> None:
        self.shape.delete()
        self.canvas.shapes.pop(self.shape.id)
        self.destroy()

    def click_add(self) -> None:
        if is_draw_shape(self.shape.shape_type):
            self.add_shape()
        elif is_shape_text(self.shape.shape_type):
            self.add_text()
        self.destroy()

    def make_font(self) -> List[Union[int, str]]:
        """
        create font for text or shape label
        """
        size = int(self.font_size.get())
        text_font = [self.font.get(), size]
        if self.bold.get():
            text_font.append("bold")
        if self.italic.get():
            text_font.append("italic")
        if self.underline.get():
            text_font.append("underline")
        return text_font

    def save_text(self) -> None:
        """
        save info related to text or shape label
        """
        data = self.shape.shape_data
        data.text = self.shape_text.get()
        data.font = self.font.get()
        data.font_size = int(self.font_size.get())
        data.text_color = self.text_color
        data.bold = self.bold.get()
        data.italic = self.italic.get()
        data.underline = self.underline.get()

    def save_shape(self) -> None:
        """
        save info related to shape
        """
        data = self.shape.shape_data
        data.fill_color = self.fill_color
        data.border_color = self.border_color
        data.border_width = int(self.border_width.get())

    def add_text(self) -> None:
        """
        add text to canvas
        """
        text = self.shape_text.get()
        text_font = self.make_font()
        self.canvas.itemconfig(
            self.shape.id, text=text, fill=self.text_color, font=text_font
        )
        self.save_text()

    def add_shape(self) -> None:
        self.canvas.itemconfig(
            self.shape.id,
            fill=self.fill_color,
            dash="",
            outline=self.border_color,
            width=int(self.border_width.get()),
        )
        shape_text = self.shape_text.get()
        size = int(self.font_size.get())
        x0, y0, x1, y1 = self.canvas.bbox(self.shape.id)
        _y = y0 + 1.5 * size
        _x = (x0 + x1) / 2
        text_font = self.make_font()
        if self.shape.text_id is None:
            self.shape.text_id = self.canvas.create_text(
                _x,
                _y,
                text=shape_text,
                fill=self.text_color,
                font=text_font,
                tags=(tags.SHAPE_TEXT, tags.ANNOTATION),
            )
            self.shape.created = True
        else:
            self.canvas.itemconfig(
                self.shape.text_id,
                text=shape_text,
                fill=self.text_color,
                font=text_font,
            )
        self.save_text()
        self.save_shape()
