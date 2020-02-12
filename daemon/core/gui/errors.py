from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum, Images
from core.gui.widgets import CodeText

if TYPE_CHECKING:
    import grpc
    from core.gui.app import Application


class ErrorDialog(Dialog):
    def __init__(self, master, app: "Application", title: str, details: str):
        super().__init__(master, app, title, modal=True)
        self.error_message = None
        self.details = details
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        image = Images.get(ImageEnum.ERROR, 36)
        label = ttk.Label(self.top, image=image)
        label.image = image
        label.grid(row=0, column=0)
        self.error_message = CodeText(self.top)
        self.error_message.text.insert("1.0", self.details)
        self.error_message.text.config(state="disabled")
        self.error_message.grid(row=1, column=0, sticky="nsew")


def show_grpc_error(e: "grpc.RpcError", master, app: "Application"):
    title = [x.capitalize() for x in e.code().name.lower().split("_")]
    title = " ".join(title)
    title = f"GRPC {title}"
    dialog = ErrorDialog(master, app, title, e.details())
    dialog.show()
