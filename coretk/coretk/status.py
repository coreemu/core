"status bar"
import time
from tkinter import ttk


class StatusBar(ttk.Frame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.status = None
        self.zoom = None
        self.cpu_usage = None
        self.memory = None
        self.emulation_light = None
        self.running = False
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=8)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)
        self.status = ttk.Label(self, text="status")
        self.status.grid(row=0, column=0)
        self.zoom = ttk.Label(self, text="zoom")
        self.zoom.grid(row=0, column=1)
        self.cpu_usage = ttk.Label(self, text="cpu usage")
        self.cpu_usage.grid(row=0, column=2)
        self.emulation_light = ttk.Label(self, text="emulation light")
        self.emulation_light.grid(row=0, column=3)

    def processing(self):
        self.running = True
        texts = ["Processing.", "Processing..", "Processing...", "Processing...."]
        i = 0
        while self.running is True:
            self.status.config(text=texts[i % 4])
            self.app.master.update()
            i = i + 1
            time.sleep(0.3)
            print("running")
        print("thread finish")
        # self.status.config(text="status")
