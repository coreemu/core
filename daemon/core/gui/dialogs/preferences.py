import logging
import math
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui import appconfig, validation
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY, scale_fonts
from core.gui.validation import LARGEST_SCALE, SMALLEST_SCALE

if TYPE_CHECKING:
    from core.gui.app import Application

SCALE_INTERVAL = 0.01


class PreferencesDialog(Dialog):
    def __init__(self, app: "Application"):
        super().__init__(app, "Preferences")
        self.gui_scale = tk.DoubleVar(value=self.app.app_scale)
        preferences = self.app.guiconfig.preferences
        self.editor = tk.StringVar(value=preferences.editor)
        self.theme = tk.StringVar(value=preferences.theme)
        self.terminal = tk.StringVar(value=preferences.terminal)
        self.gui3d = tk.StringVar(value=preferences.gui3d)
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.draw_preferences()
        self.draw_buttons()

    def draw_preferences(self):
        frame = ttk.LabelFrame(self.top, text="Preferences", padding=FRAME_PAD)
        frame.grid(sticky="nsew", pady=PADY)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Theme")
        label.grid(row=0, column=0, pady=PADY, padx=PADX, sticky="w")
        themes = self.app.style.theme_names()
        combobox = ttk.Combobox(
            frame, textvariable=self.theme, values=themes, state="readonly"
        )
        combobox.set(self.theme.get())
        combobox.grid(row=0, column=1, sticky="ew")
        combobox.bind("<<ComboboxSelected>>", self.theme_change)

        label = ttk.Label(frame, text="Editor")
        label.grid(row=1, column=0, pady=PADY, padx=PADX, sticky="w")
        combobox = ttk.Combobox(
            frame, textvariable=self.editor, values=appconfig.EDITORS, state="readonly"
        )
        combobox.grid(row=1, column=1, sticky="ew")

        label = ttk.Label(frame, text="Terminal")
        label.grid(row=2, column=0, pady=PADY, padx=PADX, sticky="w")
        terminals = sorted(appconfig.TERMINALS.values())
        combobox = ttk.Combobox(frame, textvariable=self.terminal, values=terminals)
        combobox.grid(row=2, column=1, sticky="ew")

        label = ttk.Label(frame, text="3D GUI")
        label.grid(row=3, column=0, pady=PADY, padx=PADX, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.gui3d)
        entry.grid(row=3, column=1, sticky="ew")

        label = ttk.Label(frame, text="Scaling")
        label.grid(row=4, column=0, pady=PADY, padx=PADX, sticky="w")

        scale_frame = ttk.Frame(frame)
        scale_frame.grid(row=4, column=1, sticky="ew")
        scale_frame.columnconfigure(0, weight=1)
        scale = ttk.Scale(
            scale_frame,
            from_=SMALLEST_SCALE,
            to=LARGEST_SCALE,
            value=1,
            orient=tk.HORIZONTAL,
            variable=self.gui_scale,
        )
        scale.grid(row=0, column=0, sticky="ew")
        entry = validation.AppScaleEntry(
            scale_frame, textvariable=self.gui_scale, width=4
        )
        entry.grid(row=0, column=1)

        scrollbar = ttk.Scrollbar(scale_frame, command=self.adjust_scale)
        scrollbar.grid(row=0, column=2)

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def theme_change(self, event: tk.Event):
        theme = self.theme.get()
        logging.info("changing theme: %s", theme)
        self.app.style.theme_use(theme)

    def click_save(self):
        preferences = self.app.guiconfig.preferences
        preferences.terminal = self.terminal.get()
        preferences.editor = self.editor.get()
        preferences.gui3d = self.gui3d.get()
        preferences.theme = self.theme.get()
        self.gui_scale.set(round(self.gui_scale.get(), 2))
        app_scale = self.gui_scale.get()
        self.app.guiconfig.scale = app_scale
        self.app.save_config()
        self.scale_adjust()
        self.destroy()

    def scale_adjust(self):
        app_scale = self.gui_scale.get()
        self.app.app_scale = app_scale
        self.app.master.tk.call("tk", "scaling", app_scale)

        # scale fonts
        scale_fonts(self.app.fonts_size, app_scale)
        text_scale = app_scale if app_scale < 1 else math.sqrt(app_scale)
        self.app.icon_text_font.config(size=int(12 * text_scale))
        self.app.edge_font.config(size=int(8 * text_scale))

        # scale application window
        self.app.center()

        # scale toolbar and canvas items
        self.app.toolbar.scale()
        self.app.canvas.scale_graph()

    def adjust_scale(self, arg1: str, arg2: str, arg3: str):
        scale_value = self.gui_scale.get()
        if arg2 == "-1":
            if scale_value <= LARGEST_SCALE - SCALE_INTERVAL:
                self.gui_scale.set(round(scale_value + SCALE_INTERVAL, 2))
            else:
                self.gui_scale.set(round(LARGEST_SCALE, 2))
        elif arg2 == "1":
            if scale_value >= SMALLEST_SCALE + SCALE_INTERVAL:
                self.gui_scale.set(round(scale_value - SCALE_INTERVAL, 2))
            else:
                self.gui_scale.set(round(SMALLEST_SCALE, 2))
