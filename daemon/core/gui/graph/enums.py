import enum


class GraphMode(enum.Enum):
    SELECT = 0
    EDGE = 1
    PICKNODE = 2
    NODE = 3
    ANNOTATION = 4
    OTHER = 5


class ScaleOption(enum.Enum):
    NONE = 0
    UPPER_LEFT = 1
    CENTERED = 2
    SCALED = 3
    TILED = 4
