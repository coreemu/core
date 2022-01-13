import logging
import tkinter as tk
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Optional

from core.gui.appconfig import SCRIPT_PATH
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application


class ExecutePythonDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Execute Python Script")
        self.with_options: tk.IntVar = tk.IntVar(value=0)
        self.options: tk.StringVar = tk.StringVar(value="")
        self.option_entry: Optional[ttk.Entry] = None
        self.file_entry: Optional[ttk.Entry] = None
        self.draw()

    def draw(self) -> None:
        i = 0
        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=i, column=0, sticky=tk.NSEW)
        i = i + 1
        var = tk.StringVar(value="")
        self.file_entry = ttk.Entry(frame, textvariable=var)
        self.file_entry.grid(row=0, column=0, sticky=tk.EW)
        button = ttk.Button(frame, text="...", command=self.select_file)
        button.grid(row=0, column=1, sticky=tk.EW)

        self.top.columnconfigure(0, weight=1)
        button = ttk.Checkbutton(
            self.top,
            text="With Options",
            variable=self.with_options,
            command=self.add_options,
        )
        button.grid(row=i, column=0, sticky=tk.EW)
        i = i + 1

        label = ttk.Label(
            self.top, text="Any command-line options for running the Python script"
        )
        label.grid(row=i, column=0, sticky=tk.EW)
        i = i + 1
        self.option_entry = ttk.Entry(
            self.top, textvariable=self.options, state="disabled"
        )
        self.option_entry.grid(row=i, column=0, sticky=tk.EW)
        i = i + 1

        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=i, column=0)
        button = ttk.Button(frame, text="Execute", command=self.script_execute)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)

    def add_options(self) -> None:
        if self.with_options.get():
            self.option_entry.configure(state="normal")
        else:
            self.option_entry.configure(state="disabled")

    def select_file(self) -> None:
        file = filedialog.askopenfilename(
            parent=self.top,
            initialdir=str(SCRIPT_PATH),
            title="Open python script",
            filetypes=((".py Files", "*.py"), ("All Files", "*")),
        )
        if file:
            self.file_entry.delete(0, "end")
            self.file_entry.insert("end", file)

    def script_execute(self) -> None:
        file = self.file_entry.get()
        options = self.option_entry.get()
        logger.info("Execute %s with options %s", file, options)
        self.app.core.execute_script(file, options)
        self.destroy()
