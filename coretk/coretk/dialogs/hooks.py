import tkinter as tk
from tkinter import ttk

from core.api.grpc import core_pb2
from coretk.dialogs.dialog import Dialog


class HookDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Hook", modal=True)
        self.name = tk.StringVar()
        self.data = None
        self.hook = core_pb2.Hook()
        self.state = tk.StringVar()
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

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
        values = tuple(x for x in core_pb2.SessionState.Enum.keys() if x != "NONE")
        initial_state = core_pb2.SessionState.Enum.Name(core_pb2.SessionState.RUNTIME)
        self.state.set(initial_state)
        self.name.set(f"{initial_state.lower()}_hook.sh")
        combobox = ttk.Combobox(frame, textvariable=self.state, values=values)
        combobox.grid(row=0, column=2, sticky="ew")
        combobox.bind("<<ComboboxSelected>>", self.state_change)

        # data
        frame = tk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.grid(row=1, sticky="nsew", pady=2)
        self.data = tk.Text(frame)
        self.data.insert(
            1.0,
            (
                "#!/bin/sh\n"
                "# session hook script; write commands here to execute on the host at the\n"
                "# specified state\n"
            ),
        )
        self.data.grid(row=0, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(frame)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.data.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.data.yview)

        # button row
        frame = tk.Frame(self)
        frame.grid(row=2, sticky="ew", pady=2)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = tk.Button(frame, text="Save", command=lambda: self.save())
        button.grid(row=0, column=0, sticky="ew")
        button = tk.Button(frame, text="Cancel", command=lambda: self.destroy())
        button.grid(row=0, column=1, sticky="ew")

    def state_change(self, event):
        state_name = self.state.get()
        self.name.set(f"{state_name.lower()}_hook.sh")

    def set(self, hook):
        self.hook = hook
        self.name.set(hook.file)
        self.data.delete(1.0, tk.END)
        self.data.insert(tk.END, hook.data)
        state_name = core_pb2.SessionState.Enum.Name(hook.state)
        self.state.set(state_name)

    def save(self):
        data = self.data.get("1.0", tk.END).strip()
        state_value = core_pb2.SessionState.Enum.Value(self.state.get())
        self.hook.file = self.name.get()
        self.hook.data = data
        self.hook.state = state_value
        self.destroy()


class HooksDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Hooks", modal=True)
        self.listbox = None
        self.edit_button = None
        self.delete_button = None
        self.selected = None
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.listbox = tk.Listbox(self)
        self.listbox.grid(row=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self.select)
        for hook_file in self.app.core.hooks:
            self.listbox.insert(tk.END, hook_file)
        frame = tk.Frame(self)
        frame.grid(row=1, sticky="ew")
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        button = tk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky="ew")
        self.edit_button = tk.Button(
            frame, text="Edit", state=tk.DISABLED, command=self.click_edit
        )
        self.edit_button.grid(row=0, column=1, sticky="ew")
        self.delete_button = tk.Button(frame, text="Delete", state=tk.DISABLED)
        self.delete_button.grid(row=0, column=2, sticky="ew")
        button = tk.Button(frame, text="Cancel", command=lambda: self.destroy())
        button.grid(row=0, column=3, sticky="ew")

    def click_create(self):
        dialog = HookDialog(self, self.app)
        dialog.show()
        hook = dialog.hook
        if hook:
            self.app.core.hooks[hook.file] = hook
            self.listbox.insert(tk.END, hook.file)

    def click_edit(self):
        hook = self.app.core.hooks[self.selected]
        dialog = HookDialog(self, self.app)
        dialog.set(hook)
        dialog.show()

    def select(self, event):
        self.edit_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)
        index = self.listbox.curselection()[0]
        self.selected = self.listbox.get(index)
