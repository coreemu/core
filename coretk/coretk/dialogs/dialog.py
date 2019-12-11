import tkinter as tk
from tkinter import ttk

from coretk.images import ImageEnum, Images
from coretk.themes import DIALOG_PAD


class Dialog(tk.Toplevel):
    def __init__(self, master, app, title, modal=False):
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

    def draw_spacer(self, row=None):
        frame = ttk.Frame(self.top)
        frame.grid(row=row, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        self.top.rowconfigure(frame.grid_info()["row"], weight=1)
