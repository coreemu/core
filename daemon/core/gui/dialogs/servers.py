import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.gui.appconfig import CoreServer
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application

DEFAULT_NAME: str = "example"
DEFAULT_ADDRESS: str = "127.0.0.1"
DEFAULT_PORT: int = 50051


class ServersDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "CORE Servers")
        self.name: tk.StringVar = tk.StringVar(value=DEFAULT_NAME)
        self.address: tk.StringVar = tk.StringVar(value=DEFAULT_ADDRESS)
        self.servers: Optional[tk.Listbox] = None
        self.selected_index: Optional[int] = None
        self.selected: Optional[str] = None
        self.save_button: Optional[ttk.Button] = None
        self.delete_button: Optional[ttk.Button] = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.draw_servers()
        self.draw_servers_buttons()
        self.draw_server_configuration()
        self.draw_apply_buttons()

    def draw_servers(self) -> None:
        listbox_scroll = ListboxScroll(self.top)
        listbox_scroll.grid(pady=PADY, sticky=tk.NSEW)
        listbox_scroll.columnconfigure(0, weight=1)
        listbox_scroll.rowconfigure(0, weight=1)

        self.servers = listbox_scroll.listbox
        self.servers.grid(row=0, column=0, sticky=tk.NSEW)
        self.servers.bind("<<ListboxSelect>>", self.handle_server_change)

        for server in self.app.core.servers:
            self.servers.insert(tk.END, server)

    def draw_server_configuration(self) -> None:
        frame = ttk.LabelFrame(self.top, text="Server Configuration", padding=FRAME_PAD)
        frame.grid(pady=PADY, sticky=tk.EW)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        label = ttk.Label(frame, text="Name")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=1, sticky=tk.EW)

        label = ttk.Label(frame, text="Address")
        label.grid(row=0, column=2, sticky=tk.W, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.address)
        entry.grid(row=0, column=3, sticky=tk.EW)

    def draw_servers_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(pady=PADY, sticky=tk.EW)
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

        button = ttk.Button(
            frame, text="Save Configuration", command=self.click_save_configuration
        )
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_save_configuration(self):
        self.app.guiconfig.servers.clear()
        for server in self.app.core.servers.values():
            self.app.guiconfig.servers.append(server)
        self.app.save_config()
        self.destroy()

    def click_create(self) -> None:
        name = self.name.get()
        if name not in self.app.core.servers:
            address = self.address.get()
            server = CoreServer(name, address)
            self.app.core.servers[name] = server
            self.servers.insert(tk.END, name)

    def click_save(self) -> None:
        name = self.name.get()
        if self.selected:
            previous_name = self.selected
            self.selected = name
            server = self.app.core.servers.pop(previous_name)
            server.name = name
            server.address = self.address.get()
            self.app.core.servers[name] = server
            self.servers.delete(self.selected_index)
            self.servers.insert(self.selected_index, name)
            self.servers.selection_set(self.selected_index)

    def click_delete(self) -> None:
        if self.selected:
            self.servers.delete(self.selected_index)
            del self.app.core.servers[self.selected]
            self.selected = None
            self.selected_index = None
            self.name.set(DEFAULT_NAME)
            self.address.set(DEFAULT_ADDRESS)
            self.servers.selection_clear(0, tk.END)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)

    def handle_server_change(self, event: tk.Event) -> None:
        selection = self.servers.curselection()
        if selection:
            self.selected_index = selection[0]
            self.selected = self.servers.get(self.selected_index)
            server = self.app.core.servers[self.selected]
            self.name.set(server.name)
            self.address.set(server.address)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected_index = None
            self.selected = None
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
