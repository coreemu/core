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
        self.radiovar.set(1)
        self.startup_index = tk.IntVar()
        self.start_time = tk.IntVar()
        self.documentnew_img = Images.get(ImageEnum.DOCUMENTNEW)
        self.editdelete_img = Images.get(ImageEnum.EDITDELETE)
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
        entry = tk.Entry(frame2, textvariable=self.metadata)
        entry.grid(row=0, column=1)
        frame2.grid(row=1, column=0)
        frame.grid(row=0, column=0)

        frame = tk.Frame(self)
        tab_parent = ttk.Notebook(frame)
        tab1 = ttk.Frame(tab_parent)
        tab2 = ttk.Frame(tab_parent)
        tab3 = ttk.Frame(tab_parent)
        tab1.columnconfigure(0, weight=1)
        tab2.columnconfigure(0, weight=1)
        tab3.columnconfigure(0, weight=1)

        tab_parent.add(tab1, text="Files", sticky="nsew")
        tab_parent.add(tab2, text="Directories", sticky="nsew")
        tab_parent.add(tab3, text="Startup/shutdown", sticky="nsew")
        tab_parent.grid(row=0, column=0, sticky="nsew")
        frame.grid(row=1, column=0, sticky="nsew")

        # tab 1
        label = tk.Label(
            tab1, text="Config files and scripts that are generated for this service."
        )
        label.grid(row=0, column=0, sticky="nsew")

        frame = tk.Frame(tab1)
        label = tk.Label(frame, text="File name: ")
        label.grid(row=0, column=0)
        entry = tk.Entry(frame, textvariable=self.filename)
        entry.grid(row=0, column=1)
        button = tk.Button(frame, image=self.documentnew_img)
        button.grid(row=0, column=2)
        button = tk.Button(frame, image=self.editdelete_img)
        button.grid(row=0, column=3)
        frame.grid(row=1, column=0, sticky="nsew")

        frame = tk.Frame(tab1)
        button = tk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Copy this source file:",
            indicatoron=True,
        )
        button.grid(row=0, column=0)
        entry = tk.Entry(frame, state=tk.DISABLED)
        entry.grid(row=0, column=1)
        button = tk.Button(frame, text="not implemented")
        button.grid(row=0, column=2)
        frame.grid(row=2, column=0, sticky="nsew")

        frame = tk.Frame(tab1)
        button = tk.Radiobutton(
            frame,
            variable=self.radiovar,
            text="Use text below for file contents:",
            indicatoron=True,
        )
        button.grid(row=0, column=0)
        button = tk.Button(frame, text="not implemented")
        button.grid(row=0, column=1)
        button = tk.Button(frame, text="not implemented")
        button.grid(row=0, column=2)
        frame.grid(row=3, column=0, sticky="nsew")

        # tab 2
        label = tk.Label(
            tab2,
            text="Directories required by this service that are unique for each node.",
        )
        label.grid(row=0, column=0, sticky="nsew")

        # tab 3
        label_frame = tk.LabelFrame(tab3, text="Startup commands")
        label_frame.columnconfigure(0, weight=1)
        frame = tk.Frame(label_frame)
        frame.columnconfigure(0, weight=1)
        entry = tk.Entry(frame, textvariable=tk.StringVar())
        entry.grid(row=0, column=0, stick="nsew")
        button = tk.Button(frame, image=self.documentnew_img)
        button.grid(row=0, column=1, sticky="nsew")
        button = tk.Button(frame, image=self.editdelete_img)
        button.grid(row=0, column=2, sticky="nsew")
        frame.grid(row=0, column=0, sticky="nsew")
        listbox_scroll = ListboxScroll(label_frame)
        listbox_scroll.listbox.config(height=4)
        listbox_scroll.grid(row=1, column=0, sticky="nsew")
        label_frame.grid(row=2, column=0, sticky="nsew")

        label_frame = tk.LabelFrame(tab3, text="Shutdown commands")
        label_frame.columnconfigure(0, weight=1)
        frame = tk.Frame(label_frame)
        frame.columnconfigure(0, weight=1)
        entry = tk.Entry(frame, textvariable=tk.StringVar())
        entry.grid(row=0, column=0, sticky="nsew")
        button = tk.Button(frame, image=self.documentnew_img)
        button.grid(row=0, column=1, sticky="nsew")
        button = tk.Button(frame, image=self.editdelete_img)
        button.grid(row=0, column=2, sticky="nsew")
        frame.grid(row=0, column=0, sticky="nsew")
        listbox_scroll = ListboxScroll(label_frame)
        listbox_scroll.listbox.config(height=4)
        listbox_scroll.grid(row=1, column=0, sticky="nsew")
        label_frame.grid(row=3, column=0, sticky="nsew")

        label_frame = tk.LabelFrame(tab3, text="Validate commands")
        label_frame.columnconfigure(0, weight=1)
        frame = tk.Frame(label_frame)
        frame.columnconfigure(0, weight=1)
        entry = tk.Entry(frame, textvariable=tk.StringVar())
        entry.grid(row=0, column=0, sticky="nsew")
        button = tk.Button(frame, image=self.documentnew_img)
        button.grid(row=0, column=1, sticky="nsew")
        button = tk.Button(frame, image=self.editdelete_img)
        button.grid(row=0, column=2, sticky="nsew")
        frame.grid(row=0, column=0, sticky="nsew")
        listbox_scroll = ListboxScroll(label_frame)
        listbox_scroll.listbox.config(height=4)
        listbox_scroll.grid(row=1, column=0, sticky="nsew")
        label_frame.grid(row=4, column=0, sticky="nsew")

        button = tk.Button(
            self, text="onle store values that have changed from their defaults"
        )
        button.grid(row=2, column=0)

        frame = tk.Frame(self)
        button = tk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="nsew")
        button = tk.Button(frame, text="Dafults", command=self.click_defaults)
        button.grid(row=0, column=1, sticky="nsew")
        button = tk.Button(frame, text="Copy...", command=self.click_copy)
        button.grid(row=0, column=2, sticky="nsew")
        button = tk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=3, sticky="nsew")
        frame.grid(row=3, column=0)

    def click_apply(self, event):
        print("not implemented")

    def click_defaults(self, event):
        print("not implemented")

    def click_copy(self, event):
        print("not implemented")

    def click_cancel(self, event):
        print("not implemented")
