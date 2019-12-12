"""
size and scale
"""
import tkinter as tk
from tkinter import font, ttk

from coretk.dialogs.dialog import Dialog
from coretk.themes import FRAME_PAD, PADX, PADY

PIXEL_SCALE = 100


class SizeAndScaleDialog(Dialog):
    def __init__(self, master, app):
        """
        create an instance for size and scale object

        :param app: main application
        """
        super().__init__(master, app, "Canvas Size and Scale", modal=True)
        self.canvas = self.app.canvas
        self.validation = app.validation
        self.section_font = font.Font(weight="bold")
        width, height = self.canvas.current_dimensions
        self.pixel_width = tk.IntVar(value=width)
        self.pixel_height = tk.IntVar(value=height)
        location = self.app.core.location
        self.x = tk.DoubleVar(value=location.x)
        self.y = tk.DoubleVar(value=location.y)
        self.lat = tk.DoubleVar(value=location.lat)
        self.lon = tk.DoubleVar(value=location.lon)
        self.alt = tk.DoubleVar(value=location.alt)
        self.scale = tk.DoubleVar(value=location.scale)
        self.meters_width = tk.IntVar(value=width / PIXEL_SCALE * location.scale)
        self.meters_height = tk.IntVar(value=height / PIXEL_SCALE * location.scale)
        self.save_default = tk.BooleanVar(value=False)
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.draw_size()
        self.draw_scale()
        self.draw_reference_point()
        self.draw_save_as_default()
        self.draw_spacer()
        self.draw_buttons()

    def draw_size(self):
        label_frame = ttk.Labelframe(self.top, text="Size", padding=FRAME_PAD)
        label_frame.grid(sticky="ew")
        label_frame.columnconfigure(0, weight=1)

        # draw size row 1
        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.pixel_width,
            validate="key",
            validatecommand=(self.validation.positive_int, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.pixel_height,
            validate="key",
            validatecommand=(self.validation.positive_int, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=3, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="Pixels")
        label.grid(row=0, column=4, sticky="w")

        # draw size row 2
        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.meters_width,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.meters_height,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
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
        label = ttk.Label(frame, text=f"{PIXEL_SCALE} Pixels =")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.scale,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
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
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        label = ttk.Label(frame, text="X")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.x,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)

        label = ttk.Label(frame, text="Y")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.y,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=3, sticky="ew", padx=PADX)

        label = ttk.Label(label_frame, text="Translates To")
        label.grid()

        frame = ttk.Frame(label_frame)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(5, weight=1)

        label = ttk.Label(frame, text="Lat")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.lat,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)

        label = ttk.Label(frame, text="Lon")
        label.grid(row=0, column=2, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.lon,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=3, sticky="ew", padx=PADX)

        label = ttk.Label(frame, text="Alt")
        label.grid(row=0, column=4, sticky="w", padx=PADX)
        entry = ttk.Entry(
            frame,
            textvariable=self.alt,
            validate="key",
            validatecommand=(self.validation.positive_float, "%P"),
        )
        entry.bind("<FocusOut>", lambda event: self.validation.focus_out(event, "0"))
        entry.grid(row=0, column=5, sticky="ew")

    def draw_save_as_default(self):
        button = ttk.Checkbutton(
            self.top, text="Save as default?", variable=self.save_default
        )
        button.grid(sticky="w", pady=PADY)

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
        width, height = self.pixel_width.get(), self.pixel_height.get()
        self.canvas.redraw_canvas((width, height))
        if self.canvas.wallpaper:
            self.canvas.redraw_wallpaper()
        location = self.app.core.location
        location.x = self.x.get()
        location.y = self.y.get()
        location.lat = self.lat.get()
        location.lon = self.lon.get()
        location.alt = self.alt.get()
        location.scale = self.scale.get()
        if self.save_default.get():
            location_config = self.app.guiconfig["location"]
            location_config["x"] = location.x
            location_config["y"] = location.y
            location_config["z"] = location.z
            location_config["lat"] = location.lat
            location_config["lon"] = location.lon
            location_config["alt"] = location.alt
            location_config["scale"] = location.scale
            preferences = self.app.guiconfig["preferences"]
            preferences["width"] = width
            preferences["height"] = height
            self.app.save_config()
        self.destroy()
