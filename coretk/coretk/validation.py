"""
input validation
"""
import logging
import tkinter as tk

import netaddr
from netaddr import IPNetwork


class InputValidation:
    def __init__(self, app):
        self.master = app.master
        self.positive_int = None
        self.positive_float = None
        self.name = None
        self.register()

    def register(self):
        self.positive_int = self.master.register(self.check_positive_int)
        self.positive_float = self.master.register(self.check_positive_float)
        self.name = self.master.register(self.check_node_name)

    def ip_focus_out(self, event):
        value = event.widget.get()
        try:
            IPNetwork(value)
        except netaddr.core.AddrFormatError:
            event.widget.delete(0, tk.END)
            event.widget.insert(tk.END, "invalid")

    def focus_out(self, event, default):
        value = event.widget.get()
        if value == "":
            event.widget.insert(tk.END, default)

    def check_positive_int(self, s):
        logging.debug("int validation...")
        if len(s) == 0:
            return True
        try:
            int_value = int(s)
            if int_value >= 0:
                return True
            return False
        except ValueError:
            return False

    def check_positive_float(self, s):
        logging.debug("float validation...")
        if len(s) == 0:
            return True
        try:
            float_value = float(s)
            if float_value >= 0.0:
                return True
            return False
        except ValueError:
            return False

    def check_node_name(self, s):
        logging.debug("node name validation...")
        if len(s) < 0:
            return False
        if len(s) == 0:
            return True
        for char in s:
            if not char.isalnum() and char != "_":
                return False
        return True

    def check_canvas_int(sefl, s):
        logging.debug("int validation...")
        if len(s) == 0:
            return True
        try:
            int_value = int(s)
            if int_value >= 0:
                return True
            return False
        except ValueError:
            return False

    def check_canvas_float(self, s):
        logging.debug("canvas float validation")
        if not s:
            return True
        try:
            float_value = float(s)
            if float_value >= 0.0:
                return True
            return False
        except ValueError:
            return False
