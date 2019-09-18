import os

from PIL import Image, ImageTk

PATH = os.path.abspath(os.path.dirname(__file__))


class Images:
    images = {}

    @classmethod
    def load(cls, name, file_path):
        file_path = os.path.join(PATH, file_path)
        image = Image.open(file_path)
        tk_image = ImageTk.PhotoImage(image)
        cls.images[name] = tk_image

    @classmethod
    def get(cls, name):
        return cls.images[name]
