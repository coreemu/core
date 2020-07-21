import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from core.gui.dialogs.dialog import Dialog
from core.gui.dialogs.simple import SimpleStringDialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class LayersDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Canvas Layers", modal=False)
        self.list: Optional[ListboxScroll] = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.list = ListboxScroll(self.top)
        self.list.grid(sticky=tk.EW, pady=PADY)
        for name in self.app.canvas.layers.names():
            self.list.listbox.insert(tk.END, name)
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Add", command=self.click_add)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Delete", command=self.click_delete)
        button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Toggle", command=self.click_toggle)
        button.grid(row=0, column=2, sticky=tk.EW)

    def click_add(self):
        name = SimpleStringDialog(self, self.app, "Add Layer", "Layer Name").ask()
        if name:
            result = self.app.canvas.layers.add_layer(name)
            if result:
                self.list.listbox.insert(tk.END, name)
            else:
                messagebox.showerror(
                    "Add Layer", f"Duplicate Layer: {name}", parent=self
                )

    def click_delete(self):
        selection = self.list.listbox.curselection()
        if not selection:
            return
        name = self.list.listbox.get(selection)
        print(name)

    def click_toggle(self):
        selection = self.list.listbox.curselection()
        if not selection:
            return
        name = self.list.listbox.get(selection)
        print(name)
