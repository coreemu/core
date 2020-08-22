import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import netaddr

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application


class MacConfigDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "MAC Configuration")
        mac = self.app.guiconfig.mac
        self.mac_var: tk.StringVar = tk.StringVar(value=mac)
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        # draw explanation label
        text = (
            "MAC addresses will be generated for nodes starting with the\n"
            "provided value below and increment by value in order."
        )
        label = ttk.Label(self.top, text=text)
        label.grid(sticky=tk.EW, pady=PADY)

        # draw input
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=3)
        frame.grid(stick="ew", pady=PADY)
        label = ttk.Label(frame, text="Starting MAC")
        label.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.mac_var)
        entry.grid(row=0, column=1, sticky=tk.EW)

        # draw buttons
        frame = ttk.Frame(self.top)
        frame.grid(stick="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_save(self) -> None:
        mac = self.mac_var.get()
        if not netaddr.valid_mac(mac):
            messagebox.showerror("MAC Error", f"{mac} is an invalid mac")
        else:
            self.app.core.ifaces_manager.mac = netaddr.EUI(mac)
            self.app.guiconfig.mac = mac
            self.app.save_config()
            self.destroy()
