"""
Uses coreapi_data for message and TLV types, and defines TLV data
types and objects used for parsing and building CORE API messages.

CORE API messaging is leveraged for communication with the GUI.
"""

import binascii
import socket
import struct
from enum import Enum

import netaddr

from core.api.tlv import structutils
from core.api.tlv.enumerations import (
    ConfigTlvs,
    EventTlvs,
    ExceptionTlvs,
    ExecuteTlvs,
    FileTlvs,
    InterfaceTlvs,
    LinkTlvs,
    MessageTypes,
    NodeTlvs,
    SessionTlvs,
)
from core.emulator.enumerations import MessageFlags, RegisterTlvs


class CoreTlvData:
    """
    Helper base class used for packing and unpacking values using struct.
    """

    # format string for packing data
    data_format = None
    # python data type for the data
    data_type = None
    # pad length for data after packing
    pad_len = None

    @classmethod
    def pack(cls, value):
        """
        Convenience method for packing data using the struct module.

        :param value: value to pack
        :return: length of data and the packed data itself
        :rtype: tuple
        """
        data = struct.pack(cls.data_format, value)
        length = len(data) - cls.pad_len
        return length, data

    @classmethod
    def unpack(cls, data):
        """
        Convenience method for unpacking data using the struct module.

        :param data: data to unpack
        :return: the value of the unpacked data
        """
        return struct.unpack(cls.data_format, data)[0]

    @classmethod
    def pack_string(cls, value):
        """
        Convenience method for packing data from a string representation.

        :param str value: value to pack
        :return: length of data and the packed data itself
        :rtype: tuple
        """
        return cls.pack(cls.from_string(value))

    @classmethod
    def from_string(cls, value):
        """
        Retrieve the value type from a string representation.

        :param str value: value to get a data type from
        :return: value parse from string representation
        """
        return cls.data_type(value)


class CoreTlvDataObj(CoreTlvData):
    """
    Helper class for packing custom object data.
    """

    @classmethod
    def pack(cls, value):
        """
        Convenience method for packing custom object data.

        :param value: custom object to pack
        :return: length of data and the packed data itself
        :rtype: tuple
        """
        value = cls.get_value(value)
        return super().pack(value)

    @classmethod
    def unpack(cls, data):
        """
        Convenience method for unpacking custom object data.

        :param data: data to unpack custom object from
        :return: unpacked custom object
        """
        data = super().unpack(data)
        return cls.new_obj(data)

    @staticmethod
    def get_value(obj):
        """
        Method that will be used to retrieve the data to pack from a custom object.

        :param obj: custom object to get data to pack
        :return: data value to pack
        """
        raise NotImplementedError

    @staticmethod
    def new_obj(obj):
        """
        Method for retrieving data to unpack from an object.

        :param obj: object to get unpack data from
        :return: value of unpacked data
        """
        raise NotImplementedError


class CoreTlvDataUint16(CoreTlvData):
    """
    Helper class for packing uint16 data.
    """

    data_format = "!H"
    data_type = int
    pad_len = 0


class CoreTlvDataUint32(CoreTlvData):
    """
    Helper class for packing uint32 data.
    """

    data_format = "!2xI"
    data_type = int
    pad_len = 2


class CoreTlvDataUint64(CoreTlvData):
    """
    Helper class for packing uint64 data.
    """

    data_format = "!2xQ"
    data_type = int
    pad_len = 2


class CoreTlvDataString(CoreTlvData):
    """
    Helper class for packing string data.
    """

    data_type = str

    @classmethod
    def pack(cls, value):
        """
        Convenience method for packing string data.

        :param str value: string to pack
        :return: length of data packed and the packed data
        :rtype: tuple
        """
        if not isinstance(value, str):
            raise ValueError(f"value not a string: {type(value)}")
        value = value.encode("utf-8")

        if len(value) < 256:
            header_len = CoreTlv.header_len
        else:
            header_len = CoreTlv.long_header_len

        pad_len = -(header_len + len(value)) % 4
        return len(value), value + b"\0" * pad_len

    @classmethod
    def unpack(cls, data):
        """
        Convenience method for unpacking string data.

        :param str data: unpack string data
        :return: unpacked string data
        """
        return data.rstrip(b"\0").decode("utf-8")


