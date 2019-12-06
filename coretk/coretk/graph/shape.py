from tkinter.font import Font

from coretk.dialogs.shapemod import ShapeDialog
from coretk.graph.shapeutils import ShapeType

ABOVE_COMPONENT = ["gridline", "edge", "linkinfo", "antenna", "node", "nodename"]


class AnnotationData:
    def __init__(
        self,
        text="",
        font="Arial",
        font_size=12,
        text_color="#000000",
        fill_color="",
        border_color="#000000",
        border_width=1,
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
    def __init__(self, app, canvas, shape_type, x1, y1, x2=None, y2=None, data=None):
        self.app = app
        self.canvas = canvas
        self.shape_type = shape_type
        self.id = None
        self.text_id = None
        self.x1 = x1
        self.y1 = y1
        if x2 is None:
            x2 = x1
        self.x2 = x2
        if y2 is None:
            y2 = y1
        self.y2 = y2
        if data is None:
            self.created = False
            self.shape_data = AnnotationData()
            self.cursor_x = x1
            self.cursor_y = y1
        else:
            self.created = True
            self.shape_data = data
            self.cursor_x = None
            self.cursor_y = None
        self.draw()

    def draw(self):
        if self.created:
            dash = None
        else:
            dash = "-"
        if self.shape_type == ShapeType.OVAL:
            self.id = self.canvas.create_oval(
                self.x1,
                self.y1,
                self.x2,
                self.y2,
                tags="shape",
                dash=dash,
                fill=self.shape_data.fill_color,
                outline=self.shape_data.border_color,
                width=self.shape_data.border_width,
            )
        elif self.shape_type == ShapeType.RECTANGLE:
            self.id = self.canvas.create_rectangle(
                self.x1,
                self.y1,
                self.x2,
                self.y2,
                tags="shape",
                dash=dash,
                fill=self.shape_data.fill_color,
                outline=self.shape_data.border_color,
                width=self.shape_data.border_width,
            )

        if self.shape_data.text:
            x = (self.x1 + self.x2) / 2
            y = self.y1 + 1.5 * self.shape_data.font_size
            font = Font(family=self.shape_data.font, size=self.shape_data.font_size)
            self.text_id = self.canvas.create_text(
                x,
                y,
                tags="shapetext",
                text=self.shape_data.text,
                fill=self.shape_data.text_color,
                font=font,
            )

    def shape_motion(self, x1, y1):
        self.canvas.coords(self.id, self.x1, self.y1, x1, y1)

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

    def metadata(self):
        coords = self.canvas.coords(self.id)
        return {
            "type": self.shape_type.value,
            "iconcoords": coords,
            "label": self.shape_data.text,
            "fontfamily": self.shape_data.font,
            "fontsize": self.shape_data.font_size,
            "labelcolor": self.shape_data.text_color,
            "color": self.shape_data.fill_color,
            "border": self.shape_data.border_color,
            "width": self.shape_data.border_width,
        }
