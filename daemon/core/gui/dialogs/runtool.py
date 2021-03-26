import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict, Optional

from core.gui import nodeutils as nutils
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CodeText, ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class RunToolDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Run Tool")
        self.cmd: tk.StringVar = tk.StringVar(value="ps ax")
        self.result: Optional[CodeText] = None
        self.node_list: Optional[ListboxScroll] = None
        self.executable_nodes: Dict[str, int] = {}
        self.store_nodes()
        self.draw()

    def store_nodes(self) -> None:
        """
        store all CORE nodes (nodes that execute commands) from all existing nodes
        """
        for node in self.app.core.session.nodes.values():
            if nutils.is_container(node):
                self.executable_nodes[node.name] = node.id

    def draw(self) -> None:
        self.top.rowconfigure(0, weight=1)
        self.top.columnconfigure(0, weight=1)
        self.draw_command_frame()
        self.draw_nodes_frame()

    def draw_command_frame(self) -> None:
        # the main frame
        frame = ttk.Frame(self.top)
        frame.grid(row=0, column=0, sticky=tk.NSEW, padx=PADX)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        labeled_frame = ttk.LabelFrame(frame, text="Command", padding=FRAME_PAD)
        labeled_frame.grid(sticky=tk.EW, pady=PADY)
        labeled_frame.rowconfigure(0, weight=1)
        labeled_frame.columnconfigure(0, weight=1)
        entry = ttk.Entry(labeled_frame, textvariable=self.cmd)
        entry.grid(sticky=tk.EW)

        # results frame
        labeled_frame = ttk.LabelFrame(frame, text="Output", padding=FRAME_PAD)
        labeled_frame.grid(sticky=tk.NSEW, pady=PADY)
        labeled_frame.columnconfigure(0, weight=1)
        labeled_frame.rowconfigure(0, weight=1)

        self.result = CodeText(labeled_frame)
        self.result.text.config(state=tk.DISABLED, height=15)
        self.result.grid(sticky=tk.NSEW, pady=PADY)
        button_frame = ttk.Frame(labeled_frame)
        button_frame.grid(sticky=tk.NSEW)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button = ttk.Button(button_frame, text="Run", command=self.click_run)
        button.grid(sticky=tk.EW, padx=PADX)
        button = ttk.Button(button_frame, text="Close", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def draw_nodes_frame(self) -> None:
        labeled_frame = ttk.LabelFrame(self.top, text="Nodes", padding=FRAME_PAD)
        labeled_frame.grid(row=0, column=1, sticky=tk.NSEW)
        labeled_frame.columnconfigure(0, weight=1)
        labeled_frame.rowconfigure(0, weight=1)

        self.node_list = ListboxScroll(labeled_frame)
        self.node_list.listbox.config(selectmode=tk.MULTIPLE)
        self.node_list.grid(sticky=tk.NSEW, pady=PADY)
        for n in sorted(self.executable_nodes.keys()):
            self.node_list.listbox.insert(tk.END, n)

        button_frame = ttk.Frame(labeled_frame, padding=FRAME_PAD)
        button_frame.grid(sticky=tk.NSEW)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        button = ttk.Button(button_frame, text="All", command=self.click_all)
        button.grid(sticky=tk.NSEW, padx=PADX)
        button = ttk.Button(button_frame, text="None", command=self.click_none)
        button.grid(row=0, column=1, sticky=tk.NSEW)

    def click_all(self) -> None:
        self.node_list.listbox.selection_set(0, self.node_list.listbox.size() - 1)

    def click_none(self) -> None:
        self.node_list.listbox.selection_clear(0, self.node_list.listbox.size() - 1)

    def click_run(self) -> None:
        """
        Run the command on each of the selected nodes and display the output to result
        text box.
        """
        command = self.cmd.get().strip()
        self.result.text.config(state=tk.NORMAL)
        self.result.text.delete("1.0", tk.END)
        for selection in self.node_list.listbox.curselection():
            node_name = self.node_list.listbox.get(selection)
            node_id = self.executable_nodes[node_name]
            _, output = self.app.core.client.node_command(
                self.app.core.session.id, node_id, command
            )
            self.result.text.insert(tk.END, f"> {node_name} > {command}:\n{output}\n")
        self.result.text.config(state=tk.DISABLED)
