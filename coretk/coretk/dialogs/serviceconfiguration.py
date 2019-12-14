"Service configuration dialog"
import logging
import tkinter as tk
from tkinter import ttk

import grpc

from core.api.grpc import core_pb2
from coretk.dialogs.dialog import Dialog
from coretk.errors import show_grpc_error
from coretk.images import ImageEnum, Images
from coretk.themes import FRAME_PAD, PADX, PADY
from coretk.widgets import CodeText, ListboxScroll


class ServiceConfiguration(Dialog):
    def __init__(self, master, app, service_name, node_id):
        title = f"{service_name} Service"
        super().__init__(master, app, title, modal=True)
        self.app = app
        self.core = app.core
        self.node_id = node_id
        self.service_name = service_name
        self.radiovar = tk.IntVar()
        self.radiovar.set(2)
        self.metadata = ""
        self.filenames = []
        self.dependencies = []
        self.executables = []
        self.startup_commands = []
        self.validation_commands = []
        self.shutdown_commands = []
        self.validation_mode = None
        self.validation_time = None
        self.validation_period = None
        self.documentnew_img = Images.get(ImageEnum.DOCUMENTNEW, 16)
        self.editdelete_img = Images.get(ImageEnum.EDITDELETE, 16)

        self.notebook = None
        self.metadata_entry = None
        self.filename_combobox = None
        self.startup_commands_listbox = None
        self.shutdown_commands_listbox = None
        self.validate_commands_listbox = None
        self.validation_time_entry = None
        self.validation_mode_entry = None
        self.service_file_data = None
        self.validation_period_entry = None
        self.original_service_files = {}
        self.temp_service_files = {}
        self.modified_files = set()
        self.load()
        self.draw()

    def load(self):
        try:
            self.app.core.create_nodes_and_links()
            service_configs = self.app.core.service_configs
            if (
                self.node_id in service_configs
                and self.service_name in service_configs[self.node_id]
            ):
                service_config = self.app.core.service_configs[self.node_id][
                    self.service_name
                ]
            else:
                service_config = self.app.core.get_node_service(
                    self.node_id, self.service_name
                )
            self.dependencies = [x for x in service_config.dependencies]
            self.executables = [x for x in service_config.executables]
            self.metadata = service_config.meta
            self.filenames = [x for x in service_config.configs]
            self.startup_commands = [x for x in service_config.startup]
            self.validation_commands = [x for x in service_config.validate]
            self.shutdown_commands = [x for x in service_config.shutdown]
            self.validation_mode = service_config.validation_mode
            self.validation_time = service_config.validation_timer
            self.original_service_files = {
                x: self.app.core.get_node_service_file(
                    self.node_id, self.service_name, x
                )
                for x in self.filenames
            }
            self.temp_service_files = {
                x: self.original_service_files[x] for x in self.original_service_files
            }
            file_configs = self.app.core.file_configs
            if (
                self.node_id in file_configs
                and self.service_name in file_configs[self.node_id]
            ):
                for file, data in file_configs[self.node_id][self.service_name].items():
                    self.temp_service_files[file] = data
        except grpc.RpcError as e:
            show_grpc_error(e)

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)

        # draw metadata
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="Meta-data")
        label.grid(row=0, column=0, sticky="w", padx=PADX)
        self.metadata_entry = ttk.Entry(frame, textvariable=self.metadata)
        self.metadata_entry.grid(row=0, column=1, sticky="ew")

        # draw notebook
        self.notebook = ttk.Notebook(self.top)
        self.notebook.grid(sticky="nsew")
        self.draw_tab_files()
        self.draw_tab_directories()
        self.draw_tab_startstop()
        self.draw_tab_configuration()

        button = ttk.Button(self.top, text="Only Save Changes")
        button.grid(sticky="ew", pady=PADY)
        self.draw_buttons()

    def draw_tab_files(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Files")

        label = ttk.Label(
            tab, text="Config files and scripts that are generated for this service."
        )
        label.grid()

        frame = ttk.Frame(tab)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        label = ttk.Label(frame, text="File Name")
        label.grid(row=0, column=0, padx=PADX, sticky="w")
        self.filename_combobox = ttk.Combobox(
            frame, values=self.filenames, state="readonly"
        )
        self.filename_combobox.bind(
            "<<ComboboxSelected>>", self.display_service_file_data
        )
        self.filename_combobox.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(frame, image=self.documentnew_img, state="disabled")
        button.bind("<Button-1>", self.add_filename)
        button.grid(row=0, column=2, padx=PADX)
        button = ttk.Button(frame, image=self.editdelete_img, state="disabled")
        button.bind("<Button-1>", self.delete_filename)
        button.grid(row=0, column=3)

        frame = ttk.Frame(tab)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)
        button = ttk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Copy Source File",
            value=1,
            state=tk.DISABLED,
        )
        button.grid(row=0, column=0, sticky="w", padx=PADX)
        entry = ttk.Entry(frame, state=tk.DISABLED)
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)
        image = Images.get(ImageEnum.FILEOPEN, 16)
        button = ttk.Button(frame, image=image)
        button.image = image
        button.grid(row=0, column=2)

        frame = ttk.Frame(tab)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(0, weight=1)
        button = ttk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Use text below for file contents",
            value=2,
        )
        button.grid(row=0, column=0, sticky="ew")
        image = Images.get(ImageEnum.FILEOPEN, 16)
        button = ttk.Button(frame, image=image)
        button.image = image
        button.grid(row=0, column=1)
        image = Images.get(ImageEnum.DOCUMENTSAVE, 16)
        button = ttk.Button(frame, image=image)
        button.image = image
        button.grid(row=0, column=2)

        self.service_file_data = CodeText(tab)
        self.service_file_data.grid(sticky="nsew")
        tab.rowconfigure(self.service_file_data.grid_info()["row"], weight=1)
        if len(self.filenames) > 0:
            self.filename_combobox.current(0)
            self.service_file_data.delete(1.0, "end")
            self.service_file_data.insert(
                "end", self.temp_service_files[self.filenames[0]]
            )
        self.service_file_data.bind("<FocusOut>", self.update_temp_service_file_data)

    def draw_tab_directories(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Directories")

        label = ttk.Label(
            tab,
            text="Directories required by this service that are unique for each node.",
        )
        label.grid()

    def draw_tab_startstop(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        for i in range(3):
            tab.rowconfigure(i, weight=1)
        self.notebook.add(tab, text="Startup/shutdown")

        # tab 3
        for i in range(3):
            label_frame = None
            if i == 0:
                label_frame = ttk.LabelFrame(
                    tab, text="Startup commands", padding=FRAME_PAD
                )
                commands = self.startup_commands
            elif i == 1:
                label_frame = ttk.LabelFrame(
                    tab, text="Shutdown commands", padding=FRAME_PAD
                )
                commands = self.shutdown_commands
            elif i == 2:
                label_frame = ttk.LabelFrame(
                    tab, text="Validation commands", padding=FRAME_PAD
                )
                commands = self.validation_commands
            label_frame.columnconfigure(0, weight=1)
            label_frame.rowconfigure(1, weight=1)
            label_frame.grid(row=i, column=0, sticky="nsew")

            frame = ttk.Frame(label_frame)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            entry = ttk.Entry(frame, textvariable=tk.StringVar())
            entry.grid(row=0, column=0, stick="ew", padx=PADX)
            button = ttk.Button(frame, image=self.documentnew_img)
            button.bind("<Button-1>", self.add_command)
            button.grid(row=0, column=1, sticky="ew", padx=PADX)
            button = ttk.Button(frame, image=self.editdelete_img)
            button.grid(row=0, column=2, sticky="ew")
            button.bind("<Button-1>", self.delete_command)
            listbox_scroll = ListboxScroll(label_frame, borderwidth=0)
            listbox_scroll.listbox.bind("<<ListboxSelect>>", self.update_entry)
            for command in commands:
                listbox_scroll.listbox.insert("end", command)
            listbox_scroll.listbox.config(height=4)
            listbox_scroll.grid(row=1, column=0, sticky="nsew")
            if i == 0:
                self.startup_commands_listbox = listbox_scroll.listbox
            elif i == 1:
                self.shutdown_commands_listbox = listbox_scroll.listbox
            elif i == 2:
                self.validate_commands_listbox = listbox_scroll.listbox

    def draw_tab_configuration(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Configuration", sticky="nsew")

        frame = ttk.Frame(tab)
        frame.grid(sticky="ew", pady=PADY)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Validation Time")
        label.grid(row=0, column=0, sticky="w")
        self.validation_time_entry = ttk.Entry(frame)
        self.validation_time_entry.insert("end", self.validation_time)
        self.validation_time_entry.config(state=tk.DISABLED)
        self.validation_time_entry.grid(row=0, column=1, sticky="ew")

        label = ttk.Label(frame, text="Validation Mode")
        label.grid(row=1, column=0, sticky="w")
        if self.validation_mode == core_pb2.ServiceValidationMode.BLOCKING:
            mode = "BLOCKING"
        elif self.validation_mode == core_pb2.ServiceValidationMode.NON_BLOCKING:
            mode = "NON_BLOCKING"
        else:
            mode = "TIMER"
        self.validation_mode_entry = ttk.Entry(
            frame, textvariable=tk.StringVar(value=mode)
        )
        self.validation_mode_entry.insert("end", mode)
        self.validation_mode_entry.config(state=tk.DISABLED)
        self.validation_mode_entry.grid(row=1, column=1, sticky="ew")

        label = ttk.Label(frame, text="Validation Period")
        label.grid(row=2, column=0, sticky="w")
        self.validation_period_entry = ttk.Entry(
            frame, state=tk.DISABLED, textvariable=tk.StringVar()
        )
        self.validation_period_entry.grid(row=2, column=1, sticky="ew")

        listbox_scroll = ListboxScroll(tab, text="Executables", padding=FRAME_PAD)
        listbox_scroll.grid(sticky="nsew", pady=PADY)
        tab.rowconfigure(listbox_scroll.grid_info()["row"], weight=1)
        for executable in self.executables:
            listbox_scroll.listbox.insert("end", executable)

        listbox_scroll = ListboxScroll(tab, text="Dependencies", padding=FRAME_PAD)
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
        button = ttk.Button(
            frame, text="Defaults", command=self.click_defaults, state="disabled"
        )
        button.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(
            frame, text="Copy...", command=self.click_copy, state="disabled"
        )
        button.grid(row=0, column=2, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=3, sticky="ew")

    def add_filename(self, event):
        # not worry about it for now
        return
        frame_contains_button = event.widget.master
        combobox = frame_contains_button.grid_slaves(row=0, column=1)[0]
        filename = combobox.get()
        if filename not in combobox["values"]:
            combobox["values"] += (filename,)

    def delete_filename(self, event):
        # not worry about it for now
        return
        frame_comntains_button = event.widget.master
        combobox = frame_comntains_button.grid_slaves(row=0, column=1)[0]
        filename = combobox.get()
        if filename in combobox["values"]:
            combobox["values"] = tuple([x for x in combobox["values"] if x != filename])
            combobox.set("")

    def add_command(self, event):
        frame_contains_button = event.widget.master
        listbox = frame_contains_button.master.grid_slaves(row=1, column=0)[0].listbox
        command_to_add = frame_contains_button.grid_slaves(row=0, column=0)[0].get()
        if command_to_add == "":
            return
        for cmd in listbox.get(0, tk.END):
            if cmd == command_to_add:
                return
        listbox.insert(tk.END, command_to_add)

    def update_entry(self, event):
        listbox = event.widget
        current_selection = listbox.curselection()
        if len(current_selection) > 0:
            cmd = listbox.get(current_selection[0])
            entry = listbox.master.master.grid_slaves(row=0, column=0)[0].grid_slaves(
                row=0, column=0
            )[0]
            entry.delete(0, "end")
            entry.insert(0, cmd)

    def delete_command(self, event):
        button = event.widget
        frame_contains_button = button.master
        listbox = frame_contains_button.master.grid_slaves(row=1, column=0)[0].listbox
        current_selection = listbox.curselection()
        if len(current_selection) > 0:
            listbox.delete(current_selection[0])
            entry = frame_contains_button.grid_slaves(row=0, column=0)[0]
            entry.delete(0, tk.END)

    def click_apply(self):
        service_configs = self.app.core.service_configs
        startup_commands = self.startup_commands_listbox.get(0, "end")
        shutdown_commands = self.shutdown_commands_listbox.get(0, "end")
        validate_commands = self.validate_commands_listbox.get(0, "end")
        try:
            config = self.core.set_node_service(
                self.node_id,
                self.service_name,
                startup_commands,
                validate_commands,
                shutdown_commands,
            )
            if self.node_id not in service_configs:
                service_configs[self.node_id] = {}
            if self.service_name not in service_configs[self.node_id]:
                self.app.core.service_configs[self.node_id][self.service_name] = config
            for file in self.modified_files:
                file_configs = self.app.core.file_configs
                if self.node_id not in file_configs:
                    file_configs[self.node_id] = {}
                if self.service_name not in file_configs[self.node_id]:
                    file_configs[self.node_id][self.service_name] = {}
                file_configs[self.node_id][self.service_name][
                    file
                ] = self.temp_service_files[file]

                self.app.core.set_node_service_file(
                    self.node_id, self.service_name, file, self.temp_service_files[file]
                )
        except grpc.RpcError as e:
            show_grpc_error(e)
        self.destroy()

    def display_service_file_data(self, event):
        combobox = event.widget
        filename = combobox.get()
        self.service_file_data.delete(1.0, "end")
        self.service_file_data.insert("end", self.temp_service_files[filename])

    def update_temp_service_file_data(self, event):
        scrolledtext = event.widget
        filename = self.filename_combobox.get()
        self.temp_service_files[filename] = scrolledtext.get(1.0, "end")
        if self.temp_service_files[filename] != self.original_service_files[filename]:
            self.modified_files.add(filename)
        else:
            self.modified_files.discard(filename)

    def click_defaults(self):
        logging.info("not implemented")

    def click_copy(self):
        logging.info("not implemented")

    def click_cancel(self):
        logging.info("not implemented")
