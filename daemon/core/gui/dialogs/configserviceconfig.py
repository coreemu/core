"""
Service configuration dialog
"""
import logging
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any, List

import grpc

from core.api.grpc.services_pb2 import ServiceValidationMode
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CodeText, ConfigFrame, ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode


class ConfigServiceConfigDialog(Dialog):
    def __init__(
        self,
        master: Any,
        app: "Application",
        service_name: str,
        canvas_node: "CanvasNode",
        node_id: int,
    ):
        title = f"{service_name} Config Service"
        super().__init__(master, app, title)
        self.master = master
        self.app = app
        self.core = app.core
        self.canvas_node = canvas_node
        self.node_id = node_id
        self.service_name = service_name
        self.radiovar = tk.IntVar()
        self.radiovar.set(2)
        self.directories = []
        self.templates = []
        self.dependencies = []
        self.executables = []
        self.startup_commands = []
        self.validation_commands = []
        self.shutdown_commands = []
        self.default_startup = []
        self.default_validate = []
        self.default_shutdown = []
        self.validation_mode = None
        self.validation_time = None
        self.validation_period = tk.StringVar()
        self.modes = []
        self.mode_configs = {}

        self.notebook = None
        self.templates_combobox = None
        self.modes_combobox = None
        self.startup_commands_listbox = None
        self.shutdown_commands_listbox = None
        self.validate_commands_listbox = None
        self.validation_time_entry = None
        self.validation_mode_entry = None
        self.template_text = None
        self.validation_period_entry = None
        self.original_service_files = {}
        self.temp_service_files = {}
        self.modified_files = set()
        self.config_frame = None
        self.default_config = None
        self.config = None

        self.has_error = False

        self.load()

        if not self.has_error:
            self.draw()

    def load(self):
        try:
            self.core.create_nodes_and_links()
            service = self.core.config_services[self.service_name]
            self.dependencies = service.dependencies[:]
            self.executables = service.executables[:]
            self.directories = service.directories[:]
            self.templates = service.files[:]
            self.startup_commands = service.startup[:]
            self.validation_commands = service.validate[:]
            self.shutdown_commands = service.shutdown[:]
            self.validation_mode = service.validation_mode
            self.validation_time = service.validation_timer
            self.validation_period.set(service.validation_period)

            response = self.core.client.get_config_service_defaults(self.service_name)
            self.original_service_files = response.templates
            self.temp_service_files = dict(self.original_service_files)

            self.modes = sorted(x.name for x in response.modes)
            self.mode_configs = {x.name: x.config for x in response.modes}

            service_config = self.canvas_node.config_service_configs.get(
                self.service_name, {}
            )
            self.config = response.config
            self.default_config = {x.name: x.value for x in self.config.values()}
            custom_config = service_config.get("config")
            if custom_config:
                for key, value in custom_config.items():
                    self.config[key].value = value
            logging.info("default config: %s", self.default_config)

            custom_templates = service_config.get("templates", {})
            for file, data in custom_templates.items():
                self.modified_files.add(file)
                self.temp_service_files[file] = data
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Get Config Service Error", e)
            self.has_error = True

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        # draw notebook
        self.notebook = ttk.Notebook(self.top)
        self.notebook.grid(sticky="nsew", pady=PADY)
        self.draw_tab_files()
        if self.config:
            self.draw_tab_config()
        self.draw_tab_startstop()
        self.draw_tab_validation()
        self.draw_buttons()

    def draw_tab_files(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Directories/Files")

        label = ttk.Label(
            tab, text="Directories and templates that will be used for this service."
        )
        label.grid(pady=PADY)

        frame = ttk.Frame(tab)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Directories")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        directories_combobox = ttk.Combobox(
            frame, values=self.directories, state="readonly"
        )
        directories_combobox.grid(row=0, column=1, sticky="ew", pady=PADY)
        if self.directories:
            directories_combobox.current(0)

        label = ttk.Label(frame, text="Templates")
        label.grid(row=1, column=0, sticky="w", padx=PADX)
        self.templates_combobox = ttk.Combobox(
            frame, values=self.templates, state="readonly"
        )
        self.templates_combobox.bind(
            "<<ComboboxSelected>>", self.handle_template_changed
        )
        self.templates_combobox.grid(row=1, column=1, sticky="ew", pady=PADY)

        self.template_text = CodeText(tab)
        self.template_text.grid(sticky="nsew")
        tab.rowconfigure(self.template_text.grid_info()["row"], weight=1)
        if self.templates:
            self.templates_combobox.current(0)
            self.template_text.text.delete(1.0, "end")
            self.template_text.text.insert(
                "end", self.temp_service_files[self.templates[0]]
            )
        self.template_text.text.bind("<FocusOut>", self.update_template_file_data)

    def draw_tab_config(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Configuration")

        if self.modes:
            frame = ttk.Frame(tab)
            frame.grid(sticky="ew", pady=PADY)
            frame.columnconfigure(1, weight=1)
            label = ttk.Label(frame, text="Modes")
            label.grid(row=0, column=0, padx=PADX)
            self.modes_combobox = ttk.Combobox(
                frame, values=self.modes, state="readonly"
            )
            self.modes_combobox.bind("<<ComboboxSelected>>", self.handle_mode_changed)
            self.modes_combobox.grid(row=0, column=1, sticky="ew", pady=PADY)

        logging.info("config service config: %s", self.config)
        self.config_frame = ConfigFrame(tab, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PADY)
        tab.rowconfigure(self.config_frame.grid_info()["row"], weight=1)

    def draw_tab_startstop(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        for i in range(3):
            tab.rowconfigure(i, weight=1)
        self.notebook.add(tab, text="Startup/Shutdown")
        commands = []
        # tab 3
        for i in range(3):
            label_frame = None
            if i == 0:
                label_frame = ttk.LabelFrame(
                    tab, text="Startup Commands", padding=FRAME_PAD
                )
                commands = self.startup_commands
            elif i == 1:
                label_frame = ttk.LabelFrame(
                    tab, text="Shutdown Commands", padding=FRAME_PAD
                )
                commands = self.shutdown_commands
            elif i == 2:
                label_frame = ttk.LabelFrame(
                    tab, text="Validation Commands", padding=FRAME_PAD
                )
                commands = self.validation_commands
            label_frame.columnconfigure(0, weight=1)
            label_frame.rowconfigure(0, weight=1)
            label_frame.grid(row=i, column=0, sticky="nsew", pady=PADY)
            listbox_scroll = ListboxScroll(label_frame)
            for command in commands:
                listbox_scroll.listbox.insert("end", command)
            listbox_scroll.listbox.config(height=4)
            listbox_scroll.grid(sticky="nsew")
            if i == 0:
                self.startup_commands_listbox = listbox_scroll.listbox
            elif i == 1:
                self.shutdown_commands_listbox = listbox_scroll.listbox
            elif i == 2:
                self.validate_commands_listbox = listbox_scroll.listbox

    def draw_tab_validation(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="ew")
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Validation", sticky="nsew")

        frame = ttk.Frame(tab)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Validation Time")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        self.validation_time_entry = ttk.Entry(frame)
        self.validation_time_entry.insert("end", self.validation_time)
        self.validation_time_entry.config(state=tk.DISABLED)
        self.validation_time_entry.grid(row=0, column=1, sticky="ew", pady=PADY)

        label = ttk.Label(frame, text="Validation Mode")
        label.grid(row=1, column=0, sticky="w", padx=PADX)
        if self.validation_mode == ServiceValidationMode.BLOCKING:
            mode = "BLOCKING"
        elif self.validation_mode == ServiceValidationMode.NON_BLOCKING:
            mode = "NON_BLOCKING"
        else:
            mode = "TIMER"
        self.validation_mode_entry = ttk.Entry(
            frame, textvariable=tk.StringVar(value=mode)
        )
        self.validation_mode_entry.insert("end", mode)
        self.validation_mode_entry.config(state=tk.DISABLED)
        self.validation_mode_entry.grid(row=1, column=1, sticky="ew", pady=PADY)

        label = ttk.Label(frame, text="Validation Period")
        label.grid(row=2, column=0, sticky="w", padx=PADX)
        self.validation_period_entry = ttk.Entry(
            frame, state=tk.DISABLED, textvariable=self.validation_period
        )
        self.validation_period_entry.grid(row=2, column=1, sticky="ew", pady=PADY)

        label_frame = ttk.LabelFrame(tab, text="Executables", padding=FRAME_PAD)
        label_frame.grid(sticky="nsew", pady=PADY)
        label_frame.columnconfigure(0, weight=1)
        label_frame.rowconfigure(0, weight=1)
        listbox_scroll = ListboxScroll(label_frame)
        listbox_scroll.grid(sticky="nsew")
        tab.rowconfigure(listbox_scroll.grid_info()["row"], weight=1)
        for executable in self.executables:
            listbox_scroll.listbox.insert("end", executable)

        label_frame = ttk.LabelFrame(tab, text="Dependencies", padding=FRAME_PAD)
        label_frame.grid(sticky="nsew", pady=PADY)
        label_frame.columnconfigure(0, weight=1)
        label_frame.rowconfigure(0, weight=1)
        listbox_scroll = ListboxScroll(label_frame)
        listbox_scroll.grid(sticky="nsew")
        tab.rowconfigure(listbox_scroll.grid_info()["row"], weight=1)
        for dependency in self.dependencies:
            listbox_scroll.listbox.insert("end", dependency)

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Defaults", command=self.click_defaults)
        button.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Copy...", command=self.click_copy)
        button.grid(row=0, column=2, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=3, sticky="ew")

    def click_apply(self):
        current_listbox = self.master.current.listbox
        if not self.is_custom():
            self.canvas_node.config_service_configs.pop(self.service_name, None)
            current_listbox.itemconfig(current_listbox.curselection()[0], bg="")
            self.destroy()
            return

        service_config = self.canvas_node.config_service_configs.setdefault(
            self.service_name, {}
        )
        if self.config_frame:
            self.config_frame.parse_config()
            service_config["config"] = {x.name: x.value for x in self.config.values()}
        templates_config = service_config.setdefault("templates", {})
        for file in self.modified_files:
            templates_config[file] = self.temp_service_files[file]
        all_current = current_listbox.get(0, tk.END)
        current_listbox.itemconfig(all_current.index(self.service_name), bg="green")
        self.destroy()

    def handle_template_changed(self, event: tk.Event):
        template = self.templates_combobox.get()
        self.template_text.text.delete(1.0, "end")
        self.template_text.text.insert("end", self.temp_service_files[template])

    def handle_mode_changed(self, event: tk.Event):
        mode = self.modes_combobox.get()
        config = self.mode_configs[mode]
        logging.info("mode config: %s", config)
        self.config_frame.set_values(config)

    def update_template_file_data(self, event: tk.Event):
        scrolledtext = event.widget
        template = self.templates_combobox.get()
        self.temp_service_files[template] = scrolledtext.get(1.0, "end")
        if self.temp_service_files[template] != self.original_service_files[template]:
            self.modified_files.add(template)
        else:
            self.modified_files.discard(template)

    def is_custom(self):
        has_custom_templates = len(self.modified_files) > 0
        has_custom_config = False
        if self.config_frame:
            current = self.config_frame.parse_config()
            has_custom_config = self.default_config != current
        return has_custom_templates or has_custom_config

    def click_defaults(self):
        self.canvas_node.config_service_configs.pop(self.service_name, None)
        logging.info(
            "cleared config service config: %s", self.canvas_node.config_service_configs
        )
        self.temp_service_files = dict(self.original_service_files)
        filename = self.templates_combobox.get()
        self.template_text.text.delete(1.0, "end")
        self.template_text.text.insert("end", self.temp_service_files[filename])
        if self.config_frame:
            logging.info("resetting defaults: %s", self.default_config)
            self.config_frame.set_values(self.default_config)

    def click_copy(self):
        pass

    def append_commands(
        self, commands: List[str], listbox: tk.Listbox, to_add: List[str]
    ):
        for cmd in to_add:
            commands.append(cmd)
            listbox.insert(tk.END, cmd)
