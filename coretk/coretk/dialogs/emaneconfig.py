"""
emane configuration
"""

import logging
import tkinter as tk
import webbrowser

from coretk.dialogs.dialog import Dialog
from coretk.dialogs.mobilityconfig import MobilityConfiguration
from coretk.images import ImageEnum, Images


class EmaneConfiguration(Dialog):
    def __init__(self, master, app, canvas_node):
        super().__init__(master, app, "emane configuration", modal=False)
        self.app = app
        self.canvas_node = canvas_node
        self.radiovar = tk.IntVar()
        self.radiovar.set(1)
        self.columnconfigure(0, weight=1)

        # draw
        self.node_name_and_image()
        self.emane_configuration()
        self.draw_ip_subnets()
        self.emane_options()
        self.draw_apply_and_cancel()

    def browse_emane_wiki(self):
        webbrowser.open_new("https://github.com/adjacentlink/emane/wiki")

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
        f = tk.Frame(self, bg="#d9d9d9")

        lbl = tk.Label(f, text="Node name:", bg="#d9d9d9")
        lbl.grid(row=0, column=0, padx=2, pady=2)
        e = tk.Entry(f, textvariable=self.create_text_variable(""), bg="white")
        e.grid(row=0, column=1, padx=2, pady=2)

        om = tk.OptionMenu(
            f,
            self.create_text_variable("None"),
            "(none)",
            "core1",
            "core2",
            command=self.choose_core,
        )
        om.grid(row=0, column=2, padx=2, pady=2)

        b = tk.Button(f, image=self.canvas_node.image)
        b.grid(row=0, column=3, padx=2, pady=2)

        f.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)

    def draw_option_buttons(self, parent):
        f = tk.Frame(parent, bg="#d9d9d9")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        b = tk.Button(
            f,
            text="model options",
            image=Images.get(ImageEnum.EDITNODE),
            compound=tk.RIGHT,
            bg="#d9d9d9",
            state=tk.DISABLED,
        )
        b.grid(row=0, column=0, padx=10, pady=2, sticky=tk.N + tk.S + tk.E + tk.W)
        b = tk.Button(
            f,
            text="EMANE options",
            image=Images.get(ImageEnum.EDITNODE),
            compound=tk.RIGHT,
            bg="#d9d9d9",
        )
        b.grid(row=0, column=1, padx=10, pady=2, sticky=tk.N + tk.S + tk.E + tk.W)
        f.grid(row=4, column=0, sticky=tk.N + tk.S + tk.E + tk.W)

    def radiobutton_text(self, val):
        """
        get appropriate text based on radio value

        :return: the text value to configure button
        """
        if val == 1:
            return "none"
        elif val == 2:
            return "rfpipe options"
        elif val == 3:
            return "ieee80211abg options"
        elif val == 4:
            return "commeffect options"
        elif val == 5:
            return "bypass options"
        elif val == 6:
            return "tdma options"
        else:
            logging.debug("emaneconfig.py invalid radio value")
            return ""

    def click_radio_button(self):
        print(type(self.radiovar.get()))
        config_frame = self.grid_slaves(row=2, column=0)[0]
        option_button_frame = config_frame.grid_slaves(row=4, column=0)[0]
        b = option_button_frame.grid_slaves(row=0, column=0)[0]
        text = self.radiobutton_text(self.radiovar.get())
        if text == "none":
            state = tk.DISABLED
        else:
            state = tk.NORMAL
        b.config(text=text, state=state)
        # b.config(text=)

    def draw_emane_models(self, parent):
        models = ["none", "rfpipe", "ieee80211abg", "commeffect", "bypass", "tdma"]
        f = tk.Frame(
            parent,
            bg="#d9d9d9",
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )
        value = 1
        for m in models:
            b = tk.Radiobutton(
                f,
                text=m,
                variable=self.radiovar,
                indicatoron=True,
                value=value,
                bg="#d9d9d9",
                highlightthickness=0,
                command=self.click_radio_button,
            )
            b.grid(sticky=tk.W)
            value = value + 1
        f.grid(row=3, column=0, sticky=tk.W + tk.E)

    def draw_text_label_and_entry(self, parent, label_text, entry_text):
        """
        draw a label and an entry on a single row

        :return: nothing
        """
        var = tk.StringVar()
        var.set(entry_text)
        f = tk.Frame(parent)
        lbl = tk.Label(f, text=label_text)
        lbl.grid(row=0, column=0)
        e = tk.Entry(f, textvariable=var, bg="white")
        e.grid(row=0, column=1)
        f.grid(stick=tk.W)

    def emane_configuration(self):
        lbl = tk.Label(self, text="Emane")
        lbl.grid(row=1, column=0)
        f = tk.Frame(
            self,
            bg="#d9d9d9",
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
            relief=tk.RAISED,
        )
        f.columnconfigure(0, weight=1)

        b = tk.Button(
            f,
            image=Images.get(ImageEnum.EDITNODE),
            text="EMANE Wiki",
            compound=tk.RIGHT,
            relief=tk.RAISED,
            bg="#d9d9d9",
            command=self.browse_emane_wiki,
        )
        b.grid(row=0, column=0, sticky=tk.W)

        lbl = tk.Label(
            f,
            text="The EMANE emulation system provides more complex wireless radio emulation "
            "\nusing pluggable MAC and PHY modules. Refer to the wiki for configuration option details",
            bg="#d9d9d9",
        )
        lbl.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)

        lbl = tk.Label(f, text="EMANE Models", bg="#d9d9d9")
        lbl.grid(row=2, column=0, sticky=tk.W)
        self.draw_option_buttons(f)
        self.draw_emane_models(f)
        f.grid(row=2, column=0, sticky=tk.N + tk.S + tk.E + tk.W)

    def draw_ip_subnets(self):
        self.draw_text_label_and_entry(self, "IPv4 subnet", "")
        self.draw_text_label_and_entry(self, "IPv6 subnet", "")

    def click_ns2_mobility_script(self):
        dialog = MobilityConfiguration(self, self.app, self.canvas_node)
        dialog.show()

    def emane_options(self):
        """
        create wireless node options

        :return:
        """
        f = tk.Frame(self)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        f.columnconfigure(2, weight=1)
        b = tk.Button(
            f,
            text="ns-2 mobility script...",
            command=lambda: self.click_ns2_mobility_script(),
        )
        # b.pack(side=tk.LEFT, padx=1)
        b.grid(row=0, column=0, padx=10, pady=2, sticky=tk.N + tk.S + tk.E + tk.W)
        b = tk.Button(f, text="Link to all routers")
        b.grid(row=0, column=1, padx=10, pady=2, sticky=tk.N + tk.S + tk.E + tk.W)
        # b.pack(side=tk.LEFT, padx=1)
        b = tk.Button(f, text="Choose WLAN members")
        b.grid(row=0, column=2, padx=10, pady=2, sticky=tk.N + tk.S + tk.E + tk.W)
        # b.pack(side=tk.LEFT, padx=1)
        f.grid(row=5, column=0, sticky=tk.N + tk.S + tk.E + tk.W)

    def draw_apply_and_cancel(self):
        f = tk.Frame(self, bg="#d9d9d9")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        b = tk.Button(f, text="Apply", bg="#d9d9d9")
        b.grid(row=0, column=0, padx=10, pady=2, sticky=tk.N + tk.S + tk.E + tk.W)
        b = tk.Button(f, text="Cancel", bg="#d9d9d9", command=self.destroy)
        b.grid(row=0, column=1, padx=10, pady=2, sticky=tk.N + tk.S + tk.E + tk.W)

        f.grid(sticky=tk.N + tk.S + tk.E + tk.W)
