import tkinter as tk


class CanvasWirelessEdge:
    def __init__(self, token, position, src, dst, canvas):
        self.token = token
        self.src = src
        self.dst = dst
        self.canvas = canvas
        self.id = self.canvas.create_line(
            *position, tags="wireless", width=1.5, fill="#009933"
        )

    def delete(self):
        self.canvas.delete(self.id)


class CanvasEdge:
    """
    Canvas edge class
    """

    width = 1.4

    def __init__(self, x1, y1, x2, y2, src, canvas, is_wired=None):
        """
        Create an instance of canvas edge object
        :param int x1: source x-coord
        :param int y1: source y-coord
        :param int x2: destination x-coord
        :param int y2: destination y-coord
        :param int src: source id
        :param tkinter.Canvas canvas: canvas object
        """
        self.src = src
        self.dst = None
        self.src_interface = None
        self.dst_interface = None
        self.canvas = canvas
        if is_wired is None or is_wired is True:
            self.id = self.canvas.create_line(
                x1, y1, x2, y2, tags="edge", width=self.width, fill="#ff0000"
            )
        else:
            self.id = self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                tags="edge",
                width=self.width,
                fill="#ff0000",
                state=tk.HIDDEN,
            )
        self.token = None
        self.link_info = None
        self.throughput = None
        self.wired = is_wired

    def complete(self, dst, x, y):
        self.dst = dst
        self.token = tuple(sorted((self.src, self.dst)))
        x1, y1, _, _ = self.canvas.coords(self.id)
        self.canvas.coords(self.id, x1, y1, x, y)
        self.canvas.helper.draw_wireless_case(self.src, self.dst, self)
        self.canvas.tag_raise(self.src)
        self.canvas.tag_raise(self.dst)

    def delete(self):
        self.canvas.delete(self.id)
