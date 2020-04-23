import tkinter as tk
from tkinter import ttk

from core.gui.dialogs.dialog import Dialog
from core.gui.nodeutils import NodeUtils
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CodeText, ListboxScroll


class RunToolDialog(Dialog):
    def __init__(self, master, app) -> None:
        super().__init__(master, app, "Run Tool", modal=True)
        self.cmd = tk.StringVar(value="ps ax")
        self.app = app
        self.result = None
        self.node_list = None
        self.executable_nodes = {}
        self.store_nodes()
        self.draw()

    def store_nodes(self) -> None:
        """
        store all CORE nodes (nodes that execute commands) from all existing nodes
        """
        for nid, node in self.app.core.canvas_nodes.items():
            if NodeUtils.is_container_node(node.core_node.type):
                self.executable_nodes[node.core_node.name] = nid

    def draw(self) -> None:
        self.top.rowconfigure(0, weight=1)
        self.top.columnconfigure(0, weight=1)
        self.draw_command_frame()
        self.draw_nodes_frame()

    def draw_command_frame(self) -> None:
        # the main frame
        frame = ttk.Frame(self.top)
        frame.grid(row=0, column=0, sticky="nsew", padx=PADX)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        labeled_frame = ttk.LabelFrame(frame, text="Command", padding=FRAME_PAD)
        labeled_frame.grid(sticky="ew", pady=PADY)
        labeled_frame.rowconfigure(0, weight=1)
        labeled_frame.columnconfigure(0, weight=1)
        entry = ttk.Entry(labeled_frame, textvariable=self.cmd)
        entry.grid(sticky="ew")

        # results frame
        labeled_frame = ttk.LabelFrame(frame, text="Output", padding=FRAME_PAD)
        labeled_frame.grid(sticky="nsew", pady=PADY)
        labeled_frame.columnconfigure(0, weight=1)
        labeled_frame.rowconfigure(0, weight=1)

        self.result = CodeText(labeled_frame)
        self.result.text.config(state=tk.DISABLED, height=15)
        self.result.grid(sticky="nsew", pady=PADY)
        button_frame = ttk.Frame(labeled_frame)
        button_frame.grid(sticky="nsew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button = ttk.Button(button_frame, text="Run", command=self.click_run)
        button.grid(sticky="ew", padx=PADX)
        button = ttk.Button(button_frame, text="Close", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def draw_nodes_frame(self) -> None:
        labeled_frame = ttk.LabelFrame(self.top, text="Nodes", padding=FRAME_PAD)
        labeled_frame.grid(row=0, column=1, sticky="nsew")
        labeled_frame.columnconfigure(0, weight=1)
        labeled_frame.rowconfigure(0, weight=1)

        self.node_list = ListboxScroll(labeled_frame)
        self.node_list.listbox.config(selectmode=tk.MULTIPLE)
        self.node_list.grid(sticky="nsew", pady=PADY)
        for n in sorted(self.executable_nodes.keys()):
            self.node_list.listbox.insert(tk.END, n)

        button_frame = ttk.Frame(labeled_frame, padding=FRAME_PAD)
        button_frame.grid(sticky="nsew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        button = ttk.Button(button_frame, text="All", command=self.click_all)
        button.grid(sticky="nsew", padx=PADX)
        button = ttk.Button(button_frame, text="None", command=self.click_none)
        button.grid(row=0, column=1, sticky="nsew")

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
            response = self.app.core.client.node_command(
                self.app.core.session_id, node_id, command
            )
            self.result.text.insert(
                tk.END, f"> {node_name} > {command}:\n{response.output}\n"
            )
        self.result.text.config(state=tk.DISABLED)
