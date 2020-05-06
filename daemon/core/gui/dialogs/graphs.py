import logging
import random
import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from core.gui.dialogs.dialog import Dialog
from core.gui.themes import PADY


class GraphDialog(Dialog):
    def __init__(self, app, title, live=False):
        super().__init__(app, title, modal=False)
        self.fig = None
        self.plot = None
        self.canvas = None
        self.toolbar = None
        self.animation = None
        self.live = live

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        # create figure and plot
        frame = ttk.Frame(self.top)
        frame.grid(sticky="nsew", pady=PADY)

        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.plot = self.fig.add_subplot(111)

        # create and draw figure canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # create and draw toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, frame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # initialize graph artists
        self.init_artists()

    def run(self):
        logging.info("live graph")
        self.animation = FuncAnimation(
            fig=self.fig, func=self.animate, interval=1000, repeat_delay=5000
        )

    def show(self):
        self.draw()
        if self.live:
            self.run()
        super().show()

    def init_artists(self):
        raise NotImplementedError

    def animate(self, frame, *fargs):
        raise NotImplementedError


class GraphLineDialog(GraphDialog):
    def __init__(self, app, title, live=False):
        super().__init__(app, title, live)
        self.x_data = []
        self.y_data = []
        self.line = None
        self.background = None

    def init_artists(self):
        self.plot.set_ylim(0, 10)
        self.line, = self.plot.plot(self.x_data, self.y_data)
        if self.live:
            self.background = self.canvas.copy_from_bbox(self.plot.bbox)

    def animate(self, frame, *fargs):
        logging.info("blit graph counter: %s - %s", frame, fargs)
        x = frame
        y = random.randint(1, 10)
        self.x_data.append(x)
        self.y_data.append(y)
        self.line.set_data(self.x_data, self.y_data)

        # restore background
        self.plot.relim()
        self.plot.axes.autoscale_view(True, True, True)
        self.canvas.restore_region(self.background)
        self.plot.draw_artist(self.line)
        self.canvas.blit(self.plot.bbox)


class GraphBarDialog(GraphDialog):
    def __init__(self, app, title):
        super().__init__(app, title)

    def init_artists(self):
        data = (20, 35, 30, 35, 27)
        ind = np.arange(5)
        width = 0.5
        return self.plot.bar(ind, data, width)

    def animate(self, frame, *fargs):
        pass

    def animate_blit(self, frame, *fargs):
        pass


class GraphScatterDialog(GraphDialog):
    def __init__(self, app, title):
        super().__init__(app, title)

    def init_artists(self):
        t = np.arange(0, 3, 0.01)
        return self.plot.scatter(t, 2 * np.sin(2 * np.pi * t))

    def animate(self, frame, *fargs):
        pass

    def animate_blit(self, frame, *fargs):
        pass
