"""
emane configuration
"""
import logging
import tkinter as tk
import webbrowser
from tkinter import ttk

import grpc

from coretk.dialogs.dialog import Dialog
from coretk.errors import show_grpc_error
from coretk.images import ImageEnum, Images
from coretk.widgets import ConfigFrame

PAD = 5


class GlobalEmaneDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "EMANE Configuration", modal=True)
        self.config_frame = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.app.core.emane_config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PAD)
        self.draw_spacer()
        self.draw_buttons()

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew", padx=PAD)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        self.config_frame.parse_config()
        self.destroy()


class EmaneModelDialog(Dialog):
    def __init__(self, master, app, node, model, interface=None):
        super().__init__(master, app, f"{node.name} {model} Configuration", modal=True)
        self.node = node
        self.model = f"emane_{model}"
        self.interface = interface
        self.config_frame = None
        try:
            self.config = self.app.core.get_emane_model_config(
                self.node.id, self.model, self.interface
            )
        except grpc.RpcError as e:
            show_grpc_error(e)
            self.destroy()
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PAD)
        self.draw_spacer()
        self.draw_buttons()

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew", padx=PAD)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        self.config_frame.parse_config()
        self.app.core.set_emane_model_config(
            self.node.id, self.model, self.config, self.interface
        )
        self.destroy()


class EmaneConfigDialog(Dialog):
    def __init__(self, master, app, canvas_node):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} EMANE Configuration", modal=True
        )
        self.app = app
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.radiovar = tk.IntVar()
        self.radiovar.set(1)
        self.emane_models = [x.split("_")[1] for x in self.app.core.emane_models]
        self.emane_model = tk.StringVar(value=self.node.emane.split("_")[1])
        self.emane_model_button = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.draw_emane_configuration()
        self.draw_emane_models()
        self.draw_emane_buttons()
        self.draw_spacer()
        self.draw_apply_and_cancel()

    def draw_emane_configuration(self):
        """
        draw the main frame for emane configuration

        :return: nothing
        """
        label = ttk.Label(
            self.top,
            text="The EMANE emulation system provides more complex wireless radio emulation "
            "\nusing pluggable MAC and PHY modules. Refer to the wiki for configuration option details",
            justify=tk.CENTER,
        )
        label.grid(pady=PAD)

        image = Images.get(ImageEnum.EDITNODE, 16)
        button = ttk.Button(
            self.top,
            image=image,
            text="EMANE Wiki",
            compound=tk.RIGHT,
            command=lambda: webbrowser.open_new(
                "https://github.com/adjacentlink/emane/wiki"
            ),
        )
        button.image = image
        button.grid(sticky="ew", pady=PAD)

    def draw_emane_models(self):
        """
        create a combobox that has all the known emane models

        :return: nothing
        """
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PAD)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Model")
        label.grid(row=0, column=0, sticky="w")

        # create combo box and its binding
        combobox = ttk.Combobox(
            frame,
            textvariable=self.emane_model,
            values=self.emane_models,
            state="readonly",
        )
        combobox.grid(row=0, column=1, sticky="ew")
        combobox.bind("<<ComboboxSelected>>", self.emane_model_change)

    def draw_emane_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PAD)
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        image = Images.get(ImageEnum.EDITNODE, 16)
        self.emane_model_button = ttk.Button(
            frame,
            text=f"{self.emane_model.get()} options",
            image=image,
            compound=tk.RIGHT,
            command=self.click_model_config,
        )
        self.emane_model_button.image = image
        self.emane_model_button.grid(row=0, column=0, padx=PAD, sticky="ew")

        image = Images.get(ImageEnum.EDITNODE, 16)
        button = ttk.Button(
            frame,
            text="EMANE options",
            image=image,
            compound=tk.RIGHT,
            command=self.click_emane_config,
        )
        button.image = image
        button.grid(row=0, column=1, sticky="ew")

    def draw_apply_and_cancel(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, padx=PAD, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_emane_config(self):
        dialog = GlobalEmaneDialog(self, self.app)
        dialog.show()

    def click_model_config(self):
        """
        draw emane model configuration

        :return: nothing
        """
        model_name = self.emane_model.get()
        logging.info("configuring emane model: %s", model_name)
        dialog = EmaneModelDialog(
            self, self.app, self.canvas_node.core_node, model_name
        )
        dialog.show()

    def emane_model_change(self, event):
        """
        update emane model options button

        :param event:
        :return: nothing
        """
        model_name = self.emane_model.get()
        self.emane_model_button.config(text=f"{model_name} options")

    def click_apply(self):
        self.node.emane = f"emane_{self.emane_model.get()}"
        self.destroy()
