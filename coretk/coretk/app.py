import tkinter as tk
from PIL import Image, ImageTk

from coretk.graph import CanvasGraph


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master.title("CORE")
        self.master.geometry("800x600")
        self.master.state("zoomed")
        self.set_icon()
        self.pack(fill=tk.BOTH, expand=1)
        self.images = []
        self.menubar = None
        self.create_menu()
        self.create_widgets()

    def set_icon(self):
        image = Image.open("core-icon.png")
        tk_image = ImageTk.PhotoImage(image)
        self.master.tk.call("wm", "iconphoto", self.master._w, tk_image)

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

    def create_widgets(self):
        edit_frame = tk.Frame(self)
        edit_frame.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        radio_value = tk.IntVar()
        b = tk.Radiobutton(edit_frame, text="Button 1", indicatoron=False, variable=radio_value, value=1)
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(edit_frame, text="Button 2", indicatoron=False, variable=radio_value, value=2)
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(edit_frame, text="Button 3", indicatoron=False, variable=radio_value, value=3)
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(edit_frame, text="Button 4", indicatoron=False, variable=radio_value, value=4)
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(edit_frame, text="Button 5", indicatoron=False, variable=radio_value, value=5)
        b.pack(side=tk.TOP, pady=1)

        self.canvas = CanvasGraph(
            self, background="#cccccc", scrollregion=(0, 0, 1000, 1000)
        )
        self.canvas.load("switch", "switch.png")
        self.canvas.add_node(50, 50, "Node 1", "switch")
        self.canvas.add_node(50, 100, "Node 2", "switch")
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
    app = Application()
    app.mainloop()
