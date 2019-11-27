"""
class for shapes
"""
# from coretk.images import ImageEnum, Images


class Shape:
    def __init__(self, app, canvas, topleft_x, topleft_y):
        self.app = app
        self.canvas = canvas
        self.x0 = topleft_x
        self.y0 = topleft_y
        # imageenum = self.app.toolbar
        self.id = self.canvas.create_oval(
            topleft_x, topleft_y, topleft_x + 30, topleft_y + 30
        )
