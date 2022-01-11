"""
Service configuration dialog
"""
import logging
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict, List, Optional, Set

import grpc

from core.api.grpc.wrappers import (
    ConfigOption,
    ConfigServiceData,
    Node,
    ServiceValidationMode,
)
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CodeText, ConfigFrame, ListboxScroll

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.coreclient import CoreClient


class ConfigServiceConfigDialog(Dialog):
    def __init__(
        self, master: tk.BaseWidget, app: "Application", service_name: str, node: Node
    ) -> None:
        title = f"{service_name} Config Service"
        super().__init__(app, title, master=master)
        self.core: "CoreClient" = app.core
        self.node: Node = node
        self.service_name: str = service_name
        self.radiovar: tk.IntVar = tk.IntVar()
        self.radiovar.set(2)
        self.directories: List[str] = []
        self.templates: List[str] = []
        self.dependencies: List[str] = []
        self.executables: List[str] = []
        self.startup_commands: List[str] = []
        self.validation_commands: List[str] = []
        self.shutdown_commands: List[str] = []
        self.default_startup: List[str] = []
        self.default_validate: List[str] = []
        self.default_shutdown: List[str] = []
        self.validation_mode: Optional[ServiceValidationMode] = None
        self.validation_time: Optional[int] = None
        self.validation_period: tk.StringVar = tk.StringVar()
        self.modes: List[str] = []
        self.mode_configs: Dict[str, Dict[str, str]] = {}

        self.notebook: Optional[ttk.Notebook] = None
        self.templates_combobox: Optional[ttk.Combobox] = None
        self.modes_combobox: Optional[ttk.Combobox] = None
        self.startup_commands_listbox: Optional[tk.Listbox] = None
        self.shutdown_commands_listbox: Optional[tk.Listbox] = None
        self.validate_commands_listbox: Optional[tk.Listbox] = None
        self.validation_time_entry: Optional[ttk.Entry] = None
        self.validation_mode_entry: Optional[ttk.Entry] = None
        self.template_text: Optional[CodeText] = None
        self.validation_period_entry: Optional[ttk.Entry] = None
        self.original_service_files: Dict[str, str] = {}
        self.temp_service_files: Dict[str, str] = {}
        self.modified_files: Set[str] = set()
        self.config_frame: Optional[ConfigFrame] = None
        self.default_config: Dict[str, str] = {}
        self.config: Dict[str, ConfigOption] = {}
        self.has_error: bool = False
        self.load()
        if not self.has_error:
            self.draw()

    def load(self) -> None:
        try:
            self.core.start_session(definition=True)
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

            defaults = self.core.client.get_config_service_defaults(self.service_name)
            self.original_service_files = defaults.templates
            self.temp_service_files = dict(self.original_service_files)
            self.modes = sorted(defaults.modes)
            self.mode_configs = defaults.modes
            self.config = ConfigOption.from_dict(defaults.config)
            self.default_config = {x.name: x.value for x in self.config.values()}
            service_config = self.node.config_service_configs.get(self.service_name)
            if service_config:
                for key, value in service_config.config.items():
                    self.config[key].value = value
                logger.info("default config: %s", self.default_config)
                for file, data in service_config.templates.items():
                    self.modified_files.add(file)
                    self.temp_service_files[file] = data
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Get Config Service Error", e)
            self.has_error = True

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        # draw notebook
        self.notebook = ttk.Notebook(self.top)
        self.notebook.grid(sticky=tk.NSEW, pady=PADY)
        self.draw_tab_files()
        if self.config:
            self.draw_tab_config()
        self.draw_tab_startstop()
        self.draw_tab_validation()
        self.draw_buttons()

    def draw_tab_files(self) -> None:
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky=tk.NSEW)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Directories/Files")

        label = ttk.Label(
            tab, text="Directories and templates that will be used for this service."
        )
        label.grid(pady=PADY)

        frame = ttk.Frame(tab)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Directories")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        directories_combobox = ttk.Combobox(
            frame, values=self.directories, state="readonly"
        )
        directories_combobox.grid(row=0, column=1, sticky=tk.EW, pady=PADY)
        if self.directories:
            directories_combobox.current(0)

        label = ttk.Label(frame, text="Templates")
        label.grid(row=1, column=0, sticky=tk.W, padx=PADX)
        self.templates_combobox = ttk.Combobox(
            frame, values=self.templates, state="readonly"
        )
        self.templates_combobox.bind(
            "<<ComboboxSelected>>", self.handle_template_changed
        )
        self.templates_combobox.grid(row=1, column=1, sticky=tk.EW, pady=PADY)

        self.template_text = CodeText(tab)
        self.template_text.grid(sticky=tk.NSEW)
        tab.rowconfigure(self.template_text.grid_info()["row"], weight=1)
        if self.templates:
            self.templates_combobox.current(0)
            self.template_text.text.delete(1.0, "end")
            self.template_text.text.insert(
                "end", self.temp_service_files[self.templates[0]]
            )
        self.template_text.text.bind("<FocusOut>", self.update_template_file_data)

    def draw_tab_config(self) -> None:
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky=tk.NSEW)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Configuration")

        if self.modes:
            frame = ttk.Frame(tab)
            frame.grid(sticky=tk.EW, pady=PADY)
            frame.columnconfigure(1, weight=1)
            label = ttk.Label(frame, text="Modes")
            label.grid(row=0, column=0, padx=PADX)
            self.modes_combobox = ttk.Combobox(
                frame, values=self.modes, state="readonly"
            )
            self.modes_combobox.bind("<<ComboboxSelected>>", self.handle_mode_changed)
            self.modes_combobox.grid(row=0, column=1, sticky=tk.EW, pady=PADY)

        logger.info("config service config: %s", self.config)
        self.config_frame = ConfigFrame(tab, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky=tk.NSEW, pady=PADY)
        tab.rowconfigure(self.config_frame.grid_info()["row"], weight=1)

    def draw_tab_startstop(self) -> None:
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky=tk.NSEW)
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
            label_frame.grid(row=i, column=0, sticky=tk.NSEW, pady=PADY)
            listbox_scroll = ListboxScroll(label_frame)
            for command in commands:
                listbox_scroll.listbox.insert("end", command)
            listbox_scroll.listbox.config(height=4)
            listbox_scroll.grid(sticky=tk.NSEW)
            if i == 0:
                self.startup_commands_listbox = listbox_scroll.listbox
            elif i == 1:
                self.shutdown_commands_listbox = listbox_scroll.listbox
            elif i == 2:
                self.validate_commands_listbox = listbox_scroll.listbox

    def draw_tab_validation(self) -> None:
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky=tk.EW)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Validation", sticky=tk.NSEW)

        frame = ttk.Frame(tab)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Validation Time")
        label.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        self.validation_time_entry = ttk.Entry(frame)
        self.validation_time_entry.insert("end", self.validation_time)
        self.validation_time_entry.config(state=tk.DISABLED)
        self.validation_time_entry.grid(row=0, column=1, sticky=tk.EW, pady=PADY)

        label = ttk.Label(frame, text="Validation Mode")
        label.grid(row=1, column=0, sticky=tk.W, padx=PADX)
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
        self.validation_mode_entry.grid(row=1, column=1, sticky=tk.EW, pady=PADY)

        label = ttk.Label(frame, text="Validation Period")
        label.grid(row=2, column=0, sticky=tk.W, padx=PADX)
        self.validation_period_entry = ttk.Entry(
            frame, state=tk.DISABLED, textvariable=self.validation_period
        )
        self.validation_period_entry.grid(row=2, column=1, sticky=tk.EW, pady=PADY)

        label_frame = ttk.LabelFrame(tab, text="Executables", padding=FRAME_PAD)
        label_frame.grid(sticky=tk.NSEW, pady=PADY)
        label_frame.columnconfigure(0, weight=1)
        label_frame.rowconfigure(0, weight=1)
        listbox_scroll = ListboxScroll(label_frame)
        listbox_scroll.grid(sticky=tk.NSEW)
        tab.rowconfigure(listbox_scroll.grid_info()["row"], weight=1)
        for executable in self.executables:
            listbox_scroll.listbox.insert("end", executable)

        label_frame = ttk.LabelFrame(tab, text="Dependencies", padding=FRAME_PAD)
        label_frame.grid(sticky=tk.NSEW, pady=PADY)
        label_frame.columnconfigure(0, weight=1)
        label_frame.rowconfigure(0, weight=1)
        listbox_scroll = ListboxScroll(label_frame)
        listbox_scroll.grid(sticky=tk.NSEW)
        tab.rowconfigure(listbox_scroll.grid_info()["row"], weight=1)
        for dependency in self.dependencies:
            listbox_scroll.listbox.insert("end", dependency)

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Defaults", command=self.click_defaults)
        button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Copy...", command=self.click_copy)
        button.grid(row=0, column=2, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=3, sticky=tk.EW)

    def click_apply(self) -> None:
        current_listbox = self.master.current.listbox
        if not self.is_custom():
            self.node.config_service_configs.pop(self.service_name, None)
            current_listbox.itemconfig(current_listbox.curselection()[0], bg="")
            self.destroy()
            return
        service_config = self.node.config_service_configs.setdefault(
            self.service_name, ConfigServiceData()
        )
        if self.config_frame:
            self.config_frame.parse_config()
            service_config.config = {x.name: x.value for x in self.config.values()}
        for file in self.modified_files:
            service_config.templates[file] = self.temp_service_files[file]
        all_current = current_listbox.get(0, tk.END)
        current_listbox.itemconfig(all_current.index(self.service_name), bg="green")
        self.destroy()

    def handle_template_changed(self, event: tk.Event) -> None:
        template = self.templates_combobox.get()
        self.template_text.text.delete(1.0, "end")
        self.template_text.text.insert("end", self.temp_service_files[template])

    def handle_mode_changed(self, event: tk.Event) -> None:
        mode = self.modes_combobox.get()
        config = self.mode_configs[mode]
        logger.info("mode config: %s", config)
        self.config_frame.set_values(config)

    def update_template_file_data(self, event: tk.Event) -> None:
        scrolledtext = event.widget
        template = self.templates_combobox.get()
        self.temp_service_files[template] = scrolledtext.get(1.0, "end")
        if self.temp_service_files[template] != self.original_service_files[template]:
            self.modified_files.add(template)
        else:
            self.modified_files.discard(template)

    def is_custom(self) -> bool:
        has_custom_templates = len(self.modified_files) > 0
        has_custom_config = False
        if self.config_frame:
            current = self.config_frame.parse_config()
            has_custom_config = self.default_config != current
        return has_custom_templates or has_custom_config

    def click_defaults(self) -> None:
        self.node.config_service_configs.pop(self.service_name, None)
        logger.info(
            "cleared config service config: %s", self.node.config_service_configs
        )
        self.temp_service_files = dict(self.original_service_files)
        filename = self.templates_combobox.get()
        self.template_text.text.delete(1.0, "end")
        self.template_text.text.insert("end", self.temp_service_files[filename])
        if self.config_frame:
            logger.info("resetting defaults: %s", self.default_config)
            self.config_frame.set_values(self.default_config)

    def click_copy(self) -> None:
        pass

    def append_commands(
        self, commands: List[str], listbox: tk.Listbox, to_add: List[str]
    ) -> None:
        for cmd in to_add:
            commands.append(cmd)
            listbox.insert(tk.END, cmd)
