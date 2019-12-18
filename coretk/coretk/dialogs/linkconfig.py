"""
link configuration
"""
import logging
import tkinter as tk
from tkinter import ttk

from coretk.dialogs.colorpicker import ColorPicker
from coretk.dialogs.dialog import Dialog
from coretk.themes import PADX, PADY


class LinkConfiguration(Dialog):
    def __init__(self, master, app, edge):
        super().__init__(master, app, "Link Configuration", modal=True)
        self.app = app
        self.edge = edge
        self.is_symmetric = True
        if self.is_symmetric:
            self.symmetry_var = tk.StringVar(value=">>")
        else:
            self.symmetry_var = tk.StringVar(value="<<")

        self.bandwidth = tk.StringVar()
        self.delay = tk.StringVar()
        self.jitter = tk.StringVar()
        self.loss = tk.StringVar()
        self.duplicate = tk.StringVar()
        self.color = tk.StringVar(value="#000000")
        self.color_button = None
        self.width = tk.DoubleVar()

        self.down_bandwidth = tk.IntVar(value="")
        self.down_delay = tk.IntVar(value="")
        self.down_jitter = tk.IntVar(value="")
        self.down_loss = tk.DoubleVar(value="")
        self.down_duplicate = tk.IntVar(value="")

        self.load_link_config()
        self.symmetric_frame = None
        self.asymmetric_frame = None

        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        source_name = self.app.canvas.nodes[self.edge.src].core_node.name
        dest_name = self.app.canvas.nodes[self.edge.dst].core_node.name
        label = ttk.Label(
            self.top, text=f"Link from {source_name} to {dest_name}", anchor=tk.CENTER
        )
        label.grid(row=0, column=0, sticky="ew", pady=PADY)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=1, column=0, sticky="ew", pady=PADY)
        button = ttk.Button(frame, text="Unlimited")
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        if self.is_symmetric:
            button = ttk.Button(
                frame, textvariable=self.symmetry_var, command=self.change_symmetry
            )
        else:
            button = ttk.Button(
                frame, textvariable=self.symmetry_var, command=self.change_symmetry
            )
        button.grid(row=0, column=1, sticky="ew")

        if self.is_symmetric:
            self.symmetric_frame = self.get_frame()
            self.symmetric_frame.grid(row=2, column=0, sticky="ew", pady=PADY)
        else:
            self.asymmetric_frame = self.get_frame()
            self.asymmetric_frame.grid(row=2, column=0, sticky="ew", pady=PADY)

        self.draw_spacer(row=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=4, column=0, sticky="ew")
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def get_frame(self):
        frame = ttk.Frame(self.top)
        frame.columnconfigure(1, weight=1)
        if self.is_symmetric:
            label_name = "Symmetric Link Effects"
        else:
            label_name = "Asymmetric Effects: Downstream / Upstream "
        row = 0
        label = ttk.Label(frame, text=label_name, anchor=tk.CENTER)
        label.grid(row=row, column=0, columnspan=2, sticky="ew", pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Bandwidth (bps)")
        label.grid(row=row, column=0, sticky="ew")
        entry = ttk.Entry(
            frame,
            textvariable=self.bandwidth,
            validate="key",
            validatecommand=(self.app.validation.positive_int, "%P"),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=PADY)
        if not self.is_symmetric:
            entry = ttk.Entry(
                frame,
                textvariable=self.down_bandwidth,
                validate="key",
                validatecommand=(self.app.validation.positive_int, "%P"),
            )
            entry.grid(row=row, column=2, sticky="nsew")
        row = row + 1

        label = ttk.Label(frame, text="Delay (us)")
        label.grid(row=row, column=0, sticky="ew")
        entry = ttk.Entry(
            frame,
            textvariable=self.delay,
            validate="key",
            validatecommand=(self.app.validation.positive_int, "%P"),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=PADY)
        if not self.is_symmetric:
            entry = ttk.Entry(
                frame,
                textvariable=self.down_delay,
                validate="key",
                validatecommand=(self.app.validation.positive_int, "%P"),
            )
            entry.grid(row=row, column=2, sticky="ew")
        row = row + 1

        label = ttk.Label(frame, text="Jitter (us)")
        label.grid(row=row, column=0, sticky="ew")
        entry = ttk.Entry(
            frame,
            textvariable=self.jitter,
            validate="key",
            validatecommand=(self.app.validation.positive_int, "%P"),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=PADY)
        if not self.is_symmetric:
            entry = ttk.Entry(
                frame,
                textvariable=self.down_jitter,
                validate="key",
                validatecommand=(self.app.validation.positive_int, "%P"),
            )
            entry.grid(row=row, column=2, sticky="ew")
        row = row + 1

        label = ttk.Label(frame, text="Loss (%)")
        label.grid(row=row, column=0, sticky="ew")
        entry = ttk.Entry(
            frame,
            textvariable=self.loss,
            validate="key",
            validatecommand=(self.app.validation.positive_float, "%P"),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=PADY)
        if not self.is_symmetric:
            entry = ttk.Entry(
                frame,
                textvariable=self.down_loss,
                validate="key",
                validatecommand=(self.app.validation.positive_float, "%P"),
            )
            entry.grid(row=row, column=2, sticky="ew")
        row = row + 1

        label = ttk.Label(frame, text="Duplicate (%)")
        label.grid(row=row, column=0, sticky="ew")
        entry = ttk.Entry(
            frame,
            textvariable=self.duplicate,
            validate="key",
            validatecommand=(self.app.validation.positive_int, "%P"),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=PADY)
        if not self.is_symmetric:
            entry = ttk.Entry(
                frame,
                textvariable=self.down_duplicate,
                validate="key",
                validatecommand=(self.app.validation.positive_int, "%P"),
            )
            entry.grid(row=row, column=2, sticky="ew")
        row = row + 1

        label = ttk.Label(frame, text="Color")
        label.grid(row=row, column=0, sticky="ew")
        self.color_button = tk.Button(
            frame,
            textvariable=self.color,
            background=self.color.get(),
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            command=self.click_color,
        )
        self.color_button.grid(row=row, column=1, sticky="ew", pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Width")
        label.grid(row=row, column=0, sticky="ew")
        entry = ttk.Entry(
            frame,
            textvariable=self.width,
            validate="key",
            validatecommand=(self.app.validation.positive_float, "%P"),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=PADY)

        return frame

    def click_color(self):
        dialog = ColorPicker(self, self.app, self.color.get())
        color = dialog.askcolor()
        self.color.set(color)
        self.color_button.config(background=color)

    def click_apply(self):
        logging.debug("click apply")
        self.app.canvas.itemconfigure(self.edge.id, width=self.width.get())
        self.app.canvas.itemconfigure(self.edge.id, fill=self.color.get())
        link = self.edge.link_info.link
        bandwidth = self.bandwidth.get()
        if bandwidth != "":
            link.options.bandwidth = int(bandwidth)
        jitter = self.jitter.get()
        if jitter != "":
            link.options.jitter = int(jitter)
        delay = self.delay.get()
        if delay != "":
            link.options.delay = int(delay)
        duplicate = self.duplicate.get()
        if duplicate != "":
            link.options.dup = int(duplicate)
        loss = self.loss.get()
        if loss != "":
            link.options.per = float(loss)

        if self.app.core.is_runtime() and link.HasField("options"):
            interface_one = None
            if link.HasField("interface_one"):
                interface_one = link.interface_one.id
            interface_two = None
            if link.HasField("interface_two"):
                interface_two = link.interface_two.id
            session_id = self.app.core.session_id
            self.app.core.client.edit_link(
                session_id,
                link.node_one_id,
                link.node_two_id,
                link.options,
                interface_one,
                interface_two,
            )

        self.destroy()

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
        color = self.app.canvas.itemcget(self.edge.id, "fill")
        self.color.set(color)
        link = self.edge.link_info.link
        if link.HasField("options"):
            self.bandwidth.set(str(link.options.bandwidth))
            self.jitter.set(str(link.options.jitter))
            self.duplicate.set(str(link.options.dup))
            self.loss.set(str(link.options.per))
            self.delay.set(str(link.options.delay))
