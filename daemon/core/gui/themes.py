import tkinter as tk
from tkinter import font, ttk

THEME_DARK = "black"
PADX = (0, 5)
PADY = (0, 5)
FRAME_PAD = 5
DIALOG_PAD = 5


class Styles:
    tooltip = "Tooltip.TLabel"
    tooltip_frame = "Tooltip.TFrame"
    service_checkbutton = "Service.TCheckbutton"
    picker_button = "Picker.TButton"
    green_alert = "GAlert.TButton"
    red_alert = "RAlert.TButton"
    yellow_alert = "YAlert.TButton"


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
    listboxbg = "#f2f1f0"


def load(style: ttk.Style):
    style.theme_create(
        THEME_DARK,
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
                    "background": [
                        ("disabled", Colors.frame),
                        ("active", Colors.lighter),
                    ],
                    "foreground": [("disabled", Colors.disabledfg)],
                    "selectbackground": [("!focus", Colors.darkest)],
                    "selectforeground": [("!focus", Colors.white)],
                },
            },
            "TButton": {
                "configure": {
                    "width": 8,
                    "padding": (5, 1),
                    "relief": tk.RAISED,
                    "anchor": tk.CENTER,
                },
                "map": {
                    "relief": [("pressed", tk.SUNKEN)],
                    "shiftrelief": [("pressed", 1)],
                },
            },
            "TMenubutton": {"configure": {"padding": (5, 1), "relief": tk.RAISED}},
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
                },
                "map": {"fieldbackground": [("disabled", Colors.frame)]},
            },
            "TSpinbox": {
                "configure": {
                    "fieldbackground": Colors.white,
                    "foreground": Colors.black,
                    "padding": (2, 0),
                },
                "map": {"fieldbackground": [("disabled", Colors.frame)]},
            },
            "TCombobox": {
                "configure": {
                    "fieldbackground": Colors.white,
                    "foreground": Colors.black,
                    "padding": (2, 0),
                }
            },
            "TLabelframe": {"configure": {"relief": tk.GROOVE}},
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
            Styles.tooltip: {
                "configure": {"justify": tk.LEFT, "relief": tk.SOLID, "borderwidth": 0}
            },
            Styles.tooltip_frame: {"configure": {}},
            Styles.service_checkbutton: {
                "configure": {
                    "background": Colors.listboxbg,
                    "foreground": Colors.black,
                }
            },
        },
    )


def theme_change_menu(event: tk.Event):
    if not isinstance(event.widget, tk.Menu):
        return
    style_menu(event.widget)


def style_menu(widget: tk.Widget):
    style = ttk.Style()
    bg = style.lookup(".", "background")
    fg = style.lookup(".", "foreground")
    abg = style.lookup(".", "lightcolor")
    if not abg:
        abg = bg
    widget.config(
        background=bg, foreground=fg, activebackground=abg, activeforeground=fg, bd=0
    )


def style_listbox(widget: tk.Widget):
    style = ttk.Style()
    bg = style.lookup(".", "background")
    fg = style.lookup(".", "foreground")
    bc = style.lookup(".", "bordercolor")
    if not bc:
        bc = "black"
    widget.config(
        background=bg,
        foreground=fg,
        highlightthickness=1,
        highlightcolor=bc,
        highlightbackground=bc,
        bd=0,
    )


def theme_change(event: tk.Event):
    style = ttk.Style()
    style.configure(Styles.picker_button, font="TkSmallCaptionFont")
    style.configure(
        Styles.green_alert,
        background="green",
        padding=0,
        relief=tk.RIDGE,
        borderwidth=1,
        font="TkDefaultFont",
    )
    style.configure(
        Styles.yellow_alert,
        background="yellow",
        padding=0,
        relief=tk.RIDGE,
        borderwidth=1,
        font="TkDefaultFont",
    )
    style.configure(
        Styles.red_alert,
        background="red",
        padding=0,
        relief=tk.RIDGE,
        borderwidth=1,
        font="TkDefaultFont",
    )


def scale_fonts(fonts_size, scale):
    for name in font.names():
        f = font.nametofont(name)
        if name in fonts_size:
            if name == "TkSmallCaptionFont":
                f.config(size=int(fonts_size[name] * scale * 8 / 9))
            else:
                f.config(size=int(fonts_size[name] * scale))
