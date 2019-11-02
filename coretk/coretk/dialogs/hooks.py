import tkinter as tk
from tkinter import ttk

from core.api.grpc import core_pb2
from coretk.dialogs.dialog import Dialog


class HookDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Hook", modal=True)
        self.name = tk.StringVar()
        self.data = None
        self.hook = None
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)

        # name and states
        frame = tk.Frame(self)
        frame.grid(row=0, sticky="ew", pady=2)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=7)
        frame.columnconfigure(2, weight=1)
        label = tk.Label(frame, text="Name")
        label.grid(row=0, column=0, sticky="ew")
        entry = tk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=1, sticky="ew")
        combobox = ttk.Combobox(frame, values=("DEFINITION", "CONFIGURATION"))
        combobox.grid(row=0, column=2, sticky="ew")

        # data
        self.data = tk.Text(self)
        self.data.grid(row=1, sticky="nsew", pady=2)

        # button row
        frame = tk.Frame(self)
        frame.grid(row=2, sticky="ew", pady=2)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = tk.Button(frame, text="Save", command=lambda: self.save())
        button.grid(row=0, column=0, sticky="ew")
        button = tk.Button(frame, text="Cancel", command=lambda: self.destroy())
        button.grid(row=0, column=1, sticky="ew")

    def set(self, hook):
        self.hook = hook
        self.name.set(hook.file)
        self.data.delete(1.0, tk.END)
        self.data.insert(tk.END, hook.data)

    def save(self):
        data = self.data.get("1.0", tk.END).strip()
        self.hook = core_pb2.Hook(file=self.name.get(), data=data)
        self.destroy()


class HooksDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Hooks", modal=True)
        self.listbox = None
        self.edit = None
        self.delete = None
        self.selected = None
        self.hooks = {}
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.listbox = tk.Listbox(self)
        self.listbox.grid(row=0, sticky="ew")
        self.listbox.bind("<<ListboxSelect>>", self.select)
        frame = tk.Frame(self)
        frame.grid(row=1, sticky="ew")
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        button = tk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky="ew")
        self.edit = tk.Button(
            frame, text="Edit", state=tk.DISABLED, command=self.click_edit
        )
        self.edit.grid(row=0, column=1, sticky="ew")
        self.delete = tk.Button(frame, text="Delete", state=tk.DISABLED)
        self.delete.grid(row=0, column=2, sticky="ew")
        button = tk.Button(frame, text="Cancel", command=lambda: self.destroy())
        button.grid(row=0, column=3, sticky="ew")

    def click_create(self):
        dialog = HookDialog(self, self.app)
        dialog.show()
        hook = dialog.hook
        if hook:
            self.hooks[hook.file] = hook
            self.listbox.insert(tk.END, hook.file)

    def click_edit(self):
        hook = self.hooks[self.selected]
        dialog = HookDialog(self, self.app)
        dialog.set(hook)
        dialog.show()

    def select(self, event):
        self.edit.config(state=tk.NORMAL)
        self.delete.config(state=tk.NORMAL)
        index = self.listbox.curselection()[0]
        self.selected = self.listbox.get(index)
