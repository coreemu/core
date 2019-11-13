import logging
from tkinter import ttk

from coretk.dialogs.dialog import Dialog
from coretk.widgets import ConfigFrame

PAD_X = 2
PAD_Y = 2


class SessionOptionsDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Session Options", modal=True)
        self.config_frame = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        session_id = self.app.core.session_id
        response = self.app.core.client.get_session_options(session_id)
        logging.info("session options: %s", response)

        self.config_frame = ConfigFrame(self.top, config=response.config)
        self.config_frame.draw_config()
        self.config_frame.grid(sticky="nsew")

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        for i in range(2):
            frame.columnconfigure(i, weight=1)
        button = ttk.Button(frame, text="Save", command=self.save)
        button.grid(row=0, column=0, pady=PAD_Y, padx=PAD_X, sticky="ew")
        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, pady=PAD_Y, padx=PAD_X, sticky="ew")

    def save(self):
        config = self.config_frame.parse_config()
        session_id = self.app.core.session_id
        response = self.app.core.client.set_session_options(session_id, config)
        logging.info("saved session config: %s", response)
        self.destroy()
