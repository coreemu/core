import logging
import tkinter as tk
from functools import partial
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Dict, Optional

import netaddr
from PIL.ImageTk import PhotoImage

from core.api.grpc.wrappers import Interface, Node
from core.gui import images
from core.gui import nodeutils as nutils
from core.gui import validation
from core.gui.appconfig import ICONS_PATH
from core.gui.dialogs.dialog import Dialog
from core.gui.dialogs.emaneconfig import EmaneModelDialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import ListboxScroll, image_chooser

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode

IFACE_NAME_LEN: int = 15
DEFAULT_SERVER: str = "localhost"


def check_ip6(parent: tk.BaseWidget, name: str, value: str) -> bool:
    if not value:
        return True
    title = f"IP6 Error for {name}"
    values = value.split("/")
    if len(values) != 2:
        messagebox.showerror(
            title, "Must be in the format address/prefix", parent=parent
        )
        return False
    addr, mask = values
    if not netaddr.valid_ipv6(addr):
        messagebox.showerror(title, "Invalid IP6 address", parent=parent)
        return False
    try:
        mask = int(mask)
        if not (0 <= mask <= 128):
            messagebox.showerror(title, "Mask must be between 0-128", parent=parent)
            return False
    except ValueError:
        messagebox.showerror(title, "Invalid Mask", parent=parent)
        return False
    return True


def check_ip4(parent: tk.BaseWidget, name: str, value: str) -> bool:
    if not value:
        return True
    title = f"IP4 Error for {name}"
    values = value.split("/")
    if len(values) != 2:
        messagebox.showerror(
            title, "Must be in the format address/prefix", parent=parent
        )
        return False
    addr, mask = values
    if not netaddr.valid_ipv4(addr):
        messagebox.showerror(title, "Invalid IP4 address", parent=parent)
        return False
    try:
        mask = int(mask)
        if not (0 <= mask <= 32):
            messagebox.showerror(title, "Mask must be between 0-32", parent=parent)
            return False
    except ValueError:
        messagebox.showerror(title, "Invalid mask", parent=parent)
        return False
    return True


def mac_auto(is_auto: tk.BooleanVar, entry: ttk.Entry, mac: tk.StringVar) -> None:
    if is_auto.get():
        mac.set("")
        entry.config(state=tk.DISABLED)
    else:
        mac.set("00:00:00:00:00:00")
        entry.config(state=tk.NORMAL)


class InterfaceData:
    def __init__(
        self,
        name: tk.StringVar,
        is_auto: tk.BooleanVar,
        mac: tk.StringVar,
        ip4: tk.StringVar,
        ip6: tk.StringVar,
    ) -> None:
        self.name: tk.StringVar = name
        self.is_auto: tk.BooleanVar = is_auto
        self.mac: tk.StringVar = mac
        self.ip4: tk.StringVar = ip4
        self.ip6: tk.StringVar = ip6

    def validate(self, parent: tk.BaseWidget, iface: Interface) -> bool:
        valid_name = self._validate_name(parent, iface)
        valid_ip4 = self._validate_ip4(parent, iface)
        valid_ip6 = self._validate_ip6(parent, iface)
        valid_mac = self._validate_mac(parent, iface)
        return all([valid_name, valid_ip4, valid_ip6, valid_mac])

    def _validate_name(self, parent: tk.BaseWidget, iface: Interface) -> bool:
        name = self.name.get()
        title = f"Interface Name Error for {iface.name}"
        if not name:
            messagebox.showerror(title, "Name cannot be empty", parent=parent)
            return False
        if len(name) > IFACE_NAME_LEN:
            messagebox.showerror(
                title,
                f"Name cannot be greater than {IFACE_NAME_LEN} chars",
                parent=parent,
            )
            return False
        for x in name:
            if x.isspace() or x == "/":
                messagebox.showerror(
                    title, "Name cannot contain space or /", parent=parent
                )
                return False
        iface.name = name
        return True

    def _validate_ip4(self, parent: tk.BaseWidget, iface: Interface) -> bool:
        ip4_net = self.ip4.get()
        if not check_ip4(parent, iface.name, ip4_net):
            return False
        if ip4_net:
            ip4, ip4_mask = ip4_net.split("/")
            ip4_mask = int(ip4_mask)
        else:
            ip4, ip4_mask = "", 0
        iface.ip4 = ip4
        iface.ip4_mask = ip4_mask
        return True

    def _validate_ip6(self, parent: tk.BaseWidget, iface: Interface) -> bool:
        ip6_net = self.ip6.get()
        if not check_ip6(parent, iface.name, ip6_net):
            return False
        if ip6_net:
            ip6, ip6_mask = ip6_net.split("/")
            ip6_mask = int(ip6_mask)
        else:
            ip6, ip6_mask = "", 0
        iface.ip6 = ip6
        iface.ip6_mask = ip6_mask
        return True

    def _validate_mac(self, parent: tk.BaseWidget, iface: Interface) -> bool:
        mac = self.mac.get()
        auto_mac = self.is_auto.get()
        if auto_mac:
            iface.mac = None
        else:
            if not netaddr.valid_mac(mac):
                title = f"MAC Error for {iface.name}"
                messagebox.showerror(title, "Invalid MAC Address", parent=parent)
                return False
            else:
                mac = netaddr.EUI(mac, dialect=netaddr.mac_unix_expanded)
                iface.mac = str(mac)
        return True


