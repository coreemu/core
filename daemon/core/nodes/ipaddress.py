"""
Helper objects for dealing with IPv4/v6 addresses.
"""

import random
import struct


class MacAddress:
    """
    Provides mac address utilities for use within core.
    """

    def __init__(self, address):
        """
        Creates a MacAddress instance.

        :param bytes address: mac address
        """
        self.addr = address

    def __str__(self):
        """
        Create a string representation of a MacAddress.

        :return: string representation
        :rtype: str
        """
        return ":".join(f"{x:02x}" for x in bytearray(self.addr))

    @classmethod
    def from_string(cls, s):
        """
        Create a mac address object from a string.

        :param s: string representation of a mac address
        :return: mac address class
        :rtype: MacAddress
        """
        addr = b"".join(bytes([int(x, 16)]) for x in s.split(":"))
        return cls(addr)

    @classmethod
    def random(cls):
        """
        Create a random mac address.

        :return: random mac address
        :rtype: MacAddress
        """
        tmp = random.randint(0, 0xFFFFFF)
        # use the Xen OID 00:16:3E
        tmp |= 0x00163E << 24
        tmpbytes = struct.pack("!Q", tmp)
        return cls(tmpbytes[2:])
