import tkinter as tk
from tkinter import filedialog, ttk

from coretk import nodeutils
from coretk.appconfig import ICONS_PATH
from coretk.dialogs.dialog import Dialog
from coretk.images import Images
from coretk.themes import PADX, PADY


class IconDialog(Dialog):
    def __init__(self, master, app, name, image):
        super().__init__(master, app, f"{name} Icon", modal=True)
        self.file_path = tk.StringVar()
        self.image_label = None
        self.image = image
        self.draw()

    def draw(self):
        self.top.columnconfigure(0, weight=1)

        # row one
        frame = ttk.Frame(self.top)
        frame.grid(pady=PADY, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=3)
        label = ttk.Label(frame, text="Image")
        label.grid(row=0, column=0, sticky="ew", padx=PADX)
        entry = ttk.Entry(frame, textvariable=self.file_path)
        entry.grid(row=0, column=1, sticky="ew", padx=PADX)
        button = ttk.Button(frame, text="...", command=self.click_file)
        button.grid(row=0, column=2)

        # row two
        self.image_label = ttk.Label(self.top, image=self.image, anchor=tk.CENTER)
        self.image_label.grid(pady=PADY, sticky="ew")

        # spacer
        self.draw_spacer()

        # row three
        frame = ttk.Frame(self.top)
        frame.grid(sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        button = ttk.Button(frame, text="Apply", command=self.destroy)
        button.grid(row=0, column=0, sticky="ew", padx=PADX)

        button = ttk.Button(frame, text="Cancel", command=self.click_cancel)
        button.grid(row=0, column=1, sticky="ew")

    def click_file(self):
        file_path = filedialog.askopenfilename(
            initialdir=str(ICONS_PATH),
            title="Open",
            filetypes=(
                ("images", "*.gif *.jpg *.png *.bmp *pcx *.tga ..."),
                ("All Files", "*"),
            ),
        )
        if file_path:
            self.image = Images.create(file_path, nodeutils.ICON_SIZE)
            self.image_label.config(image=self.image)
            self.file_path.set(file_path)

    def click_cancel(self):
        self.image = None
        self.destroy()
