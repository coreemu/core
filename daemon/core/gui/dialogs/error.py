import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum, Images
from core.gui.themes import PADY
from core.gui.widgets import CodeText

if TYPE_CHECKING:
    from core.gui.app import Application


class ErrorDialog(Dialog):
    def __init__(self, app: "Application", title: str, details: str) -> None:
        super().__init__(app, "CORE Exception")
        self.title: str = title
        self.details: str = details
        self.error_message: Optional[CodeText] = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)
        image = Images.get(ImageEnum.ERROR, 24)
        label = ttk.Label(
            self.top, text=self.title, image=image, compound=tk.LEFT, anchor=tk.CENTER
        )
        label.image = image
        label.grid(sticky=tk.EW, pady=PADY)
        self.error_message = CodeText(self.top)
        self.error_message.text.insert("1.0", self.details)
        self.error_message.text.config(state=tk.DISABLED)
        self.error_message.grid(sticky=tk.NSEW, pady=PADY)
        button = ttk.Button(self.top, text="Close", command=lambda: self.destroy())
        button.grid(sticky=tk.EW)
