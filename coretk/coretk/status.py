"status bar"
import time
import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Frame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.status = None
        self.statusvar = tk.StringVar()
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
        self.status = ttk.Label(self, textvariable=self.statusvar)
        self.statusvar.set("status")
        self.status.grid(row=0, column=0)
        self.zoom = ttk.Label(self, text="zoom")
        self.zoom.grid(row=0, column=1)
        self.cpu_usage = ttk.Label(self, text="cpu usage")
        self.cpu_usage.grid(row=0, column=2)
        self.emulation_light = ttk.Label(self, text="emulation light")
        self.emulation_light.grid(row=0, column=3)

    def processing(self):
        texts = ["Processing.", "Processing..", "Processing...", "Processing...."]
        i = 0
        while self.running:
            self.statusvar.set(texts[i % 4])
            self.master.update()
            i = i + 1
            time.sleep(0.002)
        print("thread finish")
