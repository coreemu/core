"""
copy service config dialog
"""

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict, Optional

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import CodeText, ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.dialogs.serviceconfig import ServiceConfigDialog


class CopyServiceConfigDialog(Dialog):
    def __init__(
        self,
        app: "Application",
        dialog: "ServiceConfigDialog",
        name: str,
        service: str,
        file_name: str,
    ) -> None:
        super().__init__(app, f"Copy Custom File to {name}", master=dialog)
        self.dialog: "ServiceConfigDialog" = dialog
        self.service: str = service
        self.file_name: str = file_name
        self.listbox: Optional[tk.Listbox] = None
        self.nodes: Dict[str, int] = {}
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)
        label = ttk.Label(
            self.top, text=f"{self.service} - {self.file_name}", anchor=tk.CENTER
        )
        label.grid(sticky=tk.EW, pady=PADY)

        listbox_scroll = ListboxScroll(self.top)
        listbox_scroll.grid(sticky=tk.NSEW, pady=PADY)
        self.listbox = listbox_scroll.listbox
        for node in self.app.core.session.nodes.values():
            file_configs = node.service_file_configs.get(self.service)
            if not file_configs:
                continue
            data = file_configs.get(self.file_name)
            if not data:
                continue
            self.nodes[node.name] = node.id
            self.listbox.insert(tk.END, node.name)

        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Copy", command=self.click_copy)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="View", command=self.click_view)
        button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=2, sticky=tk.EW)

    def click_copy(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        name = self.listbox.get(selection)
        node_id = self.nodes[name]
        node = self.app.core.session.nodes[node_id]
        data = node.service_file_configs[self.service][self.file_name]
        self.dialog.temp_service_files[self.file_name] = data
        self.dialog.modified_files.add(self.file_name)
        self.dialog.service_file_data.text.delete(1.0, tk.END)
        self.dialog.service_file_data.text.insert(tk.END, data)
        self.destroy()

    def click_view(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        name = self.listbox.get(selection)
        node_id = self.nodes[name]
        node = self.app.core.session.nodes[node_id]
        data = node.service_file_configs[self.service][self.file_name]
        dialog = ViewConfigDialog(
            self.app, self, name, self.service, self.file_name, data
        )
        dialog.show()


class ViewConfigDialog(Dialog):
    def __init__(
        self,
        app: "Application",
        master: tk.BaseWidget,
        name: str,
        service: str,
        file_name: str,
        data: str,
    ) -> None:
        title = f"{name} Service({service}) File({file_name})"
        super().__init__(app, title, master=master)
        self.data = data
        self.service_data = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.service_data = CodeText(self.top)
        self.service_data.grid(sticky=tk.NSEW, pady=PADY)
        self.service_data.text.insert(tk.END, self.data)
        self.service_data.text.config(state=tk.DISABLED)
        button = ttk.Button(self.top, text="Close", command=self.destroy)
        button.grid(sticky=tk.EW)
