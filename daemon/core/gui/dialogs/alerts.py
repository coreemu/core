"""
check engine light
"""
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict, Optional

from core.api.grpc.core_pb2 import ExceptionEvent, ExceptionLevel
from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADX, PADY
from core.gui.widgets import CodeText

if TYPE_CHECKING:
    from core.gui.app import Application


class AlertsDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "Alerts")
        self.tree: Optional[ttk.Treeview] = None
        self.codetext: Optional[CodeText] = None
        self.alarm_map: Dict[int, ExceptionEvent] = {}
        self.draw()

    def draw(self) -> None:
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
            exception = alarm.exception_event
            level_name = ExceptionLevel.Enum.Name(exception.level)
            insert_id = self.tree.insert(
                "",
                tk.END,
                text=exception.date,
                values=(
                    exception.date,
                    level_name,
                    alarm.session_id,
                    exception.node_id,
                    exception.source,
                ),
                tags=(level_name,),
            )
            self.alarm_map[insert_id] = alarm

        error_name = ExceptionLevel.Enum.Name(ExceptionLevel.ERROR)
        self.tree.tag_configure(error_name, background="#ff6666")
        fatal_name = ExceptionLevel.Enum.Name(ExceptionLevel.FATAL)
        self.tree.tag_configure(fatal_name, background="#d9d9d9")
        warning_name = ExceptionLevel.Enum.Name(ExceptionLevel.WARNING)
        self.tree.tag_configure(warning_name, background="#ffff99")
        notice_name = ExceptionLevel.Enum.Name(ExceptionLevel.NOTICE)
        self.tree.tag_configure(notice_name, background="#85e085")

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
        button = ttk.Button(frame, text="Reset", command=self.reset_alerts)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="Close", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def reset_alerts(self) -> None:
        self.codetext.text.delete("1.0", tk.END)
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.app.statusbar.core_alarms.clear()

    def click_select(self, event: tk.Event) -> None:
        current = self.tree.selection()[0]
        alarm = self.alarm_map[current]
        self.codetext.text.config(state=tk.NORMAL)
        self.codetext.text.delete("1.0", "end")
        self.codetext.text.insert("1.0", alarm.exception_event.text)
        self.codetext.text.config(state=tk.DISABLED)
