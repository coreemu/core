"Service configuration dialog"

import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog
from coretk.images import ImageEnum, Images
from coretk.widgets import ListboxScroll


class ServiceConfiguration(Dialog):
    def __init__(self, master, app, service_name, canvas_node):
        super().__init__(master, app, service_name + " service", modal=True)
        self.app = app
        self.service_name = service_name
        self.metadata = tk.StringVar()
        self.filename = tk.StringVar()
        self.radiovar = tk.IntVar()
        self.radiovar.set(2)
        self.startup_index = tk.IntVar()
        self.start_time = tk.IntVar()
        self.documentnew_img = Images.get(ImageEnum.DOCUMENTNEW)
        self.editdelete_img = Images.get(ImageEnum.EDITDELETE)
        self.tab_parent = None
        self.filenames = ["test1", "test2", "test3"]

        self.metadata_entry = None
        self.filename_combobox = None
        self.startup_commands_listbox = None
        self.shutdown_commands_listbox = None
        self.validate_commands_listbox = None

        self.draw()

    def draw(self):
        # self.columnconfigure(1, weight=1)
        frame = tk.Frame(self)
        frame1 = tk.Frame(frame)
        label = tk.Label(frame1, text=self.service_name)
        label.grid(row=0, column=0, sticky="ew")
        frame1.grid(row=0, column=0)
        frame2 = tk.Frame(frame)
        # frame2.columnconfigure(0, weight=1)
        # frame2.columnconfigure(1, weight=4)
        label = tk.Label(frame2, text="Meta-data")
        label.grid(row=0, column=0)
        self.metadata_entry = tk.Entry(frame2, textvariable=self.metadata)
        self.metadata_entry.grid(row=0, column=1)
        frame2.grid(row=1, column=0)
        frame.grid(row=0, column=0)

        frame = tk.Frame(self)
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
        label = tk.Label(
            tab1, text="Config files and scripts that are generated for this service."
        )
        label.grid(row=0, column=0, sticky="nsew")

        frame = tk.Frame(tab1)
        label = tk.Label(frame, text="File name: ")
        label.grid(row=0, column=0)
        self.filename_combobox = ttk.Combobox(frame, values=self.filenames)
        self.filename_combobox.grid(row=0, column=1)
        self.filename_combobox.current(0)
        button = tk.Button(frame, image=self.documentnew_img)
        button.bind("<Button-1>", self.add_filename)
        button.grid(row=0, column=2)
        button = tk.Button(frame, image=self.editdelete_img)
        button.bind("<Button-1>", self.delete_filename)
        button.grid(row=0, column=3)
        frame.grid(row=1, column=0, sticky="nsew")

        frame = tk.Frame(tab1)
        button = tk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Copy this source file:",
            indicatoron=True,
            value=1,
            state="disabled",
        )
        button.grid(row=0, column=0)
        entry = tk.Entry(frame, state=tk.DISABLED)
        entry.grid(row=0, column=1)
        button = tk.Button(frame, image=Images.get(ImageEnum.FILEOPEN))
        button.grid(row=0, column=2)
        frame.grid(row=2, column=0, sticky="nsew")

        frame = tk.Frame(tab1)
        button = tk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Use text below for file contents:",
            indicatoron=True,
            value=2,
        )
        button.grid(row=0, column=0)
        button = tk.Button(frame, image=Images.get(ImageEnum.FILEOPEN))
        button.grid(row=0, column=1)
        button = tk.Button(frame, image=Images.get(ImageEnum.DOCUMENTSAVE))
        button.grid(row=0, column=2)
        frame.grid(row=3, column=0, sticky="nsew")

        # tab 2
        label = tk.Label(
            tab2,
            text="Directories required by this service that are unique for each node.",
        )
        label.grid(row=0, column=0, sticky="nsew")

        # tab 3
        for i in range(3):
            label_frame = None
            if i == 0:
                label_frame = tk.LabelFrame(tab3, text="Startup commands")
            elif i == 1:
                label_frame = tk.LabelFrame(tab3, text="Shutdown commands")
            elif i == 2:
                label_frame = tk.LabelFrame(tab3, text="Validation commands")
            label_frame.columnconfigure(0, weight=1)
            frame = tk.Frame(label_frame)
            frame.columnconfigure(0, weight=1)
            entry = tk.Entry(frame, textvariable=tk.StringVar())
            entry.grid(row=0, column=0, stick="nsew")
            button = tk.Button(frame, image=self.documentnew_img)
            button.bind("<Button-1>", self.add_command)
            button.grid(row=0, column=1, sticky="nsew")
            button = tk.Button(frame, image=self.editdelete_img)
            button.grid(row=0, column=2, sticky="nsew")
            button.bind("<Button-1>", self.delete_command)
            frame.grid(row=0, column=0, sticky="nsew")
            listbox_scroll = ListboxScroll(label_frame)
            listbox_scroll.listbox.bind("<<ListboxSelect>>", self.update_entry)
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
            if i == 0:
                label_frame = tk.LabelFrame(tab4, text="Executables")
            elif i == 1:
                label_frame = tk.LabelFrame(tab4, text="Dependencies")

            label_frame.columnconfigure(0, weight=1)
            listbox_scroll = ListboxScroll(label_frame)
            listbox_scroll.listbox.config(height=4, state="disabled")
            listbox_scroll.grid(row=0, column=0, sticky="nsew")
            label_frame.grid(row=i, column=0, sticky="nsew")

        for i in range(3):
            frame = tk.Frame(tab4)
            frame.columnconfigure(0, weight=1)
            if i == 0:
                label = tk.Label(frame, text="Validation time:")
            elif i == 1:
                label = tk.Label(frame, text="Validation mode:")
            elif i == 2:
                label = tk.Label(frame, text="Validation period:")
            label.grid(row=i, column=0)
            entry = tk.Entry(frame, state="disabled", textvariable=tk.StringVar())
            entry.grid(row=i, column=1)
            frame.grid(row=2 + i, column=0, sticky="nsew")

        button = tk.Button(
            self, text="onle store values that have changed from their defaults"
        )
        button.grid(row=2, column=0)

        frame = tk.Frame(self)
        button = tk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="nsew")
        button = tk.Button(
            frame, text="Dafults", command=self.click_defaults, state="disabled"
        )
        button.grid(row=0, column=1, sticky="nsew")
        button = tk.Button(
            frame, text="Copy...", command=self.click_copy, state="disabled"
        )
        button.grid(row=0, column=2, sticky="nsew")
        button = tk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=3, sticky="nsew")
        frame.grid(row=3, column=0)

    def add_filename(self, event):
        frame_contains_button = event.widget.master
        combobox = frame_contains_button.grid_slaves(row=0, column=1)[0]
        filename = combobox.get()
        if filename not in combobox["values"]:
            combobox["values"] += (filename,)

    def delete_filename(self, event):
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
        metadata = self.metadata_entry.get()
        filenames = list(self.filename_combobox["values"])
        startup_commands = self.startup_commands_listbox.get(0, "end")
        shutdown_commands = self.shutdown_commands_listbox.get(0, "end")
        validate_commands = self.validate_commands_listbox.get(0, "end")
        print(
            metadata, filenames, startup_commands, shutdown_commands, validate_commands
        )

    def click_defaults(self):
        print("not implemented")

    def click_copy(self):
        print("not implemented")

    def click_cancel(self):
        print("not implemented")
