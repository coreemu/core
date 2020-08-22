import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.gui.dialogs.dialog import Dialog
from core.gui.widgets import CodeText

if TYPE_CHECKING:
    from core.gui.app import Application

LICENSE = """\
Copyright (c) 2005-2020, the Boeing Company.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
THE POSSIBILITY OF SUCH DAMAGE.\
"""


class AboutDialog(Dialog):
    def __init__(self, app: "Application") -> None:
        super().__init__(app, "About CORE")
        self.draw()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        codetext = CodeText(self.top)
        codetext.text.insert("1.0", LICENSE)
        codetext.text.config(state=tk.DISABLED)
        codetext.grid(sticky=tk.NSEW)

        label = ttk.Label(
            self.top, text="Icons from https://icons8.com", anchor=tk.CENTER
        )
        label.grid(sticky=tk.EW)
