import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application


class SimpleStringDialog(Dialog):
    def __init__(
        self, master: tk.BaseWidget, app: "Application", title: str, prompt: str
    ):
        super().__init__(app, title, master=master)
        self.bind("<Return>", lambda e: self.destroy())
        self.prompt: str = prompt
        self.value = tk.StringVar()
        self.entry: Optional[ttk.Entry] = None
        self.canceled = False
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        label = ttk.Label(self.top, text=self.prompt)
        label.grid(sticky=tk.EW, pady=PADY)
        entry = ttk.Entry(self.top, textvariable=self.value)
        entry.grid(stick=tk.EW, pady=PADY)
        entry.focus_set()
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Submit", command=self.destroy)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_cancel(self):
        self.canceled = True
        self.destroy()

    def ask(self) -> Optional[str]:
        self.show()
        if self.canceled:
            return None
        else:
            return self.value.get()