class CoreTlvDataUint16List(CoreTlvData):
    """
    List of unsigned 16-bit values.
    """

    data_type = tuple
    data_format = "!H"

    @classmethod
    def pack(cls, values):
        """
        Convenience method for packing a uint 16 list.

        :param list values: unint 16 list to pack
        :return: length of data packed and the packed data
        :rtype: tuple
        """
        if not isinstance(values, tuple):
            raise ValueError(f"value not a tuple: {values}")

        data = b""
        for value in values:
            data += struct.pack(cls.data_format, value)

        pad_len = -(CoreTlv.header_len + len(data)) % 4
        return len(data), data + b"\0" * pad_len

    @classmethod
    def unpack(cls, data):
        """
        Convenience method for unpacking a uint 16 list.

        :param data: data to unpack
        :return: unpacked data
        """
        size = int(len(data) / 2)
        data_format = f"!{size}H"
        return struct.unpack(data_format, data)

    @classmethod
    def from_string(cls, value):
        """
        Retrieves a unint 16 list from a string

        :param str value: string representation of a uint 16 list
        :return: uint 16 list
        :rtype: list
        """
        return tuple(int(x) for x in value.split())


class CoreTlvDataIpv4Addr(CoreTlvDataObj):
    """
    Utility class for packing/unpacking Ipv4 addresses.
    """

    data_type = str
    data_format = "!2x4s"
    pad_len = 2

    @staticmethod
    def get_value(obj):
        """
        Retrieve Ipv4 address value from object.

        :param str obj: ip address to get value from
        :return: packed address
        :rtype: bytes
        """
        return socket.inet_pton(socket.AF_INET, obj)

    @staticmethod
    def new_obj(value):
        """
        Retrieve Ipv4 address from a string representation.

        :param bytes value: value to get Ipv4 address from
        :return: Ipv4 address
        :rtype: str
        """
        return socket.inet_ntop(socket.AF_INET, value)


class CoreTlvDataIPv6Addr(CoreTlvDataObj):
    """
    Utility class for packing/unpacking Ipv6 addresses.
    """

    data_format = "!16s2x"
    data_type = str
    pad_len = 2

    @staticmethod
    def get_value(obj):
        """
        Retrieve Ipv6 address value from object.

        :param str obj: ip address to get value from
        :return: packed address
        :rtype: bytes
        """
        return socket.inet_pton(socket.AF_INET6, obj)

    @staticmethod
    def new_obj(value):
        """
        Retrieve Ipv6 address from a string representation.

        :param bytes value: value to get Ipv4 address from
        :return: Ipv4 address
        :rtype: str
        """
        return socket.inet_ntop(socket.AF_INET6, value)


class CoreTlvDataMacAddr(CoreTlvDataObj):
    """
    Utility class for packing/unpacking mac addresses.
    """

    data_format = "!2x8s"
    data_type = str
    pad_len = 2

    @staticmethod
    def get_value(obj):
        """
        Retrieve Ipv6 address value from object.

        :param str obj: mac address to get value from
        :return: packed mac address
        :rtype: bytes
        """
        # extend to 64 bits
        return b"\0\0" + netaddr.EUI(obj).packed

    @staticmethod
    def new_obj(value):
        """
        Retrieve mac address from a string representation.

        :param bytes value: value to get Ipv4 address from
        :return: mac address
        :rtype: str
        """
        # only use 48 bits
        value = binascii.hexlify(value[2:]).decode()
        mac = netaddr.EUI(value, dialect=netaddr.mac_unix_expanded)
        return str(mac)


