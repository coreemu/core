import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from core.api.grpc.wrappers import Hook, SessionState
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import CodeText, ListboxScroll

if TYPE_CHECKING:
    from core.gui.app import Application


class HookDialog(Dialog):
    def __init__(self, master: tk.BaseWidget, app: "Application") -> None:
        super().__init__(app, "Hook", master=master)
        self.name: tk.StringVar = tk.StringVar()
        self.codetext: Optional[CodeText] = None
        self.hook: Optional[Hook] = None
        self.state: tk.StringVar = tk.StringVar()
        self.editing: bool = False
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)

        # name and states
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=7)
        frame.columnconfigure(2, weight=1)
        label = ttk.Label(frame, text="Name")
        label.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        values = tuple(x.name for x in SessionState)
        initial_state = SessionState.RUNTIME.name
        self.state.set(initial_state)
        self.name.set(f"{initial_state.lower()}_hook.sh")
        combobox = ttk.Combobox(
            frame, textvariable=self.state, values=values, state="readonly"
        )
        combobox.grid(row=0, column=2, sticky=tk.EW)
        combobox.bind("<<ComboboxSelected>>", self.state_change)

        # data
        self.codetext = CodeText(self.top)
        self.codetext.text.insert(
            1.0,
            (
                "#!/bin/sh\n"
                "# session hook script; write commands here to execute on the host at the\n"
                "# specified state\n"
            ),
        )
        self.codetext.grid(sticky=tk.NSEW, pady=PADY)

        # button row
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=lambda: self.save())
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=lambda: self.destroy())
        button.grid(row=0, column=1, sticky=tk.EW)

    def state_change(self, event: tk.Event) -> None:
        if self.editing:
            return
        state_name = self.state.get()
        self.name.set(f"{state_name.lower()}_hook.sh")

    def set(self, hook: Hook) -> None:
        self.editing = True
        self.hook = hook
        self.name.set(hook.file)
        self.codetext.text.delete(1.0, tk.END)
        self.codetext.text.insert(tk.END, hook.data)
        state_name = hook.state.name
        self.state.set(state_name)

    def save(self) -> None:
        data = self.codetext.text.get("1.0", tk.END).strip()
        state = SessionState[self.state.get()]
        file_name = self.name.get()
        if self.editing:
            self.hook.state = state
            self.hook.file = file_name
            self.hook.data = data
        else:
            if file_name in self.app.core.session.hooks:
                messagebox.showerror(
                    "Hook Error",
                    f"Hook {file_name} already exists!",
                    parent=self.master,
                )
                return
            self.hook = Hook(state=state, file=file_name, data=data)
        self.destroy()


class HooksDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Hooks")
        self.listbox: Optional[tk.Listbox] = None
        self.edit_button: Optional[ttk.Button] = None
        self.delete_button: Optional[ttk.Button] = None
        self.selected: Optional[str] = None
        self.selected_index: Optional[int] = None
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        listbox_scroll = ListboxScroll(self.top)
        listbox_scroll.grid(sticky=tk.NSEW, pady=PADY)
        self.listbox = listbox_scroll.listbox
        self.listbox.bind("<<ListboxSelect>>", self.select)
        session = self.app.core.session
        for file in session.hooks:
            self.listbox.insert(tk.END, file)

        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        self.edit_button = ttk.Button(
            frame, text="Edit", state=tk.DISABLED, command=self.click_edit
        )
        self.edit_button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)
        self.delete_button = ttk.Button(
            frame, text="Delete", state=tk.DISABLED, command=self.click_delete
        )
        self.delete_button.grid(row=0, column=2, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=lambda: self.destroy())
        button.grid(row=0, column=3, sticky=tk.EW)

    def click_create(self) -> None:
        dialog = HookDialog(self, self.app)
        dialog.show()
        hook = dialog.hook
        if hook:
            self.app.core.session.hooks[hook.file] = hook
            self.listbox.insert(tk.END, hook.file)

    def click_edit(self) -> None:
        session = self.app.core.session
        hook = session.hooks.pop(self.selected)
        dialog = HookDialog(self, self.app)
        dialog.set(hook)
        dialog.show()
        session.hooks[hook.file] = hook
        self.selected = hook.file
        self.listbox.delete(self.selected_index)
        self.listbox.insert(self.selected_index, hook.file)
        self.listbox.select_set(self.selected_index)

    def click_delete(self) -> None:
        session = self.app.core.session
        del session.hooks[self.selected]
        self.listbox.delete(self.selected_index)
        self.edit_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)

    def select(self, event: tk.Event) -> None:
        if self.listbox.curselection():
            self.selected_index = self.listbox.curselection()[0]
            self.selected = self.listbox.get(self.selected_index)
            self.edit_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected = None
            self.selected_index = None
            self.edit_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
