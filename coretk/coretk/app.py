import logging
import tkinter as tk

import coretk.appcache as appcache
import coretk.images as images
from coretk.coregrpc import CoreGrpc
from coretk.coremenubar import CoreMenubar
from coretk.coretoolbar import CoreToolbar
from coretk.graph import CanvasGraph
from coretk.images import ImageEnum, Images
from coretk.menuaction import MenuAction


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        appcache.cache_variable(self)
        print(self.is_open_xml)
        self.load_images()
        self.setup_app()
        self.menubar = None
        self.core_menu = None
        self.canvas = None
        self.core_editbar = None
        self.core_grpc = None

        self.create_menu()
        self.create_widgets()
        self.draw_canvas()
        self.start_grpc()
        # self.try_make_table()

    def load_images(self):
        """
        Load core images
        :return:
        """
        images.load_core_images(Images)

    def setup_app(self):
        self.master.title("CORE")
        self.master.geometry("1000x800")
        image = Images.get(ImageEnum.CORE.value)
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.pack(fill=tk.BOTH, expand=True)

    def create_menu(self):
        self.master.option_add("*tearOff", tk.FALSE)
        self.menubar = tk.Menu(self.master)
        self.core_menu = CoreMenubar(self, self.master, self.menubar)
        self.core_menu.create_core_menubar()
        self.master.config(menu=self.menubar)

    def create_widgets(self):
        edit_frame = tk.Frame(self)
        edit_frame.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        self.core_editbar = CoreToolbar(self, edit_frame, self.menubar)
        self.core_editbar.create_toolbar()

    def draw_canvas(self):
        self.canvas = CanvasGraph(
            master=self,
            grpc=self.core_grpc,
            background="#cccccc",
            scrollregion=(0, 0, 1200, 1000),
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.core_editbar.canvas = self.canvas

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

    def start_grpc(self):
        """
        Conect client to grpc, query sessions and prompt use to choose an existing session if there exist any

        :return: nothing
        """
        self.master.update()
        self.core_grpc = CoreGrpc(self)
        self.core_grpc.set_up()
        self.canvas.core_grpc = self.core_grpc
        self.canvas.grpc_manager.core_grpc = self.core_grpc
        self.canvas.grpc_manager.update_preexisting_ids()
        self.canvas.draw_existing_component()

    def on_closing(self):
        menu_action = MenuAction(self, self.master)
        menu_action.on_quit()
        # self.quit()

    def try_make_table(self):
        f = tk.Frame(self.master)
        for i in range(3):
            e = tk.Entry(f)
            e.grid(row=0, column=1, stick="nsew")
        f.pack(side=tk.TOP)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = Application()
    app.master.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
