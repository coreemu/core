"""
wlan configuration
"""

import ast
import tkinter as tk
from functools import partial


class WlanConfiguration:
    def __init__(self, canvas, canvas_node):

        self.canvas = canvas
        self.image = canvas_node.image
        self.node_type = canvas_node.node_type
        self.name = canvas_node.name
        self.canvas_node = canvas_node

        self.top = tk.Toplevel()
        self.top.title("wlan configuration")
        self.node_name = tk.StringVar()

        self.range_var = tk.DoubleVar()
        self.range_var.set(275.0)
        self.bandwidth_var = tk.IntVar()
        self.bandwidth_var.set(54000000)

        self.delay_var = tk.StringVar()

        self.image_modification()
        self.wlan_configuration()
        self.subnet()
        self.wlan_options()
        self.config_option()

    def image_modification(self):
        f = tk.Frame(self.top, bg="#d9d9d9")
        lbl = tk.Label(f, text="Node name: ", bg="#d9d9d9")
        lbl.grid(row=0, column=0, padx=3, pady=3)
        e = tk.Entry(f, textvariable=self.node_name, bg="white")
        e.grid(row=0, column=1, padx=3, pady=3)
        b = tk.Button(f, text="None")
        b.grid(row=0, column=2, padx=3, pady=3)
        b = tk.Button(f, text="not implemented")
        b.grid(row=0, column=3, padx=3, pady=3)
        f.grid(padx=2, pady=2, ipadx=2, ipady=2)

    def create_string_var(self, val):
        v = tk.StringVar()
        v.set(val)
        return v

    def scrollbar_command(self, entry_widget, delta, event):
        try:
            value = int(entry_widget.get())
        except ValueError:
            value = ast.literal_eval(entry_widget.get())
        entry_widget.delete(0, tk.END)
        if event == "-1":
            entry_widget.insert(tk.END, str(round(value + delta, 1)))
        elif event == "1":
            entry_widget.insert(tk.END, str(round(value - delta, 1)))

    def wlan_configuration(self):
        lbl = tk.Label(self.top, text="Wireless")
        lbl.grid(sticky=tk.W, padx=3, pady=3)

        f = tk.Frame(
            self.top,
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
            bg="#d9d9d9",
        )

        lbl = tk.Label(
            f,
            text="The basic range model calculates on/off connectivity based on pixel distance between nodes.",
            bg="#d9d9d9",
        )
        lbl.grid(padx=4, pady=4)

        f1 = tk.Frame(f, bg="#d9d9d9")

        lbl = tk.Label(f1, text="Range: ", bg="#d9d9d9")
        lbl.grid(row=0, column=0)

        e = tk.Entry(f1, textvariable=self.range_var, width=5, bg="white")
        e.grid(row=0, column=1)

        lbl = tk.Label(f1, text="Bandwidth (bps): ", bg="#d9d9d9")
        lbl.grid(row=0, column=2)

        f11 = tk.Frame(f1, bg="#d9d9d9")
        sb = tk.Scrollbar(f11, orient=tk.VERTICAL)
        e = tk.Entry(f11, textvariable=self.bandwidth_var, width=10, bg="white")
        sb.config(command=partial(self.scrollbar_command, e, 1000000))
        e.grid()
        sb.grid(row=0, column=1)
        f11.grid(row=0, column=3)

        # e = tk.Entry(f1, textvariable=self.bandwidth_var, width=10)
        # e.grid(row=0, column=4)
        f1.grid(sticky=tk.W, padx=4, pady=4)

        f2 = tk.Frame(f, bg="#d9d9d9")
        lbl = tk.Label(f2, text="Delay (us): ", bg="#d9d9d9")
        lbl.grid(row=0, column=0)

        f21 = tk.Frame(f2, bg="#d9d9d9")
        sb = tk.Scrollbar(f21, orient=tk.VERTICAL)
        e = tk.Entry(f21, textvariable=self.create_string_var(20000), bg="white")
        sb.config(command=partial(self.scrollbar_command, e, 5000))
        e.grid()
        sb.grid(row=0, column=1)
        f21.grid(row=0, column=1)

        lbl = tk.Label(f2, text="Loss (%): ", bg="#d9d9d9")
        lbl.grid(row=0, column=2)

        f22 = tk.Frame(f2, bg="#d9d9d9")
        sb = tk.Scrollbar(f22, orient=tk.VERTICAL)
        e = tk.Entry(f22, textvariable=self.create_string_var(0), bg="white")
        sb.config(command=partial(self.scrollbar_command, e, 0.1))
        e.grid()
        sb.grid(row=0, column=1)
        f22.grid(row=0, column=3)

        # e = tk.Entry(f2, textvariable=self.create_string_var(0))
        # e.grid(row=0, column=3)
        f2.grid(sticky=tk.W, padx=4, pady=4)

        f3 = tk.Frame(f, bg="#d9d9d9")
        lbl = tk.Label(f3, text="Jitter (us): ", bg="#d9d9d9")
        lbl.grid()
        f31 = tk.Frame(f3, bg="#d9d9d9")
        sb = tk.Scrollbar(f31, orient=tk.VERTICAL)
        e = tk.Entry(f31, textvariable=self.create_string_var(0), bg="white")
        sb.config(command=partial(self.scrollbar_command, e, 5000))
        e.grid()
        sb.grid(row=0, column=1)
        f31.grid(row=0, column=1)

        f3.grid(sticky=tk.W, padx=4, pady=4)
        f.grid(padx=3, pady=3)

    def subnet(self):
        f = tk.Frame(self.top)
        f1 = tk.Frame(f)
        lbl = tk.Label(f1, text="IPv4 subnet")
        lbl.grid()
        e = tk.Entry(f1, width=30, bg="white")
        e.grid(row=0, column=1)
        f1.grid()

        f2 = tk.Frame(f)
        lbl = tk.Label(f2, text="IPv6 subnet")
        lbl.grid()
        e = tk.Entry(f2, width=30, bg="white")
        e.grid(row=0, column=1)
        f2.grid()
        f.grid(sticky=tk.W, padx=3, pady=3)

    def wlan_options(self):
        f = tk.Frame(self.top)
        b = tk.Button(f, text="ns-2 mobility script...")
        b.pack(side=tk.LEFT, padx=1)
        b = tk.Button(f, text="Link to all routers")
        b.pack(side=tk.LEFT, padx=1)
        b = tk.Button(f, text="Choose WLAN members")
        b.pack(side=tk.LEFT, padx=1)
        f.grid(sticky=tk.W)

    def config_option(self):
        f = tk.Frame(self.top, bg="#d9d9d9")
        b = tk.Button(f, text="Apply", bg="#d9d9d9")
        b.grid(padx=2, pady=2)
        b = tk.Button(f, text="Cancel", bg="#d9d9d9", command=self.top.destroy)
        b.grid(row=0, column=1, padx=2, pady=2)
        f.grid(padx=4, pady=4)
