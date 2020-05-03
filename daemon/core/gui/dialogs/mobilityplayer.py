import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

import grpc

from core.api.grpc.mobility_pb2 import MobilityAction
from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum, Images
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.node import CanvasNode

ICON_SIZE = 16


class MobilityPlayer:
    def __init__(
        self,
        master: "Application",
        app: "Application",
        canvas_node: "CanvasNode",
        config,
    ):
        self.master = master
        self.app = app
        self.canvas_node = canvas_node
        self.config = config
        self.dialog = None
        self.state = None

    def show(self):
        if self.dialog:
            self.dialog.destroy()
        self.dialog = MobilityPlayerDialog(
            self.master, self.app, self.canvas_node, self.config
        )
        self.dialog.protocol("WM_DELETE_WINDOW", self.handle_close)
        if self.state == MobilityAction.START:
            self.set_play()
        elif self.state == MobilityAction.PAUSE:
            self.set_pause()
        else:
            self.set_stop()
        self.dialog.show()

    def handle_close(self):
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None

    def set_play(self):
        self.state = MobilityAction.START
        if self.dialog:
            self.dialog.set_play()

    def set_pause(self):
        self.state = MobilityAction.PAUSE
        if self.dialog:
            self.dialog.set_pause()

    def set_stop(self):
        self.state = MobilityAction.STOP
        if self.dialog:
            self.dialog.set_stop()


class MobilityPlayerDialog(Dialog):
    def __init__(
        self, master: Any, app: "Application", canvas_node: "CanvasNode", config
    ):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Mobility Player", modal=False
        )
        self.resizable(False, False)
        self.geometry("")
        self.canvas_node = canvas_node
        self.node = canvas_node.core_node
        self.config = config
        self.play_button = None
        self.pause_button = None
        self.stop_button = None
        self.progressbar = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)

        file_name = self.config["file"].value
        label = ttk.Label(self.top, text=file_name)
        label.grid(sticky="ew", pady=PADY)

        self.progressbar = ttk.Progressbar(self.top, mode="indeterminate")
        self.progressbar.grid(sticky="ew", pady=PADY)

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PADY)
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        image = Images.get(ImageEnum.START, width=int(ICON_SIZE * self.app.app_scale))
        self.play_button = ttk.Button(frame, image=image, command=self.click_play)
        self.play_button.image = image
        self.play_button.grid(row=0, column=0, sticky="ew", padx=PADX)

        image = Images.get(ImageEnum.PAUSE, width=int(ICON_SIZE * self.app.app_scale))
        self.pause_button = ttk.Button(frame, image=image, command=self.click_pause)
        self.pause_button.image = image
        self.pause_button.grid(row=0, column=1, sticky="ew", padx=PADX)

        image = Images.get(ImageEnum.STOP, width=int(ICON_SIZE * self.app.app_scale))
        self.stop_button = ttk.Button(frame, image=image, command=self.click_stop)
        self.stop_button.image = image
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=PADX)

        loop = tk.IntVar(value=int(self.config["loop"].value == "1"))
        checkbutton = ttk.Checkbutton(
            frame, text="Loop?", variable=loop, state=tk.DISABLED
        )
        checkbutton.grid(row=0, column=3, padx=PADX)

        rate = self.config["refresh_ms"].value
        label = ttk.Label(frame, text=f"rate {rate} ms")
        label.grid(row=0, column=4)

    def clear_buttons(self):
        self.play_button.state(["!pressed"])
        self.pause_button.state(["!pressed"])
        self.stop_button.state(["!pressed"])

    def set_play(self):
        self.clear_buttons()
        self.play_button.state(["pressed"])
        self.progressbar.start()

    def set_pause(self):
        self.clear_buttons()
        self.pause_button.state(["pressed"])
        self.progressbar.stop()

    def set_stop(self):
        self.clear_buttons()
        self.stop_button.state(["pressed"])
        self.progressbar.stop()

    def click_play(self):
        self.set_play()
        session_id = self.app.core.session_id
        try:
            self.app.core.client.mobility_action(
                session_id, self.node.id, MobilityAction.START
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Mobility Error", e)

    def click_pause(self):
        self.set_pause()
        session_id = self.app.core.session_id
        try:
            self.app.core.client.mobility_action(
                session_id, self.node.id, MobilityAction.PAUSE
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Mobility Error", e)

    def click_stop(self):
        self.set_stop()
        session_id = self.app.core.session_id
        try:
            self.app.core.client.mobility_action(
                session_id, self.node.id, MobilityAction.STOP
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Mobility Error", e)
