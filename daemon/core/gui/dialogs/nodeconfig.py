import logging
import tkinter as tk
from functools import partial
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui import nodeutils
from core.gui.appconfig import ICONS_PATH
from core.gui.dialogs.dialog import Dialog
from core.gui.dialogs.emaneconfig import EmaneModelDialog
from core.gui.images import Images
from core.gui.nodeutils import NodeUtils
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import ListboxScroll, image_chooser

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode


def mac_auto(is_auto: tk.BooleanVar, entry: ttk.Entry):
    logging.info("mac auto clicked")
    if is_auto.get():
        logging.info("disabling mac")
        entry.delete(0, tk.END)
        entry.insert(tk.END, "")
        entry.config(state=tk.DISABLED)
    else:
        entry.delete(0, tk.END)
        entry.insert(tk.END, "00:00:00:00:00:00")
        entry.config(state=tk.NORMAL)


class InterfaceData:
    def __init__(
        self,
        is_auto: tk.BooleanVar,
        mac: tk.StringVar,
        ip4: tk.StringVar,
        ip6: tk.StringVar,
    ):
        self.is_auto = is_auto
        self.mac = mac
        self.ip4 = ip4
        self.ip6 = ip6


class NodeConfigDialog(Dialog):
    def __init__(
        self, master: "Application", app: "Application", canvas_node: "CanvasNode"
    ):
        """
        create an instance of node configuration
        """
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Configuration", modal=True
        )
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.image = canvas_node.image
        self.image_file = None
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
        label.grid(row=row, column=0, sticky="ew", padx=PADX, pady=PADY)
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
        label.grid(row=row, column=0, sticky="ew", padx=PADX, pady=PADY)
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
            label.grid(row=row, column=0, sticky="ew", padx=PADX, pady=PADY)
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
            label.grid(row=row, column=0, sticky="ew", padx=PADX, pady=PADY)
            entry = ttk.Entry(frame, textvariable=self.container_image)
            entry.grid(row=row, column=1, sticky="ew")
            row += 1

        if NodeUtils.is_container_node(self.node.type):
            # server
            frame.grid(sticky="ew")
            frame.columnconfigure(1, weight=1)
            label = ttk.Label(frame, text="Server")
            label.grid(row=row, column=0, sticky="ew", padx=PADX, pady=PADY)
            servers = ["localhost"]
            servers.extend(list(sorted(self.app.core.servers.keys())))
            combobox = ttk.Combobox(
                frame, textvariable=self.server, values=servers, state="readonly"
            )
            combobox.grid(row=row, column=1, sticky="ew")
            row += 1

        if NodeUtils.is_rj45_node(self.node.type):
            response = self.app.core.client.get_interfaces()
            logging.debug("host machine available interfaces: %s", response)
            interfaces = ListboxScroll(frame)
            interfaces.grid(
                row=row, column=0, columnspan=2, sticky="ew", padx=PADX, pady=PADY
            )
            for inf in sorted(response.interfaces[:]):
                interfaces.listbox.insert(tk.END, inf)
            row += 1
            interfaces.listbox.bind("<<ListboxSelect>>", self.interface_select)

        # interfaces
        if self.canvas_node.interfaces:
            self.draw_interfaces()

        self.draw_spacer()
        self.draw_buttons()

    def draw_interfaces(self):
        notebook = ttk.Notebook(self.top)
        notebook.grid(sticky="nsew", pady=PADY)
        self.top.rowconfigure(notebook.grid_info()["row"], weight=1)

        for interface in self.canvas_node.interfaces:
            logging.info("interface: %s", interface)
            tab = ttk.Frame(notebook, padding=FRAME_PAD)
            tab.grid(sticky="nsew", pady=PADY)
            tab.columnconfigure(1, weight=1)
            tab.columnconfigure(2, weight=1)
            notebook.add(tab, text=interface.name)

            row = 0
            emane_node = self.canvas_node.has_emane_link(interface.id)
            if emane_node:
                emane_model = emane_node.emane.split("_")[1]
                button = ttk.Button(
                    tab,
                    text=f"Configure EMANE {emane_model}",
                    command=lambda: self.click_emane_config(emane_model, interface.id),
                )
                button.grid(row=row, sticky="ew", columnspan=3, pady=PADY)
                row += 1

            label = ttk.Label(tab, text="MAC")
            label.grid(row=row, column=0, padx=PADX, pady=PADY)
            is_auto = tk.BooleanVar(value=True)
            checkbutton = ttk.Checkbutton(tab, text="Auto?", variable=is_auto)
            checkbutton.var = is_auto
            checkbutton.grid(row=row, column=1, padx=PADX)
            mac = tk.StringVar(value=interface.mac)
            entry = ttk.Entry(tab, textvariable=mac, state=tk.DISABLED)
            entry.grid(row=row, column=2, sticky="ew")
            func = partial(mac_auto, is_auto, entry)
            checkbutton.config(command=func)
            row += 1

            label = ttk.Label(tab, text="IPv4")
            label.grid(row=row, column=0, padx=PADX, pady=PADY)
            ip4 = tk.StringVar(value=f"{interface.ip4}/{interface.ip4mask}")
            entry = ttk.Entry(tab, textvariable=ip4)
            entry.bind("<FocusOut>", self.app.validation.ip_focus_out)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew")
            row += 1

            label = ttk.Label(tab, text="IPv6")
            label.grid(row=row, column=0, padx=PADX, pady=PADY)
            ip6 = tk.StringVar(value=f"{interface.ip6}/{interface.ip6mask}")
            entry = ttk.Entry(tab, textvariable=ip6)
            entry.bind("<FocusOut>", self.app.validation.ip_focus_out)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew")

            self.interfaces[interface.id] = InterfaceData(is_auto, mac, ip4, ip6)

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.config_apply)
        button.grid(row=0, column=0, padx=PADX, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_emane_config(self, emane_model: str, interface_id: int):
        dialog = EmaneModelDialog(self, self.app, self.node, emane_model, interface_id)
        dialog.show()

    def click_icon(self):
        file_path = image_chooser(self, ICONS_PATH)
        if file_path:
            self.image = Images.create(file_path, nodeutils.ICON_SIZE)
            self.image_button.config(image=self.image)
            self.image_file = file_path

    def config_apply(self):
        # update core node
        self.node.name = self.name.get()
        if NodeUtils.is_image_node(self.node.type):
            self.node.image = self.container_image.get()
        server = self.server.get()
        if NodeUtils.is_container_node(self.node.type) and server != "localhost":
            self.node.server = server

        # set custom icon
        if self.image_file:
            self.node.icon = self.image_file

        # update canvas node
        self.canvas_node.image = self.image

        # redraw
        self.canvas_node.redraw()
        self.destroy()

    def interface_select(self, event: tk.Event):
        listbox = event.widget
        cur = listbox.curselection()
        if cur:
            interface = listbox.get(cur[0])
            self.name.set(interface)
