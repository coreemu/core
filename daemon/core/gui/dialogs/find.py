import logging
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application


class FindDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Find", modal=False)
        self.find_text: tk.StringVar = tk.StringVar(value="")
        self.tree: Optional[ttk.Treeview] = None
        self.draw()
        self.protocol("WM_DELETE_WINDOW", self.close_dialog)
        self.bind("<Return>", self.find_node)

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)

        # Find node frame
        frame = ttk.Frame(self.top, padding=FRAME_PAD)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Find:")
        label.grid()
        entry = ttk.Entry(frame, textvariable=self.find_text)
        entry.grid(row=0, column=1, sticky=tk.NSEW)

        # node list frame
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.grid(sticky=tk.NSEW, pady=PADY)
        self.tree = ttk.Treeview(
            frame,
            columns=("nodeid", "name", "location", "detail"),
            show="headings",
            selectmode=tk.BROWSE,
        )
        self.tree.grid(sticky=tk.NSEW, pady=PADY)
        style = ttk.Style()
        heading_size = int(self.app.guiconfig.scale * 10)
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
        yscrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.tree.configure(yscrollcommand=yscrollbar.set)
        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, sticky=tk.EW)
        self.tree.configure(xscrollcommand=xscrollbar.set)

        # button frame
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="Find", command=self.find_node)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.close_dialog)
        button.grid(row=0, column=1, sticky=tk.EW)

    def clear_treeview_items(self) -> None:
        """
        clear all items in the treeview
        """
        for i in list(self.tree.get_children("")):
            self.tree.delete(i)

    def find_node(self, _event: tk.Event = None) -> None:
        """
        Query nodes that have the same node name as our search key,
        display results to tree view
        """
        node_name = self.find_text.get().strip()
        self.clear_treeview_items()
        for node in self.app.core.session.nodes.values():
            name = node.name
            if not node_name or node_name == name:
                pos_x = round(node.position.x, 1)
                pos_y = round(node.position.y, 1)
                # TODO: I am not sure what to insert for Detail column
                #  leaving it blank for now
                self.tree.insert(
                    "",
                    tk.END,
                    text=str(node.id),
                    values=(node.id, name, f"<{pos_x}, {pos_y}>", ""),
                )
        results = self.tree.get_children("")
        if results:
            self.tree.selection_set(results[0])

    def close_dialog(self) -> None:
        self.clear_find()
        self.destroy()

    def clear_find(self):
        for canvas in self.app.manager.all():
            canvas.delete("find")

    def click_select(self, _event: tk.Event = None) -> None:
        """
        find the node that matches search criteria, circle around that node
        and scroll the x and y scrollbar to be able to see the node if
        it is out of sight
        """
        item = self.tree.selection()
        if item:
            self.clear_find()
            node_id = int(self.tree.item(item, "text"))
            canvas_node = self.app.core.get_canvas_node(node_id)
            self.app.manager.select(canvas_node.canvas.id)
            x0, y0, x1, y1 = canvas_node.canvas.bbox(canvas_node.id)
            dist = 5 * self.app.guiconfig.scale
            canvas_node.canvas.create_oval(
                x0 - dist,
                y0 - dist,
                x1 + dist,
                y1 + dist,
                tags="find",
                outline="red",
                width=3.0 * self.app.guiconfig.scale,
            )

            _x, _y, _, _ = canvas_node.canvas.bbox(canvas_node.id)
            oid = canvas_node.canvas.find_withtag("rectangle")
            x0, y0, x1, y1 = canvas_node.canvas.bbox(oid[0])
            logger.debug("Dist to most left: %s", abs(x0 - _x))
            logger.debug("White canvas width: %s", abs(x0 - x1))

            # calculate the node's location
            # (as fractions of white canvas's width and height)
            # and instantly scroll the x and y scrollbar to that location
            xscroll_fraction = abs(x0 - _x) / abs(x0 - x1)
            yscroll_fraction = abs(y0 - _y) / abs(y0 - y1)
            # scroll a little more to the left or a little bit up so that the node
            # doesn't always fall in the most top-left corner
            for i in range(2):
                if xscroll_fraction > 0.05:
                    xscroll_fraction = xscroll_fraction - 0.05
                if yscroll_fraction > 0.05:
                    yscroll_fraction = yscroll_fraction - 0.05
            canvas_node.canvas.xview_moveto(xscroll_fraction)
            canvas_node.canvas.yview_moveto(yscroll_fraction)
