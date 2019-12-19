"""
check engine light
"""
import tkinter as tk
from tkinter import ttk

from grpc import RpcError

from core.api.grpc import core_pb2
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import CodeText


class AlertsDialog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "Alerts", modal=True)
        self.app = app
        self.tree = None
        self.codetext = None
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)

        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.grid(sticky="nsew", pady=PADY)
        self.tree = ttk.Treeview(
            frame,
            columns=("time", "level", "session_id", "node", "source"),
            show="headings",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.column("time", stretch=tk.YES)
        self.tree.heading("time", text="Time")
        self.tree.column("level", stretch=tk.YES, width=100)
        self.tree.heading("level", text="Level")
        self.tree.column("session_id", stretch=tk.YES, width=100)
        self.tree.heading("session_id", text="Session ID")
        self.tree.column("node", stretch=tk.YES, width=100)
        self.tree.heading("node", text="Node")
        self.tree.column("source", stretch=tk.YES, width=100)
        self.tree.heading("source", text="Source")
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

        self.codetext = CodeText(self.top)
        self.codetext.text.config(state=tk.DISABLED, height=11)
        self.codetext.grid(sticky="nsew", pady=PADY)

        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        button = ttk.Button(frame, text="Reset", command=self.reset_alerts)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Daemon Log", command=self.daemon_log)
        button.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Node Log")
        button.grid(row=0, column=2, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Close", command=self.destroy)
        button.grid(row=0, column=3, sticky="ew")

    def reset_alerts(self):
        self.codetext.text.delete("1.0", tk.END)
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
        self.codetext.text.delete("1.0", "end")
        self.codetext.text.insert("1.0", text)


class DaemonLog(Dialog):
    def __init__(self, master, app):
        super().__init__(master, app, "core-daemon log", modal=True)
        self.columnconfigure(0, weight=1)
        self.path = tk.StringVar(value="/var/log/core-daemon.log")
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)
        frame = ttk.Frame(self.top)
        frame.grid(row=0, column=0, sticky="ew", pady=PADY)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=9)
        label = ttk.Label(frame, text="File", anchor="w")
        label.grid(row=0, column=0, sticky="ew")
        entry = ttk.Entry(frame, textvariable=self.path, state="disabled")
        entry.grid(row=0, column=1, sticky="ew")
        try:
            file = open("/var/log/core-daemon.log", "r")
            log = file.readlines()
        except FileNotFoundError:
            log = "Log file not found"
        codetext = CodeText(self.top)
        codetext.text.insert("1.0", log)
        codetext.text.see("end")
        codetext.text.config(state=tk.DISABLED)
        codetext.grid(row=1, column=0, sticky="nsew")
