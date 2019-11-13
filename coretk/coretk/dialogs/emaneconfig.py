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
        logging.info("not implemented")

    def node_name_and_image(self):
        f = ttk.Frame(self.top)

        lbl = ttk.Label(f, text="Node name:")
        lbl.grid(row=0, column=0, padx=2, pady=2)
        e = ttk.Entry(f, textvariable=self.create_text_variable(""))
        e.grid(row=0, column=1, padx=2, pady=2)

        cbb = ttk.Combobox(f, values=["(none)", "core1", "core2"], state="readonly")
        cbb.current(0)
        cbb.grid(row=0, column=2, padx=2, pady=2)

        b = ttk.Button(f, image=self.canvas_node.image)
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

        self.emane_dialog.top.columnconfigure(0, weight=1)
        self.emane_dialog.top.rowconfigure(0, weight=1)
        self.emane_config_frame = ConfigFrame(
            self.emane_dialog.top, config=self.options
        )
        self.emane_config_frame.draw_config()
        self.emane_config_frame.grid(sticky="nsew")

        frame = ttk.Frame(self.emane_dialog.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        b1 = ttk.Button(frame, text="Appy", command=self.save_emane_option)
        b1.grid(row=0, column=0, sticky="ew")
        b2 = ttk.Button(frame, text="Cancel", command=self.emane_dialog.destroy)
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
            self.emane_model_dialog.top.columnconfigure(0, weight=1)
            self.emane_model_dialog.top.rowconfigure(0, weight=1)

        # query for configurations
        session_id = self.app.core.session_id
        # add string emane_ before model name for grpc call
        response = self.app.core.client.get_emane_model_config(
            session_id, self.canvas_node.core_id, "emane_" + model_name
        )
        logging.info("emane model config %s", response)

        self.model_options = response.config
        self.model_config_frame = ConfigFrame(
            self.emane_model_dialog.top, config=self.model_options
        )
        self.model_config_frame.grid(sticky="nsew")
        self.model_config_frame.draw_config()

        frame = ttk.Frame(self.emane_model_dialog.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        b1 = ttk.Button(frame, text="Apply", command=self.save_emane_model_options)
        b1.grid(row=0, column=0, sticky="ew")
        b2 = ttk.Button(frame, text="Cancel", command=self.emane_model_dialog.destroy)
        b2.grid(row=0, column=1, sticky="ew")
        self.emane_model_dialog.show()

    def draw_option_buttons(self, parent):
        f = ttk.Frame(parent)
        f.grid(row=4, column=0, sticky="nsew")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        image = Images.get(ImageEnum.EDITNODE, 16)
        b = ttk.Button(
            f,
            text=self.emane_models[0] + " options",
            image=image,
            compound=tk.RIGHT,
            command=self.draw_model_options,
        )
        b.image = image
        b.grid(row=0, column=0, padx=10, pady=2, sticky="nsew")

        image = Images.get(ImageEnum.EDITNODE, 16)
        b = ttk.Button(
            f,
            text="EMANE options",
            image=image,
            compound=tk.RIGHT,
            command=self.draw_emane_options,
        )
        b.image = image
        b.grid(row=0, column=1, padx=10, pady=2, sticky="nsew")

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
        f = ttk.Frame(parent)
        self.emane_model_combobox = ttk.Combobox(
            f, values=self.emane_models, state="readonly"
        )
        self.emane_model_combobox.grid()
        self.emane_model_combobox.current(0)
        self.emane_model_combobox.bind("<<ComboboxSelected>>", self.combobox_select)
        f.grid(row=3, column=0, sticky="ew")

    def draw_text_label_and_entry(self, parent, label_text, entry_text):
        """
        draw a label and an entry on a single row

        :return: nothing
        """
        var = tk.StringVar()
        var.set(entry_text)
        f = ttk.Frame(parent)
        lbl = ttk.Label(f, text=label_text)
        lbl.grid(row=0, column=0)
        e = ttk.Entry(f, textvariable=var)
        e.grid(row=0, column=1)
        f.grid(stick=tk.W, padx=2, pady=2)

    def emane_configuration(self):
        """
        draw the main frame for emane configuration

        :return: nothing
        """
        # draw label
        lbl = ttk.Label(self.top, text="Emane")
        lbl.grid(row=1, column=0)

        # main frame that has emane wiki, a short description, emane models and the configure buttons
        f = ttk.Frame(self.top)
        f.columnconfigure(0, weight=1)

        image = Images.get(ImageEnum.EDITNODE, 16)
        b = ttk.Button(
            f,
            image=image,
            text="EMANE Wiki",
            compound=tk.RIGHT,
            command=lambda: webbrowser.open_new(
                "https://github.com/adjacentlink/emane/wiki"
            ),
        )
        b.image = image
        b.grid(row=0, column=0, sticky="w")

        lbl = ttk.Label(
            f,
            text="The EMANE emulation system provides more complex wireless radio emulation "
            "\nusing pluggable MAC and PHY modules. Refer to the wiki for configuration option details",
        )
        lbl.grid(row=1, column=0, sticky="nsew")

        lbl = ttk.Label(f, text="EMANE Models")
        lbl.grid(row=2, column=0, sticky="w")

        self.draw_emane_models(f)
        self.draw_option_buttons(f)

        f.grid(row=2, column=0, sticky="nsew")

    def draw_ip_subnets(self):
        self.draw_text_label_and_entry(self.top, "IPv4 subnet", "")
        self.draw_text_label_and_entry(self.top, "IPv6 subnet", "")

    def emane_options(self):
        """
        create wireless node options

        :return:
        """
        f = ttk.Frame(self.top)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        b = ttk.Button(f, text="Link to all routers")
        b.grid(row=0, column=0, padx=10, pady=2, sticky="nsew")
        b = ttk.Button(f, text="Choose WLAN members")
        b.grid(row=0, column=1, padx=10, pady=2, sticky="nsew")
        f.grid(row=5, column=0, sticky="nsew")

    def apply(self):
        # save emane configuration
        self.app.core.emane_config = self.options
        self.destroy()

    def draw_apply_and_cancel(self):
        f = ttk.Frame(self.top)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        b = ttk.Button(f, text="Apply", command=self.apply)
        b.grid(row=0, column=0, padx=10, pady=2, sticky="nsew")
        b = ttk.Button(f, text="Cancel", command=self.destroy)
        b.grid(row=0, column=1, padx=10, pady=2, sticky="nsew")

        f.grid(sticky="nsew")
