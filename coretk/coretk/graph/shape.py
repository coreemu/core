"""
class for shapes
"""
from coretk.dialogs.shapemod import ShapeDialog
from coretk.images import ImageEnum

ABOVE_COMPONENT = ["gridline", "edge", "linkinfo", "antenna", "node", "nodename"]


class AnnotationData:
    def __init__(
        self,
        text="",
        font="Arial",
        font_size=12,
        text_color="#000000",
        fill_color="#CFCFFF",
        border_color="#000000",
        border_width=0,
        bold=0,
        italic=0,
        underline=0,
    ):

        self.text = text
        self.font = font
        self.font_size = font_size
        self.text_color = text_color
        self.fill_color = fill_color
        self.border_color = border_color
        self.border_width = border_width
        self.bold = bold
        self.italic = italic
        self.underline = underline


class Shape:
    def __init__(
        self,
        app,
        canvas,
        top_x=None,
        top_y=None,
        coords=None,
        data=None,
        shape_type=None,
    ):
        self.app = app
        self.canvas = canvas
        if data is None:
            self.x0 = top_x
            self.y0 = top_y
            self.created = False
            self.text_id = None
            self.shape_data = AnnotationData()
            canvas.delete(canvas.find_withtag("selectednodes"))
            annotation_type = self.canvas.annotation_type
            if annotation_type == ImageEnum.OVAL:
                self.id = canvas.create_oval(
                    top_x, top_y, top_x, top_y, tags="shape", dash="-"
                )
            elif annotation_type == ImageEnum.RECTANGLE:
                self.id = canvas.create_rectangle(
                    top_x, top_y, top_x, top_y, tags="shape", dash="-"
                )
        else:
            x0, y0, x1, y1 = coords
            self.x0 = x0
            self.y0 = y0
            self.created = True
            if shape_type == "oval":
                self.id = self.canvas.create_oval(
                    x0,
                    y0,
                    x1,
                    y1,
                    tags="shape",
                    fill=data.fill_color,
                    outline=data.border_color,
                    width=data.border_width,
                )
            elif shape_type == "rectangle":
                self.id = self.canvas.create_rectangle(
                    x0,
                    y0,
                    x1,
                    y1,
                    tags="shape",
                    fill=data.fill_color,
                    outline=data.border_color,
                    width=data.border_width,
                )
            _x = (x0 + x1) / 2
            _y = y0 + 1.5 * data.font_size
            self.text_id = self.canvas.create_text(
                _x, _y, tags="shapetext", text=data.text, fill=data.text_color
            )
            self.shape_data = data
        self.cursor_x = None
        self.cursor_y = None

    def shape_motion(self, x1, y1):
        self.canvas.coords(self.id, self.x0, self.y0, x1, y1)

    def shape_complete(self, x, y):
        for component in ABOVE_COMPONENT:
            self.canvas.tag_raise(component)
        s = ShapeDialog(self.app, self.app, self)
        s.show()

    def motion(self, event, delta_x=None, delta_y=None):
        if event is not None:
            delta_x = event.x - self.cursor_x
            delta_y = event.y - self.cursor_y
            self.cursor_x = event.x
            self.cursor_y = event.y
        self.canvas.move(self.id, delta_x, delta_y)
        self.canvas.object_drag(self.id, delta_x, delta_y)
        if self.text_id is not None:
            self.canvas.move(self.text_id, delta_x, delta_y)

    def delete(self):
        self.canvas.delete(self.id)
        self.canvas.delete(self.text_id)
