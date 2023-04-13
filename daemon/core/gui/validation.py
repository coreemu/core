"""
input validation
"""
import re
import tkinter as tk
from re import Pattern
from tkinter import ttk
from typing import Any, Optional

SMALLEST_SCALE: float = 0.5
LARGEST_SCALE: float = 5.0
HEX_REGEX: Pattern = re.compile("^([#]([0-9]|[a-f])+)$|^[#]$")


class ValidationEntry(ttk.Entry):
    empty: Optional[str] = None

    def __init__(
        self,
        master: tk.BaseWidget = None,
        widget: tk.BaseWidget = None,
        empty_enabled: bool = True,
        **kwargs: Any
    ) -> None:
        super().__init__(master, widget, **kwargs)
        cmd = self.register(self.is_valid)
        self.configure(validate="key", validatecommand=(cmd, "%P"))
        if self.empty is not None and empty_enabled:
            self.bind("<FocusOut>", self.focus_out)

    def is_valid(self, s: str) -> bool:
        raise NotImplementedError

    def focus_out(self, _event: tk.Event) -> None:
        value = self.get()
        if not value:
            self.insert(tk.END, self.empty)


class PositiveIntEntry(ValidationEntry):
    empty: str = "0"

    def is_valid(self, s: str) -> bool:
        if not s:
            return True
        try:
            value = int(s)
            return value >= 0
        except ValueError:
            return False


class PositiveFloatEntry(ValidationEntry):
    empty = "0.0"

    def is_valid(self, s: str) -> bool:
        if not s:
            return True
        try:
            value = float(s)
            return value >= 0.0
        except ValueError:
            return False


class FloatEntry(ValidationEntry):
    empty = "0.0"

    def is_valid(self, s: str) -> bool:
        if not s:
            return True
        try:
            float(s)
            return True
        except ValueError:
            return False


class RgbEntry(ValidationEntry):
    def is_valid(self, s: str) -> bool:
        if not s:
            return True
        if s.startswith("0") and len(s) >= 2:
            return False
        try:
            value = int(s)
            return 0 <= value <= 255
        except ValueError:
            return False


class HexEntry(ValidationEntry):
    def is_valid(self, s: str) -> bool:
        if not s:
            return True
        if HEX_REGEX.match(s):
            return 0 <= len(s) <= 7
        else:
            return False


class NodeNameEntry(ValidationEntry):
    empty: str = "noname"

    def is_valid(self, s: str) -> bool:
        if len(s) < 0:
            return False
        if len(s) == 0:
            return True
        for x in s:
            if not x.isalnum() and x != "-":
                return False
        return True


class AppScaleEntry(ValidationEntry):
    def is_valid(self, s: str) -> bool:
        if not s:
            return True
        try:
            float_value = float(s)
            return SMALLEST_SCALE <= float_value <= LARGEST_SCALE or float_value == 0
        except ValueError:
            return False
