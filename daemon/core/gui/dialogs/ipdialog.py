import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import netaddr

from core.gui import appconfig
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class IpConfigDialog(Dialog):
    def __init__(self, master: "Application", app: "Application") -> None:
        super().__init__(master, app, "IP Configuration", modal=True)
        ip_config = self.app.guiconfig.setdefault("ips")
        self.ip4 = ip_config.setdefault("ip4", appconfig.DEFAULT_IP4)
        self.ip6 = ip_config.setdefault("ip6", appconfig.DEFAULT_IP6)
        self.ip4s = ip_config.setdefault("ip4s", appconfig.DEFAULT_IP4S)
        self.ip6s = ip_config.setdefault("ip6s", appconfig.DEFAULT_IP6S)
        self.ip4_entry = None
        self.ip4_listbox = None
        self.ip6_entry = None
        self.ip6_listbox = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        # draw ip4 and ip6 lists
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.grid(sticky="nsew", pady=PADY)

        ip4_frame = ttk.LabelFrame(frame, text="IPv4", padding=FRAME_PAD)
        ip4_frame.columnconfigure(0, weight=1)
        ip4_frame.rowconfigure(0, weight=1)
        ip4_frame.grid(row=0, column=0, stick="nsew")
        self.ip4_listbox = ListboxScroll(ip4_frame)
        self.ip4_listbox.listbox.bind("<<ListboxSelect>>", self.select_ip4)
        self.ip4_listbox.grid(sticky="nsew", pady=PADY)
        for index, ip4 in enumerate(self.ip4s):
            self.ip4_listbox.listbox.insert(tk.END, ip4)
            if self.ip4 == ip4:
                self.ip4_listbox.listbox.select_set(index)
        self.ip4_entry = ttk.Entry(ip4_frame)
        self.ip4_entry.grid(sticky="ew", pady=PADY)
        ip4_button_frame = ttk.Frame(ip4_frame)
        ip4_button_frame.columnconfigure(0, weight=1)
        ip4_button_frame.columnconfigure(1, weight=1)
        ip4_button_frame.grid(sticky="ew")
        ip4_add = ttk.Button(ip4_button_frame, text="Add", command=self.click_add_ip4)
        ip4_add.grid(row=0, column=0, sticky="ew")
        ip4_del = ttk.Button(
            ip4_button_frame, text="Delete", command=self.click_del_ip4
        )
        ip4_del.grid(row=0, column=1, sticky="ew")

        ip6_frame = ttk.LabelFrame(frame, text="IPv6", padding=FRAME_PAD)
        ip6_frame.columnconfigure(0, weight=1)
        ip6_frame.rowconfigure(0, weight=1)
        ip6_frame.grid(row=0, column=1, stick="nsew")
        self.ip6_listbox = ListboxScroll(ip6_frame)
        self.ip6_listbox.listbox.bind("<<ListboxSelect>>", self.select_ip6)
        self.ip6_listbox.grid(sticky="nsew", pady=PADY)
        for index, ip6 in enumerate(self.ip6s):
            self.ip6_listbox.listbox.insert(tk.END, ip6)
            if self.ip6 == ip6:
                self.ip6_listbox.listbox.select_set(index)
        self.ip6_entry = ttk.Entry(ip6_frame)
        self.ip6_entry.grid(sticky="ew", pady=PADY)
        ip6_button_frame = ttk.Frame(ip6_frame)
        ip6_button_frame.columnconfigure(0, weight=1)
        ip6_button_frame.columnconfigure(1, weight=1)
        ip6_button_frame.grid(sticky="ew")
        ip6_add = ttk.Button(ip6_button_frame, text="Add", command=self.click_add_ip6)
        ip6_add.grid(row=0, column=0, sticky="ew")
        ip6_del = ttk.Button(
            ip6_button_frame, text="Delete", command=self.click_del_ip6
        )
        ip6_del.grid(row=0, column=1, sticky="ew")

        # draw buttons
        frame = ttk.Frame(self.top)
        frame.grid(stick="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_add_ip4(self) -> None:
        ip4 = self.ip4_entry.get()
        if not ip4 or not netaddr.valid_ipv4(ip4):
            messagebox.showerror("IPv4 Error", f"Invalid IPv4 {ip4}")
        else:
            self.ip4_listbox.listbox.insert(tk.END, ip4)

    def click_del_ip4(self) -> None:
        if self.ip4_listbox.listbox.size() == 1:
            messagebox.showerror("IPv4 Error", "Must have at least one address")
        else:
            selection = self.ip4_listbox.listbox.curselection()
            self.ip4_listbox.listbox.delete(selection)
            self.ip4_listbox.listbox.select_set(0)

    def click_add_ip6(self) -> None:
        ip6 = self.ip6_entry.get()
        if not ip6 or not netaddr.valid_ipv6(ip6):
            messagebox.showerror("IPv6 Error", f"Invalid IPv6 {ip6}")
        else:
            self.ip6_listbox.listbox.insert(tk.END, ip6)

    def click_del_ip6(self) -> None:
        if self.ip6_listbox.listbox.size() == 1:
            messagebox.showerror("IPv6 Error", "Must have at least one address")
        else:
            selection = self.ip6_listbox.listbox.curselection()
            self.ip6_listbox.listbox.delete(selection)
            self.ip6_listbox.listbox.select_set(0)

    def select_ip4(self, _event: tk.Event) -> None:
        selection = self.ip4_listbox.listbox.curselection()
        self.ip4 = self.ip4_listbox.listbox.get(selection)

    def select_ip6(self, _event: tk.Event) -> None:
        selection = self.ip6_listbox.listbox.curselection()
        self.ip6 = self.ip6_listbox.listbox.get(selection)

    def click_save(self) -> None:
        ip4s = []
        for index in range(self.ip4_listbox.listbox.size()):
            ip4 = self.ip4_listbox.listbox.get(index)
            ip4s.append(ip4)
        ip6s = []
        for index in range(self.ip6_listbox.listbox.size()):
            ip6 = self.ip6_listbox.listbox.get(index)
            ip6s.append(ip6)
        ip_config = self.app.guiconfig["ips"]
        ip_config["ip4"] = self.ip4
        ip_config["ip6"] = self.ip6
        ip_config["ip4s"] = ip4s
        ip_config["ip6s"] = ip6s
        self.app.core.interfaces_manager.update_ips(self.ip4, self.ip6)
        self.app.save_config()
        self.destroy()
