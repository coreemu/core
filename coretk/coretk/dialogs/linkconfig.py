"""
link configuration
"""
import logging
import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog


class LinkConfiguration(Dialog):
    def __init__(self, master, app, edge):
        super().__init__(master, app, "link configuration", modal=True)
        self.app = app
        self.edge = edge
        self.is_symmetric = True
        if self.is_symmetric:
            self.symmetry_var = tk.StringVar(value=">>")
        else:
            self.symmetry_var = tk.StringVar(value="<<")

        self.bandwidth = tk.DoubleVar()
        self.delay = tk.DoubleVar()
        self.jitter = tk.DoubleVar()
        self.loss = tk.DoubleVar()
        self.duplicate = tk.DoubleVar()
        self.color = "#000000"
        self.width = tk.DoubleVar()

        self.down_bandwidth = tk.DoubleVar()
        self.down_delay = tk.DoubleVar()
        self.down_jitter = tk.DoubleVar()
        self.down_loss = tk.DoubleVar()
        self.down_duplicate = tk.DoubleVar()

        self.load_link_config()
        self.symmetric_frame = None
        self.asymmetric_frame = None

        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        source_name = self.app.canvas.nodes[self.edge.src].core_node.name
        dest_name = self.app.canvas.nodes[self.edge.dst].core_node.name
        label = ttk.Label(
            self.top,
            text="Link from %s to %s" % (source_name, dest_name),
            anchor=tk.CENTER,
        )
        label.grid(row=0, column=0, sticky="nsew")
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=1, column=0, sticky="nsew")
        button = ttk.Button(frame, text="unlimited")
        button.grid(row=0, column=0, sticky="nsew")
        if self.is_symmetric:
            button = ttk.Button(
                frame, textvariable=self.symmetry_var, command=self.change_symmetry
            )
        else:
            button = ttk.Button(
                frame, textvariable=self.symmetry_var, command=self.change_symmetry
            )
        button.grid(row=0, column=1, sticky="nsew")

        if self.is_symmetric:
            self.symmetric_frame = self.get_frame()
            self.symmetric_frame.grid(row=2, column=0, sticky="nsew")
        else:
            self.asymmetric_frame = self.get_frame()
            self.asymmetric_frame.grid(row=2, column=0, sticky="nsew")

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=3, column=0, sticky="nsew")

        button = ttk.Button(frame, text="Apply")
        button.grid(row=0, column=0, sticky="nsew")
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="nsew")

    def get_frame(self):
        main_frame = ttk.Frame(self.top)
        main_frame.columnconfigure(0, weight=1)
        if self.is_symmetric:
            label_name = "Symmetric link effects: "
        else:
            label_name = "Asymmetric effects: downstream / upstream "
        row = 0
        label = ttk.Label(main_frame, text=label_name, anchor=tk.CENTER)
        label.grid(row=row, column=0, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(main_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=row, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Bandwidth (bps): ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.bandwidth)
        entry.grid(row=0, column=1, sticky="nsew")
        if not self.is_symmetric:
            entry = ttk.Entry(frame, textvariable=self.down_bandwidth)
            entry.grid(row=0, column=2, sticky="nsew")

        row = row + 1

        frame = ttk.Frame(main_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=row, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Delay (us): ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.delay)
        entry.grid(row=0, column=1, sticky="nsew")
        if not self.is_symmetric:
            entry = ttk.Entry(frame, textvariable=self.down_delay)
            entry.grid(row=0, column=2, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(main_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=row, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Jitter (us): ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.jitter)
        entry.grid(row=0, column=1, sticky="nsew")
        if not self.is_symmetric:
            entry = ttk.Entry(frame, textvariable=self.down_jitter)
            entry.grid(row=0, column=2, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(main_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=row, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Loss (%): ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.loss)
        entry.grid(row=0, column=1, sticky="nsew")
        if not self.is_symmetric:
            entry = ttk.Entry(frame, textvariable=self.down_loss)
            entry.grid(row=0, column=1, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(main_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=row, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Duplicate (%): ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.duplicate)
        entry.grid(row=0, column=1, sticky="nsew")
        if not self.is_symmetric:
            entry = ttk.Entry(frame, textvariable=self.down_duplicate)
            entry.grid(row=0, column=1, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(main_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=row, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Color: ")
        label.grid(row=0, column=0, sticky="nsew")
        button = ttk.Button(frame, text=self.color)
        button.grid(row=0, column=1, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(main_frame)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=4)
        frame.grid(row=row, column=0, sticky="nsew")
        label = ttk.Label(frame, text="Width: ")
        label.grid(row=0, column=0, sticky="nsew")
        entry = ttk.Entry(frame, textvariable=self.width)
        entry.grid(row=0, column=1, sticky="nsew")

        return main_frame

    def apply(self):
        logging.debug("click apply")

    def change_symmetry(self):
        logging.debug("change symmetry")

        if self.is_symmetric:
            self.is_symmetric = False
            self.symmetry_var.set("<<")
            if not self.asymmetric_frame:
                self.asymmetric_frame = self.get_frame()
            self.symmetric_frame.grid_forget()
            self.asymmetric_frame.grid(row=2, column=0)
        else:
            self.is_symmetric = True
            self.symmetry_var.set(">>")
            if not self.symmetric_frame:
                self.symmetric_frame = self.get_frame()
            self.asymmetric_frame.grid_forget()
            self.symmetric_frame.grid(row=2, column=0)

    def load_link_config(self):
        """
        populate link config to the table

        :return: nothing
        """
        width = self.app.canvas.itemcget(self.edge.id, "width")
        self.width.set(width)
