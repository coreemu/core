import tkinter as tk

from coretk.dialogs.dialog import Dialog


class CustomNodesDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Custom Nodes", modal=True)
        self.save_button = None
        self.delete_button = None
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

        listbox = tk.Listbox(frame)
        listbox.grid(
            row=0,
            column=0,
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            sticky="nsew",
        )

        scrollbar.config(command=listbox.yview)

        frame = tk.Frame(frame)
        frame.grid(row=0, column=2, sticky="nsew")
        frame.columnconfigure(0, weight=1)

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

        button = tk.Button(frame, text="Save Configuration")
        button.grid(row=0, column=0, sticky="ew")

        button = tk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_create(self):
        pass

    def click_save(self):
        pass

    def click_delete(self):
        pass
