"Service configuration dialog"
import logging
import tkinter as tk
from tkinter import ttk

import grpc

from core.api.grpc import core_pb2
from coretk.dialogs.dialog import Dialog
from coretk.errors import show_grpc_error
from coretk.images import ImageEnum, Images
from coretk.widgets import CodeText, ListboxScroll


class ServiceConfiguration(Dialog):
    def __init__(self, master, app, service_name, node_id):
        super().__init__(master, app, f"{service_name} service", modal=True)
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

        self.tab_parent = None
        self.metadata_entry = None
        self.filename_combobox = None
        self.startup_commands_listbox = None
        self.shutdown_commands_listbox = None
        self.validate_commands_listbox = None
        self.validation_time_entry = None
        self.validation_mode_entry = None
        self.service_file_data = None
        self.original_service_files = {}
        self.temp_service_files = {}
        self.modified_files = set()
        self.load()
        self.draw()

    def load(self):
        try:
            # create nodes and links in definition state for getting and setting service file
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
        # self.columnconfigure(1, weight=1)
        frame = ttk.Frame(self.top)
        frame1 = ttk.Frame(frame)
        label = ttk.Label(frame1, text=self.service_name)
        label.grid(row=0, column=0, sticky="ew")
        frame1.grid(row=0, column=0)
        frame2 = ttk.Frame(frame)
        # frame2.columnconfigure(0, weight=1)
        # frame2.columnconfigure(1, weight=4)
        label = ttk.Label(frame2, text="Meta-data")
        label.grid(row=0, column=0)

        self.metadata_entry = ttk.Entry(frame2, textvariable=self.metadata)
        self.metadata_entry.grid(row=0, column=1)
        frame2.grid(row=1, column=0)
        frame.grid(row=0, column=0)

        frame = ttk.Frame(self.top)
        self.tab_parent = ttk.Notebook(frame)
        tab1 = ttk.Frame(self.tab_parent)
        tab2 = ttk.Frame(self.tab_parent)
        tab3 = ttk.Frame(self.tab_parent)
        tab4 = ttk.Frame(self.tab_parent)
        tab1.columnconfigure(0, weight=1)
        tab2.columnconfigure(0, weight=1)
        tab3.columnconfigure(0, weight=1)
        tab4.columnconfigure(0, weight=1)

        self.tab_parent.add(tab1, text="Files", sticky="nsew")
        self.tab_parent.add(tab2, text="Directories", sticky="nsew")
        self.tab_parent.add(tab3, text="Startup/shutdown", sticky="nsew")
        self.tab_parent.add(tab4, text="Configuration", sticky="nsew")
        self.tab_parent.grid(row=0, column=0, sticky="nsew")
        frame.grid(row=1, column=0, sticky="nsew")

        # tab 1
        label = ttk.Label(
            tab1, text="Config files and scripts that are generated for this service."
        )
        label.grid(row=0, column=0, sticky="nsew")

        frame = ttk.Frame(tab1)
        label = ttk.Label(frame, text="File name: ")
        label.grid(row=0, column=0)
        self.filename_combobox = ttk.Combobox(
            frame, values=self.filenames, state="readonly"
        )
        self.filename_combobox.grid(row=0, column=1)
        self.filename_combobox.bind(
            "<<ComboboxSelected>>", self.display_service_file_data
        )
        button = ttk.Button(frame, image=self.documentnew_img, state="disabled")
        button.bind("<Button-1>", self.add_filename)
        button.grid(row=0, column=2)
        button = ttk.Button(frame, image=self.editdelete_img, state="disabled")
        button.bind("<Button-1>", self.delete_filename)
        button.grid(row=0, column=3)
        frame.grid(row=1, column=0, sticky="nsew")

        frame = ttk.Frame(tab1)
        button = ttk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Copy this source file:",
            value=1,
            state="disabled",
        )
        button.grid(row=0, column=0)
        entry = ttk.Entry(frame, state=tk.DISABLED)
        entry.grid(row=0, column=1)
        image = Images.get(ImageEnum.FILEOPEN, 16)
        button = ttk.Button(frame, image=image)
        button.image = image
        button.grid(row=0, column=2)
        frame.grid(row=2, column=0, sticky="nsew")

        frame = ttk.Frame(tab1)
        button = ttk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Use text below for file contents:",
            value=2,
        )
        button.grid(row=0, column=0)
        image = Images.get(ImageEnum.FILEOPEN, 16)
        button = ttk.Button(frame, image=image)
        button.image = image
        button.grid(row=0, column=1)
        image = Images.get(ImageEnum.DOCUMENTSAVE, 16)
        button = ttk.Button(frame, image=image)
        button.image = image
        button.grid(row=0, column=2)
        frame.grid(row=3, column=0, sticky="nsew")

        self.service_file_data = CodeText(tab1)
        self.service_file_data.grid(row=4, column=0, sticky="nsew")
        if len(self.filenames) > 0:
            self.filename_combobox.current(0)
            self.service_file_data.delete(1.0, "end")
            self.service_file_data.insert(
                "end", self.temp_service_files[self.filenames[0]]
            )
        self.service_file_data.bind("<FocusOut>", self.update_temp_service_file_data)

        # tab 2
        label = ttk.Label(
            tab2,
            text="Directories required by this service that are unique for each node.",
        )
        label.grid(row=0, column=0, sticky="nsew")

        # tab 3
        for i in range(3):
            label_frame = None
            if i == 0:
                label_frame = ttk.LabelFrame(tab3, text="Startup commands")
                commands = self.startup_commands
            elif i == 1:
                label_frame = ttk.LabelFrame(tab3, text="Shutdown commands")
                commands = self.shutdown_commands
            elif i == 2:
                label_frame = ttk.LabelFrame(tab3, text="Validation commands")
                commands = self.validation_commands
            label_frame.columnconfigure(0, weight=1)
            frame = ttk.Frame(label_frame)
            frame.columnconfigure(0, weight=1)
            entry = ttk.Entry(frame, textvariable=tk.StringVar())
            entry.grid(row=0, column=0, stick="nsew")
            button = ttk.Button(frame, image=self.documentnew_img)
            button.bind("<Button-1>", self.add_command)
            button.grid(row=0, column=1, sticky="nsew")
            button = ttk.Button(frame, image=self.editdelete_img)
            button.grid(row=0, column=2, sticky="nsew")
            button.bind("<Button-1>", self.delete_command)
            frame.grid(row=0, column=0, sticky="nsew")
            listbox_scroll = ListboxScroll(label_frame)
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
            label_frame.grid(row=i, column=0, sticky="nsew")

        # tab 4
        for i in range(2):
            label_frame = None
            if i == 0:
                label_frame = ttk.LabelFrame(tab4, text="Executables")
            elif i == 1:
                label_frame = ttk.LabelFrame(tab4, text="Dependencies")
            label_frame.columnconfigure(0, weight=1)
            listbox_scroll = ListboxScroll(label_frame)
            listbox_scroll.listbox.config(height=4)
            listbox_scroll.grid(row=0, column=0, sticky="nsew")
            label_frame.grid(row=i, column=0, sticky="nsew")
            if i == 0:
                for executable in self.executables:
                    print(executable)
                    listbox_scroll.listbox.insert("end", executable)
            if i == 1:
                for dependency in self.dependencies:
                    listbox_scroll.listbox.insert("end", dependency)

        for i in range(3):
            frame = ttk.Frame(tab4)
            frame.columnconfigure(0, weight=1)
            if i == 0:
                label = ttk.Label(frame, text="Validation time:")
                self.validation_time_entry = ttk.Entry(frame)
                self.validation_time_entry.insert("end", self.validation_time)
                self.validation_time_entry.config(state="disabled")
                self.validation_time_entry.grid(row=i, column=1)
            elif i == 1:
                label = ttk.Label(frame, text="Validation mode:")
                if self.validation_mode == core_pb2.ServiceValidationMode.BLOCKING:
                    mode = "BLOCKING"
                elif (
                    self.validation_mode == core_pb2.ServiceValidationMode.NON_BLOCKING
                ):
                    mode = "NON_BLOCKING"
                elif self.validation_mode == core_pb2.ServiceValidationMode.TIMER:
                    mode = "TIMER"
                self.validation_mode_entry = ttk.Entry(
                    frame, textvariable=tk.StringVar(value=mode)
                )
                self.validation_mode_entry.insert("end", mode)
                self.validation_mode_entry.config(state="disabled")
                self.validation_mode_entry.grid(row=i, column=1)
            elif i == 2:
                label = ttk.Label(frame, text="Validation period:")
                self.validation_period_entry = ttk.Entry(
                    frame, state="disabled", textvariable=tk.StringVar()
                )
                self.validation_period_entry.grid(row=i, column=1)
            label.grid(row=i, column=0)
            frame.grid(row=2 + i, column=0, sticky="nsew")

        button = ttk.Button(
            self.top, text="onle store values that have changed from their defaults"
        )
        button.grid(row=2, column=0)

        frame = ttk.Frame(self.top)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="nsew")
        button = ttk.Button(
            frame, text="Dafults", command=self.click_defaults, state="disabled"
        )
        button.grid(row=0, column=1, sticky="nsew")
        button = ttk.Button(
            frame, text="Copy...", command=self.click_copy, state="disabled"
        )
        button.grid(row=0, column=2, sticky="nsew")
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=3, sticky="nsew")
        frame.grid(row=3, column=0)

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
