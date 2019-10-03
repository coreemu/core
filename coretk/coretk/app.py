import logging
import tkinter as tk

import coretk.images as images
from coretk.coregrpc import CoreGrpc
from coretk.coremenubar import CoreMenubar
from coretk.coretoolbar import CoreToolbar
from coretk.graph import CanvasGraph
from coretk.images import Images


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.load_images()
        self.setup_app()
        self.menubar = None
        self.canvas = None

        # start grpc
        self.core_grpc = CoreGrpc()

        self.create_menu()
        self.create_widgets()

    def load_images(self):
        """
        Load core images
        :return:
        """
        images.load_core_images(Images)

    def setup_app(self):
        self.master.title("CORE")
        self.master.geometry("1000x800")
        image = Images.get("core")
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.pack(fill=tk.BOTH, expand=True)

    def create_menu(self):
        self.master.option_add("*tearOff", tk.FALSE)
        self.menubar = tk.Menu(self.master)
        core_menu = CoreMenubar(self, self.master, self.menubar)
        core_menu.create_core_menubar()
        self.master.config(menu=self.menubar)

    def create_widgets(self):
        edit_frame = tk.Frame(self)
        edit_frame.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        core_editbar = CoreToolbar(self.master, edit_frame, self.menubar)
        core_editbar.create_toolbar()

        self.canvas = CanvasGraph(
            master=self,
            grpc=self.core_grpc,
            background="#cccccc",
            scrollregion=(0, 0, 1000, 1000),
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        core_editbar.update_canvas(self.canvas)

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = Application()
    app.mainloop()
