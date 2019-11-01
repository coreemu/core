"""
node image modification
"""


import os
import tkinter as tk
from tkinter import filedialog

from PIL import Image, ImageTk

PATH = os.path.abspath(os.path.dirname(__file__))
ICONS_DIR = os.path.join(PATH, "icons")


class ImageModification:
    def __init__(self, canvas, canvas_node, node_config):
        """
        create an instance of ImageModification
        :param coretk.graph.CanvasGraph canvas: canvas object
        :param coretk.graph.CanvasNode canvas_node: node object
        :param coretk.nodeconfigtable.NodeConfig node_config: node configuration object
        """
        self.canvas = canvas
        self.image = canvas_node.image
        self.node_type = canvas_node.node_type
        self.name = canvas_node.name
        self.canvas_node = canvas_node
        self.node_configuration = node_config
        self.p_top = node_config.top

        self.top = tk.Toplevel()
        self.top.title(self.name + " image")
        self.image_modification()

    def open_icon_dir(self, toplevel, entry_text):
        filename = filedialog.askopenfilename(
            initialdir=ICONS_DIR,
            title="Open",
            filetypes=(
                ("images", "*.gif *.jpg *.png *.bmp *pcx *.tga ..."),
                ("All Files", "*"),
            ),
        )
        if len(filename) > 0:
            img = Image.open(filename)
            tk_img = ImageTk.PhotoImage(img)
            lb = toplevel.grid_slaves(1, 0)[0]
            lb.configure(image=tk_img)
            lb.image = tk_img
            entry_text.set(filename)

    def click_apply(self, toplevel, entry_text):
        imgfile = entry_text.get()
        if imgfile:
            img = Image.open(imgfile)
            tk_img = ImageTk.PhotoImage(img)
            f = self.p_top.grid_slaves(row=0, column=0)[0]
            lb = f.grid_slaves(row=0, column=3)[0]
            lb.configure(image=tk_img)
            lb.image = tk_img
            self.image = tk_img
            self.node_configuration.image = tk_img
        toplevel.destroy()

    def image_modification(self):
        f = tk.Frame(self.top)
        entry_text = tk.StringVar()
        image_file_label = tk.Label(f, text="Image file: ")
        image_file_label.grid(row=0, column=0)
        image_file_entry = tk.Entry(f, textvariable=entry_text, width=32, bg="white")
        image_file_entry.grid(row=0, column=1)
        image_file_button = tk.Button(
            f, text="...", command=lambda: self.open_icon_dir(self.top, entry_text)
        )
        image_file_button.grid(row=0, column=2)
        f.grid()

        img = tk.Label(self.top, image=self.image)
        img.grid()

        f = tk.Frame(self.top)
        apply_button = tk.Button(
            f, text="Apply", command=lambda: self.click_apply(self.top, entry_text)
        )
        apply_button.grid(row=0, column=0)
        apply_to_multiple_button = tk.Button(f, text="Apply to multiple...")
        apply_to_multiple_button.grid(row=0, column=1)
        cancel_button = tk.Button(f, text="Cancel", command=self.top.destroy)
        cancel_button.grid(row=0, column=2)
        f.grid()
