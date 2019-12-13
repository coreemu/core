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
        self.display = None

        self.red = tk.StringVar(value=0)
        self.blue = tk.StringVar(value=0)
        self.green = tk.StringVar(value=0)
        self.hex = tk.StringVar(value=initcolor)

        self.draw()
        self.set_bindings()

    def draw(self):
        edit_frame = ttk.Frame(self)
        edit_frame.columnconfigure(0, weight=4)
        edit_frame.columnconfigure(1, weight=2)
        # the rbg frame
        frame = ttk.Frame(edit_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)
        label = ttk.Label(frame, text="R: ")
        label.grid(row=0, column=0)
        self.red_entry = ttk.Entry(
            frame,
            textvariable=self.red,
            validate="key",
            validatecommand=(self.app.validation.rgb, "%P"),
        )
        self.red_entry.grid(row=0, column=1, sticky="nsew")

        label = ttk.Label(frame, text="G: ")
        label.grid(row=1, column=0)
        self.green_entry = ttk.Entry(
            frame,
            textvariable=self.green,
            validate="key",
            validatecommand=(self.app.validation.rgb, "%P"),
        )
        self.green_entry.grid(row=1, column=1, sticky="nsew")

        label = ttk.Label(frame, text="B: ")
        label.grid(row=2, column=0)
        self.blue_entry = ttk.Entry(
            frame,
            textvariable=self.blue,
            validate="key",
            validatecommand=(self.app.validation.rgb, "%P"),
        )
        self.blue_entry.grid(row=2, column=1, sticky="nsew")

        frame.grid(row=0, column=0, sticky="nsew")

        # hex code and color display
        frame = ttk.Frame(edit_frame)
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
        self.display = ttk.Label(frame, background="white")
        self.display.grid(row=2, column=0, sticky="nsew")
        frame.grid(row=0, column=1, sticky="nsew")

        edit_frame.grid(row=0, column=0, sticky="nsew")

        # button frame
        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="OK", command=self.button_ok)
        button.grid(row=0, column=0, sticky="nsew")
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="nsew")
        frame.grid(row=1, column=0, sticky="nsew")

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

    def get_hex(self):
        red = self.red_entry.get()
        blue = self.blue_entry.get()
        green = self.green_entry.get()
        return "#%02x%02x%02x" % (int(red), int(green), int(blue))

    def current_focus(self, focus):
        self.focus = focus

    def update_color(self, arg1, arg2, arg3):
        if self.focus == "rgb":
            red = self.red_entry.get()
            blue = self.blue_entry.get()
            green = self.green_entry.get()
            if red and blue and green:
                hex_code = "#%02x%02x%02x" % (int(red), int(green), int(blue))
                self.hex_entry.delete(0, tk.END)
                self.hex_entry.insert(0, hex_code)
                self.display.config(background=hex_code)
        elif self.focus == "hex":
            hex_code = self.hex.get()
            if len(hex_code) == 4 or len(hex_code) == 7:
                if len(hex_code) == 4:
                    red = hex_code[1]
                    green = hex_code[2]
                    blue = hex_code[3]
                else:
                    red = hex_code[1:3]
                    green = hex_code[3:5]
                    blue = hex_code[5:]
            else:
                return
            self.red_entry.delete(0, tk.END)
            self.green_entry.delete(0, tk.END)
            self.blue_entry.delete(0, tk.END)
            self.red_entry.insert(0, "%s" % (int(red, 16)))
            self.green_entry.insert(0, "%s" % (int(green, 16)))
            self.blue_entry.insert(0, "%s" % (int(blue, 16)))
            self.display.config(background=hex_code)
