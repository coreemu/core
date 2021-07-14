"""
core node services
"""
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional, Set

from core.api.grpc.wrappers import Node
from core.gui.dialogs.dialog import Dialog
from core.gui.dialogs.serviceconfig import ServiceConfigDialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CheckboxList, ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class NodeServiceDialog(Dialog):
    def __init__(self, app: "Application", node: Node) -> None:
        title = f"{node.name} Services (Deprecated)"
        super().__init__(app, title)
        self.node: Node = node
        self.groups: Optional[ListboxScroll] = None
        self.services: Optional[CheckboxList] = None
        self.current: Optional[ListboxScroll] = None
        services = set(node.services)
        self.current_services: Set[str] = services
        self.protocol("WM_DELETE_WINDOW", self.click_cancel)
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        frame = ttk.Frame(self.top)
        frame.grid(stick="nsew", pady=PADY)
        frame.rowconfigure(0, weight=1)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        label_frame = ttk.LabelFrame(frame, text="Groups", padding=FRAME_PAD)
        label_frame.grid(row=0, column=0, sticky=tk.NSEW)
        label_frame.rowconfigure(0, weight=1)
        label_frame.columnconfigure(0, weight=1)
        self.groups = ListboxScroll(label_frame)
        self.groups.grid(sticky=tk.NSEW)
        for group in sorted(self.app.core.services):
            self.groups.listbox.insert(tk.END, group)
        self.groups.listbox.bind("<<ListboxSelect>>", self.handle_group_change)
        self.groups.listbox.selection_set(0)

        label_frame = ttk.LabelFrame(frame, text="Services")
        label_frame.grid(row=0, column=1, sticky=tk.NSEW)
        label_frame.columnconfigure(0, weight=1)
        label_frame.rowconfigure(0, weight=1)
        self.services = CheckboxList(
            label_frame, self.app, clicked=self.service_clicked, padding=FRAME_PAD
        )
        self.services.grid(sticky=tk.NSEW)

        label_frame = ttk.LabelFrame(frame, text="Selected", padding=FRAME_PAD)
        label_frame.grid(row=0, column=2, sticky=tk.NSEW)
        label_frame.rowconfigure(0, weight=1)
        label_frame.columnconfigure(0, weight=1)
        self.current = ListboxScroll(label_frame)
        self.current.grid(sticky=tk.NSEW)
        for service in sorted(self.current_services):
            self.current.listbox.insert(tk.END, service)
            if self.is_custom_service(service):
                self.current.listbox.itemconfig(tk.END, bg="green")

        frame = ttk.Frame(self.top)
        frame.grid(stick="ew")
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Configure", command=self.click_configure)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Remove", command=self.click_remove)
        button.grid(row=0, column=2, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=3, sticky=tk.EW)

        # trigger group change
        self.handle_group_change()

    def handle_group_change(self, event: tk.Event = None) -> None:
        selection = self.groups.listbox.curselection()
        if selection:
            index = selection[0]
            group = self.groups.listbox.get(index)
            self.services.clear()
            for name in sorted(self.app.core.services[group]):
                checked = name in self.current_services
                self.services.add(name, checked)

    def service_clicked(self, name: str, var: tk.IntVar) -> None:
        if var.get() and name not in self.current_services:
            self.current_services.add(name)
        elif not var.get() and name in self.current_services:
            self.current_services.remove(name)
            self.node.service_configs.pop(name, None)
            self.node.service_file_configs.pop(name, None)
        self.current.listbox.delete(0, tk.END)
        for name in sorted(self.current_services):
            self.current.listbox.insert(tk.END, name)
            if self.is_custom_service(name):
                self.current.listbox.itemconfig(tk.END, bg="green")
        self.node.services = self.current_services.copy()

    def click_configure(self) -> None:
        current_selection = self.current.listbox.curselection()
        if len(current_selection):
            dialog = ServiceConfigDialog(
                self,
                self.app,
                self.current.listbox.get(current_selection[0]),
                self.node,
            )

            # if error occurred when creating ServiceConfigDialog, don't show the dialog
            if not dialog.has_error:
                dialog.show()
            else:
                dialog.destroy()
        else:
            messagebox.showinfo(
                "Service Configuration", "Select a service to configure", parent=self
            )

    def click_cancel(self) -> None:
        self.destroy()

    def click_save(self) -> None:
        self.node.services = self.current_services.copy()
        self.destroy()

    def click_remove(self) -> None:
        cur = self.current.listbox.curselection()
        if cur:
            service = self.current.listbox.get(cur[0])
            self.current.listbox.delete(cur[0])
            self.current_services.remove(service)
            self.node.service_configs.pop(service, None)
            self.node.service_file_configs.pop(service, None)
            for checkbutton in self.services.frame.winfo_children():
                if checkbutton["text"] == service:
                    checkbutton.invoke()
                    return

    def is_custom_service(self, service: str) -> bool:
        has_service_config = service in self.node.service_configs
        has_file_config = service in self.node.service_file_configs
        return has_service_config or has_file_config
