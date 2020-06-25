import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.themes import FRAME_PAD, PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application


class InfoFrameBase(ttk.Frame):
    def __init__(self, master: tk.BaseWidget, app: "Application") -> None:
        super().__init__(master, padding=FRAME_PAD)
        self.app: "Application" = app

    def draw(self) -> None:
        raise NotImplementedError


class DetailsFrame(ttk.Frame):
    def __init__(self, master: tk.BaseWidget) -> None:
        super().__init__(master)
        self.columnconfigure(1, weight=1)
        self.row = 0

    def add_detail(self, label: str, value: str) -> None:
        label = ttk.Label(self, text=label, anchor=tk.W)
        label.grid(row=self.row, sticky=tk.EW, column=0, padx=PADX)
        label = ttk.Label(self, text=value, anchor=tk.W, state=tk.DISABLED)
        label.grid(row=self.row, sticky=tk.EW, column=1)
        self.row += 1

    def add_separator(self) -> None:
        separator = ttk.Separator(self)
        separator.grid(row=self.row, sticky=tk.EW, columnspan=2, pady=PADY)
        self.row += 1
