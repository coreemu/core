import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from core.gui.appconfig import Observer
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class ObserverDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Observer Widgets")
        self.observers: Optional[tk.Listbox] = None
        self.save_button: Optional[ttk.Button] = None
        self.delete_button: Optional[ttk.Button] = None
        self.selected: Optional[str] = None
        self.selected_index: Optional[int] = None
        self.name: tk.StringVar = tk.StringVar()
        self.cmd: tk.StringVar = tk.StringVar()
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.draw_listbox()
        self.draw_form_fields()
        self.draw_config_buttons()
        self.draw_apply_buttons()

    def draw_listbox(self) -> None:
        listbox_scroll = ListboxScroll(self.top)
        listbox_scroll.grid(sticky=tk.NSEW, pady=PADY)
        listbox_scroll.columnconfigure(0, weight=1)
        listbox_scroll.rowconfigure(0, weight=1)
        self.observers = listbox_scroll.listbox
        self.observers.grid(row=0, column=0, sticky=tk.NSEW)
        self.observers.bind("<<ListboxSelect>>", self.handle_observer_change)
        for name in sorted(self.app.core.custom_observers):
            self.observers.insert(tk.END, name)

    def draw_form_fields(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Name")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=1, sticky=tk.EW)

        label = ttk.Label(frame, text="Command")
        label.grid(row=1, column=0, sticky=tk.W, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.cmd)
        entry.grid(row=1, column=1, sticky=tk.EW)

    def draw_config_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW, pady=PADY)
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)

        self.save_button = ttk.Button(
            frame, text="Save", state=tk.DISABLED, command=self.click_save
        )
        self.save_button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)

        self.delete_button = ttk.Button(
            frame, text="Delete", state=tk.DISABLED, command=self.click_delete
        )
        self.delete_button.grid(row=0, column=2, sticky=tk.EW)

    def draw_apply_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Save", command=self.click_save_config)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_save_config(self) -> None:
        self.app.guiconfig.observers.clear()
        for observer in self.app.core.custom_observers.values():
            self.app.guiconfig.observers.append(observer)
        self.app.save_config()
        self.destroy()

    def click_create(self) -> None:
        name = self.name.get()
        if name not in self.app.core.custom_observers:
            cmd = self.cmd.get()
            observer = Observer(name, cmd)
            self.app.core.custom_observers[name] = observer
            self.observers.insert(tk.END, name)
            self.name.set("")
            self.cmd.set("")
            self.app.menubar.observers_menu.draw_custom()
            self.app.toolbar.observers_menu.draw_custom()
        else:
            messagebox.showerror("Observer Error", f"{name} already exists")

    def click_save(self) -> None:
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

    def click_delete(self) -> None:
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
            self.app.menubar.observers_menu.draw_custom()
            self.app.toolbar.observers_menu.draw_custom()

    def handle_observer_change(self, event: tk.Event) -> None:
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
