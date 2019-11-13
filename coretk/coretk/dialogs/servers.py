import tkinter as tk
from tkinter import ttk

from coretk.coreclient import CoreServer
from coretk.dialogs.dialog import Dialog

DEFAULT_NAME = "example"
DEFAULT_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 50051


class ServersDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "CORE Servers", modal=True)
        self.name = tk.StringVar(value=DEFAULT_NAME)
        self.address = tk.StringVar(value=DEFAULT_ADDRESS)
        self.port = tk.IntVar(value=DEFAULT_PORT)
        self.servers = None
        self.selected_index = None
        self.selected = None
        self.save_button = None
        self.delete_button = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.draw_servers()
        self.draw_server_configuration()
        self.draw_servers_buttons()
        self.draw_apply_buttons()

    def draw_servers(self):
        frame = ttk.Frame(self.top)
        frame.grid(pady=2, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.servers = tk.Listbox(
            frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set
        )
        self.servers.grid(row=0, column=0, sticky="nsew")
        self.servers.bind("<<ListboxSelect>>", self.handle_server_change)

        for server in self.app.core.servers:
            self.servers.insert(tk.END, server)

        scrollbar.config(command=self.servers.yview)

    def draw_server_configuration(self):
        label = ttk.Label(self.top, text="Server Configuration")
        label.grid(pady=2, sticky="ew")

        frame = ttk.Frame(self.top)
        frame.grid(pady=2, sticky="ew")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(5, weight=1)

        label = ttk.Label(frame, text="Name")
        label.grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=1, sticky="ew")

        label = ttk.Label(frame, text="Address")
        label.grid(row=0, column=2, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.address)
        entry.grid(row=0, column=3, sticky="ew")

        label = ttk.Label(frame, text="Port")
        label.grid(row=0, column=4, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.port)
        entry.grid(row=0, column=5, sticky="ew")

    def draw_servers_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(pady=2, sticky="ew")
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky="ew")

        self.save_button = ttk.Button(
            frame, text="Save", state=tk.DISABLED, command=self.click_save
        )
        self.save_button.grid(row=0, column=1, sticky="ew")

        self.delete_button = ttk.Button(
            frame, text="Delete", state=tk.DISABLED, command=self.click_delete
        )
        self.delete_button.grid(row=0, column=2, sticky="ew")

    def draw_apply_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(
            frame, text="Save Configuration", command=self.click_save_configuration
        )
        button.grid(row=0, column=0, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_save_configuration(self):
        servers = []
        for name in sorted(self.app.core.servers):
            server = self.app.core.servers[name]
            servers.append(
                {"name": server.name, "address": server.address, "port": server.port}
            )
        self.app.config["servers"] = servers
        self.app.save_config()
        self.destroy()

    def click_create(self):
        name = self.name.get()
        if name not in self.app.core.servers:
            address = self.address.get()
            port = self.port.get()
            server = CoreServer(name, address, port)
            self.app.core.servers[name] = server
            self.servers.insert(tk.END, name)

    def click_save(self):
        name = self.name.get()
        if self.selected:
            previous_name = self.selected
            self.selected = name
            server = self.app.core.servers.pop(previous_name)
            server.name = name
            server.address = self.address.get()
            server.port = self.port.get()
            self.app.core.servers[name] = server
            self.servers.delete(self.selected_index)
            self.servers.insert(self.selected_index, name)
            self.servers.selection_set(self.selected_index)

    def click_delete(self):
        if self.selected:
            self.servers.delete(self.selected_index)
            del self.app.core.servers[self.selected]
            self.selected = None
            self.selected_index = None
            self.name.set(DEFAULT_NAME)
            self.address.set(DEFAULT_ADDRESS)
            self.port.set(DEFAULT_PORT)
            self.servers.selection_clear(0, tk.END)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)

    def handle_server_change(self, event):
        selection = self.servers.curselection()
        if selection:
            self.selected_index = selection[0]
            self.selected = self.servers.get(self.selected_index)
            server = self.app.core.servers[self.selected]
            self.name.set(server.name)
            self.address.set(server.address)
            self.port.set(server.port)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected_index = None
            self.selected = None
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
