"""
custom color picker
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional, Tuple

from core.gui import validation
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application


class ColorPickerDialog(Dialog):
    def __init__(
        self, master: tk.BaseWidget, app: "Application", initcolor: str = "#000000"
    ):
        super().__init__(app, "Color Picker", master=master)
        self.red_entry: Optional[validation.RgbEntry] = None
        self.blue_entry: Optional[validation.RgbEntry] = None
        self.green_entry: Optional[validation.RgbEntry] = None
        self.hex_entry: Optional[validation.HexEntry] = None
        self.red_label: Optional[ttk.Label] = None
        self.green_label: Optional[ttk.Label] = None
        self.blue_label: Optional[ttk.Label] = None
        self.display: Optional[tk.Frame] = None
        self.color: str = initcolor
        red, green, blue = self.get_rgb(initcolor)
        self.red: tk.IntVar = tk.IntVar(value=red)
        self.blue: tk.IntVar = tk.IntVar(value=blue)
        self.green: tk.IntVar = tk.IntVar(value=green)
        self.hex: tk.StringVar = tk.StringVar(value=initcolor)
        self.red_scale: tk.IntVar = tk.IntVar(value=red)
        self.green_scale: tk.IntVar = tk.IntVar(value=green)
        self.blue_scale: tk.IntVar = tk.IntVar(value=blue)
        self.draw()
        self.set_bindings()

    def askcolor(self) -> str:
        self.show()
        return self.color

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(3, weight=1)

        # rgb frames
        frame = ttk.Frame(self.top)
        frame.grid(row=0, column=0, sticky=tk.EW, pady=PADY)
        frame.columnconfigure(2, weight=3)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="R")
        label.grid(row=0, column=0, padx=PADX)
        self.red_entry = validation.RgbEntry(frame, width=3, textvariable=self.red)
        self.red_entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        scale = ttk.Scale(
            frame,
            from_=0,
            to=255,
            value=0,
            orient=tk.HORIZONTAL,
            variable=self.red_scale,
            command=lambda x: self.scale_callback(self.red_scale, self.red),
        )
        scale.grid(row=0, column=2, sticky=tk.EW, padx=PADX)
        self.red_label = ttk.Label(
            frame, background="#%02x%02x%02x" % (self.red.get(), 0, 0), width=5
        )
        self.red_label.grid(row=0, column=3, sticky=tk.EW)

        frame = ttk.Frame(self.top)
        frame.grid(row=1, column=0, sticky=tk.EW, pady=PADY)
        frame.columnconfigure(2, weight=3)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="G")
        label.grid(row=0, column=0, padx=PADX)
        self.green_entry = validation.RgbEntry(frame, width=3, textvariable=self.green)
        self.green_entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        scale = ttk.Scale(
            frame,
            from_=0,
            to=255,
            value=0,
            orient=tk.HORIZONTAL,
            variable=self.green_scale,
            command=lambda x: self.scale_callback(self.green_scale, self.green),
        )
        scale.grid(row=0, column=2, sticky=tk.EW, padx=PADX)
        self.green_label = ttk.Label(
            frame, background="#%02x%02x%02x" % (0, self.green.get(), 0), width=5
        )
        self.green_label.grid(row=0, column=3, sticky=tk.EW)

        frame = ttk.Frame(self.top)
        frame.grid(row=2, column=0, sticky=tk.EW, pady=PADY)
        frame.columnconfigure(2, weight=3)
        frame.columnconfigure(3, weight=1)
        label = ttk.Label(frame, text="B")
        label.grid(row=0, column=0, padx=PADX)
        self.blue_entry = validation.RgbEntry(frame, width=3, textvariable=self.blue)
        self.blue_entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        scale = ttk.Scale(
            frame,
            from_=0,
            to=255,
            value=0,
            orient=tk.HORIZONTAL,
            variable=self.blue_scale,
            command=lambda x: self.scale_callback(self.blue_scale, self.blue),
        )
        scale.grid(row=0, column=2, sticky=tk.EW, padx=PADX)
        self.blue_label = ttk.Label(
            frame, background="#%02x%02x%02x" % (0, 0, self.blue.get()), width=5
        )
        self.blue_label.grid(row=0, column=3, sticky=tk.EW)

        # hex code and color display
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        self.hex_entry = validation.HexEntry(frame, textvariable=self.hex)
        self.hex_entry.grid(sticky=tk.EW, pady=PADY)
        self.display = tk.Frame(frame, background=self.color, width=100, height=100)
        self.display.grid(sticky=tk.NSEW)
        frame.grid(row=3, column=0, sticky=tk.NSEW, pady=PADY)

        # button frame
        frame = ttk.Frame(self.top)
        frame.grid(row=4, column=0, sticky=tk.EW)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="OK", command=self.button_ok)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def set_bindings(self) -> None:
        self.red_entry.bind("<FocusIn>", lambda x: self.current_focus("rgb"))
        self.green_entry.bind("<FocusIn>", lambda x: self.current_focus("rgb"))
        self.blue_entry.bind("<FocusIn>", lambda x: self.current_focus("rgb"))
        self.hex_entry.bind("<FocusIn>", lambda x: self.current_focus("hex"))
        self.red.trace_add("write", self.update_color)
        self.green.trace_add("write", self.update_color)
        self.blue.trace_add("write", self.update_color)
        self.hex.trace_add("write", self.update_color)

    def button_ok(self) -> None:
        self.color = self.hex.get()
        self.destroy()

    def get_hex(self) -> str:
        """
        convert current RGB values into hex color
        """
        red = self.red_entry.get()
        blue = self.blue_entry.get()
        green = self.green_entry.get()
        return "#%02x%02x%02x" % (int(red), int(green), int(blue))

    def current_focus(self, focus: str) -> None:
        self.focus = focus

    def update_color(self, arg1=None, arg2=None, arg3=None) -> None:
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
            self.set_label(str(red), str(green), str(blue))

    def scale_callback(self, var: tk.IntVar, color_var: tk.IntVar) -> None:
        color_var.set(var.get())
        self.focus = "rgb"
        self.update_color()

    def set_scale(self, red: int, green: int, blue: int):
        self.red_scale.set(red)
        self.green_scale.set(green)
        self.blue_scale.set(blue)

    def set_entry(self, red: int, green: int, blue: int) -> None:
        self.red.set(red)
        self.green.set(green)
        self.blue.set(blue)

    def set_label(self, red: str, green: str, blue: str) -> None:
        self.red_label.configure(background="#%02x%02x%02x" % (int(red), 0, 0))
        self.green_label.configure(background="#%02x%02x%02x" % (0, int(green), 0))
        self.blue_label.configure(background="#%02x%02x%02x" % (0, 0, int(blue)))

    def get_rgb(self, hex_code: str) -> Tuple[int, int, int]:
        """
        convert a valid hex code to RGB values
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
