import tkinter as tk
from functools import partial
from typing import TYPE_CHECKING, Dict

from core.gui.dialogs.observers import ObserverDialog

if TYPE_CHECKING:
    from core.gui.app import Application

OBSERVERS: Dict[str, str] = {
    "List Processes": "ps",
    "Show Interfaces": "ip address",
    "IPV4 Routes": "ip -4 route",
    "IPV6 Routes": "ip -6 route",
    "Listening Sockets": "ss -tuwnl",
    "IPv4 MFC Entries": "ip -4 mroute show",
    "IPv6 MFC Entries": "ip -6 mroute show",
    "Firewall Rules": "iptables -L",
    "IPSec Policies": "setkey -DP",
}


class ObserversMenu(tk.Menu):
    def __init__(self, master: tk.BaseWidget, app: "Application") -> None:
        super().__init__(master)
        self.app: "Application" = app
        self.observer: tk.StringVar = tk.StringVar(value=tk.NONE)
        self.custom_index: int = 0
        self.draw()

    def draw(self) -> None:
        self.add_command(label="Edit Observers", command=self.click_edit)
        self.add_separator()
        self.add_radiobutton(
            label="None",
            variable=self.observer,
            value="none",
            command=lambda: self.app.core.set_observer(None),
        )
        for name in sorted(OBSERVERS):
            cmd = OBSERVERS[name]
            self.add_radiobutton(
                label=name,
                variable=self.observer,
                value=name,
                command=partial(self.app.core.set_observer, cmd),
            )
        self.custom_index = self.index(tk.END) + 1
        self.draw_custom()

    def draw_custom(self) -> None:
        current_index = self.index(tk.END) + 1
        if self.custom_index < current_index:
            self.delete(self.custom_index, tk.END)
        for name in sorted(self.app.core.custom_observers):
            observer = self.app.core.custom_observers[name]
            self.add_radiobutton(
                label=name,
                variable=self.observer,
                value=name,
                command=partial(self.app.core.set_observer, observer.cmd),
            )

    def click_edit(self) -> None:
        dialog = ObserverDialog(self.app)
        dialog.show()
