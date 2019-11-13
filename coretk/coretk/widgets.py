import logging
import tkinter as tk
from functools import partial
from tkinter import ttk

from core.api.grpc import core_pb2

INT_TYPES = {
    core_pb2.ConfigOptionType.UINT8,
    core_pb2.ConfigOptionType.UINT16,
    core_pb2.ConfigOptionType.UINT32,
    core_pb2.ConfigOptionType.UINT64,
    core_pb2.ConfigOptionType.INT8,
    core_pb2.ConfigOptionType.INT16,
    core_pb2.ConfigOptionType.INT32,
    core_pb2.ConfigOptionType.INT64,
}


class FrameScroll(ttk.LabelFrame):
    def __init__(self, master=None, _cls=tk.Frame, **kw):
        super().__init__(master, **kw)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.grid(row=0, sticky="nsew", padx=2, pady=2)
        self.canvas.columnconfigure(0, weight=1)
        self.canvas.rowconfigure(0, weight=1)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.frame = _cls(self.canvas)
        self.frame_id = self.canvas.create_window(0, 0, anchor="nw", window=self.frame)
        self.canvas.update_idletasks()
        self.canvas.configure(
            scrollregion=self.canvas.bbox("all"), yscrollcommand=self.scrollbar.set
        )
        self.frame.bind("<Configure>", self._configure_frame)
        self.canvas.bind("<Configure>", self._configure_canvas)

    def _configure_frame(self, event):
        req_width = self.frame.winfo_reqwidth()
        if req_width != self.canvas.winfo_reqwidth():
            self.canvas.configure(width=req_width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _configure_canvas(self, event):
        self.canvas.itemconfig(self.frame_id, width=event.width)

    def clear(self):
        for widget in self.frame.winfo_children():
            widget.destroy()


class ConfigFrame(FrameScroll):
    def __init__(self, master=None, config=None, **kw):
        super().__init__(master, ttk.Notebook, **kw)
        self.config = config
        self.values = {}

    def draw_config(self):
        padx = 2
        pady = 2
        group_mapping = {}
        for key in self.config:
            option = self.config[key]
            group = group_mapping.setdefault(option.group, [])
            group.append(option)

        for group_name in sorted(group_mapping):
            group = group_mapping[group_name]
            frame = ttk.Frame(self.frame)
            frame.columnconfigure(1, weight=1)
            self.frame.add(frame, text=group_name)
            for index, option in enumerate(sorted(group, key=lambda x: x.name)):
                label = ttk.Label(frame, text=option.label)
                label.grid(row=index, pady=pady, padx=padx, sticky="w")
                value = tk.StringVar()
                if option.type == core_pb2.ConfigOptionType.BOOL:
                    select = tuple(option.select)
                    combobox = ttk.Combobox(
                        frame, textvariable=value, values=select, state="readonly"
                    )
                    combobox.grid(row=index, column=1, sticky="ew", pady=pady)
                    if option.value == "1":
                        value.set("On")
                    else:
                        value.set("Off")
                elif option.select:
                    value.set(option.value)
                    select = tuple(option.select)
                    combobox = ttk.Combobox(
                        frame, textvariable=value, values=select, state="readonly"
                    )
                    combobox.grid(row=index, column=1, sticky="ew", pady=pady)
                elif option.type == core_pb2.ConfigOptionType.STRING:
                    value.set(option.value)
                    entry = ttk.Entry(frame, textvariable=value)
                    entry.grid(row=index, column=1, sticky="ew", pady=pady)
                elif option.type in INT_TYPES:
                    value.set(option.value)
                    entry = ttk.Entry(frame, textvariable=value)
                    entry.grid(row=index, column=1, sticky="ew", pady=pady)
                elif option.type == core_pb2.ConfigOptionType.FLOAT:
                    value.set(option.value)
                    entry = ttk.Entry(frame, textvariable=value)
                    entry.grid(row=index, column=1, sticky="ew", pady=pady)
                else:
                    logging.error("unhandled config option type: %s", option.type)
                self.values[option.name] = value

    def parse_config(self):
        for key in self.config:
            option = self.config[key]
            value = self.values[key]
            config_value = value.get()
            if option.type == core_pb2.ConfigOptionType.BOOL:
                if config_value == "On":
                    option.value = "1"
                else:
                    option.value = "0"
            else:
                option.value = config_value

        return {x: self.config[x].value for x in self.config}


class ListboxScroll(ttk.LabelFrame):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox = tk.Listbox(
            self, selectmode=tk.SINGLE, yscrollcommand=self.scrollbar.set
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.config(command=self.listbox.yview)


class CheckboxList(FrameScroll):
    def __init__(self, master=None, clicked=None, **kw):
        super().__init__(master, **kw)
        self.clicked = clicked
        self.frame.columnconfigure(0, weight=1)

    def add(self, name, checked):
        var = tk.BooleanVar(value=checked)
        func = partial(self.clicked, name, var)
        checkbox = ttk.Checkbutton(self.frame, text=name, variable=var, command=func)
        checkbox.grid(sticky="w")
