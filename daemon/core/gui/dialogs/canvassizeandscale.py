"""
size and scale
"""
import tkinter as tk
from tkinter import font, ttk
from typing import TYPE_CHECKING

from core.gui import validation
from core.gui.dialogs.dialog import Dialog
from core.gui.graph.manager import CanvasManager
from core.gui.themes import FRAME_PAD, PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application

PIXEL_SCALE: int = 100


class SizeAndScaleDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        """
        create an instance for size and scale object
        """
        super().__init__(app, "Canvas Size and Scale")
        self.manager: CanvasManager = self.app.manager
        self.section_font: font.Font = font.Font(weight=font.BOLD)
        width, height = self.manager.current().current_dimensions
        self.pixel_width: tk.IntVar = tk.IntVar(value=width)
        self.pixel_height: tk.IntVar = tk.IntVar(value=height)
        location = self.app.core.session.location
        self.x: tk.DoubleVar = tk.DoubleVar(value=location.x)
        self.y: tk.DoubleVar = tk.DoubleVar(value=location.y)
        self.lat: tk.DoubleVar = tk.DoubleVar(value=location.lat)
        self.lon: tk.DoubleVar = tk.DoubleVar(value=location.lon)
        self.alt: tk.DoubleVar = tk.DoubleVar(value=location.alt)
        self.scale: tk.DoubleVar = tk.DoubleVar(value=location.scale)
        self.meters_width: tk.IntVar = tk.IntVar(
            value=width / PIXEL_SCALE * location.scale
        )
        self.meters_height: tk.IntVar = tk.IntVar(
            value=height / PIXEL_SCALE * location.scale
        )
        self.save_default: tk.BooleanVar = tk.BooleanVar(value=False)
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.draw_size()
        self.draw_scale()
        self.draw_reference_point()
        self.draw_save_as_default()
        self.draw_spacer()
        self.draw_buttons()

    def draw_size(self) -> None:
        label_frame = ttk.Labelframe(self.top, text="Size", padding=FRAME_PAD)
        label_frame.grid(sticky=tk.EW)
        label_frame.columnconfigure(0, weight=1)

        # draw size row 1
        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        entry = validation.PositiveIntEntry(frame, textvariable=self.pixel_width)
        entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        entry.bind("<KeyRelease>", self.size_scale_keyup)
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky=tk.W, padx=PADX)
        entry = validation.PositiveIntEntry(frame, textvariable=self.pixel_height)
        entry.grid(row=0, column=3, sticky=tk.EW, padx=PADX)
        entry.bind("<KeyRelease>", self.size_scale_keyup)
        label = ttk.Label(frame, text="Pixels")
        label.grid(row=0, column=4, sticky=tk.W)

        # draw size row 2
        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        entry = validation.PositiveFloatEntry(
            frame, textvariable=self.meters_width, state=tk.DISABLED
        )
        entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky=tk.W, padx=PADX)
        entry = validation.PositiveFloatEntry(
            frame, textvariable=self.meters_height, state=tk.DISABLED
        )
        entry.grid(row=0, column=3, sticky=tk.EW, padx=PADX)
        label = ttk.Label(frame, text="Meters")
        label.grid(row=0, column=4, sticky=tk.W)

    def draw_scale(self) -> None:
        label_frame = ttk.Labelframe(self.top, text="Scale", padding=FRAME_PAD)
        label_frame.grid(sticky=tk.EW)
        label_frame.columnconfigure(0, weight=1)

        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text=f"{PIXEL_SCALE} Pixels =")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        entry = validation.PositiveFloatEntry(frame, textvariable=self.scale)
        entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        entry.bind("<KeyRelease>", self.size_scale_keyup)
        label = ttk.Label(frame, text="Meters")
        label.grid(row=0, column=2, sticky=tk.W)

    def draw_reference_point(self) -> None:
        label_frame = ttk.Labelframe(
            self.top, text="Reference Point", padding=FRAME_PAD
        )
        label_frame.grid(sticky=tk.EW)
        label_frame.columnconfigure(0, weight=1)

        label = ttk.Label(
            label_frame, text="Default is (0, 0), the upper left corner of the canvas"
        )
        label.grid()

        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        label = ttk.Label(frame, text="X")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        entry = validation.PositiveFloatEntry(frame, textvariable=self.x)
        entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)

        label = ttk.Label(frame, text="Y")
        label.grid(row=0, column=2, sticky=tk.W, padx=PADX)
        entry = validation.PositiveFloatEntry(frame, textvariable=self.y)
        entry.grid(row=0, column=3, sticky=tk.EW, padx=PADX)

        label = ttk.Label(label_frame, text="Translates To")
        label.grid()

        frame = ttk.Frame(label_frame)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(5, weight=1)

        label = ttk.Label(frame, text="Lat")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        entry = validation.FloatEntry(frame, textvariable=self.lat)
        entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)

        label = ttk.Label(frame, text="Lon")
        label.grid(row=0, column=2, sticky=tk.W, padx=PADX)
        entry = validation.FloatEntry(frame, textvariable=self.lon)
        entry.grid(row=0, column=3, sticky=tk.EW, padx=PADX)

        label = ttk.Label(frame, text="Alt")
        label.grid(row=0, column=4, sticky=tk.W, padx=PADX)
        entry = validation.FloatEntry(frame, textvariable=self.alt)
        entry.grid(row=0, column=5, sticky=tk.EW)

    def draw_save_as_default(self) -> None:
        button = ttk.Checkbutton(
            self.top, text="Save as default?", variable=self.save_default
        )
        button.grid(sticky=tk.W, pady=PADY)

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(sticky=tk.EW)

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def size_scale_keyup(self, _event: tk.Event) -> None:
        scale = self.scale.get()
        width = self.pixel_width.get()
        height = self.pixel_height.get()
        self.meters_width.set(width / PIXEL_SCALE * scale)
        self.meters_height.set(height / PIXEL_SCALE * scale)

    def click_apply(self) -> None:
        width, height = self.pixel_width.get(), self.pixel_height.get()
        self.manager.redraw_canvas((width, height))
        location = self.app.core.session.location
        location.x = self.x.get()
        location.y = self.y.get()
        location.lat = self.lat.get()
        location.lon = self.lon.get()
        location.alt = self.alt.get()
        location.scale = self.scale.get()
        if self.save_default.get():
            location_config = self.app.guiconfig.location
            location_config.x = location.x
            location_config.y = location.y
            location_config.z = location.z
            location_config.lat = location.lat
            location_config.lon = location.lon
            location_config.alt = location.alt
            location_config.scale = location.scale
            preferences = self.app.guiconfig.preferences
            preferences.width = width
            preferences.height = height
            self.app.save_config()
        self.destroy()
