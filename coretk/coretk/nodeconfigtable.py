"""
Create toplevel for node configuration
"""
import logging
import os
import tkinter as tk
from tkinter import filedialog

from PIL import Image, ImageTk

from coretk.imagemodification import ImageModification
from coretk.nodeservice import NodeServices

PATH = os.path.abspath(os.path.dirname(__file__))
ICONS_DIR = os.path.join(PATH, "icons")

NETWORKNODETYPES = ["switch", "hub", "wlan", "rj45", "tunnel"]
DEFAULTNODES = ["router", "host", "PC"]


class NodeConfig:
    def __init__(self, canvas, canvas_node):
        """
        create an instance of node configuration

        :param coretk.graph.CanvasGraph canvas: canvas object
        :param coretk.graph.CanvasNode canvas_node: canvas node object
        """
        self.canvas = canvas
        self.image = canvas_node.image
        self.node_type = canvas_node.node_type
        self.name = canvas_node.name
        self.canvas_node = canvas_node

        self.top = tk.Toplevel()
        self.top.title(canvas_node.node_type + " configuration")
        self.namevar = tk.StringVar(self.top, value="default name")
        self.name_and_image_definition()
        self.type_and_service_definition()
        self.select_definition()

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
            lb = self.top.grid_slaves(row=0, column=3)[0]
            lb.configure(image=tk_img)
            lb.image = tk_img
            self.image = tk_img
        toplevel.destroy()

    def img_modification(self):
        t = tk.Toplevel()
        t.title(self.name + " image")

        f = tk.Frame(t)
        entry_text = tk.StringVar()
        image_file_label = tk.Label(f, text="Image file: ")
        image_file_label.grid(row=0, column=0)
        image_file_entry = tk.Entry(f, textvariable=entry_text, width=32, bg="white")
        image_file_entry.grid(row=0, column=1)
        image_file_button = tk.Button(
            f, text="...", command=lambda: self.open_icon_dir(t, entry_text)
        )
        image_file_button.grid(row=0, column=2)
        f.grid()

        img = tk.Label(t, image=self.image)
        img.grid()

        f = tk.Frame(t)
        apply_button = tk.Button(
            f, text="Apply", command=lambda: self.click_apply(t, entry_text)
        )
        apply_button.grid(row=0, column=0)
        apply_to_multiple_button = tk.Button(f, text="Apply to multiple...")
        apply_to_multiple_button.grid(row=0, column=1)
        cancel_button = tk.Button(f, text="Cancel", command=t.destroy)
        cancel_button.grid(row=0, column=2)
        f.grid()

    def name_and_image_definition(self):
        f = tk.Frame(self.top, bg="#d9d9d9")
        name_label = tk.Label(f, text="Node name: ", bg="#d9d9d9")
        name_label.grid(padx=2, pady=2)
        name_entry = tk.Entry(f, textvariable=self.namevar)
        name_entry.grid(row=0, column=1, padx=2, pady=2)

        core_button = tk.Button(f, text="None")
        core_button.grid(row=0, column=2, padx=2, pady=2)
        img_button = tk.Button(
            f,
            image=self.image,
            width=40,
            height=40,
            command=lambda: ImageModification(self.canvas, self.canvas_node, self),
            bg="#d9d9d9",
        )
        img_button.grid(row=0, column=3, padx=4, pady=4)
        f.grid(padx=4, pady=4)

    def type_and_service_definition(self):
        f = tk.Frame(self.top)
        type_label = tk.Label(f, text="Type: ")
        type_label.grid(row=0, column=0)

        type_button = tk.Button(f, text="None")
        type_button.grid(row=0, column=1)

        service_button = tk.Button(
            f, text="Services...", command=lambda: NodeServices()
        )
        service_button.grid(row=0, column=2)

        f.grid(padx=2, pady=2)

    def config_apply(self):
        """
        modify image of the canvas node
        :return: nothing
        """
        logging.debug("nodeconfigtable.py configuration apply")
        self.canvas_node.image = self.image
        self.canvas_node.canvas.itemconfig(self.canvas_node.id, image=self.image)
        self.top.destroy()

    def config_cancel(self):
        """
        save chosen image but not modify canvas node
        :return: nothing
        """
        logging.debug("nodeconfigtable.py configuration cancel")
        self.canvas_node.image = self.image
        self.top.destroy()

    def select_definition(self):
        f = tk.Frame(self.top)
        apply_button = tk.Button(f, text="Apply", command=self.config_apply)
        apply_button.grid(row=0, column=0)
        cancel_button = tk.Button(f, text="Cancel", command=self.config_cancel)
        cancel_button.grid(row=0, column=1)
        f.grid()

    def network_node_config(self):
        self.name_and_image_definition()
        self.select_definition()