"""
check engine light
"""
import tkinter as tk
from tkinter import ttk

from grpc import RpcError

from core.api.grpc import core_pb2
from coretk.dialogs.dialog import Dialog
from coretk.images import ImageEnum, Images
from coretk.themes import PADX, PADY
from coretk.widgets import CodeText


class CheckLight(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "CEL", modal=True)
        self.app = app
        self.tree = None
        self.text = None
        self.draw()

    def draw(self):
        row = 0
        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        image = Images.get(ImageEnum.ALERT, 18)
        label = ttk.Label(frame, image=image)
        label.image = image
        label.grid(row=0, column=0, sticky="e")
        label = ttk.Label(frame, text="Check Emulation Light")
        label.grid(row=0, column=1, sticky="w")
        frame.grid(row=row, column=0, padx=PADX, pady=PADY, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.grid(row=row, column=0, sticky="nsew")
        self.tree = ttk.Treeview(
            frame,
            columns=("time", "level", "session_id", "node", "source"),
            show="headings",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.column("time", stretch=tk.YES)
        self.tree.heading("time", text="time", anchor="w")
        self.tree.column("level", stretch=tk.YES)
        self.tree.heading("level", text="level", anchor="w")
        self.tree.column("session_id", stretch=tk.YES)
        self.tree.heading("session_id", text="session id", anchor="w")
        self.tree.column("node", stretch=tk.YES)
        self.tree.heading("node", text="node", anchor="w")
        self.tree.column("source", stretch=tk.YES)
        self.tree.heading("source", text="source", anchor="w")
        self.tree.bind("<<TreeviewSelect>>", self.click_select)

        for alarm in self.app.statusbar.core_alarms:
            level = self.get_level(alarm.level)
            self.tree.insert(
                "",
                tk.END,
                text=str(alarm.date),
                values=(
                    alarm.date,
                    level + " (%s)" % alarm.level,
                    alarm.session_id,
                    alarm.node_id,
                    alarm.source,
                ),
                tags=(level,),
            )

        self.tree.tag_configure("ERROR", background="#ff6666")
        self.tree.tag_configure("FATAL", background="#d9d9d9")
        self.tree.tag_configure("WARNING", background="#ffff99")
        self.tree.tag_configure("NOTICE", background="#85e085")

        yscrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        yscrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscrollbar.set)

        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, sticky="ew")
        self.tree.configure(xscrollcommand=xscrollbar.set)
        row = row + 1

        self.text = CodeText(self)
        self.text.config(state=tk.DISABLED)
        self.text.grid(row=row, column=0, sticky="nsew")
        row = row + 1

        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        button = ttk.Button(frame, text="Reset CEL", command=self.reset_cel)
        button.grid(row=0, column=0, sticky="nsew", padx=PADX)
        button = ttk.Button(frame, text="View core-daemon log", command=self.daemon_log)
        button.grid(row=0, column=1, sticky="nsew", padx=PADX)
        button = ttk.Button(frame, text="View node log")
        button.grid(row=0, column=2, sticky="nsew", padx=PADX)
        button = ttk.Button(frame, text="Close", command=self.destroy)
        button.grid(row=0, column=3, sticky="nsew", padx=PADX)
        frame.grid(row=row, column=0, sticky="nsew")

    def reset_cel(self):
        self.text.delete("1.0", tk.END)
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.app.statusbar.core_alarms.clear()

    def daemon_log(self):
        dialog = DaemonLog(self, self.app)
        dialog.show()

    def get_level(self, level):
        if level == core_pb2.ExceptionLevel.ERROR:
            return "ERROR"
        if level == core_pb2.ExceptionLevel.FATAL:
            return "FATAL"
        if level == core_pb2.ExceptionLevel.WARNING:
            return "WARNING"
        if level == core_pb2.ExceptionLevel.NOTICE:
            return "NOTICE"

    def click_select(self, event):
        current = self.tree.selection()
        values = self.tree.item(current)["values"]
        time = values[0]
        level = values[1]
        session_id = values[2]
        node_id = values[3]
        source = values[4]
        text = "DATE: %s\nLEVEL: %s\nNODE: %s (%s)\nSESSION: %s\nSOURCE: %s\n\n" % (
            time,
            level,
            node_id,
            self.app.core.canvas_nodes[node_id].core_node.name,
            session_id,
            source,
        )
        try:
            sid = self.app.core.session_id
            self.app.core.client.get_node(sid, node_id)
            text = text + "node created"
        except RpcError:
            text = text + "node not created"
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)


class DaemonLog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "core-daemon log", modal=True)
        self.columnconfigure(0, weight=1)
        self.path = tk.StringVar(value="/var/log/core-daemon.log")
        self.draw()

    def draw(self):
        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=9)
        label = ttk.Label(frame, text="File: ")
        label.grid(row=0, column=0)
        entry = ttk.Entry(frame, textvariable=self.path, state="disabled")
        entry.grid(row=0, column=1, sticky="nsew")
        frame.grid(row=0, column=0, sticky="nsew")
        try:
            file = open("/var/log/core-daemon.log", "r")
            log = file.readlines()
        except FileNotFoundError:
            log = "Log file not found"
        text = CodeText(self)
        text.insert("1.0", log)
        text.see("end")
        text.config(state=tk.DISABLED)
        text.grid(row=1, column=0, sticky="nsew")
