import logging
import tkinter as tk
from functools import partial
from tkinter import ttk

from coretk import appconfig, themes
from coretk.coreclient import CoreClient
from coretk.graph import CanvasGraph
from coretk.images import ImageEnum, Images
from coretk.menuaction import MenuAction
from coretk.menubar import Menubar
from coretk.toolbar import Toolbar


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        # widgets
        self.menubar = None
        self.toolbar = None
        self.canvas = None
        self.statusbar = None

        # setup
        self.config = appconfig.read()
        self.style = ttk.Style()
        self.setup_theme()
        self.core = CoreClient(self)
        self.setup_app()
        self.draw()
        self.core.set_up()

    def setup_theme(self):
        themes.load(self.style)
        self.style.theme_use(self.config["preferences"]["theme"])
        func = partial(themes.update_menu, self.style)
        self.master.bind_class("Menu", "<<ThemeChanged>>", func)

    def setup_app(self):
        self.master.title("CORE")
        self.center()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        image = Images.get(ImageEnum.CORE, 16)
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.pack(fill=tk.BOTH, expand=True)

    def center(self):
        width = 1000
        height = 800
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = int((screen_width / 2) - (width / 2))
        y = int((screen_height / 2) - (height / 2))
        self.master.geometry(f"{width}x{height}+{x}+{y}")

    def draw(self):
        self.master.option_add("*tearOff", tk.FALSE)
        self.menubar = Menubar(self.master, self)
        self.toolbar = Toolbar(self, self)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        self.draw_canvas()
        self.draw_status()

    def draw_canvas(self):
        self.canvas = CanvasGraph(
            self, self.core, background="#cccccc", scrollregion=(0, 0, 1200, 1000)
        )
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
        self.statusbar = ttk.Frame(self)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_closing(self):
        menu_action = MenuAction(self, self.master)
        menu_action.on_quit()

    def save_config(self):
        appconfig.save(self.config)


if __name__ == "__main__":
    log_format = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    Images.load_all()
    appconfig.check_directory()
    app = Application()
    app.mainloop()
