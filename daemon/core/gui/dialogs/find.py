import logging
import tkinter as tk
from tkinter import ttk

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY


class FindDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Find", modal=True)

        self.find_text = tk.StringVar(value="")
        self.tree = None
        self.draw()
        self.protocol("WM_DELETE_WINDOW", self.close_dialog)
        self.bind("<Return>", self.find_node)

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=5)
        self.top.rowconfigure(2, weight=1)

        # Find node frame
        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.grid(sticky="nsew")
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Find:")
        label.grid()
        entry = ttk.Entry(frame, textvariable=self.find_text)
        entry.grid(row=0, column=1, sticky="nsew")

        # node list frame
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.grid(sticky="nsew", padx=PADX, pady=PADY)
        self.tree = ttk.Treeview(
            frame,
            columns=("nodeid", "name", "location", "detail"),
            show="headings",
            selectmode=tk.BROWSE,
        )
        self.tree.grid(sticky="nsew")
        style = ttk.Style()
        heading_size = int(self.app.guiconfig["scale"] * 10)
        style.configure("Treeview.Heading", font=(None, heading_size, "bold"))
        self.tree.column("nodeid", stretch=tk.YES, anchor="center")
        self.tree.heading("nodeid", text="Node ID")
        self.tree.column("name", stretch=tk.YES, anchor="center")
        self.tree.heading("name", text="Name")
        self.tree.column("location", stretch=tk.YES, anchor="center")
        self.tree.heading("location", text="Location")
        self.tree.column("detail", stretch=tk.YES, anchor="center")
        self.tree.heading("detail", text="Detail")

        self.tree.bind("<<TreeviewSelect>>", self.click_select)

        yscrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        yscrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscrollbar.set)

        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, sticky="ew")
        self.tree.configure(xscrollcommand=xscrollbar.set)

        # button frame
        frame = ttk.Frame(self.top)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="Find", command=self.find_node)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.close_dialog)
        button.grid(row=0, column=1, sticky="ew", padx=PADX)

    def clear_treeview_items(self):
        """
        clear all items in the treeview
        :return:
        """
        for i in list(self.tree.get_children("")):
            self.tree.delete(i)

    def find_node(self, event=None):
        """
        Query nodes that have the same node name as our search key,
        display results to tree view
        """
        node_name = self.find_text.get().strip()
        self.clear_treeview_items()
        for node_id, node in sorted(
            self.app.core.canvas_nodes.items(), key=lambda x: x[0]
        ):
            name = node.core_node.name
            if not node_name or node_name == name:
                location = f"<{node.core_node.position.x}, {node.core_node.position.y}>"
                # TODO I am not sure what to insert for Detail column, leaving in blank for now
                self.tree.insert(
                    "", tk.END, text=str(node_id), values=(node_id, name, location, "")
                )

        results = self.tree.get_children("")
        if results:
            self.tree.selection_set(results[0])

    def close_dialog(self):
        self.app.canvas.delete("find")
        self.destroy()

    def click_select(self, _event: tk.Event = None) -> None:
        item = self.tree.selection()
        if item:
            self.app.canvas.delete("find")
            node_id = int(self.tree.item(item, "text"))
            canvas_node = self.app.core.canvas_nodes[node_id]

            x0, y0, x1, y1 = self.app.canvas.bbox(canvas_node.id)
            dist = 5 * self.app.guiconfig["scale"]
            self.app.canvas.create_oval(
                x0 - dist,
                y0 - dist,
                x1 + dist,
                y1 + dist,
                tags="find",
                outline="red",
                width=3.0 * self.app.guiconfig["scale"],
            )

            _x, _y, _, _ = self.app.canvas.bbox(canvas_node.id)
            oid = self.app.canvas.find_withtag("rectangle")
            x0, y0, x1, y1 = self.app.canvas.bbox(oid[0])
            logging.debug("Dist to most left: %s", abs(x0 - _x))
            logging.debug("White canvas width: %s", abs(x0 - x1))

            # calculate the node's location
            # (as fractions of white canvas's width and height)
            # and instantly scroll the x and y scrollbar to that location

            xscroll_fraction = abs(x0 - _x) / abs(x0 - x1)
            yscroll_fraction = abs(y0 - _y) / abs(y0 - y1)
            self.app.canvas.xview_moveto(xscroll_fraction)
            self.app.canvas.yview_moveto(yscroll_fraction)
