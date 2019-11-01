import tkinter as tk

from coretk.images import ImageEnum, Images


class Dialog(tk.Toplevel):
    def __init__(self, master, app, title, modal=False):
        super().__init__(master, padx=5, pady=5)
        self.withdraw()
        self.app = app
        self.modal = modal
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        image = Images.get(ImageEnum.CORE)
        self.tk.call("wm", "iconphoto", self._w, image)

    def show(self):
        self.transient(self.master)
        self.focus_force()
        if self.modal:
            self.grab_set()
        self.update()
        self.deiconify()
        self.wait_window()