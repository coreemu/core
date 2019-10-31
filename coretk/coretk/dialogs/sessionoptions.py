import logging
import tkinter as tk

from coretk import configutils
from coretk.dialogs.dialog import Dialog

PAD_X = 2
PAD_Y = 2


class SessionOptionsDialog(Dialog):
    def __init__(self, master):
        super().__init__(master, "Session Options", modal=True)
        self.options = None
        self.values = None
        self.save_button = tk.Button(self, text="Save", command=self.save)
        self.cancel_button = tk.Button(self, text="Cancel", command=self.destroy)
        self.draw()

    def draw(self):
        session_id = self.master.core_grpc.session_id
        response = self.master.core_grpc.core.get_session_options(session_id)
        logging.info("session options: %s", response)
        self.options = response.config
        self.values = configutils.create_config(self, self.options, PAD_X, PAD_Y)
        row = len(response.config)
        self.save_button.grid(row=row, pady=PAD_Y, padx=PAD_X, sticky="ew")
        self.cancel_button.grid(row=row, column=1, pady=PAD_Y, padx=PAD_X, sticky="ew")

    def save(self):
        config = configutils.parse_config(self.options, self.values)
        session_id = self.master.core_grpc.session_id
        response = self.master.core_grpc.core.set_session_options(session_id, config)
        logging.info("saved session config: %s", response)
        self.destroy()
