"""
emane configuration
"""

import logging
import tkinter as tk
import webbrowser
from tkinter import ttk

from coretk.dialogs.dialog import Dialog
from coretk.images import ImageEnum, Images
from coretk.widgets import ConfigFrame

PAD_X = 2
PAD_Y = 2


class EmaneConfiguration(Dialog):
    def __init__(self, master, app, canvas_node):
        super().__init__(master, app, "emane configuration", modal=False)
        self.app = app
        self.canvas_node = canvas_node
        self.radiovar = tk.IntVar()
        self.radiovar.set(1)
        self.columnconfigure(0, weight=1)

        # list(string) of emane models
        self.emane_models = None

        self.emane_dialog = Dialog(self, app, "emane configuration", modal=False)
        self.emane_model_dialog = None
        self.emane_model_combobox = None

        # draw
        self.node_name_and_image()
        self.emane_configuration()
        self.draw_ip_subnets()
        self.emane_options()
        self.draw_apply_and_cancel()

        self.emane_config_frame = None
        self.options = app.core.emane_config
        self.model_options = None
        self.model_config_frame = None

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

        cbb = ttk.Combobox(f, values=["(none)", "core1", "core2"], state="readonly")
        cbb.current(0)
        cbb.grid(row=0, column=2, padx=2, pady=2)

        b = tk.Button(f, image=self.canvas_node.image)
        b.grid(row=0, column=3, padx=2, pady=2)

        f.grid(row=0, column=0, sticky="nsew")

    def save_emane_option(self):
        self.emane_config_frame.parse_config()
        self.emane_dialog.destroy()

    def draw_emane_options(self):
        if not self.emane_dialog.winfo_exists():
            self.emane_dialog = Dialog(
                self, self.app, "emane configuration", modal=False
            )

        if self.options is None:
            session_id = self.app.core.session_id
            response = self.app.core.client.get_emane_config(session_id)
            logging.info("emane config: %s", response)
            self.options = response.config

        self.emane_dialog.columnconfigure(0, weight=1)
        self.emane_dialog.rowconfigure(0, weight=1)
        self.emane_config_frame = ConfigFrame(self.emane_dialog, config=self.options)
        self.emane_config_frame.draw_config()
        self.emane_config_frame.grid(sticky="nsew")

        frame = tk.Frame(self.emane_dialog)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        b1 = tk.Button(frame, text="Appy", command=self.save_emane_option)
        b1.grid(row=0, column=0, sticky="ew")
        b2 = tk.Button(frame, text="Cancel", command=self.emane_dialog.destroy)
        b2.grid(row=0, column=1, sticky="ew")
        self.emane_dialog.show()

    def save_emane_model_options(self):
        """
        configure the node's emane model on the fly

        :return: nothing
        """
        # get model name
        model_name = self.emane_models[self.emane_model_combobox.current()]

        # parse configuration
        config = self.model_config_frame.parse_config()

        # add string emane_ infront for grpc call
        response = self.app.core.client.set_emane_model_config(
            self.app.core.session_id,
            self.canvas_node.core_id,
            "emane_" + model_name,
            config,
        )
        logging.info(
            "emaneconfig.py config emane model (%s), result: %s",
            self.canvas_node.core_id,
            response,
        )

        # store the change locally
        self.app.core.emaneconfig_management.set_custom_emane_cloud_config(
            self.canvas_node.core_id, "emane_" + model_name
        )

        self.emane_model_dialog.destroy()

    def draw_model_options(self):
        """
        draw emane model configuration

        :return: nothing
        """
        # get model name
        model_name = self.emane_models[self.emane_model_combobox.current()]

        # create the dialog and the necessry widget
        if not self.emane_model_dialog or not self.emane_model_dialog.winfo_exists():
            self.emane_model_dialog = Dialog(
                self, self.app, f"{model_name} configuration", modal=False
            )
            self.emane_model_dialog.columnconfigure(0, weight=1)
            self.emane_model_dialog.rowconfigure(0, weight=1)

        # query for configurations
        session_id = self.app.core.session_id
        # add string emane_ before model name for grpc call
        response = self.app.core.client.get_emane_model_config(
            session_id, self.canvas_node.core_id, "emane_" + model_name
        )
        logging.info("emane model config %s", response)

        self.model_options = response.config
        self.model_config_frame = ConfigFrame(
            self.emane_model_dialog, config=self.model_options
        )
        self.model_config_frame.grid(sticky="nsew")
        self.model_config_frame.draw_config()

        frame = tk.Frame(self.emane_model_dialog)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        b1 = tk.Button(frame, text="Apply", command=self.save_emane_model_options)
        b1.grid(row=0, column=0, sticky="ew")
        b2 = tk.Button(frame, text="Cancel", command=self.emane_model_dialog.destroy)
        b2.grid(row=0, column=1, sticky="ew")
        self.emane_model_dialog.show()

    def draw_option_buttons(self, parent):
        f = tk.Frame(parent, bg="#d9d9d9")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        b = tk.Button(
            f,
            text=self.emane_models[0] + " options",
            image=Images.get(ImageEnum.EDITNODE),
            compound=tk.RIGHT,
            bg="#d9d9d9",
            command=self.draw_model_options,
        )
        b.grid(row=0, column=0, padx=10, pady=2, sticky="nsew")
        b = tk.Button(
            f,
            text="EMANE options",
            image=Images.get(ImageEnum.EDITNODE),
            compound=tk.RIGHT,
            bg="#d9d9d9",
            command=self.draw_emane_options,
        )
        b.grid(row=0, column=1, padx=10, pady=2, sticky="nsew")
        f.grid(row=4, column=0, sticky="nsew")

    def combobox_select(self, event):
        """
        update emane model options button

        :param event:
        :return: nothing
        """
        # get model name
        model_name = self.emane_models[self.emane_model_combobox.current()]

        # get the button and configure button text
        config_frame = self.grid_slaves(row=2, column=0)[0]
        option_button_frame = config_frame.grid_slaves(row=4, column=0)[0]
        b = option_button_frame.grid_slaves(row=0, column=0)[0]
        b.config(text=model_name + " options")

    def draw_emane_models(self, parent):
        """
        create a combobox that has all the known emane models

        :param parent: parent
        :return: nothing
        """
        # query for all the known model names
        session_id = self.app.core.session_id
        response = self.app.core.client.get_emane_models(session_id)
        self.emane_models = [x.split("_")[1] for x in response.models]

        # create combo box and its binding
        f = tk.Frame(
            parent,
            bg="#d9d9d9",
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )
        self.emane_model_combobox = ttk.Combobox(
            f, values=self.emane_models, state="readonly"
        )
        self.emane_model_combobox.grid()
        self.emane_model_combobox.current(0)
        self.emane_model_combobox.bind("<<ComboboxSelected>>", self.combobox_select)
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
        f.grid(stick=tk.W, padx=2, pady=2)

    def emane_configuration(self):
        """
        draw the main frame for emane configuration

        :return: nothing
        """
        # draw label
        lbl = tk.Label(self, text="Emane")
        lbl.grid(row=1, column=0)

        # main frame that has emane wiki, a short description, emane models and the configure buttons
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
            command=lambda: webbrowser.open_new(
                "https://github.com/adjacentlink/emane/wiki"
            ),
        )
        b.grid(row=0, column=0, sticky=tk.W)

        lbl = tk.Label(
            f,
            text="The EMANE emulation system provides more complex wireless radio emulation "
            "\nusing pluggable MAC and PHY modules. Refer to the wiki for configuration option details",
            bg="#d9d9d9",
        )
        lbl.grid(row=1, column=0, sticky="nsew")

        lbl = tk.Label(f, text="EMANE Models", bg="#d9d9d9")
        lbl.grid(row=2, column=0, sticky=tk.W)

        self.draw_emane_models(f)
        self.draw_option_buttons(f)

        f.grid(row=2, column=0, sticky="nsew")

    def draw_ip_subnets(self):
        self.draw_text_label_and_entry(self, "IPv4 subnet", "")
        self.draw_text_label_and_entry(self, "IPv6 subnet", "")

    def emane_options(self):
        """
        create wireless node options

        :return:
        """
        f = tk.Frame(self, bg="#d9d9d9")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        b = tk.Button(f, text="Link to all routers", bg="#d9d9d9")
        b.grid(row=0, column=0, padx=10, pady=2, sticky="nsew")
        b = tk.Button(f, text="Choose WLAN members", bg="#d9d9d9")
        b.grid(row=0, column=1, padx=10, pady=2, sticky="nsew")
        f.grid(row=5, column=0, sticky="nsew")

    def apply(self):
        # save emane configuration
        self.app.core.emane_config = self.options
        self.destroy()

    def draw_apply_and_cancel(self):
        f = tk.Frame(self, bg="#d9d9d9")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        b = tk.Button(f, text="Apply", bg="#d9d9d9", command=self.apply)
        b.grid(row=0, column=0, padx=10, pady=2, sticky="nsew")
        b = tk.Button(f, text="Cancel", bg="#d9d9d9", command=self.destroy)
        b.grid(row=0, column=1, padx=10, pady=2, sticky="nsew")

        f.grid(sticky="nsew")
