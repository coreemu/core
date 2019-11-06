import tkinter as tk

from coretk.dialogs.dialog import Dialog
from coretk.dialogs.nodeicon import IconDialog
from coretk.widgets import CheckboxList, ListboxScroll


class ServicesSelectDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Node Services", modal=True)
        self.groups = None
        self.services = None
        self.current = None
        self.current_services = set()
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame = tk.Frame(self)
        frame.grid(stick="nsew")
        frame.rowconfigure(0, weight=1)
        for i in range(3):
            frame.columnconfigure(i, weight=1)
        self.groups = ListboxScroll(frame, text="Groups")
        self.groups.grid(row=0, column=0, sticky="nsew")
        for group in sorted(self.app.core.services):
            self.groups.listbox.insert(tk.END, group)
        self.groups.listbox.bind("<<ListboxSelect>>", self.handle_group_change)

        self.services = CheckboxList(
            frame, text="Services", clicked=self.service_clicked
        )
        self.services.grid(row=0, column=1, sticky="nsew")

        self.current = ListboxScroll(frame, text="Selected")
        self.current.grid(row=0, column=2, sticky="nsew")

        frame = tk.Frame(self)
        frame.grid(stick="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = tk.Button(frame, text="Save")
        button.grid(row=0, column=0, sticky="ew")
        button = tk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def handle_group_change(self, event):
        selection = self.groups.listbox.curselection()
        if selection:
            index = selection[0]
            group = self.groups.listbox.get(index)
            self.services.clear()
            for service in sorted(self.app.core.services[group], key=lambda x: x.name):
                self.services.add(service.name)

    def service_clicked(self, name, var):
        if var.get() and name not in self.current_services:
            self.current_services.add(name)
        elif not var.get() and name in self.current_services:
            self.current_services.remove(name)
        self.current.listbox.delete(0, tk.END)
        for name in sorted(self.current_services):
            self.current.listbox.insert(tk.END, name)


class CustomNodesDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Custom Nodes", modal=True)
        self.save_button = None
        self.delete_button = None
        self.name = tk.StringVar()
        self.image_button = None
        self.image = None
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.draw_node_config()
        self.draw_node_buttons()
        self.draw_buttons()

    def draw_node_config(self):
        frame = tk.Frame(self)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")

        listbox = tk.Listbox(frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set)
        listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar.config(command=listbox.yview)

        frame = tk.Frame(frame)
        frame.grid(row=0, column=2, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        entry = tk.Entry(frame, textvariable=self.name)
        entry.grid(sticky="ew")
        self.image_button = tk.Button(frame, text="Icon", command=self.click_icon)
        self.image_button.grid(sticky="ew")
        button = tk.Button(frame, text="Services", command=self.click_services)
        button.grid(sticky="ew")

    def draw_node_buttons(self):
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

    def draw_buttons(self):
        frame = tk.Frame(self)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = tk.Button(frame, text="Save", command=self.click_save)
        button.grid(row=0, column=0, sticky="ew")

        button = tk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_icon(self):
        dialog = IconDialog(self, self.app, self.name.get(), self.image)
        dialog.show()
        if dialog.image:
            self.image = dialog.image
            self.image_button.config(image=self.image)

    def click_services(self):
        dialog = ServicesSelectDialog(self, self.app)
        dialog.show()

    def click_create(self):
        pass

    def click_save(self):
        pass

    def click_delete(self):
        pass
