"""
set wallpaper
"""
import logging
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, List, Optional

from core.gui import images
from core.gui.appconfig import BACKGROUNDS_PATH
from core.gui.dialogs.dialog import Dialog
from core.gui.graph.graph import CanvasGraph
from core.gui.themes import PADX, PADY
from core.gui.widgets import image_chooser

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application


class CanvasWallpaperDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        """
        create an instance of CanvasWallpaper object
        """
        super().__init__(app, "Canvas Background")
        self.canvas: CanvasGraph = self.app.manager.current()
        self.scale_option: tk.IntVar = tk.IntVar(value=self.canvas.scale_option.get())
        self.adjust_to_dim: tk.BooleanVar = tk.BooleanVar(
            value=self.canvas.adjust_to_dim.get()
        )
        self.filename: tk.StringVar = tk.StringVar(value=self.canvas.wallpaper_file)
        self.image_label: Optional[ttk.Label] = None
        self.options: List[ttk.Radiobutton] = []
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.draw_image()
        self.draw_image_label()
        self.draw_image_selection()
        self.draw_options()
        self.draw_additional_options()
        self.draw_spacer()
        self.draw_buttons()

    def draw_image(self) -> None:
        self.image_label = ttk.Label(
            self.top, text="(image preview)", width=32, anchor=tk.CENTER
        )
        self.image_label.grid(pady=PADY)

    def draw_image_label(self) -> None:
        label = ttk.Label(self.top, text="Image filename: ")
        label.grid(sticky=tk.EW)
        if self.filename.get():
            self.draw_preview()

    def draw_image_selection(self) -> None:
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.grid(sticky=tk.EW, pady=PADY)

        entry = ttk.Entry(frame, textvariable=self.filename)
        entry.focus()
        entry.grid(row=0, column=0, sticky=tk.EW, padx=PADX)

        button = ttk.Button(frame, text="...", command=self.click_open_image)
        button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)

        button = ttk.Button(frame, text="Clear", command=self.click_clear)
        button.grid(row=0, column=2, sticky=tk.EW)

    def draw_options(self) -> None:
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.grid(sticky=tk.EW, pady=PADY)

        button = ttk.Radiobutton(
            frame, text="upper-left", value=1, variable=self.scale_option
        )
        button.grid(row=0, column=0, sticky=tk.EW)
        self.options.append(button)

        button = ttk.Radiobutton(
            frame, text="centered", value=2, variable=self.scale_option
        )
        button.grid(row=0, column=1, sticky=tk.EW)
        self.options.append(button)

        button = ttk.Radiobutton(
            frame, text="scaled", value=3, variable=self.scale_option
        )
        button.grid(row=0, column=2, sticky=tk.EW)
        self.options.append(button)

        button = ttk.Radiobutton(
            frame, text="titled", value=4, variable=self.scale_option
        )
        button.grid(row=0, column=3, sticky=tk.EW)
        self.options.append(button)

    def draw_additional_options(self) -> None:
        checkbutton = ttk.Checkbutton(
            self.top,
            text="Adjust canvas size to image dimensions",
            variable=self.adjust_to_dim,
            command=self.click_adjust_canvas,
        )
        checkbutton.grid(sticky=tk.EW, padx=PADX, pady=PADY)

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_open_image(self) -> None:
        filename = image_chooser(self, BACKGROUNDS_PATH)
        if filename:
            self.filename.set(filename)
            self.draw_preview()

    def draw_preview(self) -> None:
        image = images.from_file(self.filename.get(), width=250, height=135)
        self.image_label.config(image=image)
        self.image_label.image = image

    def click_clear(self) -> None:
        """
        delete like shown in image link entry if there is any
        """
        # delete entry
        self.filename.set("")
        # delete display image
        self.image_label.config(image="", width=32)
        self.image_label.image = None

    def click_adjust_canvas(self) -> None:
        # deselect all radio buttons and grey them out
        if self.adjust_to_dim.get():
            self.scale_option.set(0)
            for option in self.options:
                option.config(state=tk.DISABLED)
        # turn back the radio button to active state so that user can choose again
        else:
            self.scale_option.set(1)
            for option in self.options:
                option.config(state=tk.NORMAL)

    def click_apply(self) -> None:
        self.canvas.scale_option.set(self.scale_option.get())
        self.canvas.adjust_to_dim.set(self.adjust_to_dim.get())
        filename = self.filename.get()
        if not filename:
            filename = None
        try:
            self.canvas.set_wallpaper(filename)
        except FileNotFoundError:
            logger.error("invalid background: %s", filename)
        self.destroy()