class CoreTlv:
    """
    Base class for representing CORE TLVs.
    """

    header_format = "!BB"
    header_len = struct.calcsize(header_format)

    long_header_format = "!BBH"
    long_header_len = struct.calcsize(long_header_format)

    tlv_type_map = Enum
    tlv_data_class_map = {}

    def __init__(self, tlv_type, tlv_data):
        """
        Create a CoreTlv instance.

        :param int tlv_type: tlv type
        :param tlv_data: data to unpack
        :return: unpacked data
        """
        self.tlv_type = tlv_type
        if tlv_data:
            try:
                self.value = self.tlv_data_class_map[self.tlv_type].unpack(tlv_data)
            except KeyError:
                self.value = tlv_data
        else:
            self.value = None

    @classmethod
    def unpack(cls, data):
        """
        Parse data and return unpacked class.

        :param data: data to unpack
        :return: unpacked data class
        """
        tlv_type, tlv_len = struct.unpack(cls.header_format, data[: cls.header_len])
        header_len = cls.header_len
        if tlv_len == 0:
            tlv_type, _zero, tlv_len = struct.unpack(
                cls.long_header_format, data[: cls.long_header_len]
            )
            header_len = cls.long_header_len
        tlv_size = header_len + tlv_len
        # for 32-bit alignment
        tlv_size += -tlv_size % 4
        return cls(tlv_type, data[header_len:tlv_size]), data[tlv_size:]

    @classmethod
    def pack(cls, tlv_type, value):
        """
        Pack a TLV value, based on type.

        :param int tlv_type: type of data to pack
        :param value: data to pack
        :return: header and packed data
        """
        tlv_len, tlv_data = cls.tlv_data_class_map[tlv_type].pack(value)
        if tlv_len < 256:
            hdr = struct.pack(cls.header_format, tlv_type, tlv_len)
        else:
            hdr = struct.pack(cls.long_header_format, tlv_type, 0, tlv_len)
        return hdr + tlv_data

    @classmethod
    def pack_string(cls, tlv_type, value):
        """
        Pack data type from a string representation

        :param int tlv_type: type of data to pack
        :param str value: string representation of data
        :return: header and packed data
        """
        return cls.pack(tlv_type, cls.tlv_data_class_map[tlv_type].from_string(value))

    def type_str(self):
        """
        Retrieve type string for this data type.

        :return: data type name
        :rtype: str
        """
        try:
            return self.tlv_type_map(self.tlv_type).name
        except ValueError:
            return f"unknown tlv type: {self.tlv_type}"

    def __str__(self):
        """
        String representation of this data type.

        :return: string representation
        :rtype: str
        """
        return f"{self.__class__.__name__} <tlvtype = {self.type_str()}, value = {self.value}>"


class CoreNodeTlv(CoreTlv):
    """
    Class for representing CORE Node TLVs.
    """

    tlv_type_map = NodeTlvs
    tlv_data_class_map = {
        NodeTlvs.NUMBER.value: CoreTlvDataUint32,
        NodeTlvs.TYPE.value: CoreTlvDataUint32,
        NodeTlvs.NAME.value: CoreTlvDataString,
        NodeTlvs.IP_ADDRESS.value: CoreTlvDataIpv4Addr,
        NodeTlvs.MAC_ADDRESS.value: CoreTlvDataMacAddr,
        NodeTlvs.IP6_ADDRESS.value: CoreTlvDataIPv6Addr,
        NodeTlvs.MODEL.value: CoreTlvDataString,
        NodeTlvs.EMULATION_SERVER.value: CoreTlvDataString,
        NodeTlvs.SESSION.value: CoreTlvDataString,
        NodeTlvs.X_POSITION.value: CoreTlvDataUint16,
        NodeTlvs.Y_POSITION.value: CoreTlvDataUint16,
        NodeTlvs.CANVAS.value: CoreTlvDataUint16,
        NodeTlvs.EMULATION_ID.value: CoreTlvDataUint32,
        NodeTlvs.NETWORK_ID.value: CoreTlvDataUint32,
        NodeTlvs.SERVICES.value: CoreTlvDataString,
        NodeTlvs.LATITUDE.value: CoreTlvDataString,
        NodeTlvs.LONGITUDE.value: CoreTlvDataString,
        NodeTlvs.ALTITUDE.value: CoreTlvDataString,
        NodeTlvs.ICON.value: CoreTlvDataString,
        NodeTlvs.OPAQUE.value: CoreTlvDataString,
    }


