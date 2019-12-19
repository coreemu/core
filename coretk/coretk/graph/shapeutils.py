import enum


class ShapeType(enum.Enum):
    MARKER = "marker"
    OVAL = "oval"
    RECTANGLE = "rectangle"
    TEXT = "text"


SHAPES = {ShapeType.OVAL, ShapeType.RECTANGLE}


def is_draw_shape(shape_type):
    return shape_type in SHAPES


def is_shape_text(shape_type):
    return shape_type == ShapeType.TEXT


def is_marker(shape_type):
    return shape_type == ShapeType.MARKER
