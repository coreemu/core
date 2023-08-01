import logging
import tkinter as tk
from functools import partial
from pathlib import Path
from tkinter import filedialog, font, ttk
from typing import TYPE_CHECKING, Any, Callable

from core.api.grpc.wrappers import ConfigOption, ConfigOptionType
from core.gui import appconfig, themes, validation
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application

INT_TYPES: set[ConfigOptionType] = {
    ConfigOptionType.UINT8,
    ConfigOptionType.UINT16,
    ConfigOptionType.UINT32,
    ConfigOptionType.UINT64,
    ConfigOptionType.INT8,
    ConfigOptionType.INT16,
    ConfigOptionType.INT32,
    ConfigOptionType.INT64,
}


def file_button_click(value: tk.StringVar, parent: tk.Widget) -> None:
    file_path = filedialog.askopenfilename(
        title="Select File", initialdir=str(appconfig.HOME_PATH), parent=parent
    )
    if file_path:
        value.set(file_path)


class FrameScroll(ttk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        app: "Application",
        _cls: type[ttk.Frame] = ttk.Frame,
        **kw: Any
    ) -> None:
        super().__init__(master, **kw)
        self.app: "Application" = app
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        bg = self.app.style.lookup(".", "background")
        self.canvas: tk.Canvas = tk.Canvas(self, highlightthickness=0, background=bg)
        self.canvas.grid(row=0, sticky=tk.NSEW, padx=2, pady=2)
        self.canvas.columnconfigure(0, weight=1)
        self.canvas.rowconfigure(0, weight=1)
        self.scrollbar: ttk.Scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.frame: ttk.Frame = _cls(self.canvas)
        self.frame_id: int = self.canvas.create_window(
            0, 0, anchor="nw", window=self.frame
        )
        self.canvas.update_idletasks()
        self.canvas.configure(
            scrollregion=self.canvas.bbox("all"), yscrollcommand=self.scrollbar.set
        )
        self.frame.bind("<Configure>", self._configure_frame)
        self.canvas.bind("<Configure>", self._configure_canvas)

    def _configure_frame(self, event: tk.Event) -> None:
        req_width = self.frame.winfo_reqwidth()
        if req_width != self.canvas.winfo_reqwidth():
            self.canvas.configure(width=req_width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _configure_canvas(self, event: tk.Event) -> None:
        self.canvas.itemconfig(self.frame_id, width=event.width)

    def clear(self) -> None:
        for widget in self.frame.winfo_children():
            widget.destroy()


class ConfigFrame(ttk.Notebook):
    def __init__(
        self,
        master: tk.Widget,
        app: "Application",
        config: dict[str, ConfigOption],
        enabled: bool = True,
        **kw: Any
    ) -> None:
        super().__init__(master, **kw)
        self.app: "Application" = app
        self.config: dict[str, ConfigOption] = config
        self.values: dict[str, tk.StringVar] = {}
        self.enabled: bool = enabled

    def draw_config(self) -> None:
        group_mapping = {}
        for key in self.config:
            option = self.config[key]
            group = group_mapping.setdefault(option.group, [])
            group.append(option)

        for group_name in sorted(group_mapping):
            group = group_mapping[group_name]
            tab = FrameScroll(self, self.app, borderwidth=0, padding=FRAME_PAD)
            tab.frame.columnconfigure(1, weight=1)
            self.add(tab, text=group_name)
            for index, option in enumerate(sorted(group, key=lambda x: x.name)):
                label = ttk.Label(tab.frame, text=option.label)
                label.grid(row=index, pady=PADY, padx=PADX, sticky=tk.W)
                value = tk.StringVar()
                if option.type == ConfigOptionType.BOOL:
                    select = ("On", "Off")
                    state = "readonly" if self.enabled else tk.DISABLED
                    combobox = ttk.Combobox(
                        tab.frame, textvariable=value, values=select, state=state
                    )
                    combobox.grid(row=index, column=1, sticky=tk.EW)
                    if option.value == "1":
                        value.set("On")
                    else:
                        value.set("Off")
                elif option.select:
                    value.set(option.value)
                    select = tuple(option.select)
                    state = "readonly" if self.enabled else tk.DISABLED
                    combobox = ttk.Combobox(
                        tab.frame, textvariable=value, values=select, state=state
                    )
                    combobox.grid(row=index, column=1, sticky=tk.EW)
                elif option.type == ConfigOptionType.STRING:
                    value.set(option.value)
                    state = tk.NORMAL if self.enabled else tk.DISABLED
                    if "file" in option.label:
                        file_frame = ttk.Frame(tab.frame)
                        file_frame.grid(row=index, column=1, sticky=tk.EW)
                        file_frame.columnconfigure(0, weight=1)
                        entry = ttk.Entry(file_frame, textvariable=value, state=state)
                        entry.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
                        func = partial(file_button_click, value, self)
                        button = ttk.Button(
                            file_frame, text="...", command=func, state=state
                        )
                        button.grid(row=0, column=1)
                    else:
                        entry = ttk.Entry(tab.frame, textvariable=value, state=state)
                        entry.grid(row=index, column=1, sticky=tk.EW)
                elif option.type in INT_TYPES:
                    value.set(option.value)
                    state = tk.NORMAL if self.enabled else tk.DISABLED
                    entry = validation.PositiveIntEntry(
                        tab.frame, textvariable=value, state=state
                    )
                    entry.grid(row=index, column=1, sticky=tk.EW)
                elif option.type == ConfigOptionType.FLOAT:
                    value.set(option.value)
                    state = tk.NORMAL if self.enabled else tk.DISABLED
                    entry = validation.PositiveFloatEntry(
                        tab.frame, textvariable=value, state=state
                    )
                    entry.grid(row=index, column=1, sticky=tk.EW)
                else:
                    logger.error("unhandled config option type: %s", option.type)
                self.values[option.name] = value

    def parse_config(self) -> dict[str, str]:
        for key in self.config:
            option = self.config[key]
            value = self.values[key]
            config_value = value.get()
            if option.type == ConfigOptionType.BOOL:
                if config_value == "On":
                    option.value = "1"
                else:
                    option.value = "0"
            else:
                option.value = config_value
        return {x: self.config[x].value for x in self.config}

    def set_values(self, config: dict[str, str]) -> None:
        for name, data in config.items():
            option = self.config[name]
            value = self.values[name]
            if option.type == ConfigOptionType.BOOL:
                if data == "1":
                    data = "On"
                else:
                    data = "Off"
            value.set(data)


class ListboxScroll(ttk.Frame):
    def __init__(self, master: tk.BaseWidget = None, **kw: Any) -> None:
        super().__init__(master, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scrollbar: ttk.Scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.listbox: tk.Listbox = tk.Listbox(
            self,
            selectmode=tk.BROWSE,
            yscrollcommand=self.scrollbar.set,
            exportselection=False,
        )
        themes.style_listbox(self.listbox)
        self.listbox.grid(row=0, column=0, sticky=tk.NSEW)
        self.scrollbar.config(command=self.listbox.yview)


class CheckboxList(FrameScroll):
    def __init__(
        self,
        master: ttk.Widget,
        app: "Application",
        clicked: Callable = None,
        **kw: Any
    ) -> None:
        super().__init__(master, app, **kw)
        self.clicked: Callable = clicked
        self.frame.columnconfigure(0, weight=1)

    def add(self, name: str, checked: bool) -> None:
        var = tk.BooleanVar(value=checked)
        func = partial(self.clicked, name, var)
        checkbox = ttk.Checkbutton(self.frame, text=name, variable=var, command=func)
        checkbox.grid(sticky=tk.W)


class CodeFont(font.Font):
    def __init__(self) -> None:
        super().__init__(font="TkFixedFont", color="green")


class CodeText(ttk.Frame):
    def __init__(self, master: tk.BaseWidget, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text: tk.Text = tk.Text(
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
        self.text.grid(row=0, column=0, sticky=tk.NSEW)
        yscrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
        yscrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.text.configure(yscrollcommand=yscrollbar.set)

    def get_text(self) -> str:
        return self.text.get(1.0, tk.END)

    def set_text(self, text: str) -> None:
        self.text.delete(1.0, tk.END)
        self.text.insert(tk.END, text.rstrip())


class Spinbox(ttk.Entry):
    def __init__(self, master: tk.BaseWidget = None, **kwargs: Any) -> None:
        super().__init__(master, "ttk::spinbox", **kwargs)

    def set(self, value: str) -> None:
        self.tk.call(self._w, "set", value)


def image_chooser(parent: Dialog, path: Path) -> str:
    return filedialog.askopenfilename(
        parent=parent,
        initialdir=str(path),
        title="Select",
        filetypes=(
            ("images", "*.gif *.jpg *.png *.bmp *pcx *.tga ..."),
            ("All Files", "*"),
        ),
    )
