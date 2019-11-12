import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from coretk.coreclient import CustomNode
from coretk.dialogs.dialog import Dialog
from coretk.dialogs.icondialog import IconDialog
from coretk.widgets import CheckboxList, ListboxScroll


class ServicesSelectDialog(Dialog):
    def __init__(self, master, app, current_services):
        super().__init__(master, app, "Node Services", modal=True)
        self.groups = None
        self.services = None
        self.current = None
        self.current_services = set(current_services)
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame = ttk.Frame(self)
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

        frame = ttk.Frame(self)
        frame.grid(stick="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.destroy)
        button.grid(row=0, column=0, sticky="ew")
        button = ttk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=1, sticky="ew")

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

    def click_cancel(self):
        self.current_services = None
        self.destroy()


class CustomNodesDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Custom Nodes", modal=True)
        self.edit_button = None
        self.delete_button = None
        self.nodes_list = None
        self.name = tk.StringVar()
        self.image_button = None
        self.image = None
        self.image_file = None
        self.services = set()
        self.selected = None
        self.selected_index = None
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.draw_node_config()
        self.draw_node_buttons()
        self.draw_buttons()

    def draw_node_config(self):
        frame = ttk.Frame(self)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.nodes_list = ListboxScroll(frame)
        self.nodes_list.grid(row=0, column=0, sticky="nsew")
        self.nodes_list.listbox.bind("<<ListboxSelect>>", self.handle_node_select)
        for name in sorted(self.app.core.custom_nodes):
            self.nodes_list.listbox.insert(tk.END, name)

        frame = ttk.Frame(frame)
        frame.grid(row=0, column=2, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(sticky="ew")
        self.image_button = ttk.Button(frame, text="Icon", command=self.click_icon)
        self.image_button.grid(sticky="ew")
        button = ttk.Button(frame, text="Services", command=self.click_services)
        button.grid(sticky="ew")

    def draw_node_buttons(self):
        frame = ttk.Frame(self)
        frame.grid(pady=2, sticky="ew")
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky="ew")

        self.edit_button = ttk.Button(
            frame, text="Edit", state=tk.DISABLED, command=self.click_edit
        )
        self.edit_button.grid(row=0, column=1, sticky="ew")

        self.delete_button = ttk.Button(
            frame, text="Delete", state=tk.DISABLED, command=self.click_delete
        )
        self.delete_button.grid(row=0, column=2, sticky="ew")

    def draw_buttons(self):
        frame = ttk.Frame(self)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def reset_values(self):
        self.name.set("")
        self.image = None
        self.image_file = None
        self.services = set()
        self.image_button.config(image="")

    def click_icon(self):
        dialog = IconDialog(self, self.app, self.name.get(), self.image)
        dialog.show()
        if dialog.image:
            self.image = dialog.image
            self.image_file = dialog.file_path.get()
            self.image_button.config(image=self.image)

    def click_services(self):
        dialog = ServicesSelectDialog(self, self.app, self.services)
        dialog.show()
        if dialog.current_services is not None:
            self.services.clear()
            self.services.update(dialog.current_services)

    def click_save(self):
        self.app.config["nodes"].clear()
        for name in sorted(self.app.core.custom_nodes):
            custom_node = self.app.core.custom_nodes[name]
            self.app.config["nodes"].append(
                {
                    "name": custom_node.name,
                    "image": custom_node.image_file,
                    "services": list(custom_node.services),
                }
            )
        logging.info("saving custom nodes: %s", self.app.config["nodes"])
        self.app.save_config()
        self.destroy()

    def click_create(self):
        name = self.name.get()
        if name not in self.app.core.custom_nodes:
            custom_node = CustomNode(
                name, self.image, Path(self.image_file).name, set(self.services)
            )
            self.app.core.custom_nodes[name] = custom_node
            self.nodes_list.listbox.insert(tk.END, name)
            self.reset_values()

    def click_edit(self):
        name = self.name.get()
        if self.selected:
            previous_name = self.selected
            self.selected = name
            custom_node = self.app.core.custom_nodes.pop(previous_name)
            custom_node.name = name
            custom_node.image = self.image
            custom_node.image_file = Path(self.image_file).stem
            custom_node.services = self.services
            self.app.core.custom_nodes[name] = custom_node
            self.nodes_list.listbox.delete(self.selected_index)
            self.nodes_list.listbox.insert(self.selected_index, name)
            self.nodes_list.listbox.selection_set(self.selected_index)

    def click_delete(self):
        if self.selected and self.selected in self.app.core.custom_nodes:
            self.nodes_list.listbox.delete(self.selected_index)
            del self.app.core.custom_nodes[self.selected]
            self.reset_values()
            self.nodes_list.listbox.selection_clear(0, tk.END)
            self.nodes_list.listbox.event_generate("<<ListboxSelect>>")

    def handle_node_select(self, event):
        selection = self.nodes_list.listbox.curselection()
        if selection:
            self.selected_index = selection[0]
            self.selected = self.nodes_list.listbox.get(self.selected_index)
            custom_node = self.app.core.custom_nodes[self.selected]
            self.name.set(custom_node.name)
            self.services = custom_node.services
            self.image = custom_node.image
            self.image_file = custom_node.image_file
            self.image_button.config(image=self.image)
            self.edit_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected = None
            self.selected_index = None
            self.edit_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
