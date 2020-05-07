import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Set, Tuple

from core.gui.dialogs.dialog import Dialog
from core.gui.nodeutils import NodeUtils
from core.gui.themes import FRAME_PAD, PADX, PADY, Colors
from core.gui.widgets import CheckboxList, ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class MultipleNodeServiceDialog(Dialog):
    def __init__(self, app: "Application"):
        super().__init__(app, "Multiple node service config")
        self.canvas = app.canvas
        self.nodes = None
        self.groups = None
        self.services = None
        self.current = None
        self.current_services = set()
        self.selected_nodes = {}
        self.all_nodes = {}

        # maps node name to node id
        self.node_names = {}
        # track all the nodes that will need custom service configuration when we click save
        self.custom_nodes = set()

        self.store_node_services()
        self.draw()

    def store_node_services(self) -> None:
        """
        create a mapping of core node canvas id to core node services
        one mapping for currently selected nodes, one for all nodes
        """

        for node_id in self.canvas.selection:
            core_node = self.canvas.nodes[node_id].core_node
            if NodeUtils.is_container_node(core_node.type):
                self.selected_nodes[core_node.id] = set(core_node.services[:])

        for canvas_node in self.canvas.nodes.values():
            core_node = canvas_node.core_node
            if NodeUtils.is_container_node(core_node.type):
                self.all_nodes[core_node.id] = set(core_node.services[:])
                self.node_names[core_node.name] = core_node.id

    def common_services(self) -> Tuple[Set, Set]:
        """
        find the common services of all the selected nodes and the common services
        of some but not all nodes
        """
        common_services = set()
        non_common_services = set()

        for index, service_set in enumerate(self.selected_nodes.values()):
            if index == 0:
                common_services = service_set
            else:
                common_services = common_services.intersection(service_set)
            non_common_services = non_common_services.union(service_set)

        if len(self.selected_nodes) == 1:
            non_common_services = set()
        else:
            non_common_services = non_common_services - common_services

        return common_services, non_common_services

    def populate_node_list(self) -> None:
        self.nodes.listbox.delete(0, tk.END)
        for canvas_id, canvas_node in self.canvas.nodes.items():
            core_node = canvas_node.core_node
            if NodeUtils.is_container_node(core_node.type):
                self.nodes.listbox.insert(tk.END, canvas_node.core_node.name)
        for index, name in enumerate(self.nodes.listbox.get(0, tk.END)):
            if self.node_names[name] in self.selected_nodes:
                self.nodes.listbox.selection_set(index)

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        frame = ttk.Frame(self.top)
        frame.grid(stick="nsew", pady=PADY)
        frame.rowconfigure(0, weight=1)
        for i in range(4):
            frame.columnconfigure(i, weight=1)

        # nodes frame
        label_frame = ttk.LabelFrame(frame, text="Nodes", padding=FRAME_PAD)
        label_frame.grid(row=0, column=0, sticky="nsew")
        label_frame.rowconfigure(0, weight=1)
        label_frame.columnconfigure(0, weight=1)
        self.nodes = ListboxScroll(label_frame)
        self.nodes.listbox.configure(selectmode=tk.MULTIPLE)
        self.nodes.grid(sticky="nsew")

        self.populate_node_list()
        self.nodes.listbox.bind("<<ListboxSelect>>", self.handle_node_selection)

        # group frame
        label_frame = ttk.LabelFrame(frame, text="Groups", padding=FRAME_PAD)
        label_frame.grid(row=0, column=1, sticky="nsew")
        label_frame.rowconfigure(0, weight=1)
        label_frame.columnconfigure(0, weight=1)
        self.groups = ListboxScroll(label_frame)
        self.groups.grid(sticky="nsew")
        for group in sorted(self.app.core.services):
            self.groups.listbox.insert(tk.END, group)
        self.groups.listbox.bind("<<ListboxSelect>>", self.handle_group_change)
        self.groups.listbox.selection_set(0)

        # service frame
        label_frame = ttk.LabelFrame(frame, text="Services")
        label_frame.grid(row=0, column=2, sticky="nsew")
        label_frame.columnconfigure(0, weight=1)
        label_frame.rowconfigure(0, weight=1)
        self.services = CheckboxList(
            label_frame, self.app, clicked=self.service_clicked, padding=FRAME_PAD
        )
        self.services.grid(sticky="nsew")

        # service frame
        label_frame = ttk.LabelFrame(frame, text="Selected", padding=FRAME_PAD)
        label_frame.grid(row=0, column=3, sticky="nsew")
        label_frame.rowconfigure(0, weight=1)
        label_frame.columnconfigure(0, weight=1)
        self.current = ListboxScroll(label_frame)
        self.current.grid(sticky="nsew")

        # buttons frame
        frame = ttk.Frame(self.top)
        frame.grid(stick="ew")
        for i in range(5):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Turn off", command=self.turn_off)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Turn on", command=self.turn_on)
        button.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Save", command=self.save_config)
        button.grid(row=0, column=2, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Default", command=self.default_config)
        button.grid(row=0, column=3, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=4, sticky="ew")

        # trigger group change
        self.groups.listbox.event_generate("<<ListboxSelect>>")

    def handle_node_selection(self, _event: tk.Event = None) -> None:
        """
        update selected_nodes as user add/remove nodes to configure
        """
        for index, node_name in enumerate(self.nodes.listbox.get(0, tk.END)):
            node_id = self.node_names[node_name]
            if self.nodes.listbox.selection_includes(index):
                if node_id not in self.selected_nodes:
                    self.selected_nodes[node_id] = self.all_nodes[node_id]
            else:
                if node_id in self.selected_nodes:
                    self.selected_nodes.pop(node_id, None)
        # update services color according to current node selection
        self.handle_group_change()

    def handle_group_change(self, _event: tk.Event = None) -> None:
        """
        Display a list of services that belongs to currently selected group
        Service that is common to all selected nodes is colored green
        Service that is common to some but not all nodes is colored yellow
        """
        selection = self.groups.listbox.curselection()
        if selection:
            index = selection[0]
            group = self.groups.listbox.get(index)
            self.services.clear()
            common, non_common = self.common_services()
            for name in sorted(self.app.core.services[group]):
                checked = name in self.current_services
                color = Colors.frame
                if name in common:
                    color = Colors.common_services
                elif name in non_common:
                    color = Colors.noncommon_services
                self.services.add_with_color(name, checked, color)

    def service_clicked(self, name: str, var: tk.IntVar) -> None:
        if var.get() and name not in self.current_services:
            self.current_services.add(name)
        elif not var.get() and name in self.current_services:
            self.current_services.remove(name)
        self.current.listbox.delete(0, tk.END)
        for name in sorted(self.current_services):
            self.current.listbox.insert(tk.END, name)

    def turn_off(self) -> None:
        if not self.current_services:
            return
        for service in self.current_services:
            for node_id, service_set in self.selected_nodes.items():
                service_set.discard(service)
                self.all_nodes[node_id].discard(service)
        self.handle_group_change()
        self.custom_nodes = self.custom_nodes.union(set(self.selected_nodes.keys()))

    def turn_on(self) -> None:
        if not self.current_services:
            return
        for service in self.current_services:
            for node_id, service_set in self.selected_nodes.items():
                service_set.add(service)
                self.all_nodes[node_id].add(service)
        self.handle_group_change()
        self.custom_nodes = self.custom_nodes.union(set(self.selected_nodes.keys()))

    def save_config(self) -> None:
        for node_id in self.custom_nodes:
            self.app.core.canvas_nodes[node_id].core_node.services[:] = self.all_nodes[
                node_id
            ]
        self.destroy()

    def default_config(self) -> None:
        self.current_services.clear()
        self.all_nodes.clear()
        self.custom_nodes.clear()
        self.selected_nodes.clear()

        self.store_node_services()
        self.populate_node_list()
        self.current.listbox.delete(0, tk.END)
        self.handle_group_change()
