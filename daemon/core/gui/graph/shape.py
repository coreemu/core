import logging

from core.gui.dialogs.shapemod import ShapeDialog
from core.gui.graph import tags
from core.gui.graph.shapeutils import ShapeType


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
        bold=False,
        italic=False,
        underline=False,
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
        else:
            self.created = True
            self.shape_data = data
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
                tags=tags.SHAPE,
                dash=dash,
                fill=self.shape_data.fill_color,
                outline=self.shape_data.border_color,
                width=self.shape_data.border_width,
            )
            self.draw_shape_text()
        elif self.shape_type == ShapeType.RECTANGLE:
            self.id = self.canvas.create_rectangle(
                self.x1,
                self.y1,
                self.x2,
                self.y2,
                tags=tags.SHAPE,
                dash=dash,
                fill=self.shape_data.fill_color,
                outline=self.shape_data.border_color,
                width=self.shape_data.border_width,
            )
            self.draw_shape_text()
        elif self.shape_type == ShapeType.TEXT:
            font = self.get_font()
            self.id = self.canvas.create_text(
                self.x1,
                self.y1,
                tags=tags.SHAPE_TEXT,
                text=self.shape_data.text,
                fill=self.shape_data.text_color,
                font=font,
            )
        else:
            logging.error("unknown shape type: %s", self.shape_type)
        self.created = True

    def get_font(self):
        font = [self.shape_data.font, self.shape_data.font_size]
        if self.shape_data.bold:
            font.append("bold")
        if self.shape_data.italic:
            font.append("italic")
        if self.shape_data.underline:
            font.append("underline")
        return font

    def draw_shape_text(self):
        if self.shape_data.text:
            x = (self.x1 + self.x2) / 2
            y = self.y1 + 1.5 * self.shape_data.font_size
            font = self.get_font()
            self.text_id = self.canvas.create_text(
                x,
                y,
                tags=tags.SHAPE_TEXT,
                text=self.shape_data.text,
                fill=self.shape_data.text_color,
                font=font,
            )

    def shape_motion(self, x1: int, y1: int):
        self.canvas.coords(self.id, self.x1, self.y1, x1, y1)

    def shape_complete(self, x, y):
        for component in tags.ABOVE_SHAPE:
            self.canvas.tag_raise(component)
        s = ShapeDialog(self.app, self.app, self)
        s.show()

    def disappear(self):
        self.canvas.delete(self.id)

    def motion(self, x_offset: int, y_offset: int):
        original_position = self.canvas.coords(self.id)
        self.canvas.move(self.id, x_offset, y_offset)
        coords = self.canvas.coords(self.id)
        if not self.canvas.valid_position(*coords):
            self.canvas.coords(self.id, original_position)
            return

        self.canvas.move_selection(self.id, x_offset, y_offset)
        if self.text_id is not None:
            self.canvas.move(self.text_id, x_offset, y_offset)

    def delete(self):
        self.canvas.delete(self.id)
        self.canvas.delete(self.text_id)

    def metadata(self):
        coords = self.canvas.coords(self.id)
        # update coords to actual positions
        if len(coords) == 4:
            x1, y1, x2, y2 = coords
            x1, y1 = self.canvas.get_actual_coords(x1, y1)
            x2, y2 = self.canvas.get_actual_coords(x2, y2)
            coords = (x1, y1, x2, y2)
        else:
            x1, y1 = coords
            x1, y1 = self.canvas.get_actual_coords(x1, y1)
            coords = (x1, y1)
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
            "bold": self.shape_data.bold,
            "italic": self.shape_data.italic,
            "underline": self.shape_data.underline,
        }
