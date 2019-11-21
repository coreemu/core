"""
core node services
"""
import tkinter as tk
from tkinter import messagebox, ttk

from coretk.dialogs.dialog import Dialog
from coretk.dialogs.serviceconfiguration import ServiceConfiguration
from coretk.widgets import CheckboxList, ListboxScroll


class NodeService(Dialog):
    def __init__(self, master, app, canvas_node, services=None):
        super().__init__(master, app, "Node Services", modal=True)
        self.app = app
        self.canvas_node = canvas_node
        self.node_id = canvas_node.core_node.id
        self.groups = None
        self.services = None
        self.current = None
        if services is None:
            services = set(
                app.core.serviceconfig_manager.current_services[self.node_id]
            )
        self.current_services = services
        self.service_manager = self.app.core.serviceconfig_manager
        self.service_file_manager = self.app.core.servicefileconfig_manager
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        frame = ttk.Frame(self.top)
        frame.grid(stick="nsew")
        frame.rowconfigure(0, weight=1)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        self.groups = ListboxScroll(frame, text="Groups")
        self.groups.grid(row=0, column=0, sticky="nsew")
        for group in sorted(self.app.core.services):
            self.groups.listbox.insert(tk.END, group)
        self.groups.listbox.bind("<<ListboxSelect>>", self.handle_group_change)
        self.groups.listbox.selection_set(0)

        self.services = CheckboxList(
            frame, self.app, text="Services", clicked=self.service_clicked
        )
        self.services.grid(row=0, column=1, sticky="nsew")

        self.current = ListboxScroll(frame, text="Selected")
        self.current.grid(row=0, column=2, sticky="nsew")
        for service in sorted(self.current_services):
            self.current.listbox.insert(tk.END, service)

        frame = ttk.Frame(self.top)
        frame.grid(stick="ew")
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Configure", command=self.click_configure)
        button.grid(row=0, column=0, sticky="ew")
        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=1, sticky="ew")
        button = ttk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=2, sticky="ew")

        # trigger group change
        self.groups.listbox.event_generate("<<ListboxSelect>>")

    def handle_group_change(self, event):
        selection = self.groups.listbox.curselection()
        if selection:
            index = selection[0]
            group = self.groups.listbox.get(index)
            self.services.clear()
            for name in sorted(self.app.core.services[group]):
                checked = name in self.current_services
                self.services.add(name, checked)

    def service_clicked(self, name, var):
        if var.get() and name not in self.current_services:
            if self.service_manager.node_new_service_configuration(self.node_id, name):
                self.current_services.add(name)
            else:
                for checkbutton in self.services.frame.winfo_children():
                    if name == checkbutton.cget("text"):
                        checkbutton.config(variable=tk.BooleanVar(value=False))

        elif not var.get() and name in self.current_services:
            self.current_services.remove(name)
            self.service_manager.current_services[self.node_id].remove(name)
        self.current.listbox.delete(0, tk.END)
        for name in sorted(self.current_services):
            self.current.listbox.insert(tk.END, name)

    def click_configure(self):
        current_selection = self.current.listbox.curselection()
        if len(current_selection):
            dialog = ServiceConfiguration(
                master=self,
                app=self.app,
                service_name=self.current.listbox.get(current_selection[0]),
                node_id=self.node_id,
            )
            dialog.show()
        else:
            messagebox.showinfo(
                "Node service configuration", "Select a service to configure"
            )

    def click_save(self):
        if (
            self.current_services
            != self.app.core.default_services[self.canvas_node.core_node.model]
        ):
            self.canvas_node.core_node.services[:] = self.current_services
        else:
            if len(self.canvas_node.core_node.services) > 0:
                self.canvas_node.core_node.services[:] = []
        self.destroy()

    def click_cancel(self):
        self.current_services = None
        self.destroy()
