from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application


class MacConfigDialog(Dialog):
    def __init__(self, master: "Application", app: "Application") -> None:
        super().__init__(master, app, "MAC Configuration", modal=True)
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        # draw explanation label
        text = (
            "MAC addresses will be generated for nodes starting with the\n"
            "provided value below and increment by value in order."
        )
        label = ttk.Label(self.top, text=text)
        label.grid(sticky="ew", pady=PADY)

        # draw input
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=3)
        frame.grid(stick="ew", pady=PADY)
        label = ttk.Label(frame, text="Starting MAC")
        label.grid(row=0, column=0, sticky="ew", padx=PADX)
        entry = ttk.Entry(frame)
        entry.grid(row=0, column=1, sticky="ew")

        # draw buttons
        frame = ttk.Frame(self.top)
        frame.grid(stick="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_save(self) -> None:
        pass
