"""
check engine light
"""
import tkinter as tk
from tkinter import ttk

from coretk.dialogs.dialog import Dialog


class CheckLight(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "CEL", modal=True)
        self.app = app

        self.columnconfigure(0, weight=1)
        self.draw()

    def draw(self):
        row = 0
        frame = ttk.Frame(self)
        label = ttk.Label(frame, text="Check Emulation Light")
        label.grid(row=0, column=0)
        frame.grid(row=row, column=0)
        row = row + 1
        frame = ttk.Frame(self)
        button = ttk.Button(frame, text="Reset CEL")
        button.grid(row=0, column=0)
        button = ttk.Button(frame, text="View core-daemon log", command=self.daemon_log)
        button.grid(row=0, column=1)
        button = ttk.Button(frame, text="View node log")
        button.grid(row=0, column=2)
        button = ttk.Button(frame, text="Close", command=self.destroy)
        button.grid(row=0, column=3)
        frame.grid(row=row, column=0, sticky="nsew")
        ++row

    def daemon_log(self):
        dialog = DaemonLog(self, self.app)
        dialog.show()


class DaemonLog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "core-daemon log", modal=True)
        self.columnconfigure(0, weight=1)
        self.path = tk.StringVar(value="/var/log/core-daemon.log")
        self.draw()

    def draw(self):
        frame = ttk.Frame(self)
        label = ttk.Label(frame, text="File: ")
        label.grid(row=0, column=0)
        entry = ttk.Entry(frame, textvariable=self.path, state="readonly")
        entry.grid(row=0, column=1)
        frame.grid(row=0, column=0)
