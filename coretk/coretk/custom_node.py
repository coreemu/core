"""
edit node types
"""

import tkinter as tk


class EditNodeTypes:
    def __init__(self):
        self.top = tk.Toplevel
        self.top.title("CORE Node Types")

    def node_types(self):
        """
        list box of node types
        :return:
        """
        lbl = tk.Label(self.top, text="Node types")
        lbl.grid()
