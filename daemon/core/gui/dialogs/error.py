import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.gui import images
from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum
from core.gui.themes import PADY
from core.gui.widgets import CodeText

if TYPE_CHECKING:
    from core.gui.app import Application


class ErrorDialog(Dialog):
    def __init__(
        self, app: "Application", title: str, message: str, details: str
    ) -> None:
        super().__init__(app, title)
        self.message: str = message
        self.details: str = details
        self.error_message: Optional[CodeText] = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)
        image = images.from_enum(ImageEnum.ERROR, width=images.ERROR_SIZE)
        label = ttk.Label(
            self.top, text=self.message, image=image, compound=tk.LEFT, anchor=tk.CENTER
        )
        label.image = image
        label.grid(sticky=tk.W, pady=PADY)
        self.error_message = CodeText(self.top)
        self.error_message.text.insert("1.0", self.details)
        self.error_message.text.config(state=tk.DISABLED)
        self.error_message.grid(sticky=tk.EW, pady=PADY)
        button = ttk.Button(self.top, text="Close", command=lambda: self.destroy())
        button.grid(sticky=tk.EW)