class CoreLinkTlv(CoreTlv):
    """
    Class for representing CORE link TLVs.
    """

    tlv_type_map = LinkTlvs
    tlv_data_class_map = {
        LinkTlvs.N1_NUMBER.value: CoreTlvDataUint32,
        LinkTlvs.N2_NUMBER.value: CoreTlvDataUint32,
        LinkTlvs.DELAY.value: CoreTlvDataUint64,
        LinkTlvs.BANDWIDTH.value: CoreTlvDataUint64,
        LinkTlvs.LOSS.value: CoreTlvDataString,
        LinkTlvs.DUP.value: CoreTlvDataString,
        LinkTlvs.JITTER.value: CoreTlvDataUint64,
        LinkTlvs.MER.value: CoreTlvDataUint16,
        LinkTlvs.BURST.value: CoreTlvDataUint16,
        LinkTlvs.SESSION.value: CoreTlvDataString,
        LinkTlvs.MBURST.value: CoreTlvDataUint16,
        LinkTlvs.TYPE.value: CoreTlvDataUint32,
        LinkTlvs.GUI_ATTRIBUTES.value: CoreTlvDataString,
        LinkTlvs.UNIDIRECTIONAL.value: CoreTlvDataUint16,
        LinkTlvs.EMULATION_ID.value: CoreTlvDataUint32,
        LinkTlvs.NETWORK_ID.value: CoreTlvDataUint32,
        LinkTlvs.KEY.value: CoreTlvDataUint32,
        LinkTlvs.IFACE1_NUMBER.value: CoreTlvDataUint16,
        LinkTlvs.IFACE1_IP4.value: CoreTlvDataIpv4Addr,
        LinkTlvs.IFACE1_IP4_MASK.value: CoreTlvDataUint16,
        LinkTlvs.IFACE1_MAC.value: CoreTlvDataMacAddr,
        LinkTlvs.IFACE1_IP6.value: CoreTlvDataIPv6Addr,
        LinkTlvs.IFACE1_IP6_MASK.value: CoreTlvDataUint16,
        LinkTlvs.IFACE2_NUMBER.value: CoreTlvDataUint16,
        LinkTlvs.IFACE2_IP4.value: CoreTlvDataIpv4Addr,
        LinkTlvs.IFACE2_IP4_MASK.value: CoreTlvDataUint16,
        LinkTlvs.IFACE2_MAC.value: CoreTlvDataMacAddr,
        LinkTlvs.IFACE2_IP6.value: CoreTlvDataIPv6Addr,
        LinkTlvs.IFACE2_IP6_MASK.value: CoreTlvDataUint16,
        LinkTlvs.IFACE1_NAME.value: CoreTlvDataString,
        LinkTlvs.IFACE2_NAME.value: CoreTlvDataString,
        LinkTlvs.OPAQUE.value: CoreTlvDataString,
    }


class CoreExecuteTlv(CoreTlv):
    """
    Class for representing CORE execute TLVs.
    """

    tlv_type_map = ExecuteTlvs
    tlv_data_class_map = {
        ExecuteTlvs.NODE.value: CoreTlvDataUint32,
        ExecuteTlvs.NUMBER.value: CoreTlvDataUint32,
        ExecuteTlvs.TIME.value: CoreTlvDataUint32,
        ExecuteTlvs.COMMAND.value: CoreTlvDataString,
        ExecuteTlvs.RESULT.value: CoreTlvDataString,
        ExecuteTlvs.STATUS.value: CoreTlvDataUint32,
        ExecuteTlvs.SESSION.value: CoreTlvDataString,
    }


class CoreRegisterTlv(CoreTlv):
    """
    Class for representing CORE register TLVs.
    """

    tlv_type_map = RegisterTlvs
    tlv_data_class_map = {
        RegisterTlvs.WIRELESS.value: CoreTlvDataString,
        RegisterTlvs.MOBILITY.value: CoreTlvDataString,
        RegisterTlvs.UTILITY.value: CoreTlvDataString,
        RegisterTlvs.EXECUTE_SERVER.value: CoreTlvDataString,
        RegisterTlvs.GUI.value: CoreTlvDataString,
        RegisterTlvs.EMULATION_SERVER.value: CoreTlvDataString,
        RegisterTlvs.SESSION.value: CoreTlvDataString,
    }


class CoreConfigTlv(CoreTlv):
    """
    Class for representing CORE configuration TLVs.
    """

    tlv_type_map = ConfigTlvs
    tlv_data_class_map = {
        ConfigTlvs.NODE.value: CoreTlvDataUint32,
        ConfigTlvs.OBJECT.value: CoreTlvDataString,
        ConfigTlvs.TYPE.value: CoreTlvDataUint16,
        ConfigTlvs.DATA_TYPES.value: CoreTlvDataUint16List,
        ConfigTlvs.VALUES.value: CoreTlvDataString,
        ConfigTlvs.CAPTIONS.value: CoreTlvDataString,
        ConfigTlvs.BITMAP.value: CoreTlvDataString,
        ConfigTlvs.POSSIBLE_VALUES.value: CoreTlvDataString,
        ConfigTlvs.GROUPS.value: CoreTlvDataString,
        ConfigTlvs.SESSION.value: CoreTlvDataString,
        ConfigTlvs.IFACE_ID.value: CoreTlvDataUint16,
        ConfigTlvs.NETWORK_ID.value: CoreTlvDataUint32,
        ConfigTlvs.OPAQUE.value: CoreTlvDataString,
    }


