"""
Helper objects for dealing with IPv4/v6 addresses.
"""

import random
import socket
import struct
from socket import AF_INET
from socket import AF_INET6

from core import logger


class MacAddress(object):
    """
    Provides mac address utilities for use within core.
    """

    def __init__(self, address):
        """
        Creates a MacAddress instance.

        :param str address: mac address
        """
        self.addr = address

    def __str__(self):
        """
        Create a string representation of a MacAddress.

        :return: string representation
        :rtype: str
        """
        return ":".join("%02x" % ord(x) for x in self.addr)

    def to_link_local(self):
        """
        Convert the MAC address to a IPv6 link-local address, using EUI 48
        to EUI 64 conversion process per RFC 5342.

        :return: ip address object
        :rtype: IpAddress
        """
        if not self.addr:
            return IpAddress.from_string("::")
        tmp = struct.unpack("!Q", "\x00\x00" + self.addr)[0]
        nic = long(tmp) & 0x000000FFFFFFL
        oui = long(tmp) & 0xFFFFFF000000L
        # toggle U/L bit
        oui ^= 0x020000000000L
        # append EUI-48 octets
        oui = (oui << 16) | 0xFFFE000000L
        return IpAddress(AF_INET6, struct.pack("!QQ", 0xfe80 << 48, oui | nic))

    @classmethod
    def from_string(cls, s):
        """
        Create a mac address object from a string.

        :param s: string representation of a mac address
        :return: mac address class
        :rtype: MacAddress
        """
        addr = "".join(chr(int(x, 16)) for x in s.split(":"))
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


class IpAddress(object):
    """
    Provides ip utilities and functionality for use within core.
    """

    def __init__(self, af, address):
        """
        Create a IpAddress instance.

        :param int af: address family
        :param str address: ip address
        :return:
        """
        # check if (af, addr) is valid
        if not socket.inet_ntop(af, address):
            raise ValueError("invalid af/addr")
        self.af = af
        self.addr = address

    def is_ipv4(self):
        """
        Checks if this is an ipv4 address.

        :return: True if ipv4 address, False otherwise
        :rtype: bool
        """
        return self.af == AF_INET

    def is_ipv6(self):
        """
        Checks if this is an ipv6 address.

        :return: True if ipv6 address, False otherwise
        :rtype: bool
        """
        return self.af == AF_INET6

    def __str__(self):
        """
        Create a string representation of this address.

        :return: string representation of address
        :rtype: str
        """
        return socket.inet_ntop(self.af, self.addr)

    def __eq__(self, other):
        """
        Checks for equality with another ip address.

        :param IpAddress other: other ip address to check equality with
        :return: True is the other IpAddress is equal, False otherwise
        :rtype: bool
        """
        if not isinstance(other, IpAddress):
            return False
        elif self is other:
            return True
        else:
            return other.af == self.af and other.addr == self.addr

    def __add__(self, other):
        """
        Add value to ip addresses.

        :param int other: value to add to ip address
        :return: added together ip address instance
        :rtype: IpAddress
        """
        try:
            carry = int(other)
        except ValueError:
            logger.exception("error during addition")
            return NotImplemented

        tmp = [ord(x) for x in self.addr]
        for i in xrange(len(tmp) - 1, -1, -1):
            x = tmp[i] + carry
            tmp[i] = x & 0xff
            carry = x >> 8
            if carry == 0:
                break
        addr = "".join(chr(x) for x in tmp)
        return self.__class__(self.af, addr)

    def __sub__(self, other):
        """
        Subtract value from ip address.

        :param int other: value to subtract from ip address
        :return:
        """
        try:
            tmp = -int(other)
        except ValueError:
            logger.exception("error during subtraction")
            return NotImplemented

        return self.__add__(tmp)

    @classmethod
    def from_string(cls, s):
        """
        Create a ip address from a string representation.

        :param s: string representation to create ip address from
        :return: ip address instance
        :rtype: IpAddress
        """
        for af in AF_INET, AF_INET6:
            return cls(af, socket.inet_pton(af, s))

    @staticmethod
    def to_int(s):
        """
        Convert IPv4 string to integer

        :param s: string to convert to 32-bit integer
        :return: integer value
        :rtype: int
        """
        value = socket.inet_pton(AF_INET, s)
        return struct.unpack("!I", value)[0]


