import tkinter as tk
from functools import partial


class FrameScroll(tk.LabelFrame):
    def __init__(self, master=None, cnf={}, **kw):
        super().__init__(master, cnf, **kw)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.grid(row=0, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.canvas.columnconfigure(0, weight=1)
        self.canvas.rowconfigure(0, weight=1)
        self.scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollbar.grid(row=0, column=2, sticky="ns")
        self.frame = tk.Frame(self.canvas, padx=2, pady=2)
        self.frame.columnconfigure(0, weight=1)
        self.frame_id = self.canvas.create_window(0, 0, anchor="nw", window=self.frame)
        self.canvas.update_idletasks()
        self.canvas.configure(
            scrollregion=self.canvas.bbox("all"), yscrollcommand=self.scrollbar.set
        )
        self.frame.bind(
            "<Configure>",
            lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfig(self.frame_id, width=event.width),
        )

    def clear(self):
        for widget in self.frame.winfo_children():
            widget.destroy()


class ListboxScroll(tk.LabelFrame):
    def __init__(self, master=None, cnf={}, **kw):
        super().__init__(master, cnf, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox = tk.Listbox(
            self, selectmode=tk.SINGLE, yscrollcommand=self.scrollbar.set
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.config(command=self.listbox.yview)


class CheckboxList(tk.LabelFrame):
    def __init__(self, master=None, cnf={}, clicked=None, **kw):
        super().__init__(master, cnf, **kw)
        self.clicked = clicked
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.grid(row=0, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.canvas.columnconfigure(0, weight=1)
        self.canvas.rowconfigure(0, weight=1)
        self.scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollbar.grid(row=0, column=2, sticky="ns")
        self.frame = tk.Frame(self.canvas, padx=2, pady=2)
        self.frame.columnconfigure(0, weight=1)
        self.frame_id = self.canvas.create_window(0, 0, anchor="nw", window=self.frame)
        self.canvas.update_idletasks()
        self.canvas.configure(
            scrollregion=self.canvas.bbox("all"), yscrollcommand=self.scrollbar.set
        )
        self.frame.bind(
            "<Configure>",
            lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfig(self.frame_id, width=event.width),
        )

    def clear(self):
        for widget in self.frame.winfo_children():
            widget.destroy()

    def add(self, name):
        var = tk.BooleanVar()
        func = partial(self.clicked, name, var)
        checkbox = tk.Checkbutton(self.frame, text=name, variable=var, command=func)
        checkbox.grid(sticky="w")
