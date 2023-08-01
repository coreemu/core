import tkinter as tk
from tkinter import ttk
from typing import Optional

from core.gui.themes import Styles


class Tooltip:
    """
    Create tool tip for a given widget
    """

    def __init__(self, widget: tk.BaseWidget, text: str = "widget info") -> None:
        self.widget: tk.BaseWidget = widget
        self.text: str = text
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.waittime: int = 400
        self.id: Optional[str] = None
        self.tw: Optional[tk.Toplevel] = None

    def on_enter(self, event: tk.Event = None) -> None:
        self.schedule()

    def on_leave(self, event: tk.Event = None) -> None:
        self.unschedule()
        self.close(event)

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.enter)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def enter(self, event: tk.Event = None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx()
        y += self.widget.winfo_rooty() + 32
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x:d}+{y:d}")
        self.tw.rowconfigure(0, weight=1)
        self.tw.columnconfigure(0, weight=1)
        frame = ttk.Frame(self.tw, style=Styles.tooltip_frame, padding=3)
        frame.grid(sticky=tk.NSEW)
        label = ttk.Label(frame, text=self.text, style=Styles.tooltip)
        label.grid()

    def close(self, event: tk.Event = None):
        if self.tw:
            self.tw.destroy()