class NodeConfigDialog(Dialog):
    def __init__(self, app: "Application", canvas_node: "CanvasNode") -> None:
        """
        create an instance of node configuration
        """
        super().__init__(app, f"{canvas_node.core_node.name} Configuration")
        self.canvas_node: "CanvasNode" = canvas_node
        self.node: Node = canvas_node.core_node
        self.image: PhotoImage = canvas_node.image
        self.image_file: Optional[str] = None
        self.image_button: Optional[ttk.Button] = None
        self.name: tk.StringVar = tk.StringVar(value=self.node.name)
        self.type: tk.StringVar = tk.StringVar(value=self.node.model)
        self.container_image: tk.StringVar = tk.StringVar(value=self.node.image)
        server = DEFAULT_SERVER
        if self.node.server:
            server = self.node.server
        self.server: tk.StringVar = tk.StringVar(value=server)
        self.ifaces: Dict[int, InterfaceData] = {}
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        row = 0

        # field states
        state = tk.DISABLED if self.app.core.is_runtime() else tk.NORMAL
        combo_state = tk.DISABLED if self.app.core.is_runtime() else "readonly"

        # field frame
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        frame.columnconfigure(1, weight=1)

        # icon field
        label = ttk.Label(frame, text="Icon")
        label.grid(row=row, column=0, sticky=tk.EW, padx=PADX, pady=PADY)
        self.image_button = ttk.Button(
            frame,
            text="Icon",
            image=self.image,
            compound=tk.NONE,
            command=self.click_icon,
        )
        self.image_button.grid(row=row, column=1, sticky=tk.EW)
        row += 1

        # name field
        label = ttk.Label(frame, text="Name")
        label.grid(row=row, column=0, sticky=tk.EW, padx=PADX, pady=PADY)
        entry = validation.NodeNameEntry(frame, textvariable=self.name, state=state)
        entry.grid(row=row, column=1, sticky=tk.EW)
        row += 1

        # node type field
        if nutils.is_model(self.node):
            label = ttk.Label(frame, text="Type")
            label.grid(row=row, column=0, sticky=tk.EW, padx=PADX, pady=PADY)
            combobox = ttk.Combobox(
                frame,
                textvariable=self.type,
                values=list(nutils.NODE_MODELS),
                state=combo_state,
            )
            combobox.grid(row=row, column=1, sticky=tk.EW)
            row += 1

        # container image field
        if nutils.has_image(self.node.type):
            label = ttk.Label(frame, text="Image")
            label.grid(row=row, column=0, sticky=tk.EW, padx=PADX, pady=PADY)
            entry = ttk.Entry(frame, textvariable=self.container_image, state=state)
            entry.grid(row=row, column=1, sticky=tk.EW)
            row += 1

        if nutils.is_container(self.node):
            # server
            frame.grid(sticky=tk.EW)
            frame.columnconfigure(1, weight=1)
            label = ttk.Label(frame, text="Server")
            label.grid(row=row, column=0, sticky=tk.EW, padx=PADX, pady=PADY)
            servers = [DEFAULT_SERVER]
            servers.extend(list(sorted(self.app.core.servers.keys())))
            combobox = ttk.Combobox(
                frame, textvariable=self.server, values=servers, state=combo_state
            )
            combobox.grid(row=row, column=1, sticky=tk.EW)
            row += 1

        if nutils.is_rj45(self.node):
            ifaces = self.app.core.client.get_ifaces()
            logger.debug("host machine available interfaces: %s", ifaces)
            ifaces_scroll = ListboxScroll(frame)
            ifaces_scroll.listbox.config(state=state)
            ifaces_scroll.grid(
                row=row, column=0, columnspan=2, sticky=tk.EW, padx=PADX, pady=PADY
            )
            for inf in sorted(ifaces):
                ifaces_scroll.listbox.insert(tk.END, inf)
            row += 1
            ifaces_scroll.listbox.bind("<<ListboxSelect>>", self.iface_select)

        # interfaces
        if self.canvas_node.ifaces:
            self.draw_ifaces()

        self.draw_spacer()
        self.draw_buttons()

    def draw_ifaces(self) -> None:
        notebook = ttk.Notebook(self.top)
        notebook.grid(sticky=tk.NSEW, pady=PADY)
        self.top.rowconfigure(notebook.grid_info()["row"], weight=1)
        state = tk.DISABLED if self.app.core.is_runtime() else tk.NORMAL
        for iface_id in sorted(self.canvas_node.ifaces):
            iface = self.canvas_node.ifaces[iface_id]
            tab = ttk.Frame(notebook, padding=FRAME_PAD)
            tab.grid(sticky=tk.NSEW, pady=PADY)
            tab.columnconfigure(1, weight=1)
            tab.columnconfigure(2, weight=1)
            notebook.add(tab, text=iface.name)

            row = 0
            emane_node = self.canvas_node.has_emane_link(iface.id)
            if emane_node:
                emane_model = emane_node.emane.split("_")[1]
                command = partial(self.click_emane_config, emane_model, iface.id)
                button = ttk.Button(
                    tab, text=f"Configure EMANE {emane_model}", command=command
                )
                button.grid(row=row, sticky=tk.EW, columnspan=3, pady=PADY)
                row += 1

            label = ttk.Label(tab, text="Name")
            label.grid(row=row, column=0, padx=PADX, pady=PADY)
            name = tk.StringVar(value=iface.name)
            entry = ttk.Entry(tab, textvariable=name, state=state)
            entry.var = name
            entry.grid(row=row, column=1, columnspan=2, sticky=tk.EW)
            row += 1

            label = ttk.Label(tab, text="MAC")
            label.grid(row=row, column=0, padx=PADX, pady=PADY)
            auto_set = not iface.mac
            is_auto = tk.BooleanVar(value=auto_set)
            mac_state = tk.DISABLED if auto_set else tk.NORMAL
            if state == tk.DISABLED:
                mac_state = tk.DISABLED
            checkbutton = ttk.Checkbutton(
                tab, text="Auto?", variable=is_auto, state=state
            )
            checkbutton.var = is_auto
            checkbutton.grid(row=row, column=1, padx=PADX)
            mac = tk.StringVar(value=iface.mac)
            entry = ttk.Entry(tab, textvariable=mac, state=mac_state)
            entry.grid(row=row, column=2, sticky=tk.EW)
            func = partial(mac_auto, is_auto, entry, mac)
            checkbutton.config(command=func)
            row += 1

            label = ttk.Label(tab, text="IPv4")
            label.grid(row=row, column=0, padx=PADX, pady=PADY)
            ip4_net = ""
            if iface.ip4:
                ip4_net = f"{iface.ip4}/{iface.ip4_mask}"
            ip4 = tk.StringVar(value=ip4_net)
            entry = ttk.Entry(tab, textvariable=ip4, state=state)
            entry.grid(row=row, column=1, columnspan=2, sticky=tk.EW)
            row += 1

            label = ttk.Label(tab, text="IPv6")
            label.grid(row=row, column=0, padx=PADX, pady=PADY)
            ip6_net = ""
            if iface.ip6:
                ip6_net = f"{iface.ip6}/{iface.ip6_mask}"
            ip6 = tk.StringVar(value=ip6_net)
            entry = ttk.Entry(tab, textvariable=ip6, state=state)
            entry.grid(row=row, column=1, columnspan=2, sticky=tk.EW)

            self.ifaces[iface.id] = InterfaceData(name, is_auto, mac, ip4, ip6)

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, padx=PADX, sticky=tk.EW)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_emane_config(self, emane_model: str, iface_id: int) -> None:
        logger.info("configuring emane: %s - %s", emane_model, iface_id)
        dialog = EmaneModelDialog(self, self.app, self.node, emane_model, iface_id)
        dialog.show()

    def click_icon(self) -> None:
        file_path = image_chooser(self, ICONS_PATH)
        if file_path:
            self.image = images.from_file(file_path, width=images.NODE_SIZE)
            self.image_button.config(image=self.image)
            self.image_file = file_path

    def click_apply(self) -> None:
        error = False

        # update core node
        self.node.name = self.name.get()
        if nutils.has_image(self.node.type):
            self.node.image = self.container_image.get()
        server = self.server.get()
        if nutils.is_container(self.node):
            if server == DEFAULT_SERVER:
                self.node.server = None
            else:
                self.node.server = server

        # set custom icon
        if self.image_file:
            self.node.icon = self.image_file

        # update canvas node
        self.canvas_node.image = self.image

        # update node interface data
        for iface in self.canvas_node.ifaces.values():
            data = self.ifaces[iface.id]
            error = not data.validate(self, iface)
            if error:
                break

        # redraw
        if not error:
            self.canvas_node.redraw()
            self.destroy()

    def iface_select(self, event: tk.Event) -> None:
        listbox = event.widget
        cur = listbox.curselection()
        if cur:
            iface = listbox.get(cur[0])
            self.name.set(iface)
