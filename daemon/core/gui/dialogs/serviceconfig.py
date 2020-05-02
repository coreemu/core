import logging
import os
import tkinter as tk
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any, List

import grpc

from core.api.grpc.services_pb2 import ServiceValidationMode
from core.gui.dialogs.copyserviceconfig import CopyServiceConfigDialog
from core.gui.dialogs.dialog import Dialog
from core.gui.errors import show_grpc_error
from core.gui.images import ImageEnum, Images
from core.gui.themes import FRAME_PAD, PADX, PADY
from core.gui.widgets import CodeText, ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode


class ServiceConfigDialog(Dialog):
    def __init__(
        self,
        master: Any,
        app: "Application",
        service_name: str,
        canvas_node: "CanvasNode",
        node_id: int,
    ):
        title = f"{service_name} Service"
        super().__init__(master, app, title)
        self.master = master
        self.app = app
        self.core = app.core
        self.canvas_node = canvas_node
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
        self.default_startup = []
        self.default_validate = []
        self.default_shutdown = []
        self.validation_mode = None
        self.validation_time = None
        self.validation_period = None
        self.directory_entry = None
        self.default_directories = []
        self.temp_directories = []
        self.documentnew_img = Images.get(
            ImageEnum.DOCUMENTNEW, int(16 * app.app_scale)
        )
        self.editdelete_img = Images.get(ImageEnum.EDITDELETE, int(16 * app.app_scale))
        self.notebook = None
        self.metadata_entry = None
        self.filename_combobox = None
        self.dir_list = None
        self.startup_commands_listbox = None
        self.shutdown_commands_listbox = None
        self.validate_commands_listbox = None
        self.validation_time_entry = None
        self.validation_mode_entry = None
        self.service_file_data = None
        self.validation_period_entry = None
        self.original_service_files = {}
        self.default_config = None
        self.temp_service_files = {}
        self.modified_files = set()
        self.has_error = False
        self.load()
        if not self.has_error:
            self.draw()

    def load(self):
        try:
            self.app.core.create_nodes_and_links()
            default_config = self.app.core.get_node_service(
                self.node_id, self.service_name
            )
            self.default_startup = default_config.startup[:]
            self.default_validate = default_config.validate[:]
            self.default_shutdown = default_config.shutdown[:]
            self.default_directories = default_config.dirs[:]
            custom_service_config = self.canvas_node.service_configs.get(
                self.service_name
            )
            self.default_config = default_config
            service_config = (
                custom_service_config if custom_service_config else default_config
            )
            self.dependencies = service_config.dependencies[:]
            self.executables = service_config.executables[:]
            self.metadata = service_config.meta
            self.filenames = service_config.configs[:]
            self.startup_commands = service_config.startup[:]
            self.validation_commands = service_config.validate[:]
            self.shutdown_commands = service_config.shutdown[:]
            self.validation_mode = service_config.validation_mode
            self.validation_time = service_config.validation_timer
            self.temp_directories = service_config.dirs[:]
            self.original_service_files = {
                x: self.app.core.get_node_service_file(
                    self.node_id, self.service_name, x
                )
                for x in default_config.configs
            }
            self.temp_service_files = dict(self.original_service_files)

            file_configs = self.canvas_node.service_file_configs.get(
                self.service_name, {}
            )
            for file, data in file_configs.items():
                self.temp_service_files[file] = data
        except grpc.RpcError as e:
            self.has_error = True
            show_grpc_error(e, self.master, self.app)

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
        self.notebook.grid(sticky="nsew", pady=PADY)
        self.draw_tab_files()
        self.draw_tab_directories()
        self.draw_tab_startstop()
        self.draw_tab_configuration()

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
        self.filename_combobox = ttk.Combobox(frame, values=self.filenames)
        self.filename_combobox.bind(
            "<<ComboboxSelected>>", self.display_service_file_data
        )
        self.filename_combobox.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(
            frame, image=self.documentnew_img, command=self.add_filename
        )
        button.grid(row=0, column=2, padx=PADX)
        button = ttk.Button(
            frame, image=self.editdelete_img, command=self.delete_filename
        )
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
            self.service_file_data.text.delete(1.0, "end")
            self.service_file_data.text.insert(
                "end", self.temp_service_files[self.filenames[0]]
            )
        self.service_file_data.text.bind(
            "<FocusOut>", self.update_temp_service_file_data
        )

    def draw_tab_directories(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        self.notebook.add(tab, text="Directories")

        label = ttk.Label(
            tab,
            text="Directories required by this service that are unique for each node.",
        )
        label.grid(row=0, column=0, sticky="ew")
        frame = ttk.Frame(tab, padding=FRAME_PAD)
        frame.columnconfigure(0, weight=1)
        frame.grid(row=1, column=0, sticky="nsew")
        var = tk.StringVar(value="")
        self.directory_entry = ttk.Entry(frame, textvariable=var)
        self.directory_entry.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="...", command=self.find_directory_button)
        button.grid(row=0, column=1, sticky="ew")
        self.dir_list = ListboxScroll(tab)
        self.dir_list.grid(row=2, column=0, sticky="nsew", pady=PADY)
        self.dir_list.listbox.bind("<<ListboxSelect>>", self.directory_select)
        for d in self.temp_directories:
            self.dir_list.listbox.insert("end", d)

        frame = ttk.Frame(tab)
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="Add", command=self.add_directory)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Remove", command=self.remove_directory)
        button.grid(row=0, column=1, sticky="ew")

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
            label_frame.rowconfigure(1, weight=1)
            label_frame.grid(row=i, column=0, sticky="nsew", pady=PADY)

            frame = ttk.Frame(label_frame)
            frame.grid(row=0, column=0, sticky="nsew", pady=PADY)
            frame.columnconfigure(0, weight=1)
            entry = ttk.Entry(frame, textvariable=tk.StringVar())
            entry.grid(row=0, column=0, stick="ew", padx=PADX)
            button = ttk.Button(frame, image=self.documentnew_img)
            button.bind("<Button-1>", self.add_command)
            button.grid(row=0, column=1, sticky="ew", padx=PADX)
            button = ttk.Button(frame, image=self.editdelete_img)
            button.grid(row=0, column=2, sticky="ew")
            button.bind("<Button-1>", self.delete_command)
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

    def draw_tab_configuration(self):
        tab = ttk.Frame(self.notebook, padding=FRAME_PAD)
        tab.grid(sticky="nsew")
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Configuration", sticky="nsew")

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
            frame, state=tk.DISABLED, textvariable=tk.StringVar()
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

    def add_filename(self):
        filename = self.filename_combobox.get()
        if filename not in self.filename_combobox["values"]:
            self.filename_combobox["values"] += (filename,)
            self.filename_combobox.set(filename)
            self.temp_service_files[filename] = self.service_file_data.text.get(
                1.0, "end"
            )
        else:
            logging.debug("file already existed")

    def delete_filename(self):
        cbb = self.filename_combobox
        filename = cbb.get()
        if filename in cbb["values"]:
            cbb["values"] = tuple([x for x in cbb["values"] if x != filename])
        cbb.set("")
        self.service_file_data.text.delete(1.0, "end")
        self.temp_service_files.pop(filename, None)
        if filename in self.modified_files:
            self.modified_files.remove(filename)

    @classmethod
    def add_command(cls, event: tk.Event):
        frame_contains_button = event.widget.master
        listbox = frame_contains_button.master.grid_slaves(row=1, column=0)[0].listbox
        command_to_add = frame_contains_button.grid_slaves(row=0, column=0)[0].get()
        if command_to_add == "":
            return
        for cmd in listbox.get(0, tk.END):
            if cmd == command_to_add:
                return
        listbox.insert(tk.END, command_to_add)

    @classmethod
    def update_entry(cls, event: tk.Event):
        listbox = event.widget
        current_selection = listbox.curselection()
        if len(current_selection) > 0:
            cmd = listbox.get(current_selection[0])
            entry = listbox.master.master.grid_slaves(row=0, column=0)[0].grid_slaves(
                row=0, column=0
            )[0]
            entry.delete(0, "end")
            entry.insert(0, cmd)

    @classmethod
    def delete_command(cls, event: tk.Event):
        button = event.widget
        frame_contains_button = button.master
        listbox = frame_contains_button.master.grid_slaves(row=1, column=0)[0].listbox
        current_selection = listbox.curselection()
        if len(current_selection) > 0:
            listbox.delete(current_selection[0])
            entry = frame_contains_button.grid_slaves(row=0, column=0)[0]
            entry.delete(0, tk.END)

    def click_apply(self):
        if (
            not self.is_custom_command()
            and not self.is_custom_service_file()
            and not self.has_new_files()
            and not self.is_custom_directory()
        ):
            self.canvas_node.service_configs.pop(self.service_name, None)
            self.current_service_color("")
            self.destroy()
            return

        try:
            if (
                self.is_custom_command()
                or self.has_new_files()
                or self.is_custom_directory()
            ):
                startup, validate, shutdown = self.get_commands()
                config = self.core.set_node_service(
                    self.node_id,
                    self.service_name,
                    dirs=self.temp_directories,
                    files=list(self.filename_combobox["values"]),
                    startups=startup,
                    validations=validate,
                    shutdowns=shutdown,
                )
                self.canvas_node.service_configs[self.service_name] = config
            for file in self.modified_files:
                file_configs = self.canvas_node.service_file_configs.setdefault(
                    self.service_name, {}
                )
                file_configs[file] = self.temp_service_files[file]
                # TODO: check if this is really needed
                self.app.core.set_node_service_file(
                    self.node_id, self.service_name, file, self.temp_service_files[file]
                )
            self.current_service_color("green")
        except grpc.RpcError as e:
            show_grpc_error(e, self.top, self.app)
        self.destroy()

    def display_service_file_data(self, event: tk.Event):
        filename = self.filename_combobox.get()
        self.service_file_data.text.delete(1.0, "end")
        self.service_file_data.text.insert("end", self.temp_service_files[filename])

    def update_temp_service_file_data(self, event: tk.Event):
        filename = self.filename_combobox.get()
        self.temp_service_files[filename] = self.service_file_data.text.get(1.0, "end")
        if self.temp_service_files[filename] != self.original_service_files.get(
            filename, ""
        ):
            self.modified_files.add(filename)
        else:
            self.modified_files.discard(filename)

    def is_custom_command(self):
        startup, validate, shutdown = self.get_commands()
        return (
            set(self.default_startup) != set(startup)
            or set(self.default_validate) != set(validate)
            or set(self.default_shutdown) != set(shutdown)
        )

    def has_new_files(self):
        return set(self.filenames) != set(self.filename_combobox["values"])

    def is_custom_service_file(self):
        return len(self.modified_files) > 0

    def is_custom_directory(self):
        return set(self.default_directories) != set(self.dir_list.listbox.get(0, "end"))

    def click_defaults(self):
        """
        clears out any custom configuration permanently
        """
        # clear coreclient data
        self.canvas_node.service_configs.pop(self.service_name, None)
        file_configs = self.canvas_node.service_file_configs.pop(self.service_name, {})
        file_configs.pop(self.service_name, None)
        self.temp_service_files = dict(self.original_service_files)
        self.modified_files.clear()

        # reset files tab
        files = list(self.default_config.configs[:])
        self.filenames = files
        self.filename_combobox.config(values=files)
        self.service_file_data.text.delete(1.0, "end")
        if len(files) > 0:
            filename = files[0]
            self.filename_combobox.set(filename)
            self.service_file_data.text.insert("end", self.temp_service_files[filename])

        # reset commands
        self.startup_commands_listbox.delete(0, tk.END)
        self.validate_commands_listbox.delete(0, tk.END)
        self.shutdown_commands_listbox.delete(0, tk.END)
        for cmd in self.default_startup:
            self.startup_commands_listbox.insert(tk.END, cmd)
        for cmd in self.default_validate:
            self.validate_commands_listbox.insert(tk.END, cmd)
        for cmd in self.default_shutdown:
            self.shutdown_commands_listbox.insert(tk.END, cmd)

        # reset directories
        self.directory_entry.delete(0, "end")
        self.dir_list.listbox.delete(0, "end")
        self.temp_directories = list(self.default_directories)
        for d in self.default_directories:
            self.dir_list.listbox.insert("end", d)

        self.current_service_color("")

    def click_copy(self):
        dialog = CopyServiceConfigDialog(self, self.app, self.node_id)
        dialog.show()

    @classmethod
    def append_commands(
        cls, commands: List[str], listbox: tk.Listbox, to_add: List[str]
    ):
        for cmd in to_add:
            commands.append(cmd)
            listbox.insert(tk.END, cmd)

    def get_commands(self):
        startup = self.startup_commands_listbox.get(0, "end")
        shutdown = self.shutdown_commands_listbox.get(0, "end")
        validate = self.validate_commands_listbox.get(0, "end")
        return startup, validate, shutdown

    def find_directory_button(self):
        d = filedialog.askdirectory(initialdir="/")
        self.directory_entry.delete(0, "end")
        self.directory_entry.insert("end", d)

    def add_directory(self):
        d = self.directory_entry.get()
        if os.path.isdir(d):
            if d not in self.temp_directories:
                self.dir_list.listbox.insert("end", d)
                self.temp_directories.append(d)

    def remove_directory(self):
        d = self.directory_entry.get()
        dirs = self.dir_list.listbox.get(0, "end")
        if d and d in self.temp_directories:
            self.temp_directories.remove(d)
            try:
                i = dirs.index(d)
                self.dir_list.listbox.delete(i)
            except ValueError:
                logging.debug("directory is not in the list")
        self.directory_entry.delete(0, "end")

    def directory_select(self, event):
        i = self.dir_list.listbox.curselection()
        if i:
            d = self.dir_list.listbox.get(i)
            self.directory_entry.delete(0, "end")
            self.directory_entry.insert("end", d)

    def current_service_color(self, color=""):
        """
        change the current service label color
        """
        listbox = self.master.current.listbox
        services = listbox.get(0, tk.END)
        listbox.itemconfig(services.index(self.service_name), bg=color)
