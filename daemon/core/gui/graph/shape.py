import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from core.gui.dialogs.shapemod import ShapeDialog
from core.gui.graph import tags
from core.gui.graph.shapeutils import ShapeType

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.graph import CanvasGraph


class AnnotationData:
    def __init__(
        self,
        text: str = "",
        font: str = "Arial",
        font_size: int = 12,
        text_color: str = "#000000",
        fill_color: str = "",
        border_color: str = "#000000",
        border_width: int = 1,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
    ) -> None:
        self.text: str = text
        self.font: str = font
        self.font_size: int = font_size
        self.text_color: str = text_color
        self.fill_color: str = fill_color
        self.border_color: str = border_color
        self.border_width: int = border_width
        self.bold: bool = bold
        self.italic: bool = italic
        self.underline: bool = underline


class Shape:
    def __init__(
        self,
        app: "Application",
        canvas: "CanvasGraph",
        shape_type: ShapeType,
        x1: float,
        y1: float,
        x2: float = None,
        y2: float = None,
        data: AnnotationData = None,
    ) -> None:
        self.app: "Application" = app
        self.canvas: "CanvasGraph" = canvas
        self.shape_type: ShapeType = shape_type
        self.id: Optional[int] = None
        self.text_id: Optional[int] = None
        self.x1: float = x1
        self.y1: float = y1
        if x2 is None:
            x2 = x1
        self.x2: float = x2
        if y2 is None:
            y2 = y1
        self.y2: float = y2
        if data is None:
            self.created: bool = False
            self.shape_data: AnnotationData = AnnotationData()
        else:
            self.created: bool = True
            self.shape_data = data
        self.draw()

    @classmethod
    def from_metadata(cls, app: "Application", config: Dict[str, Any]) -> None:
        shape_type = config["type"]
        try:
            shape_type = ShapeType(shape_type)
            coords = config["iconcoords"]
            data = AnnotationData(
                config["label"],
                config["fontfamily"],
                config["fontsize"],
                config["labelcolor"],
                config["color"],
                config["border"],
                config["width"],
                config["bold"],
                config["italic"],
                config["underline"],
            )
            canvas_id = config.get("canvas", 1)
            canvas = app.manager.get(canvas_id)
            shape = Shape(app, canvas, shape_type, *coords, data=data)
            canvas.shapes[shape.id] = shape
        except ValueError:
            logger.exception("unknown shape: %s", shape_type)

    def draw(self) -> None:
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
                tags=(tags.SHAPE, tags.ANNOTATION),
                dash=dash,
                fill=self.shape_data.fill_color,
                outline=self.shape_data.border_color,
                width=self.shape_data.border_width,
                state=self.app.manager.show_annotations.state(),
            )
            self.draw_shape_text()
        elif self.shape_type == ShapeType.RECTANGLE:
            self.id = self.canvas.create_rectangle(
                self.x1,
                self.y1,
                self.x2,
                self.y2,
                tags=(tags.SHAPE, tags.ANNOTATION),
                dash=dash,
                fill=self.shape_data.fill_color,
                outline=self.shape_data.border_color,
                width=self.shape_data.border_width,
                state=self.app.manager.show_annotations.state(),
            )
            self.draw_shape_text()
        elif self.shape_type == ShapeType.TEXT:
            font = self.get_font()
            self.id = self.canvas.create_text(
                self.x1,
                self.y1,
                tags=(tags.SHAPE_TEXT, tags.ANNOTATION),
                text=self.shape_data.text,
                fill=self.shape_data.text_color,
                font=font,
                state=self.app.manager.show_annotations.state(),
            )
        else:
            logger.error("unknown shape type: %s", self.shape_type)
        self.created = True

    def get_font(self) -> List[Union[int, str]]:
        font = [self.shape_data.font, self.shape_data.font_size]
        if self.shape_data.bold:
            font.append("bold")
        if self.shape_data.italic:
            font.append("italic")
        if self.shape_data.underline:
            font.append("underline")
        return font

    def draw_shape_text(self) -> None:
        if self.shape_data.text:
            x = (self.x1 + self.x2) / 2
            y = self.y1 + 1.5 * self.shape_data.font_size
            font = self.get_font()
            self.text_id = self.canvas.create_text(
                x,
                y,
                tags=(tags.SHAPE_TEXT, tags.ANNOTATION),
                text=self.shape_data.text,
                fill=self.shape_data.text_color,
                font=font,
                state=self.app.manager.show_annotations.state(),
            )

    def shape_motion(self, x1: float, y1: float) -> None:
        self.canvas.coords(self.id, self.x1, self.y1, x1, y1)

    def shape_complete(self, x: float, y: float) -> None:
        self.canvas.organize()
        s = ShapeDialog(self.app, self)
        s.show()

    def disappear(self) -> None:
        self.canvas.delete(self.id)

    def motion(self, x_offset: float, y_offset: float) -> None:
        original_position = self.canvas.coords(self.id)
        self.canvas.move(self.id, x_offset, y_offset)
        coords = self.canvas.coords(self.id)
        if self.shape_type == ShapeType.TEXT:
            coords = coords * 2
        if not self.canvas.valid_position(*coords):
            self.canvas.coords(self.id, original_position)
            return
        self.canvas.move_selection(self.id, x_offset, y_offset)
        if self.text_id is not None:
            self.canvas.move(self.text_id, x_offset, y_offset)

    def delete(self) -> None:
        logger.debug("Delete shape, id(%s)", self.id)
        self.canvas.delete(self.id)
        self.canvas.delete(self.text_id)

    def metadata(self) -> Dict[str, Union[str, int, bool]]:
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
            "canvas": self.canvas.id,
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
