"""
copy service config dialog
"""

import logging
import tkinter as tk
from tkinter import ttk

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX
from core.gui.widgets import CodeText


class CopyServiceConfigDialog(Dialog):
    def __init__(self, master, app, node_id):
        super().__init__(master, app, f"Copy services to node {node_id}", modal=True)
        self.parent = master
        self.app = app
        self.node_id = node_id
        self.service_configs = app.core.service_configs
        self.file_configs = app.core.file_configs

        self.tree = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(self.top)
        self.tree.grid(row=0, column=0, sticky="ew", padx=PADX)
        self.tree["columns"] = ()
        self.tree.column("#0", width=270, minwidth=270, stretch=tk.YES)
        self.tree.heading("#0", text="Service configuration items", anchor=tk.CENTER)
        custom_nodes = set(self.service_configs).union(set(self.file_configs))
        for nid in custom_nodes:
            treeid = self.tree.insert("", "end", text=f"n{nid}", tags="node")
            services = self.service_configs.get(nid, None)
            files = self.file_configs.get(nid, None)
            tree_ids = {}
            if services:
                for service, config in services.items():
                    serviceid = self.tree.insert(
                        treeid, "end", text=service, tags="service"
                    )
                    tree_ids[service] = serviceid
                    print(config)
                    # for filename, data in config.items():
                    #     self.tree.insert(serviceid, "end", text=filename)
            if files:
                for service, configs in files.items():
                    if service in tree_ids:
                        serviceid = tree_ids[service]
                    else:
                        serviceid = self.tree.insert(
                            treeid, "end", text=service, tags="service"
                        )
                        tree_ids[service] = serviceid
                    for filename, data in configs.items():
                        self.tree.insert(serviceid, "end", text=filename, tags="file")

        frame = ttk.Frame(self.top)
        frame.grid(row=1, column=0)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Copy", command=self.click_copy)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="View", command=self.click_view)
        button.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=2, sticky="ew", padx=PADX)

    def click_copy(self):
        logging.debug("click copy")
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])
            if "file" in item["tags"]:
                filename = item["text"]
                nid, service = self.get_node_service(selected)
                data = self.file_configs[nid][service][filename]
                if service == self.parent.service_name:
                    self.parent.temp_service_files[filename] = data
                    self.parent.modified_files.add(filename)
                    if self.parent.filename_combobox.get() == filename:
                        self.parent.service_file_data.text.delete(1.0, "end")
                        self.parent.service_file_data.text.insert("end", data)
        self.destroy()

    def click_view(self):
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])
            if "file" in item["tags"]:
                nid, service = self.get_node_service(selected)
                data = self.file_configs[nid][service][item["text"]]
                dialog = ViewConfigDialog(self, self.app, self.node_id, data)
                dialog.show()

    def get_node_service(self, selected):
        service_tree_id = self.tree.parent(selected[0])
        service_name = self.tree.item(service_tree_id)["text"]
        node_tree_id = self.tree.parent(service_tree_id)
        node_id = int(self.tree.item(node_tree_id)["text"][1:])
        return node_id, service_name


class ViewConfigDialog(Dialog):
    def __init__(self, master, app, node_id, data):
        super().__init__(master, app, f"n{node_id} config data", modal=True)
        self.data = data
        self.service_data = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.grid(row=0, column=0)
        label = ttk.Label(frame, text="File: ")
        label.grid(row=0, column=0, sticky="ew")

        self.service_data = CodeText(self.top)
        self.service_data.grid(row=1, column=0, sticky="nsew")
        self.service_data.text.insert("end", self.data)
        self.service_data.text.config(state="disabled")

        button = ttk.Button(self.top, text="Close", command=self.destroy)
        button.grid(row=2, column=0, sticky="ew", padx=PADX)
