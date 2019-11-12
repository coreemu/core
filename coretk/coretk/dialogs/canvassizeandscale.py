"""
size and scale
"""
import tkinter as tk
from tkinter import font, ttk

from coretk.dialogs.canvasbackground import ScaleOption
from coretk.dialogs.dialog import Dialog

DRAW_OBJECT_TAGS = ["edge", "node", "nodename", "linkinfo", "antenna"]


class SizeAndScaleDialog(Dialog):
    def __init__(self, master, app):
        """
        create an instance for size and scale object

        :param app: main application
        """
        super().__init__(master, app, "Canvas Size and Scale", modal=True)
        self.meter_per_pixel = self.app.canvas.meters_per_pixel
        self.section_font = font.Font(weight="bold")

        # get current canvas dimensions
        canvas = self.app.canvas
        plot = canvas.find_withtag("rectangle")
        x0, y0, x1, y1 = canvas.bbox(plot[0])
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
        self.columnconfigure(0, weight=1)
        self.draw_size()
        self.draw_scale()
        self.draw_reference_point()
        self.draw_save_as_default()
        self.draw_buttons()

    def draw_size(self):
        label = ttk.Label(self, text="Size", font=self.section_font)
        label.grid(sticky="w")

        # draw size row 1
        frame = ttk.Frame(self)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.pixel_width)
        entry.grid(row=0, column=1, sticky="ew")
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.pixel_height)
        entry.grid(row=0, column=3, sticky="ew")
        label = ttk.Label(frame, text="Pixels")
        label.grid(row=0, column=4, sticky="w")

        # draw size row 2
        frame = ttk.Frame(self)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="Width")
        label.grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.meters_width)
        entry.grid(row=0, column=1, sticky="ew")
        label = ttk.Label(frame, text="x Height")
        label.grid(row=0, column=2, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.meters_height)
        entry.grid(row=0, column=3, sticky="ew")
        label = ttk.Label(frame, text="Meters")
        label.grid(row=0, column=4, sticky="w")

    def draw_scale(self):
        label = ttk.Label(self, text="Scale", font=self.section_font)
        label.grid(sticky="w")

        frame = ttk.Frame(self)
        frame.grid(sticky="ew")
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="100 Pixels =")
        label.grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.scale)
        entry.grid(row=0, column=1, sticky="ew")
        label = ttk.Label(frame, text="Meters")
        label.grid(row=0, column=2, sticky="w")

    def draw_reference_point(self):
        label = ttk.Label(self, text="Reference point", font=self.section_font)
        label.grid(sticky="w")
        label = ttk.Label(
            self, text="Default is (0, 0), the upper left corner of the canvas"
        )
        label.grid(sticky="w")

        frame = ttk.Frame(self)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        label = ttk.Label(frame, text="X")
        label.grid(row=0, column=0, sticky="w")
        x_var = tk.StringVar(value=0)
        entry = ttk.Entry(frame, textvariable=x_var)
        entry.grid(row=0, column=1, sticky="ew")

        label = ttk.Label(frame, text="Y")
        label.grid(row=0, column=2, sticky="w")
        y_var = tk.StringVar(value=0)
        entry = ttk.Entry(frame, textvariable=y_var)
        entry.grid(row=0, column=3, sticky="ew")

        label = ttk.Label(self, text="Translates To")
        label.grid(sticky="w")

        frame = ttk.Frame(self)
        frame.grid(sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(5, weight=1)

        label = ttk.Label(frame, text="Lat")
        label.grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.lat)
        entry.grid(row=0, column=1, sticky="ew")

        label = ttk.Label(frame, text="Lon")
        label.grid(row=0, column=2, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.lon)
        entry.grid(row=0, column=3, sticky="ew")

        label = ttk.Label(frame, text="Alt")
        label.grid(row=0, column=4, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.alt)
        entry.grid(row=0, column=5, sticky="ew")

    def draw_save_as_default(self):
        button = ttk.Checkbutton(
            self, text="Save as default?", variable=self.save_default
        )
        button.grid(sticky="w", pady=3)

    def draw_buttons(self):
        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(sticky="ew")

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, pady=5, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, pady=5, sticky="ew")

    def redraw_grid(self):
        """
        redraw grid with new dimension

        :return: nothing
        """
        width, height = self.pixel_width.get(), self.pixel_height.get()

        canvas = self.app.canvas
        canvas.config(scrollregion=(0, 0, width + 200, height + 200))

        # delete old plot and redraw
        for i in canvas.find_withtag("gridline"):
            canvas.delete(i)
        for i in canvas.find_withtag("rectangle"):
            canvas.delete(i)

        canvas.draw_grid(width=width, height=height)
        # lift anything that is drawn on the plot before
        for tag in DRAW_OBJECT_TAGS:
            for i in canvas.find_withtag(tag):
                canvas.lift(i)

    def click_apply(self):
        meter_per_pixel = float(self.scale.get()) / 100
        self.app.canvas.meters_per_pixel = meter_per_pixel
        self.redraw_grid()
        # if there is a current wallpaper showing, redraw it based on current wallpaper options
        wallpaper_tool = self.app.set_wallpaper
        current_wallpaper = self.app.current_wallpaper
        if current_wallpaper:
            if self.app.adjust_to_dim_var.get() == 0:
                if self.app.radiovar.get() == ScaleOption.UPPER_LEFT.value:
                    wallpaper_tool.upper_left(current_wallpaper)
                elif self.app.radiovar.get() == ScaleOption.CENTERED.value:
                    wallpaper_tool.center(current_wallpaper)
                elif self.app.radiovar.get() == ScaleOption.SCALED.value:
                    wallpaper_tool.scaled(current_wallpaper)
                elif self.app.radiovar.get() == ScaleOption.TILED.value:
                    print("not implemented")
            elif self.app.adjust_to_dim_var.get() == 1:
                wallpaper_tool.canvas_to_image_dimension(current_wallpaper)
            wallpaper_tool.show_grid()
        self.destroy()
