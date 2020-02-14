import tkinter as tk
from tkinter import font, ttk

from core.gui import appconfig, themes
from core.gui.coreclient import CoreClient
from core.gui.graph.graph import CanvasGraph
from core.gui.images import ImageEnum, Images
from core.gui.menuaction import MenuAction
from core.gui.menubar import Menubar
from core.gui.nodeutils import NodeUtils
from core.gui.statusbar import StatusBar
from core.gui.toolbar import Toolbar
from core.gui.validation import InputValidation

WIDTH = 1000
HEIGHT = 800


class Application(tk.Frame):
    def __init__(self, proxy: bool):
        super().__init__(master=None)
        # load node icons
        NodeUtils.setup()

        self.fonts_size = {name: font.nametofont(name)["size"] for name in font.names()}
        self.icon_text_font = font.Font(family="TkIconFont", size=12)
        self.edge_font = font.Font(family="TkDefaultFont", size=8)

        # widgets
        self.menubar = None
        self.toolbar = None
        self.canvas = None
        self.statusbar = None
        self.validation = None

        # setup
        self.guiconfig = appconfig.read()
        self.style = ttk.Style()
        self.setup_theme()
        self.core = CoreClient(self, proxy)
        self.setup_app()
        self.draw()
        self.core.set_up()

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
        self.pack(fill=tk.BOTH, expand=True)
        self.validation = InputValidation(self)

    def center(self):
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = int((screen_width / 2) - (WIDTH / 2))
        y = int((screen_height / 2) - (HEIGHT / 2))
        self.master.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def draw(self):
        self.master.option_add("*tearOff", tk.FALSE)
        self.menubar = Menubar(self.master, self)
        self.toolbar = Toolbar(self, self)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        self.draw_canvas()
        self.draw_status()

    def draw_canvas(self):
        width = self.guiconfig["preferences"]["width"]
        height = self.guiconfig["preferences"]["height"]
        self.canvas = CanvasGraph(self, self.core, width, height)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        scroll_x = ttk.Scrollbar(
            self.canvas, orient=tk.HORIZONTAL, command=self.canvas.xview
        )
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        scroll_y = ttk.Scrollbar(self.canvas, command=self.canvas.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(xscrollcommand=scroll_x.set)
        self.canvas.configure(yscrollcommand=scroll_y.set)

    def draw_status(self):
        self.statusbar = StatusBar(master=self, app=self)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_closing(self):
        menu_action = MenuAction(self, self.master)
        menu_action.on_quit()

    def save_config(self):
        appconfig.save(self.guiconfig)

    def joined_session_update(self):
        self.statusbar.progress_bar.stop()
        if self.core.is_runtime():
            self.toolbar.set_runtime()
        else:
            self.toolbar.set_design()

    def close(self):
        self.master.destroy()
