from tkinter import ttk
from typing import TYPE_CHECKING

import grpc

from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum, Images
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CodeText

if TYPE_CHECKING:
    from core.gui.app import Application


class ErrorDialog(Dialog):
    def __init__(self, master, app: "Application", title: str, details: str) -> None:
        super().__init__(master, app, "CORE Exception")
        self.title = title
        self.details = details
        self.error_message = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)

        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.grid(pady=PADY, sticky="ew")
        frame.columnconfigure(1, weight=1)
        image = Images.get(ImageEnum.ERROR, 36)
        label = ttk.Label(frame, image=image)
        label.image = image
        label.grid(row=0, column=0, padx=PADX)
        label = ttk.Label(frame, text=self.title)
        label.grid(row=0, column=1, sticky="ew")

        self.error_message = CodeText(self.top)
        self.error_message.text.insert("1.0", self.details)
        self.error_message.text.config(state="disabled")
        self.error_message.grid(sticky="nsew", pady=PADY)

        button = ttk.Button(self.top, text="Close", command=lambda: self.destroy())
        button.grid(sticky="ew")


def show_grpc_error(e: grpc.RpcError, master, app: "Application"):
    title = [x.capitalize() for x in e.code().name.lower().split("_")]
    title = " ".join(title)
    title = f"GRPC {title}"
    dialog = ErrorDialog(master, app, title, e.details())
    dialog.show()


def show_grpc_response_exceptions(class_name, exceptions, master, app: "Application"):
    title = f"Exceptions from {class_name}"
    detail = "\n".join([str(x) for x in exceptions])
    dialog = ErrorDialog(master, app, title, detail)
    dialog.show()
