import tkinter as tk

from coretk.dialogs.dialog import Dialog


class Widget:
    def __init__(self, name, command):
        self.name = name
        self.command = command


class ObserverWidgetsDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Observer Widgets", modal=True)
        self.config_widgets = {}
        self.widgets = None
        self.save_button = None
        self.delete_button = None
        self.selected = None
        self.selected_index = None
        self.name = tk.StringVar()
        self.command = tk.StringVar()
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.draw_widgets()
        self.draw_widget_fields()
        self.draw_widget_buttons()
        self.draw_apply_buttons()

    def draw_widgets(self):
        frame = tk.Frame(self)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.widgets = tk.Listbox(
            frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set
        )
        self.widgets.grid(row=0, column=0, sticky="nsew")
        self.widgets.bind("<<ListboxSelect>>", self.handle_widget_change)

        scrollbar.config(command=self.widgets.yview)

    def draw_widget_fields(self):
        frame = tk.Frame(self)
        frame.grid(sticky="ew")
        frame.columnconfigure(1, weight=1)

        label = tk.Label(frame, text="Name")
        label.grid(row=0, column=0, sticky="w")
        entry = tk.Entry(frame, textvariable=self.name)
        entry.grid(row=0, column=1, sticky="ew")

        label = tk.Label(frame, text="Command")
        label.grid(row=1, column=0, sticky="w")
        entry = tk.Entry(frame, textvariable=self.command)
        entry.grid(row=1, column=1, sticky="ew")

    def draw_widget_buttons(self):
        frame = tk.Frame(self)
        frame.grid(pady=2, sticky="ew")
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        button = tk.Button(frame, text="Create", command=self.click_create)
        button.grid(row=0, column=0, sticky="ew")

        self.save_button = tk.Button(
            frame, text="Save", state=tk.DISABLED, command=self.click_save
        )
        self.save_button.grid(row=0, column=1, sticky="ew")

        self.delete_button = tk.Button(
            frame, text="Delete", state=tk.DISABLED, command=self.click_delete
        )
        self.delete_button.grid(row=0, column=2, sticky="ew")

    def draw_apply_buttons(self):
        frame = tk.Frame(self)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = tk.Button(
            frame, text="Save Configuration", command=self.click_save_configuration
        )
        button.grid(row=0, column=0, sticky="ew")

        button = tk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_save_configuration(self):
        pass

    def click_create(self):
        name = self.name.get()
        if name not in self.config_widgets:
            command = self.command.get()
            widget = Widget(name, command)
            self.config_widgets[name] = widget
            self.widgets.insert(tk.END, name)

    def click_save(self):
        name = self.name.get()
        if self.selected:
            previous_name = self.selected
            self.selected = name
            widget = self.config_widgets.pop(previous_name)
            widget.name = name
            widget.command = self.command.get()
            self.config_widgets[name] = widget
            self.widgets.delete(self.selected_index)
            self.widgets.insert(self.selected_index, name)
            self.widgets.selection_set(self.selected_index)

    def click_delete(self):
        if self.selected:
            self.widgets.delete(self.selected_index)
            del self.config_widgets[self.selected]
            self.selected = None
            self.selected_index = None
            self.name.set("")
            self.command.set("")
            self.widgets.selection_clear(0, tk.END)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)

    def handle_widget_change(self, event):
        selection = self.widgets.curselection()
        if selection:
            self.selected_index = selection[0]
            self.selected = self.widgets.get(self.selected_index)
            widget = self.config_widgets[self.selected]
            self.name.set(widget.name)
            self.command.set(widget.command)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        else:
            self.selected_index = None
            self.selected = None
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
