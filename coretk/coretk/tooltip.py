import tkinter as tk
from tkinter import ttk


class Tooltip(object):
    """
    Create tool tip for a given widget
    """

    def __init__(self, widget, text="widget info"):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.waittime = 400
        self.id = None
        self.tw = None

    def on_enter(self, event=None):
        self.schedule()

    def on_leave(self, event=None):
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

    def enter(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx()
        y += self.widget.winfo_rooty() + 32

        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = ttk.Label(
            self.tw,
            text=self.text,
            justify=tk.LEFT,
            background="#FFFFEA",
            relief=tk.SOLID,
            borderwidth=0,
        )
        label.grid(padx=1)

    def close(self, event=None):
        if self.tw:
            self.tw.destroy()
