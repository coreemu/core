import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog

PAD = 5


class MobilityPlayerDialog(Dialog):
    def __init__(self, master, app, canvas_node):
        super().__init__(
            master, app, f"{canvas_node.core_node.name} Mobility Player", modal=False
        )
        self.config = self.app.core.mobility_configs[canvas_node.core_node.id]
        self.play_button = None
        self.pause_button = None
        self.stop_button = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)

        file_name = self.config["file"].value
        label = ttk.Label(self.top, text=file_name)
        label.grid(sticky="ew", pady=PAD)

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PAD)
        frame.columnconfigure(0, weight=1)
        progressbar = ttk.Progressbar(frame, mode="indeterminate")
        progressbar.grid(row=0, column=0, sticky="ew", padx=PAD)
        progressbar.start()
        label = ttk.Label(frame, text="time")
        label.grid(row=0, column=1)

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew", pady=PAD)

        self.play_button = ttk.Button(frame, text="Play", command=self.click_play)
        self.play_button.grid(row=0, column=0, sticky="ew", padx=PAD)

        self.pause_button = ttk.Button(frame, text="Pause", command=self.click_pause)
        self.pause_button.grid(row=0, column=1, sticky="ew", padx=PAD)

        self.stop_button = ttk.Button(frame, text="Stop", command=self.click_stop)
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=PAD)

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

    def click_play(self):
        self.clear_buttons()
        self.play_button.state(["pressed"])

    def click_pause(self):
        self.clear_buttons()
        self.pause_button.state(["pressed"])

    def click_stop(self):
        self.clear_buttons()
        self.stop_button.state(["pressed"])