class CoreFileTlv(CoreTlv):
    """
    Class for representing CORE file TLVs.
    """

    tlv_type_map = FileTlvs
    tlv_data_class_map = {
        FileTlvs.NODE.value: CoreTlvDataUint32,
        FileTlvs.NAME.value: CoreTlvDataString,
        FileTlvs.MODE.value: CoreTlvDataString,
        FileTlvs.NUMBER.value: CoreTlvDataUint16,
        FileTlvs.TYPE.value: CoreTlvDataString,
        FileTlvs.SOURCE_NAME.value: CoreTlvDataString,
        FileTlvs.SESSION.value: CoreTlvDataString,
        FileTlvs.DATA.value: CoreTlvDataString,
        FileTlvs.COMPRESSED_DATA.value: CoreTlvDataString,
    }


class CoreInterfaceTlv(CoreTlv):
    """
    Class for representing CORE interface TLVs.
    """

    tlv_type_map = InterfaceTlvs
    tlv_data_class_map = {
        InterfaceTlvs.NODE.value: CoreTlvDataUint32,
        InterfaceTlvs.NUMBER.value: CoreTlvDataUint16,
        InterfaceTlvs.NAME.value: CoreTlvDataString,
        InterfaceTlvs.IP_ADDRESS.value: CoreTlvDataIpv4Addr,
        InterfaceTlvs.MASK.value: CoreTlvDataUint16,
        InterfaceTlvs.MAC_ADDRESS.value: CoreTlvDataMacAddr,
        InterfaceTlvs.IP6_ADDRESS.value: CoreTlvDataIPv6Addr,
        InterfaceTlvs.IP6_MASK.value: CoreTlvDataUint16,
        InterfaceTlvs.TYPE.value: CoreTlvDataUint16,
        InterfaceTlvs.SESSION.value: CoreTlvDataString,
        InterfaceTlvs.STATE.value: CoreTlvDataUint16,
        InterfaceTlvs.EMULATION_ID.value: CoreTlvDataUint32,
        InterfaceTlvs.NETWORK_ID.value: CoreTlvDataUint32,
    }


class CoreEventTlv(CoreTlv):
    """
    Class for representing CORE event TLVs.
    """

    tlv_type_map = EventTlvs
    tlv_data_class_map = {
        EventTlvs.NODE.value: CoreTlvDataUint32,
        EventTlvs.TYPE.value: CoreTlvDataUint32,
        EventTlvs.NAME.value: CoreTlvDataString,
        EventTlvs.DATA.value: CoreTlvDataString,
        EventTlvs.TIME.value: CoreTlvDataString,
        EventTlvs.SESSION.value: CoreTlvDataString,
    }


class CoreSessionTlv(CoreTlv):
    """
    Class for representing CORE session TLVs.
    """

    tlv_type_map = SessionTlvs
    tlv_data_class_map = {
        SessionTlvs.NUMBER.value: CoreTlvDataString,
        SessionTlvs.NAME.value: CoreTlvDataString,
        SessionTlvs.FILE.value: CoreTlvDataString,
        SessionTlvs.NODE_COUNT.value: CoreTlvDataString,
        SessionTlvs.DATE.value: CoreTlvDataString,
        SessionTlvs.THUMB.value: CoreTlvDataString,
        SessionTlvs.USER.value: CoreTlvDataString,
        SessionTlvs.OPAQUE.value: CoreTlvDataString,
    }


class CoreExceptionTlv(CoreTlv):
    """
    Class for representing CORE exception TLVs.
    """

    tlv_type_map = ExceptionTlvs
    tlv_data_class_map = {
        ExceptionTlvs.NODE.value: CoreTlvDataUint32,
        ExceptionTlvs.SESSION.value: CoreTlvDataString,
        ExceptionTlvs.LEVEL.value: CoreTlvDataUint16,
        ExceptionTlvs.SOURCE.value: CoreTlvDataString,
        ExceptionTlvs.DATE.value: CoreTlvDataString,
        ExceptionTlvs.TEXT.value: CoreTlvDataString,
        ExceptionTlvs.OPAQUE.value: CoreTlvDataString,
    }


