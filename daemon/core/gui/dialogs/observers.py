import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.coreclient import Observer
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class ObserverDialog(Dialog):
    def __init__(self, master: "Application", app: "Application"):
        super().__init__(master, app, "Observer Widgets", modal=True)
        self.observers = None
        self.save_button = None
        self.delete_button = None
        self.selected = None
        self.selected_index = None
        self.name = tk.StringVar()
        self.cmd = tk.StringVar()
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.draw_listbox()
        self.draw_form_fields()
        self.draw_config_buttons()
        self.draw_apply_buttons()

    def draw_listbox(self):
        listbox_scroll = ListboxScroll(self.top)
        listbox_scroll.grid(sticky="nsew", pady=PADY)
        listbox_scroll.columnconfigure(0, weight=1)
        listbox_scroll.rowconfigure(0, weight=1)
        self.observers = listbox_scroll.listbox
        self.observers.grid(row=0, column=0, sticky="nsew")
        self.observers.bind("<<ListboxSelect>>", self.handle_observer_change)
        for name in sorted(self.app.core.custom_observers):
            self.observers.insert(tk.END, name)

    def draw_form_fields(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Name")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=1, sticky="ew")

        label = ttk.Label(frame, text="Command")
        label.grid(row=1, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.cmd)
        entry.grid(row=1, column=1, sticky="ew")

    def draw_config_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PADY)
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        self.save_button = ttk.Button(
            frame, text="Save", state=tk.DISABLED, command=self.click_save
        )
        self.save_button.grid(row=0, column=1, sticky="ew", padx=PADX)

        self.delete_button = ttk.Button(
            frame, text="Delete", state=tk.DISABLED, command=self.click_delete
        )
        self.delete_button.grid(row=0, column=2, sticky="ew")

    def draw_apply_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Save", command=self.click_save_config)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_save_config(self):
        observers = []
        for name in sorted(self.app.core.custom_observers):
            observer = self.app.core.custom_observers[name]
            observers.append({"name": observer.name, "cmd": observer.cmd})
        self.app.guiconfig["observers"] = observers
        self.app.save_config()
        self.destroy()

    def click_create(self):
        name = self.name.get()
        if name not in self.app.core.custom_observers:
            cmd = self.cmd.get()
            observer = Observer(name, cmd)
            self.app.core.custom_observers[name] = observer
            self.observers.insert(tk.END, name)

    def click_save(self):
        name = self.name.get()
        if self.selected:
            previous_name = self.selected
            self.selected = name
            observer = self.app.core.custom_observers.pop(previous_name)
            observer.name = name
            observer.cmd = self.cmd.get()
            self.app.core.custom_observers[name] = observer
            self.observers.delete(self.selected_index)
            self.observers.insert(self.selected_index, name)
            self.observers.selection_set(self.selected_index)

    def click_delete(self):
        if self.selected:
            self.observers.delete(self.selected_index)
            del self.app.core.custom_observers[self.selected]
            self.selected = None
            self.selected_index = None
            self.name.set("")
            self.cmd.set("")
            self.observers.selection_clear(0, tk.END)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)

    def handle_observer_change(self, event: tk.Event):
        selection = self.observers.curselection()
        if selection:
            self.selected_index = selection[0]
            self.selected = self.observers.get(self.selected_index)
            observer = self.app.core.custom_observers[self.selected]
            self.name.set(observer.name)
            self.cmd.set(observer.cmd)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected_index = None
            self.selected = None
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
