"""
size and scale
"""
import tkinter as tk
from tkinter import font, ttk

from coretk.dialogs.dialog import Dialog

FRAME_PAD = 5
PADX = 5


class SizeAndScaleDialog(Dialog):
    def __init__(self, master, app):
        """
        create an instance for size and scale object

        :param app: main application
        """
        super().__init__(master, app, "Canvas Size and Scale", modal=True)
        self.canvas = self.app.canvas
        self.meter_per_pixel = self.canvas.meters_per_pixel
        self.section_font = font.Font(weight="bold")

        # get current canvas dimensions
        plot = self.canvas.find_withtag("rectangle")
        x0, y0, x1, y1 = self.canvas.bbox(plot[0])
        width = abs(x0 - x1) - 2
        height = abs(y0 - y1) - 2
        self.pixel_width = tk.IntVar(value=width)
        self.pixel_height = tk.IntVar(value=height)
        self.meters_width = tk.IntVar(value=width * self.meter_per_pixel)
        self.meters_height = tk.IntVar(value=height * self.meter_per_pixel)
        self.scale = tk.IntVar(value=self.meter_per_pixel * 100)
        self.x = tk.IntVar(value=0)
        self.y = tk.IntVar(value=0)
        self.lat = tk.DoubleVar(value=47.5791667)
        self.lon = tk.DoubleVar(value=-122.132322)
        self.alt = tk.DoubleVar(value=2.0)
        self.save_default = tk.BooleanVar(value=False)
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.draw_size()
        self.draw_scale()
        self.draw_reference_point()
        self.draw_save_as_default()
        self.draw_buttons()

    def draw_size(self):
        label_frame = ttk.Labelframe(self.top, text="Size", padding=FRAME_PAD)
        label_frame.grid(sticky="ew")
        label_frame.columnconfigure(0, weight=1)

        # draw size row 1
        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.pixel_width)
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.pixel_height)
        entry.grid(row=0, column=3, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="Pixels")
        label.grid(row=0, column=4, sticky="w")

        # draw size row 2
        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.meters_width)
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.meters_height)
        entry.grid(row=0, column=3, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="Meters")
        label.grid(row=0, column=4, sticky="w")

    def draw_scale(self):
        label_frame = ttk.Labelframe(self.top, text="Scale", padding=FRAME_PAD)
        label_frame.grid(sticky="ew")
        label_frame.columnconfigure(0, weight=1)

        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew")
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="100 Pixels =")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.scale)
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="Meters")
        label.grid(row=0, column=2, sticky="w")

    def draw_reference_point(self):
        label_frame = ttk.Labelframe(
            self.top, text="Reference Point", padding=FRAME_PAD
        )
        label_frame.grid(sticky="ew")
        label_frame.columnconfigure(0, weight=1)

        label = ttk.Label(
            label_frame, text="Default is (0, 0), the upper left corner of the canvas"
        )
        label.grid()

        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        label = ttk.Label(frame, text="X")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.x)
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)

        label = ttk.Label(frame, text="Y")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.y)
        entry.grid(row=0, column=3, sticky="ew", padx=PADX)

        label = ttk.Label(label_frame, text="Translates To")
        label.grid()

        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(5, weight=1)

        label = ttk.Label(frame, text="Lat")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.lat)
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)

        label = ttk.Label(frame, text="Lon")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.lon)
        entry.grid(row=0, column=3, sticky="ew", padx=PADX)

        label = ttk.Label(frame, text="Alt")
        label.grid(row=0, column=4, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.alt)
        entry.grid(row=0, column=5, sticky="ew")

    def draw_save_as_default(self):
        button = ttk.Checkbutton(
            self.top, text="Save as default?", variable=self.save_default
        )
        button.grid(sticky="w", pady=3)

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(sticky="ew")

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        meter_per_pixel = float(self.scale.get()) / 100
        width, height = self.pixel_width.get(), self.pixel_height.get()
        self.canvas.meters_per_pixel = meter_per_pixel
        self.canvas.redraw_grid(width, height)
        if self.canvas.wallpaper:
            self.canvas.redraw()
        self.destroy()
