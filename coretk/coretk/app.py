import logging
import tkinter as tk

from coretk.graph import CanvasGraph
from coretk.images import Images


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.load_images()
        self.setup_app()
        self.menubar = None
        self.create_menu()
        self.create_widgets()

    def load_images(self):
        # Images.load("switch", "switch.png")
        Images.load("core", "core-icon.png")
        Images.load("start", "start.gif")
        Images.load("switch", "lanswitch.gif")
        Images.load("marker", "marker.gif")
        Images.load("router", "router.gif")
        Images.load("select", "select.gif")
        Images.load("link", "link.gif")
        Images.load("hub", "hub.gif")

    def setup_app(self):
        self.master.title("CORE")
        self.master.geometry("800x600")
        image = Images.get("core")
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.pack(fill=tk.BOTH, expand=True)

    def create_menu(self):
        self.master.option_add("*tearOff", tk.FALSE)
        self.menubar = tk.Menu(self.master)
        file_menu = tk.Menu(self.menubar)
        file_menu.add_command(label="Open")
        file_menu.add_command(label="Exit", command=self.master.quit)
        self.menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        self.master.config(menu=self.menubar)

    def create_network_layer_node(
        self, edit_frame, radio_value, hub_image, switch_image
    ):
        menu_button = tk.Menubutton(
            edit_frame,
            direction=tk.RIGHT,
            image=hub_image,
            width=32,
            height=32,
            relief=tk.RAISED,
        )
        # menu_button.grid()
        menu_button.menu = tk.Menu(menu_button)
        menu_button["menu"] = menu_button.menu

        menu_button.menu.add_radiobutton(
            image=hub_image, variable=radio_value, value=7, indicatoron=False
        )
        menu_button.menu.add_radiobutton(
            image=switch_image, variable=radio_value, value=8, indicatoron=False
        )
        menu_button.pack(side=tk.TOP, pady=1)

    def create_widgets(self):
        select_image = Images.get("select")
        start_image = Images.get("start")
        link_image = Images.get("link")
        router_image = Images.get("router")
        hub_image = Images.get("hub")
        switch_image = Images.get("switch")
        marker_image = Images.get("marker")

        edit_frame = tk.Frame(self)
        edit_frame.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        radio_value = tk.IntVar()
        b = tk.Radiobutton(
            edit_frame,
            indicatoron=False,
            variable=radio_value,
            value=1,
            width=32,
            height=32,
            image=select_image,
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame,
            indicatoron=False,
            variable=radio_value,
            value=2,
            width=32,
            height=32,
            image=start_image,
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame,
            indicatoron=False,
            variable=radio_value,
            value=3,
            width=32,
            height=32,
            image=link_image,
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame,
            indicatoron=False,
            variable=radio_value,
            value=4,
            width=32,
            height=32,
            image=router_image,
        )

        b.pack(side=tk.TOP, pady=1)

        b = tk.Radiobutton(
            edit_frame,
            indicatoron=False,
            variable=radio_value,
            value=5,
            width=32,
            height=32,
            image=hub_image,
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame,
            indicatoron=False,
            variable=radio_value,
            value=6,
            width=32,
            height=32,
            image=marker_image,
        )
        b.pack(side=tk.TOP, pady=1)

        self.create_network_layer_node(edit_frame, radio_value, hub_image, switch_image)

        self.canvas = CanvasGraph(
            self, background="#cccccc", scrollregion=(0, 0, 1000, 1000)
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
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
