import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

import grpc

from core.api.grpc.wrappers import MobilityAction, Node
from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application

ICON_SIZE: int = 16


class MobilityPlayer:
    def __init__(self, app: "Application", node: Node) -> None:
        self.app: "Application" = app
        self.node: Node = node
        self.dialog: Optional[MobilityPlayerDialog] = None
        self.state: Optional[MobilityAction] = None

    def show(self) -> None:
        if self.dialog:
            self.dialog.destroy()
        self.dialog = MobilityPlayerDialog(self.app, self.node)
        self.dialog.protocol("WM_DELETE_WINDOW", self.close)
        if self.state == MobilityAction.START:
            self.set_play()
        elif self.state == MobilityAction.PAUSE:
            self.set_pause()
        else:
            self.set_stop()
        self.dialog.show()

    def close(self) -> None:
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None

    def set_play(self) -> None:
        self.state = MobilityAction.START
        if self.dialog:
            self.dialog.set_play()

    def set_pause(self) -> None:
        self.state = MobilityAction.PAUSE
        if self.dialog:
            self.dialog.set_pause()

    def set_stop(self) -> None:
        self.state = MobilityAction.STOP
        if self.dialog:
            self.dialog.set_stop()


class MobilityPlayerDialog(Dialog):
    def __init__(self, app: "Application", node: Node) -> None:
        super().__init__(app, f"{node.name} Mobility Player", modal=False)
        self.resizable(False, False)
        self.geometry("")
        self.node: Node = node
        self.play_button: Optional[ttk.Button] = None
        self.pause_button: Optional[ttk.Button] = None
        self.stop_button: Optional[ttk.Button] = None
        self.progressbar: Optional[ttk.Progressbar] = None
        self.draw()

    def draw(self) -> None:
        config = self.node.mobility_config
        self.top.columnconfigure(0, weight=1)

        file_name = config["file"].value
        label = ttk.Label(self.top, text=file_name)
        label.grid(sticky=tk.EW, pady=PADY)

        self.progressbar = ttk.Progressbar(self.top, mode="indeterminate")
        self.progressbar.grid(sticky=tk.EW, pady=PADY)

        frame = ttk.Frame(self.top)
        frame.grid(sticky=tk.EW, pady=PADY)
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        image = self.app.get_enum_icon(ImageEnum.START, width=ICON_SIZE)
        self.play_button = ttk.Button(frame, image=image, command=self.click_play)
        self.play_button.image = image
        self.play_button.grid(row=0, column=0, sticky=tk.EW, padx=PADX)

        image = self.app.get_enum_icon(ImageEnum.PAUSE, width=ICON_SIZE)
        self.pause_button = ttk.Button(frame, image=image, command=self.click_pause)
        self.pause_button.image = image
        self.pause_button.grid(row=0, column=1, sticky=tk.EW, padx=PADX)

        image = self.app.get_enum_icon(ImageEnum.STOP, width=ICON_SIZE)
        self.stop_button = ttk.Button(frame, image=image, command=self.click_stop)
        self.stop_button.image = image
        self.stop_button.grid(row=0, column=2, sticky=tk.EW, padx=PADX)

        loop = tk.IntVar(value=int(config["loop"].value == "1"))
        checkbutton = ttk.Checkbutton(
            frame, text="Loop?", variable=loop, state=tk.DISABLED
        )
        checkbutton.grid(row=0, column=3, padx=PADX)

        rate = config["refresh_ms"].value
        label = ttk.Label(frame, text=f"rate {rate} ms")
        label.grid(row=0, column=4)

    def clear_buttons(self) -> None:
        self.play_button.state(["!pressed"])
        self.pause_button.state(["!pressed"])
        self.stop_button.state(["!pressed"])

    def set_play(self) -> None:
        self.clear_buttons()
        self.play_button.state(["pressed"])
        self.progressbar.start()

    def set_pause(self) -> None:
        self.clear_buttons()
        self.pause_button.state(["pressed"])
        self.progressbar.stop()

    def set_stop(self) -> None:
        self.clear_buttons()
        self.stop_button.state(["pressed"])
        self.progressbar.stop()

    def click_play(self) -> None:
        self.set_play()
        session_id = self.app.core.session.id
        try:
            self.app.core.client.mobility_action(
                session_id, self.node.id, MobilityAction.START
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Mobility Error", e)

    def click_pause(self) -> None:
        self.set_pause()
        session_id = self.app.core.session.id
        try:
            self.app.core.client.mobility_action(
                session_id, self.node.id, MobilityAction.PAUSE
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Mobility Error", e)

    def click_stop(self) -> None:
        self.set_stop()
        session_id = self.app.core.session.id
        try:
            self.app.core.client.mobility_action(
                session_id, self.node.id, MobilityAction.STOP
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Mobility Error", e)
