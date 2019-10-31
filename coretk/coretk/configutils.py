import enum
import logging
import tkinter as tk
from tkinter import ttk


class ConfigType(enum.Enum):
    STRING = 10
    BOOL = 11


def create_config(master, config, pad_x=2, pad_y=2):
    master.columnconfigure(0, weight=1)
    master.columnconfigure(1, weight=3)
    values = {}
    for index, key in enumerate(sorted(config)):
        option = config[key]
        label = tk.Label(master, text=option.label)
        label.grid(row=index, pady=pad_y, padx=pad_x, sticky="ew")
        value = tk.StringVar()
        config_type = ConfigType(option.type)
        if config_type == ConfigType.BOOL:
            select = tuple(option.select)
            combobox = ttk.Combobox(master, textvariable=value, values=select)
            combobox.grid(row=index, column=1, sticky="ew", pady=pad_y)
            if option.value == "1":
                value.set("On")
            else:
                value.set("Off")
        elif config_type == ConfigType.STRING:
            entry = tk.Entry(master, textvariable=value)
            entry.grid(row=index, column=1, sticky="ew", pady=pad_y)
        else:
            logging.error("unhandled config option type: %s", config_type)
        values[key] = value
    return values


def parse_config(options, values):
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
