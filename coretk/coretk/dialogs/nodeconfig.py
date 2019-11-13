import tkinter as tk
from tkinter import ttk

from coretk.coreclient import DEFAULT_NODES
from coretk.dialogs.dialog import Dialog
from coretk.dialogs.icondialog import IconDialog
from coretk.dialogs.nodeservice import NodeService


class NodeConfigDialog(Dialog):
    def __init__(self, master, app, canvas_node):
        """
        create an instance of node configuration

        :param master: dialog master
        :param coretk.app.Application: main app
        :param coretk.graph.CanvasNode canvas_node: canvas node object
        """
        super().__init__(master, app, f"{canvas_node.name} Configuration", modal=True)
        self.canvas_node = canvas_node
        self.image = canvas_node.image
        self.image_button = None
        self.name = tk.StringVar(value=canvas_node.name)
        self.type = tk.StringVar(value=canvas_node.node_type)
        self.server = tk.StringVar()
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.draw_first_row()
        self.draw_second_row()
        self.draw_third_row()

    def draw_first_row(self):
        frame = ttk.Frame(self)
        frame.grid(row=0, column=0, pady=2, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)

        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=0, padx=2, sticky="ew")

        combobox = ttk.Combobox(
            frame, textvariable=self.type, values=DEFAULT_NODES, state="readonly"
        )
        combobox.grid(row=0, column=1, padx=2, sticky="ew")

        servers = [""]
        servers.extend(list(sorted(self.app.core.servers.keys())))
        combobox = ttk.Combobox(
            frame, textvariable=self.server, values=servers, state="readonly"
        )
        combobox.current(0)
        combobox.grid(row=0, column=2, sticky="ew")

    def draw_second_row(self):
        frame = ttk.Frame(self)
        frame.grid(row=1, column=0, pady=2, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        button = ttk.Button(frame, text="Services", command=self.click_services)
        button.grid(row=0, column=0, padx=2, sticky="ew")

        self.image_button = ttk.Button(
            frame,
            text="Icon",
            image=self.image,
            compound=tk.LEFT,
            command=self.click_icon,
        )
        self.image_button.grid(row=0, column=1, sticky="ew")

    def draw_third_row(self):
        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.config_apply)
        button.grid(row=0, column=0, padx=2, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_services(self):
        dialog = NodeService(self, self.app, self.canvas_node)
        dialog.show()

    def click_icon(self):
        dialog = IconDialog(
            self, self.app, self.canvas_node.name, self.canvas_node.image
        )
        dialog.show()
        if dialog.image:
            self.image = dialog.image
            self.image_button.config(image=self.image)

    def config_apply(self):
        self.canvas_node.name = self.name.get()
        self.canvas_node.image = self.image
        self.canvas_node.canvas.itemconfig(self.canvas_node.id, image=self.image)
        self.destroy()
