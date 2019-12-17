import logging
import tkinter as tk
from functools import partial
from tkinter import filedialog, font, ttk

from core.api.grpc import core_pb2
from coretk import themes
from coretk.appconfig import ICONS_PATH
from coretk.themes import FRAME_PAD, PADX, PADY

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


def file_button_click(value):
    file_path = filedialog.askopenfilename(title="Select File")
    if file_path:
        value.set(file_path)


class FrameScroll(ttk.LabelFrame):
    def __init__(self, master, app, _cls=ttk.Frame, **kw):
        super().__init__(master, **kw)
        self.app = app
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        bg = self.app.style.lookup(".", "background")
        self.canvas = tk.Canvas(self, highlightthickness=0, background=bg)
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
    def __init__(self, master, app, config, **kw):
        super().__init__(master, app, ttk.Notebook, borderwidth=0, **kw)
        self.app = app
        self.config = config
        self.values = {}

    def draw_config(self):
        group_mapping = {}
        for key in self.config:
            option = self.config[key]
            group = group_mapping.setdefault(option.group, [])
            group.append(option)

        for group_name in sorted(group_mapping):
            group = group_mapping[group_name]
            frame = ttk.Frame(self.frame, padding=FRAME_PAD)
            frame.columnconfigure(1, weight=1)
            self.frame.add(frame, text=group_name)
            for index, option in enumerate(sorted(group, key=lambda x: x.name)):
                label = ttk.Label(frame, text=option.label)
                label.grid(row=index, pady=PADY, padx=PADX, sticky="w")
                value = tk.StringVar()
                if option.type == core_pb2.ConfigOptionType.BOOL:
                    select = tuple(option.select)
                    combobox = ttk.Combobox(
                        frame, textvariable=value, values=select, state="readonly"
                    )
                    combobox.grid(row=index, column=1, sticky="ew")
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
                    combobox.grid(row=index, column=1, sticky="ew")
                elif option.type == core_pb2.ConfigOptionType.STRING:
                    value.set(option.value)
                    if "file" in option.label:
                        file_frame = ttk.Frame(frame)
                        file_frame.grid(row=index, column=1, sticky="ew")
                        file_frame.columnconfigure(0, weight=1)
                        entry = ttk.Entry(file_frame, textvariable=value)
                        entry.grid(row=0, column=0, sticky="ew", padx=PADX)
                        func = partial(file_button_click, value)
                        button = ttk.Button(file_frame, text="...", command=func)
                        button.grid(row=0, column=1)
                    else:
                        if "controlnet" in option.name and "script" not in option.name:
                            entry = ttk.Entry(
                                frame,
                                textvariable=value,
                                validate="key",
                                validatecommand=(self.app.validation.ip4, "%P"),
                            )
                            entry.grid(row=index, column=1, sticky="ew")
                        else:
                            entry = ttk.Entry(frame, textvariable=value)
                            entry.grid(row=index, column=1, sticky="ew")

                elif option.type in INT_TYPES:
                    value.set(option.value)
                    entry = ttk.Entry(
                        frame,
                        textvariable=value,
                        validate="key",
                        validatecommand=(self.app.validation.positive_int, "%P"),
                    )
                    entry.bind(
                        "<FocusOut>",
                        lambda event: self.app.validation.focus_out(event, "0"),
                    )
                    entry.grid(row=index, column=1, sticky="ew")
                elif option.type == core_pb2.ConfigOptionType.FLOAT:
                    value.set(option.value)
                    entry = ttk.Entry(
                        frame,
                        textvariable=value,
                        validate="key",
                        validatecommand=(self.app.validation.positive_float, "%P"),
                    )
                    entry.bind(
                        "<FocusOut>",
                        lambda event: self.app.validation.focus_out(event, "0"),
                    )
                    entry.grid(row=index, column=1, sticky="ew")
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


class ListboxScroll(ttk.Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox = tk.Listbox(
            self, selectmode=tk.SINGLE, yscrollcommand=self.scrollbar.set
        )
        themes.style_listbox(self.listbox)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.config(command=self.listbox.yview)


class CheckboxList(FrameScroll):
    def __init__(self, master, app, clicked=None, **kw):
        super().__init__(master, app, **kw)
        self.clicked = clicked
        self.frame.columnconfigure(0, weight=1)

    def add(self, name, checked):
        var = tk.BooleanVar(value=checked)
        func = partial(self.clicked, name, var)
        checkbox = ttk.Checkbutton(self.frame, text=name, variable=var, command=func)
        checkbox.grid(sticky="w")


class CodeFont(font.Font):
    def __init__(self):
        super().__init__(font="TkFixedFont", color="green")


class CodeText(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text = tk.Text(
            self,
            bd=0,
            bg="black",
            cursor="xterm lime lime",
            fg="lime",
            font=CodeFont(),
            highlightbackground="black",
            insertbackground="lime",
            selectbackground="lime",
            selectforeground="black",
            relief=tk.FLAT,
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        yscrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
        yscrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=yscrollbar.set)


class Spinbox(ttk.Entry):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, "ttk::spinbox", **kwargs)

    def set(self, value):
        self.tk.call(self._w, "set", value)


def image_chooser(parent):
    return filedialog.askopenfilename(
        parent=parent,
        initialdir=str(ICONS_PATH),
        title="Select Icon",
        filetypes=(
            ("images", "*.gif *.jpg *.png *.bmp *pcx *.tga ..."),
            ("All Files", "*"),
        ),
    )
