import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.images import ImageEnum, Images
from core.gui.themes import DIALOG_PAD

if TYPE_CHECKING:
    from core.gui.app import Application


class Dialog(tk.Toplevel):
    def __init__(
        self,
        app: "Application",
        title: str,
        modal: bool = True,
        master: tk.BaseWidget = None,
    ):
        if master is None:
            master = app
        super().__init__(master)
        self.withdraw()
        self.app = app
        self.modal = modal
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        image = Images.get(ImageEnum.CORE, 16)
        self.tk.call("wm", "iconphoto", self._w, image)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.top = ttk.Frame(self, padding=DIALOG_PAD)
        self.top.grid(sticky="nsew")

    def show(self):
        self.transient(self.master)
        self.focus_force()
        self.update()
        self.deiconify()
        if self.modal:
            self.wait_visibility()
            self.grab_set()
            self.wait_window()

    def draw_spacer(self, row: int = None):
        frame = ttk.Frame(self.top)
        frame.grid(row=row, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        self.top.rowconfigure(frame.grid_info()["row"], weight=1)
