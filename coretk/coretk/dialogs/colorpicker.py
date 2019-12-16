"""
custom color picker
"""
import logging
import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog


class ColorPicker(Dialog):
    def __init__(self, master, app, initcolor="#000000"):
        super().__init__(master, app, "color picker", modal=True)
        self.red_entry = None
        self.blue_entry = None
        self.green_entry = None
        self.hex_entry = None
        self.red_label = None
        self.green_label = None
        self.blue_label = None
        self.display = None
        self.color = initcolor
        red, green, blue = self.get_rgb(initcolor)
        self.red = tk.IntVar(value=red)
        self.blue = tk.IntVar(value=blue)
        self.green = tk.IntVar(value=green)
        self.hex = tk.StringVar(value=initcolor)
        self.red_scale = tk.IntVar(value=red)
        self.green_scale = tk.IntVar(value=green)
        self.blue_scale = tk.IntVar(value=blue)
        self.draw()
        self.set_bindings()

    def askcolor(self):
        self.show()
        return self.color

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        # rgb frames
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=4)
        frame.columnconfigure(3, weight=2)
        label = ttk.Label(frame, text="R: ")
        label.grid(row=0, column=0)
        self.red_entry = ttk.Entry(
            frame,
            width=4,
            textvariable=self.red,
            validate="key",
            validatecommand=(self.app.validation.rgb, "%P"),
        )
        self.red_entry.grid(row=0, column=1, sticky="nsew")
        scale = ttk.Scale(
            frame,
            from_=0,
            to=255,
            value=0,
            # length=200,
            orient=tk.HORIZONTAL,
            variable=self.red_scale,
            command=lambda x: self.scale_callback(self.red_scale, self.red),
        )
        scale.grid(row=0, column=2, sticky="nsew")
        self.red_label = ttk.Label(
            frame, background="#%02x%02x%02x" % (self.red.get(), 0, 0)
        )
        self.red_label.grid(row=0, column=3, sticky="nsew")
        frame.grid(row=0, column=0, sticky="nsew")

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=4)
        frame.columnconfigure(3, weight=2)
        label = ttk.Label(frame, text="G: ")
        label.grid(row=0, column=0)
        self.green_entry = ttk.Entry(
            frame,
            width=4,
            textvariable=self.green,
            validate="key",
            validatecommand=(self.app.validation.rgb, "%P"),
        )
        self.green_entry.grid(row=0, column=1, sticky="nsew")
        scale = ttk.Scale(
            frame,
            from_=0,
            to=255,
            value=0,
            # length=200,
            orient=tk.HORIZONTAL,
            variable=self.green_scale,
            command=lambda x: self.scale_callback(self.green_scale, self.green),
        )
        scale.grid(row=0, column=2, sticky="nsew")
        self.green_label = ttk.Label(
            frame, background="#%02x%02x%02x" % (0, self.green.get(), 0)
        )
        self.green_label.grid(row=0, column=3, sticky="nsew")
        frame.grid(row=1, column=0, sticky="nsew")

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=4)
        frame.columnconfigure(3, weight=2)
        label = ttk.Label(frame, text="B: ")
        label.grid(row=0, column=0)
        self.blue_entry = ttk.Entry(
            frame,
            width=4,
            textvariable=self.blue,
            validate="key",
            validatecommand=(self.app.validation.rgb, "%P"),
        )
        self.blue_entry.grid(row=0, column=1, sticky="nsew")
        scale = ttk.Scale(
            frame,
            from_=0,
            to=255,
            value=0,
            # length=200,
            orient=tk.HORIZONTAL,
            variable=self.blue_scale,
            command=lambda x: self.scale_callback(self.blue_scale, self.blue),
        )
        scale.grid(row=0, column=2, sticky="nsew")
        self.blue_label = ttk.Label(
            frame, background="#%02x%02x%02x" % (0, 0, self.blue.get())
        )
        self.blue_label.grid(row=0, column=3, sticky="nsew")
        frame.grid(row=2, column=0, sticky="nsew")

        # hex code and color display
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        label = ttk.Label(frame, text="Selection: ")
        label.grid(row=0, column=0, sticky="nsew")
        self.hex_entry = ttk.Entry(
            frame,
            textvariable=self.hex,
            validate="key",
            validatecommand=(self.app.validation.hex, "%P"),
        )
        self.hex_entry.grid(row=1, column=0, sticky="nsew")
        self.display = tk.Frame(frame, background=self.color, width=100, height=100)
        self.display.grid(row=2, column=0)
        frame.grid(row=3, column=0, sticky="nsew")

        # button frame
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="OK", command=self.button_ok)
        button.grid(row=0, column=0, sticky="nsew")
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="nsew")
        frame.grid(row=4, column=0, sticky="nsew")

    def set_bindings(self):
        self.red_entry.bind("<FocusIn>", lambda x: self.current_focus("rgb"))
        self.green_entry.bind("<FocusIn>", lambda x: self.current_focus("rgb"))
        self.blue_entry.bind("<FocusIn>", lambda x: self.current_focus("rgb"))
        self.hex_entry.bind("<FocusIn>", lambda x: self.current_focus("hex"))
        self.red.trace_add("write", self.update_color)
        self.green.trace_add("write", self.update_color)
        self.blue.trace_add("write", self.update_color)
        self.hex.trace_add("write", self.update_color)

    def button_ok(self):
        logging.debug("not implemented")
        self.color = self.hex.get()
        self.destroy()

    def get_hex(self):
        """
        convert current RGB values into hex color

        :rtype: str
        :return: hex color
        """
        red = self.red_entry.get()
        blue = self.blue_entry.get()
        green = self.green_entry.get()
        return "#%02x%02x%02x" % (int(red), int(green), int(blue))

    def current_focus(self, focus):
        self.focus = focus

    def update_color(self, arg1=None, arg2=None, arg3=None):
        if self.focus == "rgb":
            red = self.red_entry.get()
            blue = self.blue_entry.get()
            green = self.green_entry.get()
            self.set_scale(red, green, blue)
            if red and blue and green:
                hex_code = "#%02x%02x%02x" % (int(red), int(green), int(blue))
                self.hex.set(hex_code)
                self.display.config(background=hex_code)
                self.set_label(red, green, blue)
        elif self.focus == "hex":
            hex_code = self.hex.get()
            if len(hex_code) == 4 or len(hex_code) == 7:
                red, green, blue = self.get_rgb(hex_code)
            else:
                return
            self.set_entry(red, green, blue)
            self.set_scale(red, green, blue)
            self.display.config(background=hex_code)
            self.set_label(red, green, blue)

    def scale_callback(self, var, color_var):
        color_var.set(var.get())
        self.focus = "rgb"
        self.update_color()

    def set_scale(self, red, green, blue):
        self.red_scale.set(red)
        self.green_scale.set(green)
        self.blue_scale.set(blue)

    def set_entry(self, red, green, blue):
        self.red.set(red)
        self.green.set(green)
        self.blue.set(blue)

    def set_label(self, red, green, blue):
        self.red_label.configure(background="#%02x%02x%02x" % (int(red), 0, 0))
        self.green_label.configure(background="#%02x%02x%02x" % (0, int(green), 0))
        self.blue_label.configure(background="#%02x%02x%02x" % (0, 0, int(blue)))

    def get_rgb(self, hex_code):
        """
        convert a valid hex code to RGB values

        :param string hex_code: color in hex
        :rtype: tuple(int, int, int)
        :return: the RGB values
        """
        if len(hex_code) == 4:
            red = hex_code[1]
            green = hex_code[2]
            blue = hex_code[3]
        else:
            red = hex_code[1:3]
            green = hex_code[3:5]
            blue = hex_code[5:]
        return int(red, 16), int(green, 16), int(blue, 16)
