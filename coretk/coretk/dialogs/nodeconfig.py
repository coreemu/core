import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog
from coretk.dialogs.icondialog import IconDialog
from coretk.dialogs.nodeservice import NodeService

DEFAULT_NODES = {"router", "host", "PC", "mdr", "prouter"}
PAD = 5


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
        self.type = tk.StringVar(value=canvas_node.core_node.model)
        self.server = tk.StringVar()
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        row = 0

        # field frame
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        frame.columnconfigure(1, weight=1)

        # name field
        label = ttk.Label(frame, text="Name")
        label.grid(row=row, column=0, sticky="ew", padx=PAD, pady=PAD)
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=row, column=1, sticky="ew")
        row += 1

        # icon field
        label = ttk.Label(frame, text="Icon")
        label.grid(row=row, column=0, sticky="ew", padx=PAD, pady=PAD)
        self.image_button = ttk.Button(
            frame,
            text="Icon",
            image=self.image,
            compound=tk.NONE,
            command=self.click_icon,
        )
        self.image_button.grid(row=row, column=1, sticky="ew")
        row += 1

        # node type field
        label = ttk.Label(frame, text="Type")
        label.grid(row=row, column=0, sticky="ew", padx=PAD, pady=PAD)
        combobox = ttk.Combobox(
            frame, textvariable=self.type, values=list(DEFAULT_NODES), state="readonly"
        )
        combobox.grid(row=row, column=1, sticky="ew")
        row += 1

        # server
        frame.grid(sticky="ew")
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Server")
        label.grid(row=row, column=0, sticky="ew", padx=PAD, pady=PAD)
        servers = ["localhost"]
        servers.extend(list(sorted(self.app.core.servers.keys())))
        combobox = ttk.Combobox(
            frame, textvariable=self.server, values=servers, state="readonly"
        )
        combobox.grid(row=row, column=1, sticky="ew")
        row += 1

        # services
        button = ttk.Button(self.top, text="Services", command=self.click_services)
        button.grid(sticky="ew", pady=PAD)

        self.draw_buttons()

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
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
