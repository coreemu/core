"""
core node services
"""
import tkinter as tk
from tkinter import messagebox

from coretk.dialogs.dialog import Dialog
from coretk.dialogs.serviceconfiguration import ServiceConfiguration
from coretk.widgets import CheckboxList, ListboxScroll


class NodeService(Dialog):
    def __init__(self, master, app, canvas_node, current_services=set()):
        super().__init__(master, app, "Node Services", modal=True)
        self.canvas_node = canvas_node
        self.groups = None
        self.services = None
        self.current = None
        self.current_services = current_services
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame = tk.Frame(self)
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
            frame, text="Services", clicked=self.service_clicked
        )
        self.services.grid(row=0, column=1, sticky="nsew")

        self.current = ListboxScroll(frame, text="Selected")
        self.current.grid(row=0, column=2, sticky="nsew")
        for service in sorted(self.current_services):
            self.current.listbox.insert(tk.END, service)

        frame = tk.Frame(self)
        frame.grid(stick="ew")
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        button = tk.Button(frame, text="Configure", command=self.click_configure)
        button.grid(row=0, column=0, sticky="ew")
        button = tk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=1, sticky="ew")
        button = tk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=2, sticky="ew")

        # trigger group change
        self.groups.listbox.event_generate("<<ListboxSelect>>")

    def handle_group_change(self, event):
        selection = self.groups.listbox.curselection()
        if selection:
            index = selection[0]
            group = self.groups.listbox.get(index)
            self.services.clear()
            for service in sorted(self.app.core.services[group], key=lambda x: x.name):
                checked = service.name in self.current_services
                self.services.add(service.name, checked)

    def service_clicked(self, name, var):
        if var.get() and name not in self.current_services:
            self.current_services.add(name)
        elif not var.get() and name in self.current_services:
            self.current_services.remove(name)
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
                canvas_node=self.canvas_node,
            )
            dialog.show()
        else:
            messagebox.showinfo(
                "Node service configuration", "Select a service to configure"
            )

    def click_save(self):
        print("not implemented")
        print(self.current_services)

    def click_cancel(self):
        self.current_services = None
        self.destroy()
