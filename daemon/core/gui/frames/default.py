import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.frames.base import InfoFrameBase

if TYPE_CHECKING:
    from core.gui.app import Application


class DefaultInfoFrame(InfoFrameBase):
    def __init__(self, master: tk.BaseWidget, app: "Application") -> None:
        super().__init__(master, app)

    def draw(self) -> None:
        label = ttk.Label(self, text="Click a Node/Link", anchor=tk.CENTER)
        label.grid(sticky=tk.EW)
        label = ttk.Label(self, text="to see details", anchor=tk.CENTER)
        label.grid(sticky=tk.EW)
