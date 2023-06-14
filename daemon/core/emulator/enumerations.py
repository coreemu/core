"""
Common enumerations used within CORE.
"""

from enum import Enum


class MessageFlags(Enum):
    """
    CORE message flags.
    """

    NONE = 0x00
    ADD = 0x01
    DELETE = 0x02
    CRI = 0x04
    LOCAL = 0x08
    STRING = 0x10
    TEXT = 0x20
    TTY = 0x40


class ConfigFlags(Enum):
    """
    Configuration flags.
    """

    NONE = 0x00
    REQUEST = 0x01
    UPDATE = 0x02
    RESET = 0x03


class NodeTypes(Enum):
    """
    Node types.
    """

    DEFAULT = 0
    PHYSICAL = 1
    SWITCH = 4
    HUB = 5
    WIRELESS_LAN = 6
    RJ45 = 7
    TUNNEL = 8
    EMANE = 10
    TAP_BRIDGE = 11
    PEER_TO_PEER = 12
    CONTROL_NET = 13
    DOCKER = 15
    LXC = 16
    WIRELESS = 17
    PODMAN = 18


class LinkTypes(Enum):
    """
    Link types.
    """

    WIRELESS = 0
    WIRED = 1


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

    def should_start(self) -> bool:
        return self.value > self.DEFINITION_STATE.value

    def already_collected(self) -> bool:
        return self.value >= self.DATACOLLECT_STATE.value


class ExceptionLevels(Enum):
    """
    Exception levels.
    """

    NONE = 0
    FATAL = 1
    ERROR = 2
    WARNING = 3
    NOTICE = 4


class NetworkPolicy(Enum):
    ACCEPT = "ACCEPT"
    DROP = "DROP"


class TransportType(Enum):
    RAW = "raw"
    VIRTUAL = "virtual"
