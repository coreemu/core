"""
size and scale
"""

import tkinter as tk


class SizeAndScale:
    def __init__(self):
        self.top = tk.Toplevel()
        self.top.title("Canvas Size and Scale")
        self.size_chart()

        self.pixel_width_text = None

    def click_scrollbar(self, e1, e2, e3):
        print(e1, e2, e3)

    def create_text_label(self, frame, text, row, column):
        text_label = tk.Label(frame, text=text)
        text_label.grid(row=row, column=column)

    def size_chart(self):
        f = tk.Frame(self.top)
        t = tk.Label(f, text="Size")
        t.grid(row=0, column=0, sticky=tk.W)

        scrollbar = tk.Scrollbar(f, orient=tk.VERTICAL)
        scrollbar.grid(row=1, column=1)
        e = tk.Entry(f, text="1000", xscrollcommand=scrollbar.set)
        e.focus()
        e.grid(row=1, column=0)
        scrollbar.config(command=self.click_scrollbar)

        # l = tk.Label(f, text="W")
        # l.grid(row=1, column=2)
        # l = tk.Label(f, text=" X ")
        # l.grid(row=1, column=3)
        self.create_text_label(f, "W", 1, 2)
        self.create_text_label(f, " X ", 1, 3)

        hpixel_scrollbar = tk.Scrollbar(f, orient=tk.VERTICAL)
        hpixel_scrollbar.grid(row=1, column=5)

        hpixel_entry = tk.Entry(f, text="750", xscrollcommand=hpixel_scrollbar.set)
        hpixel_entry.focus()
        hpixel_entry.grid(row=1, column=4)

        h_label = tk.Label(f, text="H")
        h_label.grid(row=1, column=6)

        self.create_text_label(f, "pixels", 1, 7)
        # pixel_label = tk.Label(f, text="pixels")
        # pixel_label.grid(row=1, column=7)

        wmeter_scrollbar = tk.Scrollbar(f, orient=tk.VERTICAL)
        wmeter_scrollbar.grid(row=2, column=2)

        wmeter_entry = tk.Entry(f, text="1500.0", xscrollcommand=wmeter_scrollbar.set)
        wmeter_entry.focus()
        wmeter_entry.grid(row=2, column=0, columnspan=2, sticky=tk.W + tk.E)

        # l = tk.Label(f, text=" X ")
        # l.grid(row=2, column=3)
        self.create_text_label(f, " X ", row=2, column=3)

        # f1 = tk.Frame(f)
        hmeter_scrollbar = tk.Scrollbar(f, orient=tk.VERTICAL)
        hmeter_scrollbar.grid(row=2, column=6)

        hmeter_entry = tk.Entry(f, text="1125.0", xscrollcommand=hmeter_scrollbar.set)
        hmeter_entry.focus()
        hmeter_entry.grid(row=2, column=4, columnspan=2, sticky=tk.W + tk.E)

        self.create_text_label(f, "pixels", 2, 7)
        # pixel_label = tk.Label(f, text="pixels")
        # pixel_label.grid(row=2, column=7)
        # hmeter_entry.pack(side=tk.LEFT)
        #
        # hmeter_scrollbar = tk.Scrollbar(hmeter_entry, orient=tk.VERTICAL)
        # hmeter_scrollbar.pack(side=tk.LEFT)
        # f1.grid(row=2, column=4)

        f.grid()

    # def scale_chart(self):
