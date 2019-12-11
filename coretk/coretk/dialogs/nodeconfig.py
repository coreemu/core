import logging
import tkinter as tk
from functools import partial
from tkinter import ttk

from coretk.dialogs.dialog import Dialog
from coretk.dialogs.icondialog import IconDialog
from coretk.dialogs.nodeservice import NodeService
from coretk.nodeutils import NodeUtils
from coretk.widgets import FrameScroll

PAD = 5


def mac_auto(is_auto, entry):
    logging.info("mac auto clicked")
    if is_auto.get():
        logging.info("disabling mac")
        entry.var.set("")
        entry.config(state=tk.DISABLED)
    else:
        entry.var.set("00:00:00:00:00:00")
        entry.config(state=tk.NORMAL)


class InterfaceData:
    def __init__(self, is_auto, mac, ip4, ip6):
        self.is_auto = is_auto
        self.mac = mac
        self.ip4 = ip4
        self.ip6 = ip6


class NodeConfigDialog(Dialog):
    def __init__(self, master, app, canvas_node):
        """
        create an instance of node configuration

        :param master: dialog master
        :param coretk.app.Application: main app
        :param coretk.graph.CanvasNode canvas_node: canvas node object
        """
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Configuration", modal=True
        )
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.image = canvas_node.image
        self.image_button = None
        self.name = tk.StringVar(value=self.node.name)
        self.type = tk.StringVar(value=self.node.model)
        self.container_image = tk.StringVar(value=self.node.image)
        server = "localhost"
        if self.node.server:
            server = self.node.server
        self.server = tk.StringVar(value=server)
        self.interfaces = {}
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        row = 0

        # field frame
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        frame.columnconfigure(1, weight=1)

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

        # name field
        label = ttk.Label(frame, text="Name")
        label.grid(row=row, column=0, sticky="ew", padx=PAD, pady=PAD)
        entry = ttk.Entry(
            frame,
            textvariable=self.name,
            validate="key",
            validatecommand=(self.app.validation.name, "%P"),
        )
        entry.bind(
            "<FocusOut>", lambda event: self.app.validation.focus_out(event, "noname")
        )
        entry.grid(row=row, column=1, sticky="ew")
        row += 1

        # node type field
        if NodeUtils.is_model_node(self.node.type):
            label = ttk.Label(frame, text="Type")
            label.grid(row=row, column=0, sticky="ew", padx=PAD, pady=PAD)
            combobox = ttk.Combobox(
                frame,
                textvariable=self.type,
                values=list(NodeUtils.NODE_MODELS),
                state="readonly",
            )
            combobox.grid(row=row, column=1, sticky="ew")
            row += 1

        # container image field
        if NodeUtils.is_image_node(self.node.type):
            label = ttk.Label(frame, text="Image")
            label.grid(row=row, column=0, sticky="ew", padx=PAD, pady=PAD)
            entry = ttk.Entry(frame, textvariable=self.container_image)
            entry.grid(row=row, column=1, sticky="ew")
            row += 1

        if NodeUtils.is_container_node(self.node.type):
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

        # interfaces
        if self.canvas_node.interfaces:
            self.draw_interfaces()

        self.draw_spacer()
        self.draw_buttons()

    def draw_interfaces(self):
        scroll = FrameScroll(self.top, self.app, text="Interfaces")
        scroll.grid(sticky="nsew")
        scroll.frame.columnconfigure(0, weight=1)
        scroll.frame.rowconfigure(0, weight=1)
        for interface in self.canvas_node.interfaces:
            logging.info("interface: %s", interface)
            frame = ttk.LabelFrame(scroll.frame, text=interface.name, padding=PAD)
            frame.grid(sticky="ew", pady=PAD)
            frame.columnconfigure(1, weight=1)
            frame.columnconfigure(2, weight=1)

            label = ttk.Label(frame, text="MAC")
            label.grid(row=0, column=0, padx=PAD, pady=PAD)
            is_auto = tk.BooleanVar(value=True)
            checkbutton = ttk.Checkbutton(frame, text="Auto?", variable=is_auto)
            checkbutton.var = is_auto
            checkbutton.grid(row=0, column=1, padx=PAD)
            mac = tk.StringVar(value=interface.mac)
            entry = ttk.Entry(frame, textvariable=mac, state=tk.DISABLED)
            entry.grid(row=0, column=2, sticky="ew")
            func = partial(mac_auto, is_auto, entry)
            checkbutton.config(command=func)

            label = ttk.Label(frame, text="IPv4")
            label.grid(row=1, column=0, padx=PAD, pady=PAD)
            ip4 = tk.StringVar(value=f"{interface.ip4}/{interface.ip4mask}")
            entry = ttk.Entry(frame, textvariable=ip4)
            entry.bind("<FocusOut>", self.app.validation.ip_focus_out)
            entry.grid(row=1, column=1, columnspan=2, sticky="ew")

            label = ttk.Label(frame, text="IPv6")
            label.grid(row=2, column=0, padx=PAD, pady=PAD)
            ip6 = tk.StringVar(value=f"{interface.ip6}/{interface.ip6mask}")
            entry = ttk.Entry(frame, textvariable=ip6)
            entry.bind("<FocusOut>", self.app.validation.ip_focus_out)
            entry.grid(row=2, column=1, columnspan=2, sticky="ew")

            self.interfaces[interface.id] = InterfaceData(is_auto, mac, ip4, ip6)

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
        dialog = IconDialog(self, self.app, self.node.name, self.canvas_node.image)
        dialog.show()
        if dialog.image:
            self.image = dialog.image
            self.image_button.config(image=self.image)

    def config_apply(self):
        # update core node
        self.node.name = self.name.get()
        if NodeUtils.is_image_node(self.node.type):
            self.node.image = self.container_image.get()
        server = self.server.get()
        if NodeUtils.is_container_node(self.node.type) and server != "localhost":
            self.node.server = server

        # update canvas node
        self.canvas_node.image = self.image

        # redraw
        self.canvas_node.redraw()
        self.destroy()
