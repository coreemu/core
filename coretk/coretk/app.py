import logging
import tkinter as tk

from coretk import appdirs
from coretk.coreclient import CoreClient
from coretk.coremenubar import CoreMenubar
from coretk.graph import CanvasGraph
from coretk.images import ImageEnum, Images
from coretk.menuaction import MenuAction
from coretk.toolbar import Toolbar


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        Images.load_all()
        self.menubar = None
        self.core_menu = None
        self.canvas = None
        self.toolbar = None
        self.is_open_xml = False
        self.size_and_scale = None
        self.set_wallpaper = None
        self.wallpaper_id = None
        self.current_wallpaper = None
        self.radiovar = tk.IntVar(value=1)
        self.show_grid_var = tk.IntVar(value=1)
        self.adjust_to_dim_var = tk.IntVar(value=0)
        self.config = appdirs.read_config()
        self.core = CoreClient(self)
        self.setup_app()
        self.draw()
        self.core.set_up()

    def setup_app(self):
        self.master.title("CORE")
        self.master.geometry("1000x800")
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        image = Images.get(ImageEnum.CORE)
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.pack(fill=tk.BOTH, expand=True)

    def draw(self):
        self.draw_menu()
        self.draw_toolbar()
        self.draw_canvas()

    def draw_menu(self):
        self.master.option_add("*tearOff", tk.FALSE)
        self.menubar = tk.Menu(self.master)
        self.core_menu = CoreMenubar(self, self.master, self.menubar)
        self.core_menu.create_core_menubar()
        self.master.config(menu=self.menubar)

    def draw_toolbar(self):
        self.toolbar = Toolbar(self, self)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)

    def draw_canvas(self):
        self.canvas = CanvasGraph(
            self, self.core, background="#cccccc", scrollregion=(0, 0, 1200, 1000)
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.toolbar.canvas = self.canvas

        scroll_x = tk.Scrollbar(
            self.canvas, orient=tk.HORIZONTAL, command=self.canvas.xview
        )
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        scroll_y = tk.Scrollbar(self.canvas, command=self.canvas.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(xscrollcommand=scroll_x.set)
        self.canvas.configure(yscrollcommand=scroll_y.set)

        status_bar = tk.Frame(self)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        b = tk.Button(status_bar, text="Button 1")
        b.pack(side=tk.LEFT, padx=1)
        b = tk.Button(status_bar, text="Button 2")
        b.pack(side=tk.LEFT, padx=1)
        b = tk.Button(status_bar, text="Button 3")
        b.pack(side=tk.LEFT, padx=1)

    def on_closing(self):
        menu_action = MenuAction(self, self.master)
        menu_action.on_quit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    appdirs.check_directory()
    app = Application()
    app.mainloop()
