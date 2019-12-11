"""
check engine light
"""
from tkinter import ttk

from coretk.dialogs.dialog import Dialog


class CheckLight(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "CEL", modal=True)
        self.app = app

        self.columnconfigure(0, weight=1)
        self.draw()

    def draw(self):
        row = 0
        frame = ttk.Frame(self)
        button = ttk.Button(frame, text="Reset CEL")
        button.grid(row=0, column=0)
        button = ttk.Button(frame, text="View core-daemon log")
        button.grid(row=0, column=1)
        button = ttk.Button(frame, text="View node log")
        button.grid(row=0, column=2)
        button = ttk.Button(frame, text="Close", command=self.destroy)
        button.grid(row=0, column=3)
        frame.grid(row=row, column=0, sticky="nsew")
        ++row
