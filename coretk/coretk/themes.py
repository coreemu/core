import tkinter as tk

DARK = "black"


class Styles:
    tooltip = "Tooltip.TLabel"
    tooltip_frame = "Tooltip.TFrame"


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


def load(style):
    style.theme_create(
        DARK,
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
        },
    )


def update_toplevel(style, event):
    if not isinstance(event.widget, tk.Toplevel):
        return
    bg = style.lookup(".", "background")
    event.widget.config(background=bg)


def update_menu(style, event):
    if not isinstance(event.widget, tk.Menu):
        return
    bg = style.lookup(".", "background")
    fg = style.lookup(".", "foreground")
    abg = style.lookup(".", "lightcolor")
    event.widget.config(
        background=bg, foreground=fg, activebackground=abg, activeforeground=fg
    )
