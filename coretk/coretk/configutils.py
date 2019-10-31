import enum
import logging
import tkinter as tk
from tkinter import ttk


class ConfigType(enum.Enum):
    STRING = 10
    BOOL = 11


def create_config(master, config, padx=2, pady=2):
    """
    Creates a scrollable canvas with an embedded window for displaying configuration
    options. Will use grid layout to consume row 0 and columns 0-2.

    :param master: master to add scrollable canvas to
    :param dict config: config option mapping keys to config options
    :param int padx: x padding for widgets
    :param int pady: y padding for widgets
    :return: widget value mapping
    """
    master.rowconfigure(0, weight=1)
    master.columnconfigure(0, weight=1)
    master.columnconfigure(1, weight=1)

    canvas = tk.Canvas(master)
    canvas.grid(row=0, columnspan=2, sticky="nsew", padx=padx, pady=pady)
    canvas.columnconfigure(0, weight=1)
    canvas.rowconfigure(0, weight=1)

    scroll_y = tk.Scrollbar(master, orient="vertical", command=canvas.yview)
    scroll_y.grid(row=0, column=2, sticky="ns")

    frame = tk.Frame(canvas, padx=padx, pady=pady)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=3)

    values = {}
    for index, key in enumerate(sorted(config)):
        option = config[key]
        label = tk.Label(frame, text=option.label)
        label.grid(row=index, pady=pady, padx=padx, sticky="ew")
        value = tk.StringVar()
        config_type = ConfigType(option.type)
        if config_type == ConfigType.BOOL:
            select = tuple(option.select)
            combobox = ttk.Combobox(frame, textvariable=value, values=select)
            combobox.grid(row=index, column=1, sticky="ew", pady=pady)
            if option.value == "1":
                value.set("On")
            else:
                value.set("Off")
        elif config_type == ConfigType.STRING:
            entry = tk.Entry(frame, textvariable=value)
            entry.grid(row=index, column=1, sticky="ew", pady=pady)
        else:
            logging.error("unhandled config option type: %s", config_type)
        values[key] = value

    frame_id = canvas.create_window(0, 0, anchor="nw", window=frame)
    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"), yscrollcommand=scroll_y.set)

    frame.bind(
        "<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.bind(
        "<Configure>", lambda event: canvas.itemconfig(frame_id, width=event.width)
    )

    return values


def parse_config(options, values):
    """
    Given a set of configurations, parse out values and transform them when needed.

    :param dict options: option key mapping to configuration options
    :param dict values: option key mapping to widget values
    :return:
    """
    config = {}
    for key in options:
        option = options[key]
        value = values[key]
        config_type = ConfigType(option.type)
        config_value = value.get()
        if config_type == ConfigType.BOOL:
            if config_value == "On":
                config_value = "1"
            else:
                config_value = "0"
        config[key] = config_value
    return config
