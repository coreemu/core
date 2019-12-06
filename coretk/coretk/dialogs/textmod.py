"""
text dialog
"""
import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog


class TextDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Add a new text", modal=True)
        self.canvas = app.canvas
        self.text = tk.StringVar(value="")

        self.draw()

    def draw(self):
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        label = ttk.Label(frame, text="Text for top of text: ")
        label.grid(row=0, column=0)
        entry = ttk.Entry(frame, textvariable=self.text)
        entry.grid(row=0, column=1)
        frame.grid(row=0, column=0, sticky="nsew")
