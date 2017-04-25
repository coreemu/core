"""
Contains all legacy enumerations for interacting with legacy CORE code.
"""

from enum import Enum

CORE_API_VERSION = "1.23"
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


class MessageFlags(Enum):
    """
    CORE message flags.
    """
    ADD = 0x01
    DELETE = 0x02
    CRI = 0x04
    LOCAL = 0x08
    STRING = 0x10
    TEXT = 0x20
    TTY = 0x40


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


class NodeTypes(Enum):
    """
    Node types.
    """
    DEFAULT = 0
    PHYSICAL = 1
    XEN = 2
    TBD = 3
    SWITCH = 4
    HUB = 5
    WIRELESS_LAN = 6
    RJ45 = 7
    TUNNEL = 8
    KTUNNEL = 9
    EMANE = 10
    TAP_BRIDGE = 11
    PEER_TO_PEER = 12
    CONTROL_NET = 13
    EMANE_NET = 14


class Rj45Models(Enum):
    """
    RJ45 model types.
    """
    LINKED = 0
    WIRELESS = 1
    INSTALLED = 2


# Link Message TLV Types
class LinkTlvs(Enum):
    """
    Link type, length, value enumerations.
    """
    N1_NUMBER = 0x01
    N2_NUMBER = 0x02
    DELAY = 0x03
    BANDWIDTH = 0x04
    PER = 0x05
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
    INTERFACE1_NUMBER = 0x30
    INTERFACE1_IP4 = 0x31
    INTERFACE1_IP4_MASK = 0x32
    INTERFACE1_MAC = 0x33
    INTERFACE1_IP6 = 0x34
    INTERFACE1_IP6_MASK = 0x35
    INTERFACE2_NUMBER = 0x36
    INTERFACE2_IP4 = 0x37
    INTERFACE2_IP4_MASK = 0x38
    INTERFACE2_MAC = 0x39
    INTERFACE2_IP6 = 0x40
    INTERFACE2_IP6_MASK = 0x41
    INTERFACE1_NAME = 0x42
    INTERFACE2_NAME = 0x43
    OPAQUE = 0x50


class LinkTypes(Enum):
    """
    Link types.
    """
    WIRELESS = 0
    WIRED = 1


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


class RegisterTlvs(Enum):
    """
    Register type, length, value enumerations.
    """
    WIRELESS = 0x01
    MOBILITY = 0x02
    UTILITY = 0x03
    EXECUTE_SERVER = 0x04
    GUI = 0x05
    EMULATION_SERVER = 0x06
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
    INTERFACE_NUMBER = 0x0B
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


class ConfigDataTypes(Enum):
    """
    Configuration data types.
    """
    UINT8 = 0x01
    UINT16 = 0x02
    UINT32 = 0x03
    UINT64 = 0x04
    INT8 = 0x05
    INT16 = 0x06
    INT32 = 0x07
    INT64 = 0x08
    FLOAT = 0x09
    STRING = 0x0A
    BOOL = 0x0B


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


class EventTypes(Enum):
    """
    Event types.
    """
    NONE = 0
    DEFINITION_STATE = 1
    CONFIGURATION_STATE = 2
    INSTANTIATION_STATE = 3
    RUNTIME_STATE = 4
    DATACOLLECT_STATE = 5
    SHUTDOWN_STATE = 6
    START = 7
    STOP = 8
    PAUSE = 9
    RESTART = 10
    FILE_OPEN = 11
    FILE_SAVE = 12
    SCHEDULED = 13
    RECONFIGURE = 14
    INSTANTIATION_COMPLETE = 15


# Session Message TLV Types
class SessionTlvs(Enum):
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


class ExceptionLevels(Enum):
    """
    Exception levels.
    """
    NONE = 0
    FATAL = 1
    ERROR = 2
    WARNING = 3
    NOTICE = 4
