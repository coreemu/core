"""
emane configuration
"""
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import TYPE_CHECKING, Any

import grpc

from core.gui.dialogs.dialog import Dialog
from core.gui.errors import show_grpc_error
from core.gui.images import ImageEnum, Images
from core.gui.themes import PADX, PADY
from core.gui.widgets import ConfigFrame

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode


class GlobalEmaneDialog(Dialog):
    def __init__(self, master: Any, app: "Application"):
        super().__init__(master, app, "EMANE Configuration")
        self.config_frame = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.app.core.emane_config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PADY)
        self.draw_spacer()
        self.draw_buttons()

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        self.config_frame.parse_config()
        self.destroy()


class EmaneModelDialog(Dialog):
    def __init__(
        self,
        master: Any,
        app: "Application",
        canvas_node: "CanvasNode",
        model: str,
        interface: int = None,
    ):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} {model} Configuration"
        )
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.model = f"emane_{model}"
        self.interface = interface
        self.config_frame = None
        self.has_error = False
        try:
            self.config = self.canvas_node.emane_model_configs.get(
                (self.model, self.interface)
            )
            if not self.config:
                self.config = self.app.core.get_emane_model_config(
                    self.node.id, self.model, self.interface
                )
            self.draw()
        except grpc.RpcError as e:
            show_grpc_error(e, self.app, self.app)
            self.has_error = True
            self.destroy()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew", pady=PADY)
        self.draw_spacer()
        self.draw_buttons()

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_apply(self):
        self.config_frame.parse_config()
        key = (self.model, self.interface)
        self.canvas_node.emane_model_configs[key] = self.config
        self.destroy()


class EmaneConfigDialog(Dialog):
    def __init__(
        self, master: "Application", app: "Application", canvas_node: "CanvasNode"
    ):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} EMANE Configuration"
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
        """
        label = ttk.Label(
            self.top,
            text="The EMANE emulation system provides more complex wireless radio emulation "
            "\nusing pluggable MAC and PHY modules. Refer to the wiki for configuration option details",
            justify=tk.CENTER,
        )
        label.grid(pady=PADY)

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
        button.grid(sticky="ew", pady=PADY)

    def draw_emane_models(self):
        """
        create a combobox that has all the known emane models
        """
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PADY)
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
        frame.grid(sticky="ew", pady=PADY)
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
        self.emane_model_button.grid(row=0, column=0, padx=PADX, sticky="ew")

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
        button.grid(row=0, column=0, padx=PADX, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_emane_config(self):
        dialog = GlobalEmaneDialog(self, self.app)
        dialog.show()

    def click_model_config(self):
        """
        draw emane model configuration
        """
        model_name = self.emane_model.get()
        dialog = EmaneModelDialog(self, self.app, self.canvas_node, model_name)
        if not dialog.has_error:
            dialog.show()

    def emane_model_change(self, event: tk.Event):
        """
        update emane model options button
        """
        model_name = self.emane_model.get()
        self.emane_model_button.config(text=f"{model_name} options")

    def click_apply(self):
        self.node.emane = f"emane_{self.emane_model.get()}"
        self.destroy()
