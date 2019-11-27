import tkinter as tk
from tkinter import ttk

from core.api.grpc import core_pb2
from coretk.dialogs.dialog import Dialog
from coretk.images import ImageEnum, Images

PAD = 5
ICON_SIZE = 16


class MobilityPlayerDialog(Dialog):
    def __init__(self, master, app, canvas_node, config):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Mobility Player", modal=False
        )
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
        label.grid(sticky="ew", pady=PAD)

        self.progressbar = ttk.Progressbar(self.top, mode="indeterminate")
        self.progressbar.grid(sticky="ew", pady=PAD)

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PAD)
        for i in range(3):
            frame.columnconfigure(i, weight=1)

        image = Images.get(ImageEnum.START, width=ICON_SIZE)
        self.play_button = ttk.Button(frame, image=image, command=self.click_play)
        self.play_button.image = image
        self.play_button.grid(row=0, column=0, sticky="ew", padx=PAD)

        image = Images.get(ImageEnum.PAUSE, width=ICON_SIZE)
        self.pause_button = ttk.Button(frame, image=image, command=self.click_pause)
        self.pause_button.image = image
        self.pause_button.grid(row=0, column=1, sticky="ew", padx=PAD)

        image = Images.get(ImageEnum.STOP, width=ICON_SIZE)
        self.stop_button = ttk.Button(frame, image=image, command=self.click_stop)
        self.stop_button.image = image
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=PAD)
        self.stop_button.state(["pressed"])

        loop = tk.IntVar(value=int(self.config["loop"].value == "1"))
        checkbutton = ttk.Checkbutton(
            frame, text="Loop?", variable=loop, state=tk.DISABLED
        )
        checkbutton.grid(row=0, column=3, padx=PAD)

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
        self.app.core.client.mobility_action(
            session_id, self.node.id, core_pb2.MobilityAction.START
        )

    def click_pause(self):
        self.set_pause()
        session_id = self.app.core.session_id
        self.app.core.client.mobility_action(
            session_id, self.node.id, core_pb2.MobilityAction.PAUSE
        )

    def click_stop(self):
        self.set_stop()
        session_id = self.app.core.session_id
        self.app.core.client.mobility_action(
            session_id, self.node.id, core_pb2.MobilityAction.STOP
        )
