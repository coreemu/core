"""
input validation
"""
import re
import tkinter as tk

import netaddr
from netaddr import IPNetwork


class InputValidation:
    def __init__(self, app):
        self.master = app.master
        self.positive_int = None
        self.positive_float = None
        self.name = None
        self.ip4 = None
        self.register()

    def register(self):
        self.positive_int = self.master.register(self.check_positive_int)
        self.positive_float = self.master.register(self.check_positive_float)
        self.name = self.master.register(self.check_node_name)
        self.ip4 = self.master.register(self.check_ip4)

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
        if len(s) < 0:
            return False
        if len(s) == 0:
            return True
        for char in s:
            if not char.isalnum() and char != "_":
                return False
        return True

    def check_canvas_int(sefl, s):
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
        if not s:
            return True
        try:
            float_value = float(s)
            if float_value >= 0.0:
                return True
            return False
        except ValueError:
            return False

    def check_ip4(self, s):
        if not s:
            return True
        pat = re.compile("^([0-9]+[.])*[0-9]*$")
        if pat.match(s) is not None:
            _32bits = s.split(".")
            if len(_32bits) > 4:
                return False
            for _8bits in _32bits:
                if (
                    (_8bits and int(_8bits) > 225)
                    or len(_8bits) > 3
                    or (_8bits.startswith("0") and len(_8bits) > 1)
                ):
                    return False
            return True
        else:
            return False
