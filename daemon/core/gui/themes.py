import tkinter as tk
from tkinter import font, ttk
from typing import Dict, Tuple

THEME_DARK: str = "black"
PADX: Tuple[int, int] = (0, 5)
PADY: Tuple[int, int] = (0, 5)
FRAME_PAD: int = 5
DIALOG_PAD: int = 5


class Styles:
    tooltip: str = "Tooltip.TLabel"
    tooltip_frame: str = "Tooltip.TFrame"
    service_checkbutton: str = "Service.TCheckbutton"
    picker_button: str = "Picker.TButton"
    no_alert: str = "NAlert.TButton"
    green_alert: str = "GAlert.TButton"
    red_alert: str = "RAlert.TButton"
    yellow_alert: str = "YAlert.TButton"


class Colors:
    disabledfg: str = "DarkGrey"
    frame: str = "#424242"
    dark: str = "#222222"
    darker: str = "#121212"
    darkest: str = "black"
    lighter: str = "#626262"
    lightest: str = "#ffffff"
    selectbg: str = "#4a6984"
    selectfg: str = "#ffffff"
    white: str = "white"
    black: str = "black"
    listboxbg: str = "#f2f1f0"


def load(style: ttk.Style) -> None:
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


def theme_change_menu(event: tk.Event) -> None:
    if not isinstance(event.widget, tk.Menu):
        return
    style_menu(event.widget)


def style_menu(widget: tk.Widget) -> None:
    style = ttk.Style()
    bg = style.lookup(".", "background")
    fg = style.lookup(".", "foreground")
    abg = style.lookup(".", "lightcolor")
    if not abg:
        abg = bg
    widget.config(
        background=bg, foreground=fg, activebackground=abg, activeforeground=fg, bd=0
    )


def style_listbox(widget: tk.Widget) -> None:
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


def _alert_style(style: ttk.Style, name: str, background: str):
    style.configure(
        name,
        background=background,
        padding=0,
        relief=tk.RIDGE,
        borderwidth=1,
        font="TkDefaultFont",
        foreground="black",
        highlightbackground="white",
    )
    style.map(name, background=[("!active", background), ("active", "white")])


def theme_change(event: tk.Event) -> None:
    style = ttk.Style()
    style.configure(Styles.picker_button, font="TkSmallCaptionFont")
    style.configure(
        Styles.no_alert, padding=0, relief=tk.RIDGE, borderwidth=1, font="TkDefaultFont"
    )
    _alert_style(style, Styles.green_alert, "green")
    _alert_style(style, Styles.yellow_alert, "yellow")
    _alert_style(style, Styles.red_alert, "red")


def scale_fonts(fonts_size: Dict[str, int], scale: float) -> None:
    for name in font.names():
        f = font.nametofont(name)
        if name in fonts_size:
            if name == "TkSmallCaptionFont":
                f.config(size=int(fonts_size[name] * scale * 8 / 9))
            else:
                f.config(size=int(fonts_size[name] * scale))
