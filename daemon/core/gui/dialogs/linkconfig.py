"""
link configuration
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from core.api.grpc.wrappers import Interface, Link, LinkOptions
from core.gui import validation
from core.gui.dialogs.colorpicker import ColorPickerDialog
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.graph import CanvasEdge


def get_int(var: tk.StringVar) -> Optional[int]:
    value = var.get()
    if value != "":
        return int(value)
    else:
        return 0


def get_float(var: tk.StringVar) -> Optional[float]:
    value = var.get()
    if value != "":
        return float(value)
    else:
        return 0.0


class LinkConfigurationDialog(Dialog):
    def __init__(self, app: "Application", edge: "CanvasEdge") -> None:
        super().__init__(app, "Link Configuration")
        self.edge: "CanvasEdge" = edge

        self.is_symmetric: bool = edge.link.is_symmetric()
        if self.is_symmetric:
            symmetry_var = tk.StringVar(value=">>")
        else:
            symmetry_var = tk.StringVar(value="<<")
        self.symmetry_var: tk.StringVar = symmetry_var

        self.bandwidth: tk.StringVar = tk.StringVar()
        self.delay: tk.StringVar = tk.StringVar()
        self.jitter: tk.StringVar = tk.StringVar()
        self.loss: tk.StringVar = tk.StringVar()
        self.duplicate: tk.StringVar = tk.StringVar()
        self.buffer: tk.StringVar = tk.StringVar()

        self.down_bandwidth: tk.StringVar = tk.StringVar()
        self.down_delay: tk.StringVar = tk.StringVar()
        self.down_jitter: tk.StringVar = tk.StringVar()
        self.down_loss: tk.StringVar = tk.StringVar()
        self.down_duplicate: tk.StringVar = tk.StringVar()
        self.down_buffer: tk.StringVar = tk.StringVar()

        self.color: tk.StringVar = tk.StringVar(value=self.edge.color)
        self.color_button: Optional[tk.Button] = None
        self.width: tk.DoubleVar = tk.DoubleVar(value=self.edge.width)

        self.load_link_config()
        self.symmetric_frame: Optional[ttk.Frame] = None
        self.asymmetric_frame: Optional[ttk.Frame] = None

        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        src_label = self.edge.src.core_node.name
        if self.edge.link.iface1:
            src_label += f":{self.edge.link.iface1.name}"
        dst_label = self.edge.dst.core_node.name
        if self.edge.link.iface2:
            dst_label += f":{self.edge.link.iface2.name}"
        label = ttk.Label(
            self.top, text=f"{src_label} to {dst_label}", anchor=tk.CENTER
        )
        label.grid(row=0, column=0, sticky=tk.EW, pady=PADY)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.grid(row=1, column=0, sticky=tk.EW, pady=PADY)
        if self.is_symmetric:
            button = ttk.Button(
                frame, textvariable=self.symmetry_var, command=self.change_symmetry
            )
        else:
            button = ttk.Button(
                frame, textvariable=self.symmetry_var, command=self.change_symmetry
            )
        button.grid(sticky=tk.EW)

        if self.is_symmetric:
            self.symmetric_frame = self.get_frame()
            self.symmetric_frame.grid(row=2, column=0, sticky=tk.EW, pady=PADY)
        else:
            self.asymmetric_frame = self.get_frame()
            self.asymmetric_frame.grid(row=2, column=0, sticky=tk.EW, pady=PADY)

        self.draw_spacer(row=3)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=4, column=0, sticky=tk.EW)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def get_frame(self) -> ttk.Frame:
        frame = ttk.Frame(self.top)
        frame.columnconfigure(1, weight=1)
        if self.is_symmetric:
            label_name = "Symmetric Link Effects"
        else:
            label_name = "Asymmetric Effects: Downstream / Upstream "
        row = 0
        label = ttk.Label(frame, text=label_name, anchor=tk.CENTER)
        label.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Bandwidth (bps)")
        label.grid(row=row, column=0, sticky=tk.EW)
        entry = validation.PositiveIntEntry(
            frame, empty_enabled=False, textvariable=self.bandwidth
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=PADY)
        if not self.is_symmetric:
            entry = validation.PositiveIntEntry(
                frame, empty_enabled=False, textvariable=self.down_bandwidth
            )
            entry.grid(row=row, column=2, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Delay (us)")
        label.grid(row=row, column=0, sticky=tk.EW)
        entry = validation.PositiveIntEntry(
            frame, empty_enabled=False, textvariable=self.delay
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=PADY)
        if not self.is_symmetric:
            entry = validation.PositiveIntEntry(
                frame, empty_enabled=False, textvariable=self.down_delay
            )
            entry.grid(row=row, column=2, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Jitter (us)")
        label.grid(row=row, column=0, sticky=tk.EW)
        entry = validation.PositiveIntEntry(
            frame, empty_enabled=False, textvariable=self.jitter
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=PADY)
        if not self.is_symmetric:
            entry = validation.PositiveIntEntry(
                frame, empty_enabled=False, textvariable=self.down_jitter
            )
            entry.grid(row=row, column=2, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Loss (%)")
        label.grid(row=row, column=0, sticky=tk.EW)
        entry = validation.PositiveFloatEntry(
            frame, empty_enabled=False, textvariable=self.loss
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=PADY)
        if not self.is_symmetric:
            entry = validation.PositiveFloatEntry(
                frame, empty_enabled=False, textvariable=self.down_loss
            )
            entry.grid(row=row, column=2, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Duplicate (%)")
        label.grid(row=row, column=0, sticky=tk.EW)
        entry = validation.PositiveIntEntry(
            frame, empty_enabled=False, textvariable=self.duplicate
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=PADY)
        if not self.is_symmetric:
            entry = validation.PositiveIntEntry(
                frame, empty_enabled=False, textvariable=self.down_duplicate
            )
            entry.grid(row=row, column=2, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Buffer (Packets)")
        label.grid(row=row, column=0, sticky=tk.EW)
        entry = validation.PositiveIntEntry(
            frame, empty_enabled=False, textvariable=self.buffer
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=PADY)
        if not self.is_symmetric:
            entry = validation.PositiveIntEntry(
                frame, empty_enabled=False, textvariable=self.down_buffer
            )
            entry.grid(row=row, column=2, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Color")
        label.grid(row=row, column=0, sticky=tk.EW)
        self.color_button = tk.Button(
            frame,
            textvariable=self.color,
            background=self.color.get(),
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            command=self.click_color,
        )
        self.color_button.grid(row=row, column=1, sticky=tk.EW, pady=PADY)
        row = row + 1

        label = ttk.Label(frame, text="Width")
        label.grid(row=row, column=0, sticky=tk.EW)
        entry = validation.PositiveFloatEntry(
            frame, empty_enabled=False, textvariable=self.width
        )
        entry.grid(row=row, column=1, sticky=tk.EW, pady=PADY)

        return frame

    def click_color(self) -> None:
        dialog = ColorPickerDialog(self, self.app, self.color.get())
        color = dialog.askcolor()
        self.color.set(color)
        self.color_button.config(background=color)

    def click_apply(self) -> None:
        self.edge.width = self.width.get()
        self.edge.color = self.color.get()
        link = self.edge.link
        bandwidth = get_int(self.bandwidth)
        jitter = get_int(self.jitter)
        delay = get_int(self.delay)
        duplicate = get_int(self.duplicate)
        buffer = get_int(self.buffer)
        loss = get_float(self.loss)
        options = LinkOptions(
            bandwidth=bandwidth,
            jitter=jitter,
            delay=delay,
            dup=duplicate,
            loss=loss,
            buffer=buffer,
        )
        link.options = options
        iface1_id = link.iface1.id if link.iface1 else None
        iface2_id = link.iface2.id if link.iface2 else None
        if not self.is_symmetric:
            link.options.unidirectional = True
            asym_iface1 = None
            if iface1_id is not None:
                asym_iface1 = Interface(id=iface1_id)
            asym_iface2 = None
            if iface2_id is not None:
                asym_iface2 = Interface(id=iface2_id)
            down_bandwidth = get_int(self.down_bandwidth)
            down_jitter = get_int(self.down_jitter)
            down_delay = get_int(self.down_delay)
            down_duplicate = get_int(self.down_duplicate)
            down_buffer = get_int(self.down_buffer)
            down_loss = get_float(self.down_loss)
            options = LinkOptions(
                bandwidth=down_bandwidth,
                jitter=down_jitter,
                delay=down_delay,
                dup=down_duplicate,
                loss=down_loss,
                buffer=down_buffer,
                unidirectional=True,
            )
            self.edge.asymmetric_link = Link(
                node1_id=link.node2_id,
                node2_id=link.node1_id,
                iface1=asym_iface2,
                iface2=asym_iface1,
                options=options,
            )
        else:
            link.options.unidirectional = False
            self.edge.asymmetric_link = None

        if self.app.core.is_runtime() and link.options:
            self.app.core.edit_link(link)
            if self.edge.asymmetric_link:
                self.app.core.edit_link(self.edge.asymmetric_link)

        # update edge label
        self.edge.redraw()
        self.edge.check_visibility()
        self.destroy()

    def change_symmetry(self) -> None:
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

    def load_link_config(self) -> None:
        """
        populate link config to the table
        """
        self.width.set(self.edge.width)
        self.color.set(self.edge.color)
        link = self.edge.link
        if link.options:
            self.bandwidth.set(str(link.options.bandwidth))
            self.jitter.set(str(link.options.jitter))
            self.duplicate.set(str(link.options.dup))
            self.loss.set(str(link.options.loss))
            self.delay.set(str(link.options.delay))
            self.buffer.set(str(link.options.buffer))
        if not self.is_symmetric:
            asym_link = self.edge.asymmetric_link
            self.down_bandwidth.set(str(asym_link.options.bandwidth))
            self.down_jitter.set(str(asym_link.options.jitter))
            self.down_duplicate.set(str(asym_link.options.dup))
            self.down_loss.set(str(asym_link.options.loss))
            self.down_delay.set(str(asym_link.options.delay))
            self.down_buffer.set(str(asym_link.options.buffer))