class CoreMessage:
    """
    Base class for representing CORE messages.
    """

    header_format = "!BBH"
    header_len = struct.calcsize(header_format)
    message_type = None
    flag_map = MessageFlags
    tlv_class = CoreTlv

    def __init__(self, flags, hdr, data):
        self.raw_message = hdr + data
        self.flags = flags
        self.tlv_data = {}
        self.parse_data(data)

    @classmethod
    def unpack_header(cls, data):
        """
        parse data and return (message_type, message_flags, message_len).

        :param str data: data to parse
        :return: unpacked tuple
        :rtype: tuple
        """
        message_type, message_flags, message_len = struct.unpack(
            cls.header_format, data[: cls.header_len]
        )
        return message_type, message_flags, message_len

    @classmethod
    def create(cls, flags, values):
        tlv_data = structutils.pack_values(cls.tlv_class, values)
        packed = cls.pack(flags, tlv_data)
        header_data = packed[: cls.header_len]
        return cls(flags, header_data, tlv_data)

    @classmethod
    def pack(cls, message_flags, tlv_data):
        """
        Pack CORE message data.

        :param message_flags: message flags to pack with data
        :param tlv_data: data to get length from for packing
        :return: combined header and tlv data
        """
        header = struct.pack(
            cls.header_format, cls.message_type, message_flags, len(tlv_data)
        )
        return header + tlv_data

    def add_tlv_data(self, key, value):
        """
        Add TLV data into the data map.

        :param int key: key to store TLV data
        :param value: data to associate with key
        :return: nothing
        """
        if key in self.tlv_data:
            raise KeyError(f"key already exists: {key} (val={value})")

        self.tlv_data[key] = value

    def get_tlv(self, tlv_type):
        """
        Retrieve TLV data from data map.

        :param int tlv_type: type of data to retrieve
        :return: TLV type data
        """
        return self.tlv_data.get(tlv_type)

    def parse_data(self, data):
        """
        Parse data while possible and adding TLV data to the data map.

        :param data: data to parse for TLV data
        :return: nothing
        """
        while data:
            tlv, data = self.tlv_class.unpack(data)
            self.add_tlv_data(tlv.tlv_type, tlv.value)

    def pack_tlv_data(self):
        """
        Opposite of parse_data(). Return packed TLV data using self.tlv_data dict. Used by repack().

        :return: packed data
        :rtype: str
        """
        keys = sorted(self.tlv_data.keys())
        tlv_data = b""
        for key in keys:
            value = self.tlv_data[key]
            tlv_data += self.tlv_class.pack(key, value)
        return tlv_data

    def repack(self):
        """
        Invoke after updating self.tlv_data[] to rebuild self.raw_message.
        Useful for modifying a message that has been parsed, before
        sending the raw data again.

        :return: nothing
        """
        tlv_data = self.pack_tlv_data()
        self.raw_message = self.pack(self.flags, tlv_data)

    def type_str(self):
        """
        Retrieve data of the message type.

        :return: name of message type
        :rtype: str
        """
        try:
            return MessageTypes(self.message_type).name
        except ValueError:
            return f"unknown message type: {self.message_type}"

    def flag_str(self):
        """
        Retrieve message flag string.

        :return: message flag string
        :rtype: str
        """
        message_flags = []
        flag = 1

        while True:
            if self.flags & flag:
                try:
                    message_flags.append(self.flag_map(flag).name)
                except ValueError:
                    message_flags.append(f"0x{flag:x}")
            flag <<= 1
            if not (self.flags & ~(flag - 1)):
                break

        message_flags = " | ".join(message_flags)
        return f"0x{self.flags:x} <{message_flags}>"

    def __str__(self):
        """
        Retrieve string representation of the message.

        :return: string representation
        :rtype: str
        """
        result = f"{self.__class__.__name__} <msgtype = {self.type_str()}, flags = {self.flag_str()}>"

        for key in self.tlv_data:
            value = self.tlv_data[key]
            try:
                tlv_type = self.tlv_class.tlv_type_map(key).name
            except ValueError:
                tlv_type = f"tlv type {key}"

            result += f"\n  {tlv_type}: {value}"

        return result

    def node_numbers(self):
        """
        Return a list of node numbers included in this message.
        """
        number1 = None
        number2 = None

        # not all messages have node numbers
        if self.message_type == MessageTypes.NODE.value:
            number1 = self.get_tlv(NodeTlvs.NUMBER.value)
        elif self.message_type == MessageTypes.LINK.value:
            number1 = self.get_tlv(LinkTlvs.N1_NUMBER.value)
            number2 = self.get_tlv(LinkTlvs.N2_NUMBER.value)
        elif self.message_type == MessageTypes.EXECUTE.value:
            number1 = self.get_tlv(ExecuteTlvs.NODE.value)
        elif self.message_type == MessageTypes.CONFIG.value:
            number1 = self.get_tlv(ConfigTlvs.NODE.value)
        elif self.message_type == MessageTypes.FILE.value:
            number1 = self.get_tlv(FileTlvs.NODE.value)
        elif self.message_type == MessageTypes.INTERFACE.value:
            number1 = self.get_tlv(InterfaceTlvs.NODE.value)
        elif self.message_type == MessageTypes.EVENT.value:
            number1 = self.get_tlv(EventTlvs.NODE.value)

        result = []

        if number1:
            result.append(number1)

        if number2:
            result.append(number2)

        return result

    def session_numbers(self):
        """
        Return a list of session numbers included in this message.
        """
        result = []

        if self.message_type == MessageTypes.SESSION.value:
            sessions = self.get_tlv(SessionTlvs.NUMBER.value)
        elif self.message_type == MessageTypes.EXCEPTION.value:
            sessions = self.get_tlv(ExceptionTlvs.SESSION.value)
        else:
            # All other messages share TLV number 0xA for the session number(s).
            sessions = self.get_tlv(NodeTlvs.SESSION.value)

        if sessions:
            for session_id in sessions.split("|"):
                result.append(int(session_id))

        return result


