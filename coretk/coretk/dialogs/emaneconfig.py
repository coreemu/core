"""
emane configuration
"""

import tkinter as tk

from coretk.dialogs.dialog import Dialog


class EmaneConfiguration(Dialog):
    def __init__(self, master, app, canvas_node):
        super().__init__(master, app, "emane configuration", modal=False)
        self.canvas_node = canvas_node

    def create_text_variable(self, val):
        """
        create a string variable for convenience

        :param str val: entry text
        :return: nothing
        """
        var = tk.StringVar()
        var.set(val)
        return var

    def choose_core(self):
        print("not implemented")

    def node_name_and_image(self):
        f = tk.Frame(self)

        lbl = tk.Label(f, text="Node name:")
        lbl.grid(row=0, column=0)
        e = tk.Entry(f, textvariable=self.create_text_variable(""), bg="white")
        e.grid(row=0, column=1)

        om = tk.OptionMenu(
            f,
            self.create_text_variable("None"),
            "(none)",
            "core1",
            "core2",
            command=self.choose_core,
        )
        om.grid(row=0, column=2)

        # b = tk.Button(f,)
