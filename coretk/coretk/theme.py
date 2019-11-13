import tkinter as tk
from tkinter import ttk


class Colors:
    disabledfg = "DarkGrey"
    frame = "#424242"
    dark = "#222222"
    darker = "#121212"
    darkest = "black"
    lighter = "#626262"
    lightest = "#ffffff"
    selectbg = "#4a6984"
    selectfg = "#ffffff"
    white = "white"
    black = "black"


style = ttk.Style()
style.theme_create(
    "black",
    "clam",
    {
        ".": {
            "configure": {
                "background": Colors.frame,
                "foreground": Colors.white,
                "bordercolor": Colors.darkest,
                "darkcolor": Colors.dark,
                "lightcolor": Colors.lighter,
                "troughcolor": Colors.darker,
                "selectbackground": Colors.selectbg,
                "selectforeground": Colors.selectfg,
                "selectborderwidth": 0,
                "font": "TkDefaultFont",
            },
            "map": {
                "background": [("disabled", Colors.frame), ("active", Colors.lighter)],
                "foreground": [("disabled", Colors.disabledfg)],
                "selectbackground": [("!focus", Colors.darkest)],
                "selectforeground": [("!focus", Colors.white)],
            },
        },
        "TButton": {
            "configure": {"width": 8, "padding": (5, 1), "relief": tk.RAISED},
            "map": {
                "relief": [("pressed", tk.SUNKEN)],
                "shiftrelief": [("pressed", 1)],
            },
        },
        "TMenubutton": {
            "configure": {"width": 11, "padding": (5, 1), "relief": tk.RAISED}
        },
        "TCheckbutton": {
            "configure": {
                "indicatorbackground": Colors.white,
                "indicatormargin": (1, 1, 4, 1),
            }
        },
        "TRadiobutton": {
            "configure": {
                "indicatorbackground": Colors.white,
                "indicatormargin": (1, 1, 4, 1),
            }
        },
        "TEntry": {
            "configure": {
                "fieldbackground": Colors.white,
                "foreground": Colors.black,
                "padding": (2, 0),
            }
        },
        "TCombobox": {
            "configure": {
                "fieldbackground": Colors.white,
                "foreground": Colors.black,
                "padding": (2, 0),
            }
        },
        "TNotebook.Tab": {
            "configure": {"padding": (6, 2, 6, 2)},
            "map": {"background": [("selected", Colors.lighter)]},
        },
        "Treeview": {
            "configure": {
                "fieldbackground": Colors.white,
                "background": Colors.white,
                "foreground": Colors.black,
            },
            "map": {
                "background": [("selected", Colors.selectbg)],
                "foreground": [("selected", Colors.selectfg)],
            },
        },
    },
)
style.theme_use("black")


def update_menu(event):
    bg = style.lookup(".", "background")
    fg = style.lookup(".", "foreground")
    abg = style.lookup(".", "lightcolor")
    event.widget.config(
        background=bg, foreground=fg, activebackground=abg, activeforeground=fg
    )


class Application(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master.bind_class("Menu", "<<ThemeChanged>>", update_menu)
        self.master.geometry("800x600")
        menu = tk.Menu(self.master)
        menu.add_command(label="Command1")
        menu.add_command(label="Command2")
        submenu = tk.Menu(menu, tearoff=False)
        submenu.add_command(label="Command1")
        submenu.add_command(label="Command2")
        menu.add_cascade(label="Submenu", menu=submenu)
        self.master.config(menu=menu)
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        notebook = ttk.Notebook(self.master)
        notebook.grid(sticky="nsew")
        frame = ttk.Frame(notebook)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="Label").grid()
        ttk.Entry(frame).grid()
        ttk.Button(frame, text="Button").grid()
        ttk.Combobox(frame, values=("one", "two", "three")).grid()
        menubutton = ttk.Menubutton(frame, text="MenuButton")
        menubutton.grid()
        mbmenu = tk.Menu(menubutton, tearoff=False)
        menubutton.config(menu=mbmenu)
        mbmenu.add_command(label="Menu1")
        mbmenu.add_command(label="Menu2")
        submenu = tk.Menu(mbmenu, tearoff=False)
        submenu.add_command(label="Command1")
        submenu.add_command(label="Command2")
        mbmenu.add_cascade(label="Submenu", menu=submenu)
        ttk.Radiobutton(frame, text="Radio Button").grid()
        ttk.Checkbutton(frame, text="Check Button").grid()
        tv = ttk.Treeview(frame, columns=("one", "two", "three"), show="headings")
        tv.grid()
        tv.column("one", stretch=tk.YES)
        tv.heading("one", text="ID")
        tv.column("two", stretch=tk.YES)
        tv.heading("two", text="State")
        tv.column("three", stretch=tk.YES)
        tv.heading("three", text="Node Count")
        tv.insert("", tk.END, text="1", values=("v1", "v2", "v3"))
        tv.insert("", tk.END, text="2", values=("v1", "v2", "v3"))
        notebook.add(frame, text="Tab1")
        frame = ttk.Frame(notebook)
        frame.grid(sticky="nsew")
        notebook.add(frame, text="Tab2")


if __name__ == "__main__":
    app = Application()
    app.mainloop()
