"""
emane configuration
"""
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

import grpc

from core.api.grpc.wrappers import ConfigOption, Node
from core.gui import images
from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum
from core.gui.themes import PADX, PADY
from core.gui.widgets import ConfigFrame

if TYPE_CHECKING:
    from core.gui.app import Application


class EmaneModelDialog(Dialog):
    def __init__(
        self,
        master: tk.BaseWidget,
        app: "Application",
        node: Node,
        model: str,
        iface_id: int = None,
    ) -> None:
        super().__init__(app, f"{node.name} {model} Configuration", master=master)
        self.node: Node = node
        self.model: str = f"emane_{model}"
        self.iface_id: int = iface_id
        self.config_frame: Optional[ConfigFrame] = None
        self.enabled: bool = not self.app.core.is_runtime()
        self.has_error: bool = False
        try:
            config = self.node.emane_model_configs.get((self.model, self.iface_id))
            if not config:
                config = self.node.emane_model_configs.get((self.model, None))
            if not config:
                config = self.app.core.get_emane_model_config(
                    self.node.id, self.model, self.iface_id
                )
            self.config: dict[str, ConfigOption] = config
            self.draw()
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Get EMANE Config Error", e)
            self.has_error: bool = True
            self.destroy()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.config_frame = ConfigFrame(self.top, self.app, self.config, self.enabled)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky=tk.NSEW, pady=PADY)
        self.draw_buttons()

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        state = tk.NORMAL if self.enabled else tk.DISABLED
        button = ttk.Button(frame, text="Apply", command=self.click_apply, state=state)
        button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_apply(self) -> None:
        self.config_frame.parse_config()
        key = (self.model, self.iface_id)
        self.node.emane_model_configs[key] = self.config
        self.destroy()


class EmaneConfigDialog(Dialog):
    def __init__(self, app: "Application", node: Node) -> None:
        super().__init__(app, f"{node.name} EMANE Configuration")
        self.node: Node = node
        self.radiovar: tk.IntVar = tk.IntVar()
        self.radiovar.set(1)
        self.emane_models: list[str] = [
            x.split("_")[1] for x in self.app.core.emane_models
        ]
        model = self.node.emane.split("_")[1]
        self.emane_model: tk.StringVar = tk.StringVar(value=model)
        self.emane_model_button: Optional[ttk.Button] = None
        self.enabled: bool = not self.app.core.is_runtime()
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.draw_emane_configuration()
        self.draw_emane_models()
        self.draw_emane_buttons()
        self.draw_spacer()
        self.draw_apply_and_cancel()

    def draw_emane_configuration(self) -> None:
        """
        draw the main frame for emane configuration
        """
        label = ttk.Label(
            self.top,
            text="The EMANE emulation system provides more complex wireless radio "
            "emulation \nusing pluggable MAC and PHY modules. Refer to the wiki "
            "for configuration option details",
            justify=tk.CENTER,
        )
        label.grid(pady=PADY)

        image = images.from_enum(ImageEnum.EDITNODE, width=images.BUTTON_SIZE)
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
        button.grid(sticky=tk.EW, pady=PADY)

    def draw_emane_models(self) -> None:
        """
        create a combobox that has all the known emane models
        """
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(1, weight=1)

        label = ttk.Label(frame, text="Model")
        label.grid(row=0, column=0, sticky=tk.W)

        # create combo box and its binding
        state = "readonly" if self.enabled else tk.DISABLED
        combobox = ttk.Combobox(
            frame, textvariable=self.emane_model, values=self.emane_models, state=state
        )
        combobox.grid(row=0, column=1, sticky=tk.EW)
        combobox.bind("<<ComboboxSelected>>", self.emane_model_change)

    def draw_emane_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW, pady=PADY)
        frame.columnconfigure(0, weight=1)
        image = images.from_enum(ImageEnum.EDITNODE, width=images.BUTTON_SIZE)
        self.emane_model_button = ttk.Button(
            frame,
            text=f"{self.emane_model.get()} options",
            image=image,
            compound=tk.RIGHT,
            command=self.click_model_config,
        )
        self.emane_model_button.image = image
        self.emane_model_button.grid(padx=PADX, sticky=tk.EW)

    def draw_apply_and_cancel(self) -> None:
        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW)
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        state = tk.NORMAL if self.enabled else tk.DISABLED
        button = ttk.Button(frame, text="Apply", command=self.click_apply, state=state)
        button.grid(row=0, column=0, padx=PADX, sticky=tk.EW)
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky=tk.EW)

    def click_model_config(self) -> None:
        """
        draw emane model configuration
        """
        model_name = self.emane_model.get()
        dialog = EmaneModelDialog(self, self.app, self.node, model_name)
        if not dialog.has_error:
            dialog.show()

    def emane_model_change(self, event: tk.Event) -> None:
        """
        update emane model options button
        """
        model_name = self.emane_model.get()
        self.emane_model_button.config(text=f"{model_name} options")

    def click_apply(self) -> None:
        self.node.emane = f"emane_{self.emane_model.get()}"
        self.destroy()