class CoreNodeMessage(CoreMessage):
    """
    CORE node message class.
    """

    message_type = MessageTypes.NODE.value
    tlv_class = CoreNodeTlv


class CoreLinkMessage(CoreMessage):
    """
    CORE link message class.
    """

    message_type = MessageTypes.LINK.value
    tlv_class = CoreLinkTlv


class CoreExecMessage(CoreMessage):
    """
    CORE execute message class.
    """

    message_type = MessageTypes.EXECUTE.value
    tlv_class = CoreExecuteTlv


class CoreRegMessage(CoreMessage):
    """
    CORE register message class.
    """

    message_type = MessageTypes.REGISTER.value
    tlv_class = CoreRegisterTlv


class CoreConfMessage(CoreMessage):
    """
    CORE configuration message class.
    """

    message_type = MessageTypes.CONFIG.value
    tlv_class = CoreConfigTlv


class CoreFileMessage(CoreMessage):
    """
    CORE file message class.
    """

    message_type = MessageTypes.FILE.value
    tlv_class = CoreFileTlv


class CoreIfaceMessage(CoreMessage):
    """
    CORE interface message class.
    """

    message_type = MessageTypes.INTERFACE.value
    tlv_class = CoreInterfaceTlv


class CoreEventMessage(CoreMessage):
    """
    CORE event message class.
    """

    message_type = MessageTypes.EVENT.value
    tlv_class = CoreEventTlv


class CoreSessionMessage(CoreMessage):
    """
    CORE session message class.
    """

    message_type = MessageTypes.SESSION.value
    tlv_class = CoreSessionTlv


class CoreExceptionMessage(CoreMessage):
    """
    CORE exception message class.
    """

    message_type = MessageTypes.EXCEPTION.value
    tlv_class = CoreExceptionTlv


# map used to translate enumerated message type values to message class objects
CLASS_MAP = {
    MessageTypes.NODE.value: CoreNodeMessage,
    MessageTypes.LINK.value: CoreLinkMessage,
    MessageTypes.EXECUTE.value: CoreExecMessage,
    MessageTypes.REGISTER.value: CoreRegMessage,
    MessageTypes.CONFIG.value: CoreConfMessage,
    MessageTypes.FILE.value: CoreFileMessage,
    MessageTypes.INTERFACE.value: CoreIfaceMessage,
    MessageTypes.EVENT.value: CoreEventMessage,
    MessageTypes.SESSION.value: CoreSessionMessage,
    MessageTypes.EXCEPTION.value: CoreExceptionMessage,
}


def str_to_list(value):
    """
    Helper to convert pipe-delimited string ("a|b|c") into a list (a, b, c).

    :param str value: string to convert
    :return: converted list
    :rtype: list
    """

    if value is None:
        return None

    return value.split("|")
