import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from core.gui.appconfig import NodeCommand
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class NodeCommandsDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Node Commands")
        self.commands: tk.Listbox | None = None
        self.save_button: ttk.Button | None = None
        self.delete_button: ttk.Button | None = None
        self.selected: str | None = None
        self.selected_index: int | None = None
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
        self.commands = listbox_scroll.listbox
        self.commands.grid(row=0, column=0, sticky=tk.NSEW)
        self.commands.bind("<<ListboxSelect>>", self.handle_change)
        for name in sorted(self.app.core.node_commands):
            self.commands.insert(tk.END, name)

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
        self.app.guiconfig.node_commands.clear()
        for name, cmd in self.app.core.node_commands.items():
            self.app.guiconfig.node_commands.append(NodeCommand(name, cmd))
        self.app.save_config()
        self.destroy()

    def click_create(self) -> None:
        name = self.name.get()
        if name not in self.app.core.node_commands:
            cmd = self.cmd.get()
            self.app.core.node_commands[name] = cmd
            self.commands.insert(tk.END, name)
            self.name.set("")
            self.cmd.set("")
        else:
            messagebox.showerror("Node Command Error", f"{name} already exists")

    def click_save(self) -> None:
        name = self.name.get()
        cmd = self.cmd.get()
        if self.selected:
            previous_name = self.selected
            self.selected = name
            self.app.core.node_commands.pop(previous_name)
            self.app.core.node_commands[name] = cmd
            self.commands.delete(self.selected_index)
            self.commands.insert(self.selected_index, name)
            self.commands.selection_set(self.selected_index)

    def click_delete(self) -> None:
        if self.selected:
            self.commands.delete(self.selected_index)
            del self.app.core.node_commands[self.selected]
            self.selected = None
            self.selected_index = None
            self.name.set("")
            self.cmd.set("")
            self.commands.selection_clear(0, tk.END)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)

    def handle_change(self, _event: tk.Event) -> None:
        selection = self.commands.curselection()
        if selection:
            self.selected_index = selection[0]
            self.selected = self.commands.get(self.selected_index)
            cmd = self.app.core.node_commands[self.selected]
            self.name.set(self.selected)
            self.cmd.set(cmd)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected_index = None
            self.selected = None
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