class IpPrefix(object):
    """
    Provides ip address generation and prefix utilities.
    """

    def __init__(self, af, prefixstr):
        """
        Create a IpPrefix instance.

        :param int af: address family for ip prefix
        :param prefixstr: ip prefix string
        """
        # prefixstr format: address/prefixlen
        tmp = prefixstr.split("/")
        if len(tmp) > 2:
            raise ValueError("invalid prefix: %s" % prefixstr)
        self.af = af
        if self.af == AF_INET:
            self.addrlen = 32
        elif self.af == AF_INET6:
            self.addrlen = 128
        else:
            raise ValueError("invalid address family: %s" % self.af)
        if len(tmp) == 2:
            self.prefixlen = int(tmp[1])
        else:
            self.prefixlen = self.addrlen
        self.prefix = socket.inet_pton(self.af, tmp[0])
        if self.addrlen > self.prefixlen:
            addrbits = self.addrlen - self.prefixlen
            netmask = ((1L << self.prefixlen) - 1) << addrbits
            prefix = ""
            for i in xrange(-1, -(addrbits >> 3) - 2, -1):
                prefix = chr(ord(self.prefix[i]) & (netmask & 0xff)) + prefix
                netmask >>= 8
            self.prefix = self.prefix[:i] + prefix

    def __str__(self):
        """
        String representation of an ip prefix.

        :return: string representation
        :rtype: str
        """
        return "%s/%s" % (socket.inet_ntop(self.af, self.prefix), self.prefixlen)

    def __eq__(self, other):
        """
        Compare equality with another ip prefix.

        :param IpPrefix other: other ip prefix to compare with
        :return: True is equal, False otherwise
        :rtype: bool
        """
        if not isinstance(other, IpPrefix):
            return False
        elif self is other:
            return True
        else:
            return other.af == self.af and other.prefixlen == self.prefixlen and other.prefix == self.prefix

    def __add__(self, other):
        """
        Add a value to this ip prefix.

        :param int other: value to add
        :return: added ip prefix instance
        :rtype: IpPrefix
        """
        try:
            tmp = int(other)
        except ValueError:
            logger.exception("error during addition")
            return NotImplemented

        a = IpAddress(self.af, self.prefix) + (tmp << (self.addrlen - self.prefixlen))
        prefixstr = "%s/%s" % (a, self.prefixlen)
        if self.__class__ == IpPrefix:
            return self.__class__(self.af, prefixstr)
        else:
            return self.__class__(prefixstr)

    def __sub__(self, other):
        """
        Subtract value from this ip prefix.

        :param int other: value to subtract
        :return: subtracted ip prefix instance
        :rtype: IpPrefix
        """
        try:
            tmp = -int(other)
        except ValueError:
            logger.exception("error during subtraction")
            return NotImplemented

        return self.__add__(tmp)

    def addr(self, hostid):
        """
        Create an ip address for a given host id.

        :param hostid: host id for an ip address
        :return: ip address
        :rtype: IpAddress
        """
        tmp = int(hostid)
        if tmp in [-1, 0, 1] and self.addrlen == self.prefixlen:
            return IpAddress(self.af, self.prefix)

        if tmp == 0 or tmp > (1 << (self.addrlen - self.prefixlen)) - 1 or (
                    self.af == AF_INET and tmp == (1 << (self.addrlen - self.prefixlen)) - 1):
            raise ValueError("invalid hostid for prefix %s: %s" % (self, hostid))

        addr = ""
        prefix_endpoint = -1
        for i in xrange(-1, -(self.addrlen >> 3) - 1, -1):
            prefix_endpoint = i
            addr = chr(ord(self.prefix[i]) | (tmp & 0xff)) + addr
            tmp >>= 8
            if not tmp:
                break
        addr = self.prefix[:prefix_endpoint] + addr
        return IpAddress(self.af, addr)

    def min_addr(self):
        """
        Return the minimum ip address for this prefix.

        :return: minimum ip address
        :rtype: IpAddress
        """
        return self.addr(1)

    def max_addr(self):
        """
        Return the maximum ip address for this prefix.

        :return: maximum ip address
        :rtype: IpAddress
        """
        if self.af == AF_INET:
            return self.addr((1 << (self.addrlen - self.prefixlen)) - 2)
        else:
            return self.addr((1 << (self.addrlen - self.prefixlen)) - 1)

    def num_addr(self):
        """
        Retrieve the number of ip addresses for this prefix.

        :return: maximum number of ip addresses
        :rtype: int
        """
        return max(0, (1 << (self.addrlen - self.prefixlen)) - 2)

    def prefix_str(self):
        """
        Retrieve the prefix string for this ip address.

        :return: prefix string
        :rtype: str
        """
        return "%s" % socket.inet_ntop(self.af, self.prefix)

    def netmask_str(self):
        """
        Retrieve the netmask string for this ip address.

        :return: netmask string
        :rtype: str
        """
        addrbits = self.addrlen - self.prefixlen
        netmask = ((1L << self.prefixlen) - 1) << addrbits
        netmaskbytes = struct.pack("!L", netmask)
        return IpAddress(af=AF_INET, address=netmaskbytes).__str__()


class Ipv4Prefix(IpPrefix):
    """
    Provides an ipv4 specific class for ip prefixes.
    """

    def __init__(self, prefixstr):
        """
        Create a Ipv4Prefix instance.

        :param str prefixstr: ip prefix
        """
        IpPrefix.__init__(self, AF_INET, prefixstr)


class Ipv6Prefix(IpPrefix):
    """
    Provides an ipv6 specific class for ip prefixes.
    """

    def __init__(self, prefixstr):
        """
        Create a Ipv6Prefix instance.

        :param str prefixstr: ip prefix
        """
        IpPrefix.__init__(self, AF_INET6, prefixstr)


def is_ip_address(af, addrstr):
    """
    Check if ip address string is a valid ip address.

    :param int af: address family
    :param str addrstr: ip address string
    :return: True if a valid ip address, False otherwise
    :rtype: bool
    """
    try:
        socket.inet_pton(af, addrstr)
        return True
    except IOError:
        return False


def is_ipv4_address(addrstr):
    """
    Check if ipv4 address string is a valid ipv4 address.

    :param str addrstr: ipv4 address string
    :return: True if a valid ipv4 address, False otherwise
    :rtype: bool
    """
    return is_ip_address(AF_INET, addrstr)


def is_ipv6_address(addrstr):
    """
    Check if ipv6 address string is a valid ipv6 address.

    :param str addrstr: ipv6 address string
    :return: True if a valid ipv6 address, False otherwise
    :rtype: bool
    """
    return is_ip_address(AF_INET6, addrstr)
