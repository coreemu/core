import logging
import tkinter as tk

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
        core_menu = CoreMenubar(self, self.master, self.menubar)
        core_menu.create_core_menubar()
        self.master.config(menu=self.menubar)

    # TODO clean up this code
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
        self.master.update()
        print(menu_button.winfo_rootx(), menu_button.winfo_rooty())
        # print(menu_button.winfo_width(), menu_button.winfo_height())
        # print(self.master.winfo_height())
        option_frame = tk.Frame(self.master)

        switch_button = tk.Button(option_frame, image=switch_image, width=32, height=32)
        switch_button.pack(side=tk.LEFT, pady=1)
        hub_button = tk.Button(option_frame, image=hub_image, width=32, height=32)
        hub_button.pack(side=tk.LEFT, pady=1)
        print("Place the button")
        print(menu_button.winfo_rootx(), menu_button.winfo_rooty())
        option_frame.place(
            x=menu_button.winfo_rootx() + 33, y=menu_button.winfo_rooty() - 117
        )
        self.update()

        print("option frame: " + str(option_frame.winfo_rooty()))
        print("option frame x: " + str(option_frame.winfo_rootx()))

        print("frame dimension: " + str(option_frame.winfo_height()))
        print("button height: " + str(hub_button.winfo_rooty()))

    # TODO switch 177 into the rooty of the selection tool, retrieve image in here
    def draw_options(self, main_button, radio_value):
        hub_image = Images.get("hub")
        switch_image = Images.get("switch")
        option_frame = tk.Frame(self.master)

        switch_button = tk.Radiobutton(
            option_frame,
            image=switch_image,
            width=32,
            height=32,
            variable=radio_value,
            value=7,
            indicatoron=False,
        )
        switch_button.pack(side=tk.LEFT, pady=1)
        hub_button = tk.Radiobutton(
            option_frame,
            image=hub_image,
            width=32,
            height=32,
            variable=radio_value,
            value=8,
            indicatoron=False,
        )
        hub_button.pack(side=tk.LEFT, pady=1)
        self.master.update()
        option_frame.place(
            x=main_button.winfo_rootx() + 35 - self.selection_button.winfo_rootx(),
            y=main_button.winfo_rooty() - self.selection_button.winfo_rooty(),
        )

    def create_network_layer_node_attempt2(self, edit_frame, radio_value):
        hub_image = Images.get("hub")
        main_button = tk.Radiobutton(
            edit_frame, image=hub_image, width=32, height=32, indicatoron=False
        )
        main_button.pack(side=tk.TOP, pady=1)
        self.draw_options(main_button, radio_value)

    def create_widgets(self):

        """
        select_image = Images.get("select")
        start_image = Images.get("start")
        link_image = Images.get("link")
        router_image = Images.get("router")
        hub_image = Images.get("hub")
        switch_image = Images.get("switch")
        marker_image = Images.get("marker")
        """

        edit_frame = tk.Frame(self)
        edit_frame.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        core_editbar = CoreToolbar(self.master, edit_frame)
        core_editbar.create_toolbar()
        """
        radio_value = tk.IntVar()
        self.selection_button = tk.Radiobutton(
            edit_frame,
            indicatoron=False,
            variable=radio_value,
            value=1,
            width=32,
            height=32,
            image=select_image,
        )
        self.selection_button.pack(side=tk.TOP, pady=1)
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

        #self.create_network_layer_node(edit_frame, radio_value, hub_image, switch_image)
        self.create_network_layer_node_attempt2(edit_frame, radio_value)
        """
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
