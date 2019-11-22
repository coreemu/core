import logging
import tkinter as tk
from tkinter import ttk

from coretk import appconfig
from coretk.dialogs.dialog import Dialog


class PreferencesDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Preferences", modal=True)
        preferences = self.app.guiconfig["preferences"]
        self.editor = tk.StringVar(value=preferences["editor"])
        self.theme = tk.StringVar(value=preferences["theme"])
        self.terminal = tk.StringVar(value=preferences["terminal"])
        self.gui3d = tk.StringVar(value=preferences["gui3d"])
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.draw_preferences()
        self.draw_buttons()

    def draw_preferences(self):
        frame = ttk.LabelFrame(self.top, text="Preferences")
        frame.grid(sticky="ew", pady=2)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Theme")
        label.grid(row=0, column=0, pady=2, padx=2, sticky="w")
        themes = self.app.style.theme_names()
        combobox = ttk.Combobox(
            frame, textvariable=self.theme, values=themes, state="readonly"
        )
        combobox.set(self.theme.get())
        combobox.grid(row=0, column=1, sticky="ew")
        combobox.bind("<<ComboboxSelected>>", self.theme_change)

        label = ttk.Label(frame, text="Editor")
        label.grid(row=1, column=0, pady=2, padx=2, sticky="w")
        combobox = ttk.Combobox(
            frame, textvariable=self.editor, values=appconfig.EDITORS, state="readonly"
        )
        combobox.grid(row=1, column=1, sticky="ew")

        label = ttk.Label(frame, text="Terminal")
        label.grid(row=2, column=0, pady=2, padx=2, sticky="w")
        combobox = ttk.Combobox(
            frame,
            textvariable=self.terminal,
            values=appconfig.TERMINALS,
            state="readonly",
        )
        combobox.grid(row=2, column=1, sticky="ew")

        label = ttk.Label(frame, text="3D GUI")
        label.grid(row=3, column=0, pady=2, padx=2, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.gui3d)
        entry.grid(row=3, column=1, sticky="ew")

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def theme_change(self, event):
        theme = self.theme.get()
        logging.info("changing theme: %s", theme)
        self.app.style.theme_use(theme)

    def click_save(self):
        preferences = self.app.guiconfig["preferences"]
        preferences["terminal"] = self.terminal.get()
        preferences["editor"] = self.editor.get()
        preferences["gui3d"] = self.gui3d.get()
        preferences["theme"] = self.theme.get()
        self.app.save_config()
        self.destroy()
