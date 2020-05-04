import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Set

from core.gui import nodeutils
from core.gui.appconfig import ICONS_PATH
from core.gui.dialogs.dialog import Dialog
from core.gui.images import Images
from core.gui.nodeutils import NodeDraw
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CheckboxList, ListboxScroll, image_chooser

if TYPE_CHECKING:
    from core.gui.app import Application


class ServicesSelectDialog(Dialog):
    def __init__(self, master: Any, app: "Application", current_services: Set[str]):
        super().__init__(master, app, "Node Services")
        self.groups = None
        self.services = None
        self.current = None
        self.current_services = set(current_services)
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        frame = ttk.LabelFrame(self.top)
        frame.grid(stick="nsew", pady=PADY)
        frame.rowconfigure(0, weight=1)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        label_frame = ttk.LabelFrame(frame, text="Groups", padding=FRAME_PAD)
        label_frame.grid(row=0, column=0, sticky="nsew")
        label_frame.rowconfigure(0, weight=1)
        label_frame.columnconfigure(0, weight=1)
        self.groups = ListboxScroll(label_frame)
        self.groups.grid(sticky="nsew")
        for group in sorted(self.app.core.services):
            self.groups.listbox.insert(tk.END, group)
        self.groups.listbox.bind("<<ListboxSelect>>", self.handle_group_change)
        self.groups.listbox.selection_set(0)

        label_frame = ttk.LabelFrame(frame, text="Services")
        label_frame.grid(row=0, column=1, sticky="nsew")
        label_frame.columnconfigure(0, weight=1)
        label_frame.rowconfigure(0, weight=1)
        self.services = CheckboxList(
            label_frame, self.app, clicked=self.service_clicked, padding=FRAME_PAD
        )
        self.services.grid(sticky="nsew")

        label_frame = ttk.LabelFrame(frame, text="Selected", padding=FRAME_PAD)
        label_frame.grid(row=0, column=2, sticky="nsew")
        label_frame.rowconfigure(0, weight=1)
        label_frame.columnconfigure(0, weight=1)
        self.current = ListboxScroll(label_frame)
        self.current.grid(sticky="nsew")
        for service in sorted(self.current_services):
            self.current.listbox.insert(tk.END, service)

        frame = ttk.Frame(self.top)
        frame.grid(stick="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.destroy)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=1, sticky="ew")

        # trigger group change
        self.groups.listbox.event_generate("<<ListboxSelect>>")

    def handle_group_change(self, event: tk.Event):
        selection = self.groups.listbox.curselection()
        if selection:
            index = selection[0]
            group = self.groups.listbox.get(index)
            self.services.clear()
            for name in sorted(self.app.core.services[group]):
                checked = name in self.current_services
                self.services.add(name, checked)

    def service_clicked(self, name: str, var: tk.BooleanVar):
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
    def __init__(self, master: "Application", app: "Application"):
        super().__init__(master, app, "Custom Nodes")
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
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.draw_node_config()
        self.draw_node_buttons()
        self.draw_buttons()

    def draw_node_config(self):
        frame = ttk.LabelFrame(self.top, text="Nodes", padding=FRAME_PAD)
        frame.grid(sticky="nsew", pady=PADY)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.nodes_list = ListboxScroll(frame)
        self.nodes_list.grid(row=0, column=0, sticky="nsew", padx=PADX)
        self.nodes_list.listbox.bind("<<ListboxSelect>>", self.handle_node_select)
        for name in sorted(self.app.core.custom_nodes):
            self.nodes_list.listbox.insert(tk.END, name)

        frame = ttk.Frame(frame)
        frame.grid(row=0, column=2, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(sticky="ew", pady=PADY)
        self.image_button = ttk.Button(
            frame, text="Icon", compound=tk.LEFT, command=self.click_icon
        )
        self.image_button.grid(sticky="ew", pady=PADY)
        button = ttk.Button(frame, text="Services", command=self.click_services)
        button.grid(sticky="ew")

    def draw_node_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PADY)
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        self.edit_button = ttk.Button(
            frame, text="Edit", state=tk.DISABLED, command=self.click_edit
        )
        self.edit_button.grid(row=0, column=1, sticky="ew", padx=PADX)

        self.delete_button = ttk.Button(
            frame, text="Delete", state=tk.DISABLED, command=self.click_delete
        )
        self.delete_button.grid(row=0, column=2, sticky="ew")

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def reset_values(self):
        self.name.set("")
        self.image = None
        self.image_file = None
        self.services = set()
        self.image_button.config(image="")

    def click_icon(self):
        file_path = image_chooser(self, ICONS_PATH)
        if file_path:
            image = Images.create(file_path, nodeutils.ICON_SIZE)
            self.image = image
            self.image_file = file_path
            self.image_button.config(image=self.image)

    def click_services(self):
        dialog = ServicesSelectDialog(self, self.app, self.services)
        dialog.show()
        if dialog.current_services is not None:
            self.services.clear()
            self.services.update(dialog.current_services)

    def click_save(self):
        self.app.guiconfig["nodes"].clear()
        for name in sorted(self.app.core.custom_nodes):
            node_draw = self.app.core.custom_nodes[name]
            self.app.guiconfig["nodes"].append(
                {
                    "name": name,
                    "image": node_draw.image_file,
                    "services": list(node_draw.services),
                }
            )
        logging.info("saving custom nodes: %s", self.app.guiconfig["nodes"])
        self.app.save_config()
        self.destroy()

    def click_create(self):
        name = self.name.get()
        if name not in self.app.core.custom_nodes:
            image_file = Path(self.image_file).stem
            node_draw = NodeDraw.from_custom(name, image_file, set(self.services))
            logging.info(
                "created new custom node (%s), image file (%s), services: (%s)",
                name,
                image_file,
                self.services,
            )
            self.app.core.custom_nodes[name] = node_draw
            self.nodes_list.listbox.insert(tk.END, name)
            self.reset_values()

    def click_edit(self):
        name = self.name.get()
        if self.selected:
            previous_name = self.selected
            self.selected = name
            node_draw = self.app.core.custom_nodes.pop(previous_name)
            node_draw.model = name
            node_draw.image_file = Path(self.image_file).stem
            node_draw.image = self.image
            node_draw.services = self.services
            logging.debug(
                "edit custom node (%s), image: (%s), services (%s)",
                name,
                self.image_file,
                self.services,
            )
            self.app.core.custom_nodes[name] = node_draw
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

    def handle_node_select(self, event: tk.Event):
        selection = self.nodes_list.listbox.curselection()
        if selection:
            self.selected_index = selection[0]
            self.selected = self.nodes_list.listbox.get(self.selected_index)
            node_draw = self.app.core.custom_nodes[self.selected]
            self.name.set(node_draw.model)
            self.services = node_draw.services
            self.image = node_draw.image
            self.image_file = node_draw.image_file
            self.image_button.config(image=self.image)
            self.edit_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected = None
            self.selected_index = None
            self.edit_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
