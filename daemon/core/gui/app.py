import logging
import math
import tkinter as tk
from tkinter import font, ttk
from tkinter.ttk import Progressbar

import grpc

from core.gui import appconfig, themes
from core.gui.coreclient import CoreClient
from core.gui.dialogs.error import ErrorDialog
from core.gui.graph.graph import CanvasGraph
from core.gui.images import ImageEnum, Images
from core.gui.menubar import Menubar
from core.gui.nodeutils import NodeUtils
from core.gui.statusbar import StatusBar
from core.gui.toolbar import Toolbar
from core.gui.validation import InputValidation

WIDTH = 1000
HEIGHT = 800


class Application(ttk.Frame):
    def __init__(self, proxy: bool):
        super().__init__(master=None)
        # load node icons
        NodeUtils.setup()

        # widgets
        self.menubar = None
        self.toolbar = None
        self.right_frame = None
        self.canvas = None
        self.statusbar = None
        self.validation = None
        self.progress = None

        # fonts
        self.fonts_size = None
        self.icon_text_font = None
        self.edge_font = None

        # setup
        self.guiconfig = appconfig.read()
        self.app_scale = self.guiconfig["scale"]
        self.setup_scaling()
        self.style = ttk.Style()
        self.setup_theme()
        self.core = CoreClient(self, proxy)
        self.setup_app()
        self.draw()
        self.core.setup()

    def setup_scaling(self):
        self.fonts_size = {name: font.nametofont(name)["size"] for name in font.names()}
        text_scale = self.app_scale if self.app_scale < 1 else math.sqrt(self.app_scale)
        themes.scale_fonts(self.fonts_size, self.app_scale)
        self.icon_text_font = font.Font(family="TkIconFont", size=int(12 * text_scale))
        self.edge_font = font.Font(
            family="TkDefaultFont", size=int(8 * text_scale), weight=font.BOLD
        )

    def setup_theme(self):
        themes.load(self.style)
        self.master.bind_class("Menu", "<<ThemeChanged>>", themes.theme_change_menu)
        self.master.bind("<<ThemeChanged>>", themes.theme_change)
        self.style.theme_use(self.guiconfig["preferences"]["theme"])

    def setup_app(self):
        self.master.title("CORE")
        self.center()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        image = Images.get(ImageEnum.CORE, 16)
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.validation = InputValidation(self)
        self.master.option_add("*tearOff", tk.FALSE)

    def center(self):
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = int((screen_width / 2) - (WIDTH * self.app_scale / 2))
        y = int((screen_height / 2) - (HEIGHT * self.app_scale / 2))
        self.master.geometry(
            f"{int(WIDTH * self.app_scale)}x{int(HEIGHT * self.app_scale)}+{x}+{y}"
        )

    def draw(self):
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.grid(sticky="nsew")
        self.toolbar = Toolbar(self, self)
        self.toolbar.grid(sticky="ns")
        self.right_frame = ttk.Frame(self)
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(0, weight=1)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.draw_canvas()
        self.draw_status()
        self.progress = Progressbar(self.right_frame, mode="indeterminate")
        self.menubar = Menubar(self.master, self)

    def draw_canvas(self):
        width = self.guiconfig["preferences"]["width"]
        height = self.guiconfig["preferences"]["height"]
        canvas_frame = ttk.Frame(self.right_frame)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.grid(sticky="nsew", pady=1)
        self.canvas = CanvasGraph(canvas_frame, self, self.core, width, height)
        self.canvas.grid(sticky="nsew")
        scroll_y = ttk.Scrollbar(canvas_frame, command=self.canvas.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(
            canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview
        )
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(xscrollcommand=scroll_x.set)
        self.canvas.configure(yscrollcommand=scroll_y.set)

    def draw_status(self):
        self.statusbar = StatusBar(self.right_frame, self)
        self.statusbar.grid(sticky="ew")

    def show_grpc_exception(self, title: str, e: grpc.RpcError) -> None:
        logging.exception("app grpc exception", exc_info=e)
        message = e.details()
        self.show_error(title, message)

    def show_exception(self, title: str, e: Exception) -> None:
        logging.exception("app exception", exc_info=e)
        self.show_error(title, str(e))

    def show_error(self, title: str, message: str) -> None:
        self.after(0, lambda: ErrorDialog(self, title, message).show())

    def on_closing(self):
        self.menubar.prompt_save_running_session(True)

    def save_config(self):
        appconfig.save(self.guiconfig)

    def joined_session_update(self):
        if self.core.is_runtime():
            self.toolbar.set_runtime()
        else:
            self.toolbar.set_design()

    def close(self):
        self.master.destroy()
