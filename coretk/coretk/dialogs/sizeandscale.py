"""
size and scale
"""
import tkinter as tk
from functools import partial

from coretk.dialogs.setwallpaper import ScaleOption

DRAW_OBJECT_TAGS = ["edge", "node", "nodename", "linkinfo", "antenna"]


class SizeAndScale:
    def __init__(self, app):
        """
        create an instance for size and scale object

        :param app: main application
        """
        self.app = app
        self.top = tk.Toplevel()
        self.top.title("Canvas Size and Scale")
        self.meter_per_pixel = self.app.canvas.meters_per_pixel

        self.size_chart()
        self.scale_chart()
        self.reference_point_chart()
        self.save_as_default()
        self.apply_cancel()

    def pixel_scrollbar_command(self, size_frame, entry_row, entry_column, event):
        """
        change the value shown based on scrollbar action

        :param tkinter.Frame frame: pixel dimension frame
        :param int entry_row: row number of entry of the frame
        :param int entry_column: column number of entry of the frame
        :param event: scrollbar event
        :return: nothing
        """
        pixel_frame = size_frame.grid_slaves(0, 0)[0]
        pixel_entry = pixel_frame.grid_slaves(entry_row, entry_column)[0]
        val = int(pixel_entry.get())

        if event == "-1":
            new_val = val + 2
        elif event == "1":
            new_val = val - 2

        pixel_entry.delete(0, tk.END)
        pixel_entry.insert(tk.END, str(new_val))

        # change meter dimension
        meter_frame = size_frame.grid_slaves(1, 0)[0]
        meter_entry = meter_frame.grid_slaves(entry_row, entry_column)[0]
        meter_entry.delete(0, tk.END)
        meter_entry.insert(tk.END, str(new_val * self.meter_per_pixel))

    def meter_scrollbar_command(self, size_frame, entry_row, entry_column, event):
        """
        change the value shown based on scrollbar action

        :param tkinter.Frame size_frame: size frame
        :param int entry_row: row number of entry in the frame it is contained in
        :param int entry_column: column number of entry in the frame in is contained in
        :param event: scroolbar event
        :return: nothing
        """
        meter_frame = size_frame.grid_slaves(1, 0)[0]
        meter_entry = meter_frame.grid_slaves(entry_row, entry_column)[0]
        val = float(meter_entry.get())

        if event == "-1":
            val += 100.0
        elif event == "1":
            val -= 100.0
        meter_entry.delete(0, tk.END)
        meter_entry.insert(tk.END, str(val))

        # change pixel dimension
        pixel_frame = size_frame.grid_slaves(0, 0)[0]
        pixel_entry = pixel_frame.grid_slaves(entry_row, entry_column)[0]
        pixel_entry.delete(0, tk.END)
        pixel_entry.insert(tk.END, str(int(val / self.meter_per_pixel)))

    def create_text_label(self, frame, text, row, column, sticky=None):
        """
        create text label
        :param tkinter.Frame frame: parent frame
        :param str text: label text
        :param int row: row number
        :param int column: column number
        :param sticky: sticky value

        :return: nothing
        """
        text_label = tk.Label(frame, text=text)
        text_label.grid(row=row, column=column, sticky=sticky, padx=3, pady=3)

    def create_entry(self, frame, default_value, row, column, width):
        text_var = tk.StringVar(frame, value=str(default_value))
        entry = tk.Entry(
            frame, textvariable=text_var, width=width, bg="white", state=tk.NORMAL
        )
        entry.focus()
        entry.grid(row=row, column=column, padx=3, pady=3)

    def size_chart(self):
        label = tk.Label(self.top, text="Size")
        label.grid(sticky=tk.W, padx=5)

        canvas = self.app.canvas
        plot = canvas.find_withtag("rectangle")
        x0, y0, x1, y1 = canvas.bbox(plot[0])
        w = abs(x0 - x1) - 2
        h = abs(y0 - y1) - 2

        f = tk.Frame(
            self.top,
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )

        f1 = tk.Frame(f)
        pw_scrollbar = tk.Scrollbar(f1, orient=tk.VERTICAL)
        pw_scrollbar.grid(row=0, column=1)
        self.create_entry(f1, w, 0, 0, 6)
        pw_scrollbar.config(command=partial(self.pixel_scrollbar_command, f, 0, 0))

        self.create_text_label(f1, " W x ", 0, 2)

        scrollbar = tk.Scrollbar(f1, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=4)
        self.create_entry(f1, h, 0, 3, 6)
        scrollbar.config(command=partial(self.pixel_scrollbar_command, f, 0, 3))
        self.create_text_label(f1, " H pixels ", 0, 7)
        f1.grid(sticky=tk.W, pady=3)

        f2 = tk.Frame(f)
        scrollbar = tk.Scrollbar(f2, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1)
        self.create_entry(f2, w * self.meter_per_pixel, 0, 0, 8)
        scrollbar.config(command=partial(self.meter_scrollbar_command, f, 0, 0))
        self.create_text_label(f2, " x ", 0, 2)

        scrollbar = tk.Scrollbar(f2, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=4)
        self.create_entry(f2, h * self.meter_per_pixel, 0, 3, 8)
        scrollbar.config(command=partial(self.meter_scrollbar_command, f, 0, 3))
        self.create_text_label(f2, " meters ", 0, 5)

        f2.grid(sticky=tk.W, pady=3)

        f.grid(sticky=tk.W + tk.E, padx=5, pady=5, columnspan=2)

    def scale_chart(self):
        label = tk.Label(self.top, text="Scale")
        label.grid(padx=5, sticky=tk.W)
        f = tk.Frame(
            self.top,
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )
        # self.create_text_label(f, "Scale", 0, 0, tk.W)
        # f1 = tk.Frame(f)
        self.create_text_label(f, "100 pixels = ", 0, 0)
        self.create_entry(f, self.meter_per_pixel * 100, 0, 1, 10)
        self.create_text_label(f, "meters", 0, 2)
        # f1.grid(sticky=tk.W, pady=3)
        f.grid(sticky=tk.W + tk.E, padx=5, pady=5, columnspan=2)

    def reference_point_chart(self):
        label = tk.Label(self.top, text="Reference point")
        label.grid(padx=5, sticky=tk.W)

        f = tk.Frame(
            self.top,
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )
        self.create_text_label(
            f,
            "The default reference point is (0, 0), the upper left corner of the canvas.",
            1,
            0,
            tk.W,
        )
        f1 = tk.Frame(f)
        self.create_entry(f1, 0, 0, 0, 4)
        self.create_text_label(f1, " X, ", 0, 1)
        self.create_entry(f1, 0, 0, 2, 4)
        self.create_text_label(f1, "Y = ", 0, 3)
        self.create_entry(f1, 47.5791667, 0, 4, 13)
        self.create_text_label(f1, " lat, ", 0, 5)
        self.create_entry(f1, -122.132322, 0, 6, 13)
        self.create_text_label(f1, "long", 0, 7)
        f1.grid(row=2, column=0, sticky=tk.W, pady=3)

        f2 = tk.Frame(f)
        self.create_text_label(f2, "Altitude: ", 0, 0)
        self.create_entry(f2, 2.0, 0, 1, 11)
        self.create_text_label(f2, " meters ", 0, 2)
        f2.grid(row=3, column=0, sticky=tk.W, pady=3)

        f.grid(sticky=tk.W, padx=5, pady=5, columnspan=2)

    def save_as_default(self):
        var = tk.IntVar()
        button = tk.Checkbutton(self.top, text="Save as default", variable=var)
        button.grid(sticky=tk.W, padx=5, pady=5, columnspan=2)

    def redraw_grid(self, pixel_width, pixel_height):
        """
        redraw grid with new dimension

        :param int pixel_width: width in pixel
        :param int pixel_height: height in pixel
        :return: nothing
        """
        canvas = self.app.canvas
        canvas.config(scrollregion=(0, 0, pixel_width + 200, pixel_height + 200))

        # delete old plot and redraw
        for i in canvas.find_withtag("gridline"):
            canvas.delete(i)
        for i in canvas.find_withtag("rectangle"):
            canvas.delete(i)

        canvas.draw_grid(width=pixel_width, height=pixel_height)
        # lift anything that is drawn on the plot before
        for tag in DRAW_OBJECT_TAGS:
            for i in canvas.find_withtag(tag):
                canvas.lift(i)

    def click_apply(self):
        size_frame = self.top.grid_slaves(1, 0)[0]
        pixel_size_frame = size_frame.grid_slaves(0, 0)[0]

        pixel_width = int(pixel_size_frame.grid_slaves(0, 0)[0].get())
        pixel_height = int(pixel_size_frame.grid_slaves(0, 3)[0].get())

        scale_frame = self.top.grid_slaves(3, 0)[0]
        meter_per_pixel = float(scale_frame.grid_slaves(0, 1)[0].get()) / 100
        self.app.canvas.meters_per_pixel = meter_per_pixel
        self.redraw_grid(pixel_width, pixel_height)
        print(self.app.current_wallpaper)
        print(self.app.radiovar)
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

        self.top.destroy()

    def apply_cancel(self):
        apply_button = tk.Button(self.top, text="Apply", command=self.click_apply)
        apply_button.grid(row=7, column=0, pady=5)
        cancel_button = tk.Button(self.top, text="Cancel", command=self.top.destroy)
        cancel_button.grid(row=7, column=1, pady=5)
