import logging
import tkinter as tk
from tkinter import filedialog, ttk

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX


class ExecutePythonDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Execute Python Script", modal=True)
        self.app = app
        self.with_options = tk.IntVar(value=0)
        self.options = tk.StringVar(value="")
        self.option_entry = None
        self.file_entry = None
        self.draw()

    def draw(self):
        i = 0
        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=i, column=0, sticky="nsew")
        i = i + 1
        var = tk.StringVar(value="")
        self.file_entry = ttk.Entry(frame, textvariable=var)
        self.file_entry.grid(row=0, column=0, sticky="ew")
        button = ttk.Button(frame, text="...", command=self.select_file)
        button.grid(row=0, column=1, sticky="ew")

        self.top.columnconfigure(0, weight=1)
        button = ttk.Checkbutton(
            self.top,
            text="With Options",
            variable=self.with_options,
            command=self.add_options,
        )
        button.grid(row=i, column=0, sticky="ew")
        i = i + 1

        label = ttk.Label(
            self.top, text="Any command-line options for running the Python script"
        )
        label.grid(row=i, column=0, sticky="ew")
        i = i + 1
        self.option_entry = ttk.Entry(
            self.top, textvariable=self.options, state="disabled"
        )
        self.option_entry.grid(row=i, column=0, sticky="ew")
        i = i + 1

        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=i, column=0)
        button = ttk.Button(frame, text="Execute", command=self.script_execute)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew", padx=PADX)

    def add_options(self):
        if self.with_options.get():
            self.option_entry.configure(state="normal")
        else:
            self.option_entry.configure(state="disabled")

    def select_file(self):
        file = filedialog.askopenfilename(
            parent=self.top,
            initialdir="/",
            title="Open python script",
            filetypes=((".py Files", "*.py"), ("All Files", "*")),
        )
        if file:
            self.file_entry.delete(0, "end")
            self.file_entry.insert("end", file)

    def script_execute(self):
        file = self.file_entry.get()
        options = self.option_entry.get()
        logging.debug("Execute %s with options %s", file, options)
        self.destroy()
