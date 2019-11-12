"""
set wallpaper
"""
import enum
import logging
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

from coretk.appconfig import BACKGROUNDS_PATH
from coretk.dialogs.dialog import Dialog


class ScaleOption(enum.Enum):
    NONE = 0
    UPPER_LEFT = 1
    CENTERED = 2
    SCALED = 3
    TILED = 4


class CanvasBackgroundDialog(Dialog):
    def __init__(self, master, app):
        """
        create an instance of CanvasWallpaper object

        :param coretk.app.Application app: root application
        """
        super().__init__(master, app, "Canvas Background", modal=True)
        self.canvas = self.app.canvas
        self.radiovar = tk.IntVar(value=self.app.radiovar.get())
        self.show_grid_var = tk.IntVar(value=self.app.show_grid_var.get())
        self.adjust_to_dim_var = tk.IntVar(value=self.app.adjust_to_dim_var.get())
        self.image_label = None
        self.file_name = tk.StringVar()
        self.options = []
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.draw_image()
        self.draw_image_label()
        self.draw_image_selection()
        self.draw_options()
        self.draw_additional_options()
        self.draw_buttons()

    def draw_image(self):
        self.image_label = ttk.Label(
            self, text="(image preview)", width=32, anchor=tk.CENTER
        )
        self.image_label.grid(row=0, column=0, pady=5)

    def draw_image_label(self):
        label = ttk.Label(self, text="Image filename: ")
        label.grid(row=1, column=0, sticky="ew")

    def draw_image_selection(self):
        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.grid(row=2, column=0, sticky="ew")

        entry = ttk.Entry(frame, textvariable=self.file_name)
        entry.focus()
        entry.grid(row=0, column=0, sticky="ew")

        button = ttk.Button(frame, text="...", command=self.click_open_image)
        button.grid(row=0, column=1, sticky="ew")

        button = ttk.Button(frame, text="Clear", command=self.click_clear)
        button.grid(row=0, column=2, sticky="ew")

    def draw_options(self):
        frame = ttk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.grid(row=3, column=0, sticky="ew")

        button = ttk.Radiobutton(
            frame, text="upper-left", value=1, variable=self.radiovar
        )
        button.grid(row=0, column=0, sticky="ew")
        self.options.append(button)

        button = ttk.Radiobutton(
            frame, text="centered", value=2, variable=self.radiovar
        )
        button.grid(row=0, column=1, sticky="ew")
        self.options.append(button)

        button = ttk.Radiobutton(frame, text="scaled", value=3, variable=self.radiovar)
        button.grid(row=0, column=2, sticky="ew")
        self.options.append(button)

        button = ttk.Radiobutton(frame, text="titled", value=4, variable=self.radiovar)
        button.grid(row=0, column=3, sticky="ew")
        self.options.append(button)

    def draw_additional_options(self):
        checkbutton = ttk.Checkbutton(
            self, text="Show grid", variable=self.show_grid_var
        )
        checkbutton.grid(row=4, column=0, sticky="ew", padx=5)

        checkbutton = ttk.Checkbutton(
            self,
            text="Adjust canvas size to image dimensions",
            variable=self.adjust_to_dim_var,
            command=self.click_adjust_canvas,
        )
        checkbutton.grid(row=5, column=0, sticky="ew", padx=5)

        self.show_grid_var.set(1)
        self.adjust_to_dim_var.set(0)

    def draw_buttons(self):
        frame = ttk.Frame(self)
        frame.grid(row=6, column=0, pady=5, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        button = ttk.Button(frame, text="Apply", command=self.click_apply)
        button.grid(row=0, column=0, sticky="ew")

        button = ttk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=1, sticky="ew")

    def click_open_image(self):
        filename = filedialog.askopenfilename(
            initialdir=str(BACKGROUNDS_PATH),
            title="Open",
            filetypes=(
                ("images", "*.gif *.jpg *.png *.bmp *pcx *.tga ..."),
                ("All Files", "*"),
            ),
        )
        if filename:
            self.file_name.set(filename)
            width, height = 250, 135
            img = Image.open(filename)
            img = img.resize((width, height), Image.ANTIALIAS)
            tk_img = ImageTk.PhotoImage(img)
            self.image_label.config(image=tk_img, width=width)
            self.image_label.image = tk_img

    def click_clear(self):
        """
        delete like shown in image link entry if there is any

        :return: nothing
        """
        # delete entry
        self.file_name.set("")
        # delete display image
        self.image_label.config(image="", width=32)

    def click_adjust_canvas(self):
        # deselect all radio buttons and grey them out
        if self.adjust_to_dim_var.get() == 1:
            self.radiovar.set(0)
            for option in self.options:
                option.config(state=tk.DISABLED)
        # turn back the radio button to active state so that user can choose again
        elif self.adjust_to_dim_var.get() == 0:
            self.radiovar.set(1)
            for option in self.options:
                option.config(state=tk.NORMAL)
        else:
            logging.error("canvasbackground.py adjust_canvas_size invalid value")

    def delete_canvas_components(self, tag_list):
        """
        delete canvas items whose tag is in the tag list

        :param list[string] tag_list: list of tags
        :return: nothing
        """
        for tag in tag_list:
            for i in self.canvas.find_withtag(tag):
                self.canvas.delete(i)

    def get_canvas_width_and_height(self):
        """
        retrieve canvas width and height in pixels

        :return: nothing
        """
        canvas = self.app.canvas
        grid = canvas.find_withtag("rectangle")[0]
        x0, y0, x1, y1 = canvas.coords(grid)
        canvas_w = abs(x0 - x1)
        canvas_h = abs(y0 - y1)
        return canvas_w, canvas_h

    def determine_cropped_image_dimension(self):
        """
        determine the dimension of the image after being cropped

        :return: nothing
        """
        return

    def upper_left(self, img):
        print("upperleft")
        tk_img = ImageTk.PhotoImage(img)

        # crop image if it is bigger than canvas
        canvas_w, canvas_h = self.get_canvas_width_and_height()

        cropx = img_w = tk_img.width()
        cropy = img_h = tk_img.height()

        if img_w > canvas_w:
            cropx -= img_w - canvas_w
        if img_h > canvas_h:
            cropy -= img_h - canvas_h
        cropped = img.crop((0, 0, cropx, cropy))
        cropped_tk = ImageTk.PhotoImage(cropped)

        # place left corner of image to the left corner of the canvas
        self.app.croppedwallpaper = cropped_tk

        self.delete_canvas_components(["wallpaper"])
        # self.delete_previous_wallpaper()

        wid = self.canvas.create_image(
            (cropx / 2, cropy / 2), image=cropped_tk, tags="wallpaper"
        )
        self.app.wallpaper_id = wid

    def center(self, img):
        """
        place the image at the center of canvas

        :param Image img: image object
        :return: nothing
        """
        tk_img = ImageTk.PhotoImage(img)
        canvas_w, canvas_h = self.get_canvas_width_and_height()

        cropx = img_w = tk_img.width()
        cropy = img_h = tk_img.height()

        # dimension of the cropped image
        if img_w > canvas_w:
            cropx -= img_w - canvas_w
        if img_h > canvas_h:
            cropy -= img_h - canvas_h

        x0 = (img_w - cropx) / 2
        y0 = (img_h - cropy) / 2
        x1 = x0 + cropx
        y1 = y0 + cropy
        cropped = img.crop((x0, y0, x1, y1))
        cropped_tk = ImageTk.PhotoImage(cropped)

        # place the center of the image at the center of the canvas
        self.app.croppedwallpaper = cropped_tk
        self.delete_canvas_components(["wallpaper"])
        # self.delete_previous_wallpaper()
        wid = self.canvas.create_image(
            (canvas_w / 2, canvas_h / 2), image=cropped_tk, tags="wallpaper"
        )
        self.app.wallpaper_id = wid

    def scaled(self, img):
        """
        scale image based on canvas dimension

        :param Image img: image object
        :return: nothing
        """
        canvas_w, canvas_h = self.get_canvas_width_and_height()
        resized_image = img.resize((int(canvas_w), int(canvas_h)), Image.ANTIALIAS)
        image_tk = ImageTk.PhotoImage(resized_image)
        self.app.croppedwallpaper = image_tk

        self.delete_canvas_components(["wallpaper"])
        # self.delete_previous_wallpaper()

        wid = self.canvas.create_image(
            (canvas_w / 2, canvas_h / 2), image=image_tk, tags="wallpaper"
        )
        self.app.wallpaper_id = wid

    def tiled(self, img):
        return

    def draw_new_canvas(self, canvas_width, canvas_height):
        """
        delete the old canvas and draw a new one

        :param int canvas_width: canvas width in pixel
        :param int canvas_height: canvas height in pixel
        :return:
        """
        self.delete_canvas_components(["rectangle", "gridline"])
        self.canvas.draw_grid(canvas_width, canvas_height)

    def canvas_to_image_dimension(self, img):
        image_tk = ImageTk.PhotoImage(img)
        img_w = image_tk.width()
        img_h = image_tk.height()
        self.delete_canvas_components(["wallpaper"])
        self.draw_new_canvas(img_w, img_h)
        wid = self.canvas.create_image((img_w / 2, img_h / 2), image=image_tk)
        self.app.croppedwallpaper = image_tk
        self.app.wallpaper_id = wid

    def show_grid(self):
        """

        :return: nothing
        """
        self.app.adjust_to_dim_var.set(self.adjust_to_dim_var.get())

        if self.show_grid_var.get() == 0:
            for i in self.canvas.find_withtag("gridline"):
                self.canvas.itemconfig(i, state=tk.HIDDEN)
        elif self.show_grid_var.get() == 1:
            for i in self.canvas.find_withtag("gridline"):
                self.canvas.itemconfig(i, state=tk.NORMAL)
                self.canvas.lift(i)
        else:
            logging.error("canvasbackground.py show_grid invalid value")

    def save_wallpaper_options(self):
        self.app.radiovar.set(self.radiovar.get())
        self.app.show_grid_var.set(self.show_grid_var.get())
        self.app.adjust_to_dim_var.set(self.adjust_to_dim_var.get())

    def click_apply(self):
        filename = self.file_name.get()
        if not filename:
            self.delete_canvas_components(["wallpaper"])
            self.destroy()
            self.app.current_wallpaper = None
            self.save_wallpaper_options()
            return

        try:
            img = Image.open(filename)
            self.app.current_wallpaper = img
        except FileNotFoundError:
            logging.error("invalid background: %s", filename)
            if self.app.wallpaper_id:
                self.canvas.delete(self.app.wallpaper_id)
            self.destroy()
            return

        self.app.adjust_to_dim_var.set(self.adjust_to_dim_var.get())
        if self.adjust_to_dim_var.get() == 0:
            self.app.radiovar.set(self.radiovar.get())
            option = ScaleOption(self.radiovar.get())
            if option == ScaleOption.UPPER_LEFT:
                self.upper_left(img)
            elif option == ScaleOption.CENTERED:
                self.center(img)
            elif option == ScaleOption.SCALED:
                self.scaled(img)
            elif option == ScaleOption.TILED:
                print("not implemented yet")

        elif self.adjust_to_dim_var.get() == 1:
            self.canvas_to_image_dimension(img)

        self.show_grid()
        self.destroy()
