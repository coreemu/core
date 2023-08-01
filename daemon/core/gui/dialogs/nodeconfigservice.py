"""
core node services
"""
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from core.api.grpc.wrappers import Node
from core.gui.dialogs.configserviceconfig import ConfigServiceConfigDialog
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CheckboxList, ListboxScroll

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application


class NodeConfigServiceDialog(Dialog):
    def __init__(
        self, app: "Application", node: Node, services: set[str] = None
    ) -> None:
        title = f"{node.name} Config Services"
        super().__init__(app, title)
        self.node: Node = node
        self.groups: Optional[ListboxScroll] = None
        self.services: Optional[CheckboxList] = None
        self.current: Optional[ListboxScroll] = None
        if services is None:
            services = set(node.config_services)
        self.current_services: set[str] = services
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
        for group in sorted(self.app.core.config_services_groups):
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
        self.draw_current_services()

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
            for name in sorted(self.app.core.config_services_groups[group]):
                checked = name in self.current_services
                self.services.add(name, checked)

    def service_clicked(self, name: str, var: tk.IntVar) -> None:
        if var.get() and name not in self.current_services:
            self.current_services.add(name)
        elif not var.get() and name in self.current_services:
            self.current_services.remove(name)
            self.node.config_service_configs.pop(name, None)
        self.draw_current_services()
        self.node.config_services = self.current_services.copy()

    def click_configure(self) -> None:
        current_selection = self.current.listbox.curselection()
        if len(current_selection):
            dialog = ConfigServiceConfigDialog(
                self,
                self.app,
                self.current.listbox.get(current_selection[0]),
                self.node,
            )
            if not dialog.has_error:
                dialog.show()
                self.draw_current_services()
        else:
            messagebox.showinfo(
                "Config Service Configuration",
                "Select a service to configure",
                parent=self,
            )

    def draw_current_services(self) -> None:
        self.current.listbox.delete(0, tk.END)
        for name in sorted(self.current_services):
            self.current.listbox.insert(tk.END, name)
            if self.is_custom_service(name):
                self.current.listbox.itemconfig(tk.END, bg="green")

    def click_save(self) -> None:
        self.node.config_services = self.current_services.copy()
        logger.info("saved node config services: %s", self.node.config_services)
        self.destroy()

    def click_cancel(self) -> None:
        self.current_services = None
        self.destroy()

    def click_remove(self) -> None:
        cur = self.current.listbox.curselection()
        if cur:
            service = self.current.listbox.get(cur[0])
            self.current.listbox.delete(cur[0])
            self.current_services.remove(service)
            self.node.config_service_configs.pop(service, None)
            for checkbutton in self.services.frame.winfo_children():
                if checkbutton["text"] == service:
                    checkbutton.invoke()
                    return

    def is_custom_service(self, service: str) -> bool:
        return service in self.node.config_service_configs
