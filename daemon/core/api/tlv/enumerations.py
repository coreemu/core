"""
Enumerations specific to the CORE TLV API.
"""
from enum import Enum

CORE_API_PORT = 4038


class MessageTypes(Enum):
    """
    CORE message types.
    """

    NODE = 0x01
    LINK = 0x02
    EXECUTE = 0x03
    REGISTER = 0x04
    CONFIG = 0x05
    FILE = 0x06
    INTERFACE = 0x07
    EVENT = 0x08
    SESSION = 0x09
    EXCEPTION = 0x0A


class NodeTlvs(Enum):
    """
    Node type, length, value enumerations.
    """

    NUMBER = 0x01
    TYPE = 0x02
    NAME = 0x03
    IP_ADDRESS = 0x04
    MAC_ADDRESS = 0x05
    IP6_ADDRESS = 0x06
    MODEL = 0x07
    EMULATION_SERVER = 0x08
    SESSION = 0x0A
    X_POSITION = 0x20
    Y_POSITION = 0x21
    CANVAS = 0x22
    EMULATION_ID = 0x23
    NETWORK_ID = 0x24
    SERVICES = 0x25
    LATITUDE = 0x30
    LONGITUDE = 0x31
    ALTITUDE = 0x32
    ICON = 0x42
    OPAQUE = 0x50


class LinkTlvs(Enum):
    """
    Link type, length, value enumerations.
    """

    N1_NUMBER = 0x01
    N2_NUMBER = 0x02
    DELAY = 0x03
    BANDWIDTH = 0x04
    LOSS = 0x05
    DUP = 0x06
    JITTER = 0x07
    MER = 0x08
    BURST = 0x09
    SESSION = 0x0A
    MBURST = 0x10
    TYPE = 0x20
    GUI_ATTRIBUTES = 0x21
    UNIDIRECTIONAL = 0x22
    EMULATION_ID = 0x23
    NETWORK_ID = 0x24
    KEY = 0x25
    IFACE1_NUMBER = 0x30
    IFACE1_IP4 = 0x31
    IFACE1_IP4_MASK = 0x32
    IFACE1_MAC = 0x33
    IFACE1_IP6 = 0x34
    IFACE1_IP6_MASK = 0x35
    IFACE2_NUMBER = 0x36
    IFACE2_IP4 = 0x37
    IFACE2_IP4_MASK = 0x38
    IFACE2_MAC = 0x39
    IFACE2_IP6 = 0x40
    IFACE2_IP6_MASK = 0x41
    IFACE1_NAME = 0x42
    IFACE2_NAME = 0x43
    OPAQUE = 0x50


class ExecuteTlvs(Enum):
    """
    Execute type, length, value enumerations.
    """

    NODE = 0x01
    NUMBER = 0x02
    TIME = 0x03
    COMMAND = 0x04
    RESULT = 0x05
    STATUS = 0x06
    SESSION = 0x0A


class ConfigTlvs(Enum):
    """
    Configuration type, length, value enumerations.
    """

    NODE = 0x01
    OBJECT = 0x02
    TYPE = 0x03
    DATA_TYPES = 0x04
    VALUES = 0x05
    CAPTIONS = 0x06
    BITMAP = 0x07
    POSSIBLE_VALUES = 0x08
    GROUPS = 0x09
    SESSION = 0x0A
    IFACE_ID = 0x0B
    NETWORK_ID = 0x24
    OPAQUE = 0x50


class ConfigFlags(Enum):
    """
    Configuration flags.
    """

    NONE = 0x00
    REQUEST = 0x01
    UPDATE = 0x02
    RESET = 0x03


class FileTlvs(Enum):
    """
    File type, length, value enumerations.
    """

    NODE = 0x01
    NAME = 0x02
    MODE = 0x03
    NUMBER = 0x04
    TYPE = 0x05
    SOURCE_NAME = 0x06
    SESSION = 0x0A
    DATA = 0x10
    COMPRESSED_DATA = 0x11


class InterfaceTlvs(Enum):
    """
    Interface type, length, value enumerations.
    """

    NODE = 0x01
    NUMBER = 0x02
    NAME = 0x03
    IP_ADDRESS = 0x04
    MASK = 0x05
    MAC_ADDRESS = 0x06
    IP6_ADDRESS = 0x07
    IP6_MASK = 0x08
    TYPE = 0x09
    SESSION = 0x0A
    STATE = 0x0B
    EMULATION_ID = 0x23
    NETWORK_ID = 0x24


class EventTlvs(Enum):
    """
    Event type, length, value enumerations.
    """

    NODE = 0x01
    TYPE = 0x02
    NAME = 0x03
    DATA = 0x04
    TIME = 0x05
    SESSION = 0x0A


class SessionTlvs(Enum):
    """
    Session type, length, value enumerations.
    """

    NUMBER = 0x01
    NAME = 0x02
    FILE = 0x03
    NODE_COUNT = 0x04
    DATE = 0x05
    THUMB = 0x06
    USER = 0x07
    OPAQUE = 0x0A


class ExceptionTlvs(Enum):
    """
    Exception type, length, value enumerations.
    """

    NODE = 0x01
    SESSION = 0x02
    LEVEL = 0x03
    SOURCE = 0x04
    DATE = 0x05
    TEXT = 0x06
    OPAQUE = 0x0A
